"""故事文本模型的後端層。

此模組把「怎麼載入文字模型」與「故事主流程」分開，讓未來更換模型時：

1. 優先只改 `LLMConfig`
2. 若要換不同後端，再新增 provider 並註冊到 registry
3. `story.py` 與 `chief.py` 不必知道每個模型家族的載入細節
"""

from __future__ import annotations

import gc
import importlib.util
import inspect
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple, Union

import torch

from .llm_runtime_strategy import resolve_model_selection
from prompts.prompt_utils import ChatPrompt
from utils import cleanup_torch


@dataclass
class GenerationParams:
	"""集中管理 LLM 取樣相關的參數。"""

	max_tokens: int
	min_tokens: int
	temperature: float
	top_p: float
	top_k: int
	repetition_penalty: float
	no_repeat_ngram_size: Optional[int]


@dataclass
class LLMConfig:
	"""描述建立 LLM 物件所需的關鍵參數。"""

	model_dir: Union[str, Path]
	device_map: str = "auto"
	dtype: str = "float16"
	seed: int = 42
	quantization: Optional[str] = None  # "4bit", "8bit", "gptq", or None
	use_sdpa: bool = True  # 向後相容欄位；目前建模流程未使用
	provider: str = "transformers"  # 先保留單一後端入口，方便未來擴充
	model_family: Optional[str] = None  # 預留給特定模型家族的相容策略


class BaseLLM:
	"""抽象 LLM 介面，方便在本地/雲端實作間切換。"""

	def generate(self, prompt: ChatPrompt, params: GenerationParams) -> Tuple[str, int]:
		"""子類別需依參數產生文本。"""
		raise NotImplementedError

	def stream(self, prompt: ChatPrompt, params: GenerationParams) -> Iterator[str]:
		"""逐步生成文本的迭代器。"""
		raise NotImplementedError

	def set_seed(self, seed: int) -> None:
		"""讓不同 provider 共享同一個重設隨機狀態的介面。"""
		random.seed(seed)
		torch.manual_seed(seed)
		if torch.cuda.is_available():
			torch.cuda.manual_seed_all(seed)


class TransformersLLM(BaseLLM):
	"""使用 HuggingFace transformers 模型真實生成文本。"""

	@staticmethod
	def _normalize_runtime_device(device: str) -> str:
		"""將裝置字串正規化為可直接給 transformers 的值。"""
		normalized = (device or "auto").strip().lower()
		if normalized == "auto":
			return "cuda:0" if torch.cuda.is_available() else "cpu"
		if normalized.startswith("cuda") and not torch.cuda.is_available():
			logging.warning("CUDA was requested but is unavailable; falling back to CPU.")
			return "cpu"
		return normalized

	@staticmethod
	def _resolve_transformers_device_map(requested_device: str, runtime_device: str) -> Union[str, Dict[str, int]]:
		"""Preserve device_map='auto' so larger quantized models can offload when needed."""
		normalized = (requested_device or "auto").strip().lower()
		if normalized == "auto":
			if torch.cuda.is_available():
				if importlib.util.find_spec("accelerate") is None:
					logging.warning(
						"device_map='auto' requested but accelerate is unavailable; using single-GPU placement instead."
					)
					return {"": 0}
				return "auto"
			return "cpu"
		if runtime_device.startswith("cuda"):
			gpu_id = int(runtime_device.split(":")[1]) if ":" in runtime_device else 0
			return {"": gpu_id}
		return runtime_device

	def _resolve_input_device(self) -> torch.device:
		"""Pick a stable input device even when the model is sharded or offloaded."""
		if self.model is not None:
			hf_device_map = getattr(self.model, "hf_device_map", None)
			if isinstance(hf_device_map, dict):
				for value in hf_device_map.values():
					if isinstance(value, int):
						return torch.device(f"cuda:{value}")
					if isinstance(value, str) and value.startswith("cuda"):
						return torch.device(value)
			model_device = getattr(self.model, "device", None)
			if model_device is not None:
				return torch.device(str(model_device))
		return torch.device(self.device)

	def _apply_chat_template(self, messages: List[Dict[str, str]], *, add_generation_prompt: bool = True) -> str:
		"""Use the tokenizer chat template while disabling vendor-specific hidden thinking when available."""
		kwargs: Dict[str, Any] = {
			"tokenize": False,
			"add_generation_prompt": add_generation_prompt,
		}
		try:
			signature = inspect.signature(self.tokenizer.apply_chat_template)
			if "enable_thinking" in signature.parameters:
				kwargs["enable_thinking"] = False
		except (TypeError, ValueError):
			pass
		return self.tokenizer.apply_chat_template(messages, **kwargs)

	@staticmethod
	def _register_model_family_aliases(model_type: Optional[str]) -> None:
		"""僅在需要時為舊版 transformers 補上模型家族別名。"""
		if model_type not in {"qwen3", "qwen3_5", "phi4"}:
			return
		try:
			import transformers
			transformers_version = transformers.__version__
			version_parts = transformers_version.split(".")
			major, minor = int(version_parts[0]), int(version_parts[1])
			if major > 4 or (major == 4 and minor >= 51):
				logging.debug("transformers %s should natively support Qwen3", transformers_version)
				return

			from transformers.models.auto.configuration_auto import CONFIG_MAPPING
			from transformers.models.auto.modeling_auto import MODEL_FOR_CAUSAL_LM_MAPPING

			if model_type in {"qwen3", "qwen3_5"} and model_type not in CONFIG_MAPPING and "qwen2" in CONFIG_MAPPING:
				CONFIG_MAPPING.register(model_type, CONFIG_MAPPING["qwen2"])
				logging.warning("Registered '%s' model type to use Qwen2Config", model_type)

			if (
				model_type in {"qwen3", "qwen3_5"}
				and model_type not in MODEL_FOR_CAUSAL_LM_MAPPING
				and "qwen2" in CONFIG_MAPPING
				and CONFIG_MAPPING["qwen2"] in MODEL_FOR_CAUSAL_LM_MAPPING
			):
				MODEL_FOR_CAUSAL_LM_MAPPING.register(
					model_type,
					MODEL_FOR_CAUSAL_LM_MAPPING[CONFIG_MAPPING["qwen2"]],
				)
				logging.warning("Registered '%s' to use Qwen2ForCausalLM", model_type)

			if model_type == "phi4" and "phi4" not in CONFIG_MAPPING and "phi3" in CONFIG_MAPPING:
				CONFIG_MAPPING.register("phi4", CONFIG_MAPPING["phi3"])
				logging.warning("Registered 'phi4' model type to use Phi3Config")

			if (
				model_type == "phi4"
				and "phi4" not in MODEL_FOR_CAUSAL_LM_MAPPING
				and "phi3" in CONFIG_MAPPING
				and CONFIG_MAPPING["phi3"] in MODEL_FOR_CAUSAL_LM_MAPPING
			):
				MODEL_FOR_CAUSAL_LM_MAPPING.register(
					"phi4",
					MODEL_FOR_CAUSAL_LM_MAPPING[CONFIG_MAPPING["phi3"]],
				)
				logging.warning("Registered 'phi4' to use Phi3ForCausalLM")
		except Exception as exc:
			logging.warning("Failed to check/register custom model mappings: %s", exc)

	def __init__(
		self,
		model_path: str,
		device: str = "auto",
		dtype: str = "float16",
		quantization: Optional[str] = None,
		seed: int = 42,
		model_family: Optional[str] = None,
	) -> None:
		"""載入 HuggingFace transformers 模型做為主要文字生成器。"""
		from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig  # type: ignore

		self.model_path = model_path
		self.model_family = model_family
		self.device = self._normalize_runtime_device(device)
		self.requested_device_map = (device or "auto").strip().lower()
		self.quantization = quantization
		self.model = None
		self.tokenizer = None
		self.set_seed(seed)

		if self.device == "cpu" and dtype in {"float16", "bfloat16"}:
			logging.warning(
				"CPU mode does not reliably support %s for this model; switching dtype to float32.",
				dtype,
			)
			dtype = "float32"

		requested_quantization = (quantization or "").strip().lower() or None
		if requested_quantization == "none":
			requested_quantization = None
		if requested_quantization not in {None, "4bit", "8bit", "gptq"}:
			logging.warning(
				"Unsupported quantization '%s', fallback to no quantization.",
				requested_quantization,
			)
			requested_quantization = None

		selection = resolve_model_selection(
			Path(model_path),
			requested_quantization,
			device=self.device,
		)
		if selection.status == "blocked":
			raise RuntimeError(
				"No usable text model candidate found for requested model "
				f"'{model_path}'. Reasons: {'; '.join(selection.reasons)}"
			)
		if selection.candidate.path != Path(model_path) or selection.effective_quantization != requested_quantization:
			logging.warning(
				"Model selection resolved '%s' (quantization=%s) to '%s' (quantization=%s, status=%s, source=%s).",
				model_path,
				requested_quantization,
				selection.candidate.path,
				selection.effective_quantization,
				selection.status,
				selection.candidate.source,
			)
		if selection.reasons:
			readiness_log = logging.warning if selection.status in {"degraded", "blocked"} else logging.info
			readiness_log(
				"Model readiness for '%s' is %s: %s",
				selection.candidate.path,
				selection.status,
				"; ".join(selection.reasons),
			)
		model_path = str(selection.candidate.path)
		self.model_path = model_path
		requested_quantization = selection.effective_quantization

		torch_dtype = {
			"float16": torch.float16,
			"bfloat16": torch.bfloat16,
			"float32": torch.float32,
		}.get(dtype, torch.float16)

		try:
			self.tokenizer = AutoTokenizer.from_pretrained(
				model_path,
				trust_remote_code=True,
				use_fast=False,
			)
		except Exception as exc:
			logging.warning("Failed to load slow tokenizer, trying fast: %s", exc)
			self.tokenizer = AutoTokenizer.from_pretrained(
				model_path,
				trust_remote_code=True,
				use_fast=True,
			)

		quantization_config = None
		is_pre_quantized = False
		if requested_quantization == "4bit":
			quantization_config = BitsAndBytesConfig(
				load_in_4bit=True,
				bnb_4bit_compute_dtype=torch_dtype,
				bnb_4bit_use_double_quant=True,
				bnb_4bit_quant_type="nf4",
			)
			logging.info("Enabling 4-bit quantization for LLM")
		elif requested_quantization == "8bit":
			quantization_config = BitsAndBytesConfig(load_in_8bit=True)
			logging.info("Enabling 8-bit quantization for LLM")
		elif requested_quantization == "gptq":
			from runtime.compat import prepare_gptq_runtime
			from transformers import GPTQConfig

			is_pre_quantized = True
			prepare_gptq_runtime()
			quantization_config = GPTQConfig(
				bits=4,
				exllama_config={"version": 2},
				desc_act=False,
			)
			logging.info("Loading GPTQ pre-quantized model")

		device_map = self._resolve_transformers_device_map(self.requested_device_map, self.device)

		self._register_model_family_aliases(selection.model_type)

		load_kwargs: Dict[str, Any] = {
			"trust_remote_code": True,
			"device_map": device_map,
		}
		if quantization_config is None or is_pre_quantized:
			load_kwargs["torch_dtype"] = torch_dtype
		if quantization_config is not None:
			load_kwargs["quantization_config"] = quantization_config

		self.model = AutoModelForCausalLM.from_pretrained(
			model_path,
			**load_kwargs,
		)

	def generate(
		self,
		prompt: ChatPrompt,
		params: GenerationParams,
		prefill: str = "",
		bad_words_ids: Optional[List[List[int]]] = None,
	) -> Tuple[str, int]:
		"""使用 HuggingFace generate API 生成文本。"""
		messages = prompt.to_messages()
		prompt_text = self._apply_chat_template(messages, add_generation_prompt=True)
		if prefill:
			prompt_text += prefill

		inputs = self.tokenizer(
			prompt_text,
			return_tensors="pt",
			padding=True,
			truncation=True,
		)
		input_device = self._resolve_input_device()
		inputs = {k: v.to(input_device) for k, v in inputs.items()}
		if "attention_mask" not in inputs:
			inputs["attention_mask"] = torch.ones_like(inputs["input_ids"])

		use_greedy = params.temperature <= 0.3 and params.top_p >= 0.95 and params.top_k == 0
		do_sample = not use_greedy and (
			params.temperature > 0 or params.top_p < 1.0 or params.top_k > 0
		)

		eos_token_id = self.tokenizer.eos_token_id
		pad_token_id = self.tokenizer.pad_token_id
		if pad_token_id is None:
			if self.tokenizer.unk_token_id is not None:
				pad_token_id = self.tokenizer.unk_token_id
			else:
				pad_token_id = eos_token_id if eos_token_id is not None else 0
		if eos_token_id is None:
			eos_token_id = pad_token_id
		if pad_token_id == eos_token_id and pad_token_id is not None:
			if self.tokenizer.unk_token_id is not None and self.tokenizer.unk_token_id != eos_token_id:
				pad_token_id = self.tokenizer.unk_token_id
			else:
				pad_token_id = 0
			logging.debug(
				"Adjusted pad_token_id from %s to %s to avoid attention_mask warning",
				eos_token_id,
				pad_token_id,
			)

		generate_kwargs = {
			**inputs,
			"max_new_tokens": params.max_tokens,
			"min_new_tokens": params.min_tokens,
			"do_sample": do_sample,
			"pad_token_id": pad_token_id,
			"eos_token_id": eos_token_id,
		}
		if bad_words_ids:
			generate_kwargs["bad_words_ids"] = bad_words_ids
		if do_sample:
			generate_kwargs.update(
				{
					"temperature": max(params.temperature, 1e-5),
					"top_p": params.top_p if params.top_p < 1.0 else None,
					"top_k": params.top_k if params.top_k > 0 else None,
				}
			)
		if params.repetition_penalty != 1.0:
			generate_kwargs["repetition_penalty"] = params.repetition_penalty
		if params.no_repeat_ngram_size:
			generate_kwargs["no_repeat_ngram_size"] = params.no_repeat_ngram_size

		with torch.no_grad():
			output_ids = self.model.generate(**generate_kwargs)
		generated_ids = output_ids[0][inputs["input_ids"].shape[1] :]
		decoded = self.tokenizer.decode(generated_ids, skip_special_tokens=True)
		return decoded.strip(), len(generated_ids)

	def stream(
		self,
		prompt: ChatPrompt,
		params: GenerationParams,
		prefill: str = "",
	) -> Iterator[Dict[str, Any]]:
		"""逐步生成文本。"""
		from transformers import (
			LogitsProcessorList,
			MinLengthLogitsProcessor,
			RepetitionPenaltyLogitsProcessor,
			TemperatureLogitsWarper,
			TopKLogitsWarper,
			TopPLogitsWarper,
		)

		messages = prompt.to_messages()
		text = self._apply_chat_template(messages, add_generation_prompt=True)
		if prefill:
			text += prefill

		inputs = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True)
		input_device = self._resolve_input_device()
		input_ids = inputs["input_ids"].to(input_device)
		mask = inputs.get("attention_mask", torch.ones_like(input_ids)).to(input_device)

		processors = LogitsProcessorList()
		if params.min_tokens > 0:
			processors.append(
				MinLengthLogitsProcessor(params.min_tokens, eos_token_id=self.tokenizer.eos_token_id)
			)
		if params.repetition_penalty != 1.0:
			processors.append(RepetitionPenaltyLogitsProcessor(penalty=params.repetition_penalty))

		warpers = LogitsProcessorList()
		sample = params.temperature > 0 and (params.top_p < 1.0 or params.top_k > 0)
		if sample:
			if params.temperature > 0:
				warpers.append(TemperatureLogitsWarper(params.temperature))
			if params.top_k > 0:
				warpers.append(TopKLogitsWarper(params.top_k))
			if params.top_p < 1.0:
				warpers.append(TopPLogitsWarper(params.top_p))

		past = None
		tokens: List[int] = []
		for i in range(params.max_tokens):
			model_inputs = self.model.prepare_inputs_for_generation(
				input_ids,
				past_key_values=past,
				attention_mask=mask,
				use_cache=True,
			)
			with torch.no_grad():
				out = self.model(**model_inputs, return_dict=True)

			logits = out.logits[:, -1, :]
			past = out.past_key_values
			logits = processors(input_ids, logits)

			if sample:
				logits = warpers(input_ids, logits)
				probs = torch.nn.functional.softmax(logits, dim=-1)
				next_token = torch.multinomial(probs, num_samples=1)
			else:
				next_token = torch.argmax(logits, dim=-1).unsqueeze(-1)

			input_ids = torch.cat([input_ids, next_token], dim=-1)
			mask = torch.cat(
				[
					mask,
					torch.ones((mask.shape[0], 1), device=input_ids.device, dtype=mask.dtype),
				],
				dim=-1,
			)

			token = next_token.item()
			word = self.tokenizer.decode([token], skip_special_tokens=True)
			tokens.append(token)

			yield {
				"token": token,
				"text": word,
				"end": False,
				"step": i,
			}

			if token == self.tokenizer.eos_token_id:
				break

		yield {
			"token": None,
			"text": "",
			"end": True,
			"full": self.tokenizer.decode(tokens, skip_special_tokens=True),
		}

	def offload(self) -> None:
		"""將模型移至 CPU 以釋放 VRAM。"""
		if not hasattr(self, "model") or self.model is None:
			return
		try:
			logging.info("Attempting to offload LLM to CPU...")
			self.model.to("cpu")
			torch.cuda.empty_cache()
			logging.info("LLM offloaded to CPU.")
		except Exception as exc:
			logging.warning("Failed to offload LLM to CPU (likely due to quantization): %s", exc)

	def load(self, device: str = "cuda") -> None:
		"""將模型移回指定設備。"""
		if not hasattr(self, "model") or self.model is None:
			return
		try:
			logging.info("Restoring LLM to %s...", device)
			self.model.to(device)
		except Exception as exc:
			logging.error("Failed to restore LLM to %s: %s", device, exc)

	def cleanup(self) -> None:
		"""強制釋放模型與 Tokenizer，清理 VRAM。"""
		if hasattr(self, "model") and self.model is not None:
			del self.model
			self.model = None
		if hasattr(self, "tokenizer") and self.tokenizer is not None:
			del self.tokenizer
			self.tokenizer = None
		for _ in range(3):
			gc.collect()
		cleanup_torch()


LLMProviderBuilder = Callable[[LLMConfig], BaseLLM]

_LLM_PROVIDER_BUILDERS: Dict[str, LLMProviderBuilder] = {}
_LLM_PROVIDER_CANONICAL: Dict[str, str] = {}


def register_llm_provider(
	name: str,
	builder: LLMProviderBuilder,
	aliases: Sequence[str] = (),
) -> None:
	"""註冊新的 LLM provider。

	未來若想接 OpenAI API、vLLM 或其他本地執行器，只要新增 builder 並註冊，
	主流程即可沿用 `build_llm()`。
	"""
	canonical = name.strip().lower()
	_LLM_PROVIDER_BUILDERS[canonical] = builder
	_LLM_PROVIDER_CANONICAL[canonical] = canonical
	for alias in aliases:
		normalized = alias.strip().lower()
		_LLM_PROVIDER_BUILDERS[normalized] = builder
		_LLM_PROVIDER_CANONICAL[normalized] = canonical


def available_llm_providers() -> List[str]:
	"""列出目前可用的 provider 名稱。"""
	return sorted({canonical for canonical in _LLM_PROVIDER_CANONICAL.values()})


def _resolve_provider_name(provider: Optional[str]) -> str:
	normalized = (provider or "transformers").strip().lower()
	return _LLM_PROVIDER_CANONICAL.get(normalized, normalized)


def _build_transformers_llm(config: LLMConfig) -> BaseLLM:
	model_path = str(Path(config.model_dir))
	return TransformersLLM(
		model_path,
		device=config.device_map,
		dtype=config.dtype,
		quantization=config.quantization,
		seed=config.seed,
		model_family=config.model_family,
	)


register_llm_provider(
	"transformers",
	_build_transformers_llm,
	aliases=("hf", "huggingface"),
)


def build_llm(config: LLMConfig) -> BaseLLM:
	"""依設定建立對應的 LLM 物件。"""
	provider = _resolve_provider_name(config.provider)
	builder = _LLM_PROVIDER_BUILDERS.get(provider)
	if builder is None:
		raise ValueError(
			f"Unknown LLM provider '{config.provider}'. Available providers: {', '.join(available_llm_providers())}"
		)
	return builder(config)
