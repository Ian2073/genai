"""翻譯模型後端層。"""

from __future__ import annotations

import gc
import logging
import re
import subprocess
import torch
from typing import Any, Callable, Dict, List, Sequence

from backends.common import resolve_torch_runtime
from backends.translation_common import SAMPLE_LANGUAGE_MAP, chunk_text
from utils import cleanup_torch


class BaseTranslationBackend:
    """翻譯後端介面。"""

    def translate(self, text: str, target_lang: str) -> str:
        raise NotImplementedError

    def cleanup(self) -> None:
        raise NotImplementedError


class TransformersNLLBBackend(BaseTranslationBackend):
    """Transformers NLLB 翻譯後端。"""

    def __init__(self, config: Any) -> None:
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, BitsAndBytesConfig  # type: ignore

        self.config = config
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(config.model_dir),
            use_fast=False,
        )
        self.lang_code_to_id = self._build_lang_code_map()

        try:
            device, dtype = resolve_torch_runtime(
                config.device,
                config.dtype,
                module_name="Translation pipeline",
                auto_cuda_device="cuda:0",
                cpu_fallback=False,
            )
        except RuntimeError as exc:
            gpu_hint = ""
            try:
                gpu_names = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                    text=True,
                    errors="replace",
                    stderr=subprocess.STDOUT,
                ).strip()
                if gpu_names:
                    gpu_hint = f" nvidia-smi 偵測到 GPU: {gpu_names}."
            except Exception:
                pass
            raise RuntimeError(
                "系統未偵測到可用的 CUDA GPU，無法用 GPU 執行翻譯。"
                + gpu_hint
                + " 建議先執行 `python scripts/doctor.py --expect-cuda auto` 檢查環境。"
            ) from exc

        if not device.startswith("cuda"):
            logging.warning("翻譯模組改用 CPU 執行，速度會明顯下降。")
            if config.quantize:
                logging.warning("CPU 模式不啟用 bitsandbytes 量化，將使用標準載入。")
            if dtype in (torch.float16, torch.bfloat16):
                dtype = torch.float32
                logging.info("CPU 模式下將翻譯模型 dtype 調整為 float32。")

        load_kwargs = {}
        if self.config.quantize and device.startswith("cuda"):
            try:
                import bitsandbytes  # noqa: F401

                logging.info("啟用 8-bit 量化載入 NLLB 模型 (節省 VRAM)")
                load_kwargs["quantization_config"] = BitsAndBytesConfig(load_in_8bit=True)
                device_map = "auto"
            except ImportError:
                logging.warning("未安裝 bitsandbytes，無法使用量化，將使用標準載入")
                if device.startswith("cuda"):
                    gpu_id = int(device.split(":")[1]) if ":" in device else 0
                    device_map = {"": gpu_id}
                else:
                    device_map = device
        else:
            if device.startswith("cuda"):
                gpu_id = int(device.split(":")[1]) if ":" in device else 0
                device_map = {"": gpu_id}
            else:
                device_map = "cpu"

        cleanup_torch()
        self.model = AutoModelForSeq2SeqLM.from_pretrained(
            str(config.model_dir),
            torch_dtype=dtype,
            device_map=device_map,
            **load_kwargs,
        )
        self.device = self.model.device
        self.glossary = {}

    def _apply_glossary(self, text: str, target_lang: str) -> str:
        is_chinese = "zh" in target_lang.lower()
        is_simplified = "zh-cn" in target_lang.lower() or "hans" in target_lang.lower()
        if not is_chinese:
            return text

        replacements = {
            "姆爷爷": "湯姆爺爺",
            "姆祖父": "湯姆爺爺",
            "姆大叔": "湯姆爺爺",
            "Tom爷爷": "湯姆爺爺",
            "爷爷汤姆": "湯姆爺爺",
            "亚历克斯大叔": "艾力克斯",
            "阿力克斯": "艾力克斯",
            "艾玛": "艾瑪",
        }
        for bad, good in replacements.items():
            text = text.replace(bad, good)

        if is_simplified:
            simp_map = {
                "湯姆爺爺": "汤姆爷爷",
                "爺爺": "爷爷",
                "艾力克斯": "艾力克斯",
                "艾瑪": "艾玛",
                "豆蔻": "豆蔻",
                "掛墜盒": "挂坠盒",
                "星之橋": "星之桥",
                "彩虹橋": "彩虹桥",
                "為": "为",
                "裡": "里",
                "後": "后",
            }
            for trad, simp in simp_map.items():
                text = text.replace(trad, simp)
        return text

    def _build_lang_code_map(self) -> Dict[str, int]:
        mapping = getattr(self.tokenizer, "lang_code_to_id", None)
        if isinstance(mapping, dict) and mapping:
            return mapping

        lang_tokens: Sequence[str] = []
        if getattr(self.tokenizer, "additional_special_tokens", None):
            lang_tokens = list(self.tokenizer.additional_special_tokens)
        if not lang_tokens:
            special_map = getattr(self.tokenizer, "special_tokens_map_extended", {}) or getattr(
                self.tokenizer, "special_tokens_map", {}
            )
            lang_tokens = special_map.get("additional_special_tokens", [])

        temp_map: Dict[str, int] = {}
        for token in lang_tokens:
            try:
                token_id = self.tokenizer.convert_tokens_to_ids(token)
            except Exception:
                continue
            if token_id is None or token_id == self.tokenizer.unk_token_id:
                continue
            temp_map[str(token)] = int(token_id)

        if not temp_map:
            raise RuntimeError("無法從 NLLB tokenizer 推導語言代碼 mapping，請確認模型檔案完整。")
        return temp_map

    def _resolve_target_lang_code(self, target_lang: str) -> tuple[str, int]:
        target_code = SAMPLE_LANGUAGE_MAP.get(target_lang.lower(), target_lang)
        if target_code not in self.lang_code_to_id:
            if "zh" in target_lang.lower():
                target_code = "zho_Hant" if target_lang.lower() in ["zh", "zh-tw"] else "zho_Hans"
            else:
                raise ValueError(f"Target language {target_lang} ({target_code}) unsupported by tokenizer")

        forced_bos = self.lang_code_to_id.get(target_code)
        if forced_bos is None:
            logging.warning("Could not find token ID for %s, trying zho_Hant default", target_code)
            forced_bos = self.lang_code_to_id.get("zho_Hant")
            if forced_bos is None:
                raise RuntimeError(f"Failed to resolve forced_bos for {target_lang}")
        return target_code, forced_bos

    def _estimate_max_new_tokens(self, inputs: Dict[str, torch.Tensor], target_lang: str) -> int:
        max_output = max(32, int(getattr(self.config, "max_output", 256)))
        min_output = max(16, int(getattr(self.config, "min_output", 32)))

        if "attention_mask" in inputs and inputs["attention_mask"].numel() > 0:
            src_len = int(inputs["attention_mask"].sum(dim=1).max().item())
        elif "input_ids" in inputs and inputs["input_ids"].numel() > 0:
            src_len = int(inputs["input_ids"].shape[-1])
        else:
            src_len = int(getattr(self.config, "max_input", 128))

        src_len = max(1, src_len)
        lang = target_lang.lower()
        ratio = 1.25
        if lang in {"es", "pt", "fr", "de", "tr", "it"}:
            ratio = 1.35
        if lang in {"ja", "zh", "zh-tw", "zh-cn", "ko", "th", "my", "km", "lo"}:
            ratio = 1.45

        estimated = int(src_len * ratio) + 20
        return max(min_output, min(max_output, estimated))

    def _chunk_texts_with_mapping(self, texts: List[str]) -> tuple[List[str], List[List[int]]]:
        all_segments = []
        segment_map = []
        for text in texts:
            if not text.strip():
                segment_map.append([])
                continue
            sub_segments = chunk_text(text, self.config.chunk_size)
            current_indices = []
            for seg in sub_segments:
                if seg.strip():
                    all_segments.append(seg)
                    current_indices.append(len(all_segments) - 1)
            segment_map.append(current_indices)
        return all_segments, segment_map

    def _batch_translate_segments(
        self,
        segments: List[str],
        forced_bos: int,
        target_lang: str,
    ) -> List[str]:
        translated = [""] * len(segments)
        batch_size = getattr(self.config, "batch_size", 16)
        total_batches = (len(segments) + batch_size - 1) // batch_size
        for batch_idx, start_idx in enumerate(range(0, len(segments), batch_size)):
            end_idx = min(start_idx + batch_size, len(segments))
            batch_texts = segments[start_idx:end_idx]
            batch_texts_masked = [self._inject_entities(t, target_lang) for t in batch_texts]
            try:
                inputs = self.tokenizer(
                    batch_texts_masked,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_input,
                )
                inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
                max_new_tokens = self._estimate_max_new_tokens(inputs, target_lang)
                logging.info(
                    "    processing batch %s/%s (%s segments) | beam=%s | max_new_tokens=%s",
                    batch_idx + 1,
                    total_batches,
                    len(batch_texts),
                    max(1, self.config.beam_size),
                    max_new_tokens,
                )
                with torch.no_grad():
                    generated = self.model.generate(
                        **inputs,
                        forced_bos_token_id=forced_bos,
                        max_new_tokens=max_new_tokens,
                        num_beams=max(1, self.config.beam_size),
                        do_sample=False,
                        length_penalty=self.config.length_penalty,
                        no_repeat_ngram_size=getattr(self.config, "no_repeat_ngram_size", 0),
                    )
                decoded = self.tokenizer.batch_decode(generated, skip_special_tokens=True)
                for i, text in enumerate(decoded):
                    translated[start_idx + i] = text.strip()
            except RuntimeError as exc:
                if "CUDA" in str(exc):
                    logging.warning("Batch %s/%s OOM, falling back to sequential...", batch_idx + 1, total_batches)
                    cleanup_torch()
                    for i, text in enumerate(batch_texts):
                        translated[start_idx + i] = self._translate_single(text, forced_bos, target_lang)
                else:
                    raise
            if (batch_idx + 1) % 5 == 0:
                cleanup_torch()
        return translated

    def _reassemble_translations(
        self,
        texts: List[str],
        segment_map: List[List[int]],
        translated_segments: List[str],
        target_lang: str,
    ) -> List[str]:
        final_results = []
        for i, text in enumerate(texts):
            if not text.strip():
                final_results.append(text)
                continue
            indices = segment_map[i]
            if not indices:
                final_results.append(text)
                continue
            translated_parts = [translated_segments[idx] for idx in indices]
            full_text = "\n\n".join(translated_parts)
            full_text = self._scrub_translation(full_text)
            full_text = self._apply_glossary(full_text, target_lang)
            final_results.append(full_text)
        return final_results

    def translate_multiple(self, texts: List[str], target_lang: str) -> List[str]:
        if not texts:
            return []
        all_segments, segment_map = self._chunk_texts_with_mapping(texts)
        if not all_segments:
            return texts
        self.tokenizer.src_lang = self.config.source_lang
        _target_code, forced_bos = self._resolve_target_lang_code(target_lang)
        translated_segments = self._batch_translate_segments(all_segments, forced_bos, target_lang)
        return self._reassemble_translations(texts, segment_map, translated_segments, target_lang)

    def translate(self, text: str, target_lang: str) -> str:
        if not text.strip():
            return text

        self.tokenizer.src_lang = self.config.source_lang
        _target_code, forced_bos = self._resolve_target_lang_code(target_lang)
        segments = chunk_text(text, self.config.chunk_size)
        non_empty_segments = [(i, seg) for i, seg in enumerate(segments) if seg.strip()]
        if not non_empty_segments:
            return text

        batch_size = getattr(self.config, "batch_size", 8)
        translated_results = [""] * len(segments)
        for batch_start in range(0, len(non_empty_segments), batch_size):
            batch_items = non_empty_segments[batch_start : batch_start + batch_size]
            batch_indices = [item[0] for item in batch_items]
            batch_texts = [item[1] for item in batch_items]
            batch_texts_masked = [self._inject_entities(t, target_lang) for t in batch_texts]

            inputs = self.tokenizer(
                batch_texts_masked,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=self.config.max_input,
            )
            inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
            max_new_tokens = self._estimate_max_new_tokens(inputs, target_lang)

            try:
                with torch.no_grad():
                    generated = self.model.generate(
                        **inputs,
                        forced_bos_token_id=forced_bos,
                        max_new_tokens=max_new_tokens,
                        num_beams=max(1, self.config.beam_size),
                        do_sample=False,
                        length_penalty=self.config.length_penalty,
                        no_repeat_ngram_size=getattr(self.config, "no_repeat_ngram_size", 3),
                    )
            except RuntimeError as exc:
                if "CUDA" in str(exc):
                    logging.warning("Batch translation OOM, falling back to single mode...")
                    del inputs
                    cleanup_torch()
                    gc.collect()
                    for idx, seg_text in zip(batch_indices, batch_texts):
                        translated_results[idx] = self._translate_single(seg_text, forced_bos, target_lang)
                    continue
                raise

            vocab_size = len(self.tokenizer)
            if hasattr(self.tokenizer, "fairseq_offset"):
                max_valid_id = vocab_size + self.tokenizer.fairseq_offset - 1
                min_valid_id = self.tokenizer.fairseq_offset
            else:
                max_valid_id = vocab_size - 1
                min_valid_id = 0

            pad_token_id = self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else self.tokenizer.eos_token_id
            if pad_token_id is None:
                pad_token_id = 0

            generated_filtered = generated.clone()
            invalid_mask = (generated_filtered < min_valid_id) | (generated_filtered > max_valid_id)
            generated_filtered[invalid_mask] = pad_token_id

            try:
                decoded_list = self.tokenizer.batch_decode(generated_filtered, skip_special_tokens=True)
                for idx, decoded_text in zip(batch_indices, decoded_list):
                    translated_results[idx] = decoded_text.strip()
            except (IndexError, ValueError) as decode_error:
                logging.warning("Batch decode failed: %s", decode_error)
                for i, (idx, gen_seq) in enumerate(zip(batch_indices, generated_filtered)):
                    try:
                        valid_tokens = gen_seq[(gen_seq >= min_valid_id) & (gen_seq <= max_valid_id)]
                        if len(valid_tokens) > 0:
                            decoded_text = self.tokenizer.decode(valid_tokens, skip_special_tokens=True)
                            translated_results[idx] = decoded_text.strip()
                        else:
                            translated_results[idx] = batch_texts[i]
                    except Exception:
                        translated_results[idx] = batch_texts[i]

            del inputs
            del generated
            del generated_filtered

        for i, seg in enumerate(segments):
            if not seg.strip():
                translated_results[i] = seg

        final_text = "\n\n".join(translated_results).strip()
        final_text = self._scrub_translation(final_text)
        return self._apply_glossary(final_text, target_lang)

    def _inject_entities(self, text: str, target_lang: str) -> str:
        replacements = {
            r"Grandpa Tom": "湯姆爺爺",
            r"Uncle Tom": "湯姆爺爺",
            r"Grandpa": "爺爺",
            r"Alex": "艾力克斯",
            r"Emma": "艾瑪",
            r"Cinnamon": "肉桂",
            r"Locket": "掛墜盒",
            r"Shovel": "鏟子",
            r"Bottle": "瓶子",
            r"Patch": "補丁",
            r"Mid-Autumn": "中秋節",
            r"Diwali": "排燈節",
        }

        is_simplified = "zh-cn" in target_lang.lower() or "hans" in target_lang.lower()
        if is_simplified:
            simp_map = {
                "湯姆爺爺": "汤姆爷爷",
                "爺爺": "爷爷",
                "艾力克斯": "艾力克斯",
                "艾瑪": "艾玛",
                "肉桂": "肉桂",
                "掛墜盒": "挂坠盒",
                "鏟子": "铲子",
                "瓶子": "瓶子",
                "補丁": "补丁",
                "中秋節": "中秋节",
                "排燈節": "排灯节",
            }
            replacements = {k: simp_map.get(v, v) for k, v in replacements.items()}

        masked_text = text
        for pattern, target in replacements.items():
            real_pattern = r"\b" + pattern + r"(?=[^a-zA-Z]|$)" if pattern in ["Alex", "Emma", "Tom"] else pattern
            masked_text = re.sub(real_pattern, target, masked_text, flags=re.IGNORECASE)
        return masked_text

    def _scrub_translation(self, text: str) -> str:
        banned = [
            "低聲地低聲",
            "地便地",
            "摸摸地圖",
            "姆老公",
            "姆大叔",
            "米老公",
        ]
        for ban in banned:
            if ban in text:
                text = text.replace(ban, "湯姆爺爺" if "姆" in ban else "")
        text = re.sub(r"\b(The|And|But|So)\b", "", text, flags=re.IGNORECASE)
        return text

    def _translate_single(self, text: str, forced_bos: int, target_lang: str) -> str:
        if not text.strip():
            return text
        masked_text = self._inject_entities(text, target_lang)
        inputs = self.tokenizer(
            masked_text,
            return_tensors="pt",
            padding=False,
            truncation=True,
            max_length=self.config.max_input,
        )
        inputs = {k: v.to(self.model.device) for k, v in inputs.items()}
        max_new_tokens = self._estimate_max_new_tokens(inputs, target_lang)

        with torch.no_grad():
            generated = self.model.generate(
                **inputs,
                forced_bos_token_id=forced_bos,
                max_new_tokens=max_new_tokens,
                num_beams=max(1, self.config.beam_size),
                do_sample=False,
                length_penalty=self.config.length_penalty,
                no_repeat_ngram_size=getattr(self.config, "no_repeat_ngram_size", 0),
            )

        vocab_size = len(self.tokenizer)
        if hasattr(self.tokenizer, "fairseq_offset"):
            max_valid_id = vocab_size + self.tokenizer.fairseq_offset - 1
            min_valid_id = self.tokenizer.fairseq_offset
        else:
            max_valid_id = vocab_size - 1
            min_valid_id = 0

        pad_token_id = self.tokenizer.pad_token_id or self.tokenizer.eos_token_id or 0
        generated_filtered = generated.clone()
        invalid_mask = (generated_filtered < min_valid_id) | (generated_filtered > max_valid_id)
        generated_filtered[invalid_mask] = pad_token_id

        try:
            decoded = self.tokenizer.batch_decode(generated_filtered, skip_special_tokens=True)
            result = decoded[0].strip()
            result = self._scrub_translation(result)
            return result
        except Exception:
            return text

    def cleanup(self) -> None:
        from utils import ResourceManager

        if hasattr(self, "model") and self.model is not None:
            ResourceManager.cleanup_model(self.model, aggressive=True)
            self.model = None
        if hasattr(self, "tokenizer") and self.tokenizer is not None:
            del self.tokenizer
            self.tokenizer = None
        if hasattr(self, "lang_code_to_id"):
            self.lang_code_to_id = {}


TranslationBackendBuilder = Callable[[Any], BaseTranslationBackend]

_TRANSLATION_BACKEND_BUILDERS: Dict[str, TranslationBackendBuilder] = {}
_TRANSLATION_BACKEND_CANONICAL: Dict[str, str] = {}


def register_translation_provider(
    name: str,
    builder: TranslationBackendBuilder,
    aliases: Sequence[str] = (),
) -> None:
    canonical = name.strip().lower()
    _TRANSLATION_BACKEND_BUILDERS[canonical] = builder
    _TRANSLATION_BACKEND_CANONICAL[canonical] = canonical
    for alias in aliases:
        normalized = alias.strip().lower()
        _TRANSLATION_BACKEND_BUILDERS[normalized] = builder
        _TRANSLATION_BACKEND_CANONICAL[normalized] = canonical


def available_translation_providers() -> List[str]:
    return sorted(set(_TRANSLATION_BACKEND_CANONICAL.values()))


def build_translation_backend(config: Any) -> BaseTranslationBackend:
    provider = (getattr(config, "provider", None) or "transformers_nllb").strip().lower()
    canonical = _TRANSLATION_BACKEND_CANONICAL.get(provider, provider)
    builder = _TRANSLATION_BACKEND_BUILDERS.get(canonical)
    if builder is None:
        raise ValueError(
            f"Unknown translation provider '{getattr(config, 'provider', None)}'. Available providers: {', '.join(available_translation_providers())}"
        )
    return builder(config)


register_translation_provider(
    "transformers_nllb",
    TransformersNLLBBackend,
    aliases=("nllb", "transformers"),
)


Translator = TransformersNLLBBackend
