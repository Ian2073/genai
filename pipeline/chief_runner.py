"""主控流程實作：串聯文字、影像、翻譯、語音、驗證各個模組。"""

from __future__ import annotations

import gc
import json
import multiprocessing as mp
import os
import random
import re
import time
from datetime import datetime, timezone
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import replace

import torch

from observability import Session as ObsSession
from image import Config as ImageConfig, generate_photos_for_story
from story import (
	GenerationParams,
	PipelineOptions,
	StoryInput,
	StoryPipeline,
	_apply_default_step_generations,
	estimate_tokens,
	generate_story_id,
)
from backends.llm import LLMConfig, build_llm
from trans import Config as TransConfig, translate_story
from voice import Config as VoiceConfig, generate_narration_for_story
from runtime.story_files import detect_story_languages
from utils import (
	ProjectPaths,
	StoryProfile,
	build_story_profile,
	build_story_relative_path,
	cleanup_torch,
	create_story_root,
	ensure_dir,
	force_cleanup_models,
	setup_logging,
)
from .chief_verification import verify_story
from .chief_workload_stats import (
	build_llm_complexity,
	collect_image_prompt_stats,
	collect_translation_stats,
	collect_tts_text_stats,
	detect_tts_clipping,
)
from .chief_observability import (
	generate_observability_reports,
	init_observability,
	maybe_record_tts_clipping,
	record_pipeline_baseline,
	record_stage_outcome,
)
from .chief_runtime import (
	book_prefix,
	build_book_context,
	build_initial_result,
	build_request_meta,
	build_strategy_state,
	summarize_batch_results,
	update_workload_summary,
)
from .options import PUNCTUATION_PATTERN, STYLE_KEYWORDS, CATEGORY_CHOICES, AGE_CHOICES, ChiefOptions, parse_dtype

class _PipelineEarlyExit(Exception):
	"""用於提前結束單本書流程的內部例外狀況 (例如發生不可挽回的錯誤)。"""

def _story_worker_process(
	profile: StoryProfile,
	options: ChiefOptions,
	seed: int,
	result_queue: mp.Queue
) -> None:
	"""在獨立的子行程中執行 LLM 故事生成，確保 VRAM 能在結束時被作業系統徹底回收。"""
	try:
		from story_core.story_entry import generate_story_id
		from backends.llm import LLMConfig, build_llm
		from story import (
			GenerationParams,
			PipelineOptions,
			StoryInput,
			StoryPipeline,
			_apply_default_step_generations,
		)
		from utils import (
			build_story_relative_path,
			create_story_root,
			setup_logging,
			force_cleanup_models
		)

		random.seed(seed)
		input_mode = (options.story_input_mode or "preset").strip().lower()
		if input_mode not in {"preset", "custom"}:
			input_mode = "preset"
		story_input = StoryInput(
			language=profile.language,
			age_group=profile.age_label,
			category=profile.category_label,
			subcategory=profile.subcategory_label,
			theme=profile.theme_label,
			input_mode=input_mode,
			user_prompt=options.story_user_prompt if input_mode == "custom" else "",
			user_materials=options.story_user_materials if input_mode == "custom" else "",
			kg_payload=profile.kg_payload,
			kg_profile=profile,
		)
		story_id = generate_story_id(story_input)
		relative_path = build_story_relative_path(profile, story_id)
		story_root = create_story_root(options.story_output_root, relative_path, languages=[profile.language])
		log_path = story_root / "logs" / "generation.log"
		story_logger = setup_logging(f"story_pipeline_{story_id}", log_path, console=True)

		pages_expected = (
			options.story_pages_expected 
			if options.story_pages_expected and options.story_pages_expected > 0
			else profile.pages_expected
		)
		base_generation = GenerationParams(
			max_tokens=options.story_max_tokens,
			min_tokens=options.story_min_tokens,
			temperature=options.story_temperature,
			top_p=options.story_top_p,
			top_k=options.story_top_k,
			repetition_penalty=options.story_repetition_penalty,
			no_repeat_ngram_size=options.story_no_repeat_ngram or None,
		)
		step_generations = _apply_default_step_generations(base_generation, {})
		pipeline_options = PipelineOptions(
			pages_expected=pages_expected,
			max_page_chars=options.story_max_chars,
			max_page_sentences=options.story_max_sentences,
			generation=base_generation,
			model_name=options.story_model_name,
			prompt_set=options.story_prompt_set,
			cover_source=options.story_cover_source,
			kg_enabled=True,
			kg_version=profile.kg_version,
			step_generations=step_generations,
			aggressive_memory_cleanup=options.low_vram,
		)
		llm = build_llm(
			LLMConfig(
				model_dir=options.story_model,
				device_map=options.story_device,
				dtype=options.story_dtype,
				seed=seed,
				quantization=options.story_quantization,
			)
		)
		pipeline = StoryPipeline(
			story_input,
			story_id,
			relative_path,
			options.story_output_root,
			story_root,
			llm,
			pipeline_options,
			story_logger,
			kernel_recorder=None,
		)
		
		meta = pipeline.run()
		step_history = pipeline.step_history
		final_story_root = pipeline.story_root
		
		if hasattr(llm, "cleanup"):
			try:
				llm.cleanup()
			except Exception:
				pass
		del llm
		del pipeline
		try:
			force_cleanup_models()
		except Exception:
			pass
			
		result_queue.put((final_story_root, meta, step_history, None))
	except Exception as exc:
		import traceback
		result_queue.put((None, None, None, "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))))


class ChiefRunner:
	"""協調故事、影像、翻譯、語音等模組的主控類別 (Controller)。"""
	def __init__(self, options: ChiefOptions) -> None:
		"""根據輸入選項初始化各模組設定與亂數種子。"""
		self.options = options
		self.paths = ProjectPaths.discover()
		# run_dir 僅作為預設輸出根目錄，實際每本書會在 _run_single_isolated 中建立自己的 run 資料夾
		self.run_dir = self.paths.runs_dir
		self.logger = setup_logging("chief", self.paths.logs_dir / "chief.log", console=True)
		self.options = self._normalize_language_options(self.options)
		self.voice_languages = self._planned_voice_languages()
		self._voice_languages_used: List[str] = []
		self.total_books = max(1, self.options.count)
		self._active_requests = 0
		seed = options.seed or int(time.time())
		self.seed = seed
		self.random = random.Random(seed)
		self.logger.info("Chief initialized with seed %s", seed)
		self.observability: Optional[ObsSession] = None
		self.status_json_path: Optional[Path] = options.status_json_path
		self._status_state: Dict[str, Any] = {
			"state": "idle",
			"total_books": self.total_books,
			"completed_books": 0,
			"success_books": 0,
			"failed_books": 0,
			"current_book": None,
			"current_attempt": 1,
			"current_stage": None,
			"last_error": None,
			"updated_at": datetime.now(timezone.utc).isoformat(),
		}
		if self.status_json_path:
			try:
				self.status_json_path.parent.mkdir(parents=True, exist_ok=True)
			except Exception:
				self.status_json_path = None
		self.photo_config = ImageConfig(
			base_model_dir=options.sdxl_base,
			refiner_model_dir=options.sdxl_refiner,
			device=options.photo_device,
			dtype=parse_dtype(options.photo_dtype),
			width=options.photo_width,
			height=options.photo_height,
			steps=options.photo_steps,
			guidance=options.photo_guidance,
			refiner_steps=options.photo_refiner_steps,
			skip_refiner=options.photo_skip_refiner,
			negative_prompt=options.photo_negative_prompt,
			cover_prompt_suffix=options.photo_cover_suffix,
			character_prompt_suffix=options.photo_character_suffix,
			scene_prompt_suffix=options.photo_scene_suffix,
			seed=options.photo_seed,
			remove_bg=not options.photo_no_remove_bg,
			low_vram=options.low_vram,
		)
		self.voice_config = VoiceConfig(
			model_dir=self.paths.models_dir / "XTTS-v2",
			device=options.voice_device,
			language=self.options.voice_language,
			speaker_wav=options.speaker_wav,
			speaker_dir=options.speaker_dir,
			page_start=options.voice_page_start,
			page_end=options.voice_page_end,
			gain=options.voice_volume_gain,
			concat=not options.voice_no_concat,
			keep_raw=not options.voice_drop_raw,
		)
		self.translation_base = TransConfig(
			model_dir=options.translation_model,
			device=options.translation_device,
			dtype=parse_dtype(options.translation_dtype),
			source_lang=options.translation_source_lang,
			source_folder=options.story_language,
			target_langs=self.options.languages,
			sample_dir=self.paths.models_dir / "XTTS-v2" / "samples",
			output_dir_name="",
			beam_size=options.translation_beam_size,
			length_penalty=options.translation_length_penalty,
		)
		self._write_status_snapshot(state="idle")

	@staticmethod
	def _normalize_language_code(raw: str) -> str:
		token = str(raw or "").strip().lower()
		if token in {"zh-tw", "zh_hant", "zh-hant", "zho_hant"}:
			return "zh"
		if token.startswith("en"):
			return "en"
		if token.startswith("zh"):
			return "zh"
		return token

	def _normalize_language_options(self, options: ChiefOptions) -> ChiefOptions:
		allowed = ("en", "zh")
		source = self._normalize_language_code(options.story_language)

		requested: List[str] = []
		for lang in options.languages or []:
			token = self._normalize_language_code(lang)
			if token in allowed and token not in requested:
				requested.append(token)

		candidates = requested or list(allowed)
		targets = [lang for lang in candidates if lang != source]
		if not targets:
			fallback = [lang for lang in allowed if lang != source]
			targets = fallback if fallback else ["zh"]

		primary_voice = self._normalize_language_code(options.voice_language)
		if primary_voice not in allowed:
			primary_voice = "en" if source != "zh" else "zh"

		normalized = replace(options, languages=targets, voice_language=primary_voice)
		if normalized.languages != options.languages:
			self.logger.info("Auto-run translation languages constrained to: %s", ",".join(normalized.languages))
		if normalized.voice_language != options.voice_language:
			self.logger.info("Auto-run voice language normalized to: %s", normalized.voice_language)
		return normalized

	def _planned_voice_languages(self) -> List[str]:
		allowed = ("en", "zh")
		source = self._normalize_language_code(self.options.story_language)
		planned: List[str] = []

		if source in allowed:
			planned.append(source)
		elif self.options.voice_language in allowed:
			planned.append(self.options.voice_language)
		else:
			planned.append("en")

		if self.options.translation_enabled:
			for lang in self.options.languages:
				token = self._normalize_language_code(lang)
				if token in allowed and token not in planned:
					planned.append(token)
		return planned

	def _primary_voice_language(self) -> str:
		if self._voice_languages_used:
			return self._voice_languages_used[0]
		if self.voice_languages:
			return self.voice_languages[0]
		return self.options.voice_language

	def _write_status_snapshot(self, **updates: Any) -> None:
		"""更新即時狀態並輸出 JSON，供儀表板輪詢。"""
		self._status_state.update(updates)
		self._status_state["updated_at"] = datetime.now(timezone.utc).isoformat()
		if not self.status_json_path:
			return
		try:
			payload = dict(self._status_state)
			tmp = self.status_json_path.with_suffix(self.status_json_path.suffix + ".tmp")
			tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
			tmp.replace(self.status_json_path)
		except Exception:
			# 不讓狀態檔寫入影響主流程
			return

	def _extract_error_summary(self, result: Dict[str, object]) -> str:
		"""把結果中的錯誤與警告整理成單行摘要。"""
		errors = [str(x) for x in (result.get("errors") or [])]
		warnings = [str(x) for x in (result.get("warnings") or [])]
		parts: List[str] = []
		if errors:
			parts.append("errors=" + ",".join(errors))
		if warnings:
			parts.append("warnings=" + ",".join(warnings))
		return " | ".join(parts) if parts else ""

	def _prepare_run_directories(self, index: int = 0, total: int = 0) -> Path:
		"""準備執行目錄，根據批次模式產生唯一的資料夾名稱。
		
		Args:
			index: 當前書籍序號
			total: 總書籍數量
			
		Returns:
			執行目錄路徑
		"""
		ensure_dir(self.paths.runs_dir)
		timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
		# 為了區分不同的書，使用包含序號的資料夾名稱
		if total > 0:
			# 批次模式命名格式：timestamp_book-01_of_05_run-XX
			counter = 1
			while True:
				run_name = f"{timestamp}_book-{index:02d}_of_{total:02d}_run-{counter:02d}"
				run_path = self.paths.runs_dir / run_name
				if not run_path.exists():
					break
				counter += 1
		else:
			# 預設模式 (相容舊行為): timestamp_run-XX
			counter = 1
			while True:
				run_name = f"{timestamp}_run-{counter:02d}"
				run_path = self.paths.runs_dir / run_name
				if not run_path.exists():
					break
				counter += 1
				
		ensure_dir(run_path)
		ensure_dir(run_path / "logs")
		ensure_dir(run_path / "observability")
		ensure_dir(run_path / "analysis")
		return run_path

	@contextmanager
	def _segment_timer(
		self,
		trace_id: str,
		stage: str,
		category: str,
		metadata: Optional[Dict[str, Any]] = None,
	):
		"""計時器上下文管理器，記錄階段執行時間與 GPU 記憶體使用。
		
		Args:
			trace_id: 追蹤 ID
			stage: 階段名稱
			category: 類別名稱
			metadata: 額外的元數據
		"""
		start_wall = time.perf_counter()
		start_cpu = time.process_time()
		gpu_stats = self._current_gpu_memory()
		try:
			yield
			status = "success"
		except Exception:
			status = "error"
			raise
		finally:
			end_wall = time.perf_counter()
			end_cpu = time.process_time()
			end_gpu = self._current_gpu_memory()
			segment_metrics = {
				"stage": stage,
				"category": category,
				"duration_sec": round(end_wall - start_wall, 6),
				"cpu_sec": round(end_cpu - start_cpu, 6),
				"gpu_alloc_before": gpu_stats.get("allocated"),
				"gpu_alloc_after": end_gpu.get("allocated"),
				"gpu_reserved_before": gpu_stats.get("reserved"),
				"gpu_reserved_after": end_gpu.get("reserved"),
				"status": status,
				"metadata": metadata or {},
			}
			self.observability.pipeline.record_segment(
				trace_id,
				stage=stage,
				metrics=segment_metrics,
			)

	def _current_gpu_memory(self) -> Dict[str, Optional[int]]:
		"""取得當前 GPU 記憶體使用狀況。
		
		Returns:
			包含 allocated 和 reserved 記憶體大小的字典
		"""
		if not torch.cuda.is_available():
			return {}
		try:
			device = torch.cuda.current_device()
		except Exception:
			device = 0
		try:
			return {
				"allocated": torch.cuda.memory_allocated(device),
				"reserved": torch.cuda.memory_reserved(device),
			}
		except Exception:
			return {}
	def _record_story_steps(
		self,
		trace_id: str,
		steps: List[Dict[str, Any]],
		story_root: Optional[Path],
	) -> None:
		"""記錄故事生成的各個步驟到可觀測性系統。
		
		Args:
			trace_id: 追蹤 ID
			steps: 步驟列表
			story_root: 故事根目錄
		"""
		if not steps:
			return
		for idx, entry in enumerate(steps, start=1):
			metrics = dict(entry)
			metrics["page_index"] = idx
			self.observability.model.record_llm(
				stage="story_step",
				metrics=metrics,
				extra={
					"trace_id": trace_id,
					"story_root": str(story_root) if story_root else "",
				},
			)
	
	def _run_stage_story(
		self,
		index: int,
		profile: StoryProfile,
		trace_id: str,
		book_context: Dict[str, Any],
		result: Dict[str, object],
		workload_complexity: Dict[str, Any],
	) -> Optional[Dict[str, object]]:
		"""執行故事生成階段 (Story Generation - LLM)。"""
		self._log_stage(index, profile, "STORY", "start")
		
		with self._segment_timer(trace_id, "story_llm", "llm", metadata=book_context):
			story_stage_start = time.perf_counter()
			try:
				story_root, story_meta, story_steps = self._create_story(profile)
			except Exception as exc:
				self.logger.exception("Story generation failed: %s", exc)
				result["errors"].append("story")
				self._log_stage(index, profile, "STORY", "fail")
				self._record_stage_outcome(
					trace_id, "LLM", story_stage_start,
					status="error",
					error_type=exc.__class__.__name__,
					details=str(exc),
				)
				raise _PipelineEarlyExit() from exc
			
			if story_root is None:
				result["errors"].append("story")
				self._log_stage(index, profile, "STORY", "fail")
				self._record_stage_outcome(
					trace_id, "LLM", story_stage_start,
					status="error",
					error_type="StoryPipelineError",
					details="Story pipeline returned no story_root",
				)
				raise _PipelineEarlyExit()
			
			self._log_stage(index, profile, "STORY", "done")
			self._record_stage_outcome(trace_id, "LLM", story_stage_start, status="success")
			result["story_root"] = str(story_root)
			self._record_story_steps(trace_id, story_steps, story_root)
			
			if story_meta:
				workload_complexity["llm"] = self._build_llm_complexity(profile, story_meta)
				self.observability.model.record_llm(
					stage="story_pipeline",
					metrics={
						"generation_time_sec": story_meta.get("timestamps", {}).get("generation_time_sec"),
						"pages_expected": story_meta.get("summary", {}).get("pages_expected"),
						"pages_actual": story_meta.get("summary", {}).get("pages_actual"),
					},
					extra={
						"story_id": story_meta.get("story_id"),
						"relative_path": story_meta.get("relative_path"),
						"trace_id": trace_id,
					},
				)
			
			self.logger.info("Capturing memory snapshot...")
			self.observability.memory.snapshot(
				label="post_story",
				metadata={"story_root": str(story_root), "trace_id": trace_id},
			)
			self.logger.info("Memory snapshot captured")
			
			del story_steps
			self.logger.info("Running final cleanup before image stage...")
			force_cleanup_models()
			self.logger.info("LLM resources released, preparing for next stage...")
		
		return story_meta
	
	def _run_stage_image(
		self,
		index: int,
		profile: StoryProfile,
		trace_id: str,
		book_context: Dict[str, Any],
		result: Dict[str, object],
		workload_complexity: Dict[str, Any],
		story_root: Path,
	) -> bool:
		"""執行圖像生成階段 (Image Generation - SDXL)。"""
		if not self.options.photo_enabled:
			self._record_stage_outcome(
				trace_id, "SDXL", time.perf_counter(),
				status="skipped",
				degradation={"reason": "disabled"},
			)
			self._log_stage(index, profile, "IMAGE", "skip")
			return True
		
		self._log_stage(index, profile, "IMAGE", "start")
		self.observability.pipeline.record_switch("LLM", "SDXL", {"story_root": str(story_root), "trace_id": trace_id})
		
		with self._segment_timer(trace_id, "image", "sdxl", metadata=book_context):
			image_stage_start = time.perf_counter()
			with self.observability.pipeline.span(
				"image_sdxl",
				category="image",
				metadata=book_context,
				capture_gpu=True,
				trace_id=trace_id,
			):
				photo_ok = self._run_photo(story_root)
			
			if not photo_ok:
				result["errors"].append("photo")
				self._log_stage(index, profile, "IMAGE", "fail")
			else:
				self._log_stage(index, profile, "IMAGE", "done")
				workload_complexity["sdxl"] = self._collect_image_prompt_stats(story_root)
			
			status = "success" if photo_ok else "error"
			self._record_stage_outcome(
				trace_id, "SDXL", image_stage_start,
				status=status,
				error_type=None if photo_ok else "PhotoGenerationError",
				details=None if photo_ok else "SDXL pipeline returned False",
			)
			self.observability.model.record_image(
				stage="sdxl",
				metrics={
					"width": self.photo_config.width,
					"height": self.photo_config.height,
					"steps": self.photo_config.steps,
					"guidance": self.photo_config.guidance,
					"refiner_steps": self.photo_config.refiner_steps or 0,
					"skip_refiner": self.photo_config.skip_refiner,
					"success": photo_ok,
				},
				extra={"story_root": str(story_root), "trace_id": trace_id},
			)
		
		force_cleanup_models()
		self.logger.info("SDXL resources released, preparing for next stage...")
		return photo_ok
	
	def _run_stage_translation(
		self,
		index: int,
		profile: StoryProfile,
		trace_id: str,
		book_context: Dict[str, Any],
		result: Dict[str, object],
		workload_complexity: Dict[str, Any],
		story_root: Path,
		photo_ok: bool,
	) -> Optional[Dict[str, List[Path]]]:
		"""執行翻譯階段 (Translation - NLLB)。"""
		if not self.options.translation_enabled:
			self._record_stage_outcome(
				trace_id, "TRANSLATION", time.perf_counter(),
				status="skipped",
				degradation={"reason": "disabled"},
			)
			self._log_stage(index, profile, "TRANSLATE", "skip")
			return {}
		
		self._log_stage(index, profile, "TRANSLATE", "start")
		prev_stage = "SDXL" if self.options.photo_enabled else "LLM"
		self.observability.pipeline.record_switch(
			prev_stage, "TRANSLATE",
			{"story_root": str(story_root), "trace_id": trace_id},
		)
		
		with self._segment_timer(
			trace_id, "translation", "translation",
			metadata={**book_context, "languages": self.options.languages},
		):
			translation_stage_start = time.perf_counter()
			with self.observability.kernel.profile(
				trace_id, "translation",
				metadata={**book_context, "languages": self.options.languages},
			):
				with self.observability.pipeline.span(
					"translation_llm",
					category="translation",
					metadata={**book_context, "languages": self.options.languages},
					capture_gpu=True,
					trace_id=trace_id,
				):
					translation_outputs = self._run_translation(story_root)
			
			translation_ok = translation_outputs is not None
			if not translation_ok:
				if self.options.strict_translation:
					result["errors"].append("translation")
				else:
					result["warnings"].append("translation")
				self._log_stage(index, profile, "TRANSLATE", "fail")
			else:
				self._log_stage(index, profile, "TRANSLATE", "done")
				workload_complexity["translation"] = self._collect_translation_stats(translation_outputs)
			
			status = "success" if translation_ok else ("error" if self.options.strict_translation else "degraded")
			degradation = None
			if not translation_ok and not self.options.strict_translation:
				degradation = {"strategy": "non_strict_translation"}
			
			self._record_stage_outcome(
				trace_id, "TRANSLATION", translation_stage_start,
				status=status,
				error_type=None if translation_ok else "TranslationError",
				details=None if translation_ok else "translate_story returned failure",
				degradation=degradation,
			)
			self.observability.model.record_translator(
				stage="nllb",
				metrics={
					"beam_size": self.options.translation_beam_size,
					"length_penalty": self.options.translation_length_penalty,
					"target_count": len(self.options.languages or self.translation_base.target_langs),
					"success": translation_ok,
				},
				extra={
					"source_lang": self.options.translation_source_lang,
					"dtype": self.options.translation_dtype,
					"trace_id": trace_id,
				},
			)
		
		return translation_outputs if translation_ok else None
	
	def _run_stage_voice(
		self,
		index: int,
		profile: StoryProfile,
		trace_id: str,
		book_context: Dict[str, Any],
		result: Dict[str, object],
		workload_complexity: Dict[str, Any],
		story_root: Path,
		translation_ok: bool,
	) -> bool:
		"""執行語音生成階段 (Voice Generation - XTTS)。"""
		if not self.options.voice_enabled:
			self._record_stage_outcome(
				trace_id, "TTS", time.perf_counter(),
				status="skipped",
				degradation={"reason": "disabled"},
			)
			self._log_stage(index, profile, "VOICE", "skip")
			return True
		
		self._log_stage(index, profile, "VOICE", "start")
		prev_stage = (
			"TRANSLATE" if self.options.translation_enabled
			else ("SDXL" if self.options.photo_enabled else "LLM")
		)
		self.observability.pipeline.record_switch(
			prev_stage, "VOICE",
			{"story_root": str(story_root), "trace_id": trace_id},
		)
		
		with self._segment_timer(trace_id, "voice", "tts", metadata=book_context):
			voice_stage_start = time.perf_counter()
			with self.observability.kernel.profile(trace_id, "tts", metadata=book_context):
				with self.observability.pipeline.span(
					"voice_xtts",
					category="tts",
					metadata=book_context,
					capture_gpu=True,
					trace_id=trace_id,
				):
					voice_ok = self._run_voice(story_root)
			
			if not voice_ok:
				if self.options.strict_voice:
					result["errors"].append("voice")
				else:
					result["warnings"].append("voice")
				self._log_stage(index, profile, "VOICE", "fail")
			else:
				self._log_stage(index, profile, "VOICE", "done")
				workload_complexity["tts"] = self._collect_tts_text_stats(story_root)
				self._maybe_record_tts_clipping(trace_id, story_root)
			
			status = "success" if voice_ok else ("error" if self.options.strict_voice else "degraded")
			degradation = None
			if not voice_ok and not self.options.strict_voice:
				degradation = {"strategy": "non_strict_voice"}
			
			self._record_stage_outcome(
				trace_id, "TTS", voice_stage_start,
				status=status,
				error_type=None if voice_ok else "VoiceGenerationError",
				details=None if voice_ok else "XTTS pipeline returned False",
				degradation=degradation,
			)
			self.observability.model.record_tts(
				stage="xtts",
				metrics={
					"language": ",".join(self._voice_languages_used or self.voice_languages),
					"gain": self.options.voice_volume_gain,
					"page_range": (self.options.voice_page_start, self.options.voice_page_end),
					"success": voice_ok,
				},
				extra={
					"speaker": str(self.options.speaker_wav or self.options.speaker_dir or ""),
					"device": self.options.voice_device,
					"trace_id": trace_id,
				},
			)
		
		return voice_ok
	
	def _run_stage_verify(
		self,
		index: int,
		profile: StoryProfile,
		trace_id: str,
		book_context: Dict[str, Any],
		result: Dict[str, object],
		story_root: Path,
		translation_ok: bool,
		voice_ok: bool,
		photo_ok: bool,
	) -> bool:
		"""執行最終驗證階段 (Verification)，確認產出完整性。"""
		if not self.options.verify_enabled:
			self._record_stage_outcome(
				trace_id, "VERIFY", time.perf_counter(),
				status="skipped",
				degradation={"reason": "disabled"},
			)
			self._log_stage(index, profile, "VERIFY", "skip")
			return True
		
		self._log_stage(index, profile, "VERIFY", "start")
		with self._segment_timer(trace_id, "verify", "verification", metadata=book_context):
			verify_stage_start = time.perf_counter()
			with self.observability.kernel.profile(trace_id, "verify", metadata=book_context):
				with self.observability.pipeline.span(
					"verify",
					category="verify",
					metadata=book_context,
					trace_id=trace_id,
				):
					verified = self._verify_story(
						story_root,
						expect_translation=self.options.translation_enabled and translation_ok,
						expect_voice=self.options.voice_enabled and voice_ok,
						expect_photo=self.options.photo_enabled and photo_ok,
					)
			
			if not verified:
				result["errors"].append("verify")
				self._log_stage(index, profile, "VERIFY", "fail")
			else:
				self._log_stage(index, profile, "VERIFY", "done")
			
			self._record_stage_outcome(
				trace_id, "VERIFY", verify_stage_start,
				status="success" if verified else "error",
				error_type=None if verified else "VerificationError",
				details=None if verified else "Verification stage reported failure",
			)
		
		return verified
	
	def _run_pipeline_stages(
		self,
		index: int,
		profile: StoryProfile,
		trace_id: str,
		book_context: Dict[str, Any],
		result: Dict[str, object],
		workload_summary: Dict[str, Any],
		workload_complexity: Dict[str, Any],
		start: float,
	) -> Optional[Dict[str, object]]:
		"""協調調度所有子流程階段 (已分解為小方法以提高可讀性)。"""
		# Stage 1: Story (LLM)
		story_meta = self._run_stage_story(
			index, profile, trace_id, book_context, result, workload_complexity
		)
		story_root = Path(result["story_root"]) if result.get("story_root") else None
		if not story_root:
			raise _PipelineEarlyExit()
		
		# Stage 2: Image (SDXL)
		photo_ok = self._run_stage_image(
			index, profile, trace_id, book_context, result, workload_complexity, story_root
		)
		
		# Stage 3: Translation (NLLB)
		translation_outputs = self._run_stage_translation(
			index, profile, trace_id, book_context, result, workload_complexity, story_root, photo_ok
		)
		translation_ok = translation_outputs is not None
		
		# Stage 4: Voice (XTTS)
		voice_ok = self._run_stage_voice(
			index, profile, trace_id, book_context, result, workload_complexity, story_root, translation_ok
		)
		
		# Stage 5: Verify
		verified = self._run_stage_verify(
			index, profile, trace_id, book_context, result, story_root, translation_ok, voice_ok, photo_ok
		)
		
		# Finalize
		result["success"] = not result["errors"] and verified
		result["duration_sec"] = round(time.time() - start, 2)
		self.observability.memory.fragmentation(label="book_end")
		
		return story_meta

	def run(self) -> Dict[str, object]:
		"""根據模式 (Single/Batch) 啟動故事生成流程。"""
		self._write_status_snapshot(
			state="running",
			total_books=self.total_books,
			completed_books=0,
			success_books=0,
			failed_books=0,
			current_book=None,
			current_stage="start",
			last_error=None,
		)
		if self.total_books == 1:
			result = self._run_single_with_retries(1)
			summary = {"total": 1, "success": 1 if result["success"] else 0, "results": [result]}
			self._write_status_snapshot(
				state="completed" if result.get("success") else "failed",
				completed_books=1,
				success_books=1 if result.get("success") else 0,
				failed_books=0 if result.get("success") else 1,
				current_stage="done",
				last_error=self._extract_error_summary(result),
			)
			return summary
		summary = self._run_batch()
		self._write_status_snapshot(
			state="completed" if summary.get("total", 0) == summary.get("success", 0) else "failed",
			current_stage="done",
		)
		return summary

	def _run_single_with_retries(self, index: int) -> Dict[str, object]:
		"""整本書失敗時重跑（不降級）。"""
		max_retries = max(0, int(self.options.max_book_retries))
		max_attempts = max_retries + 1
		result: Dict[str, object] = {
			"index": index,
			"success": False,
			"errors": ["not_started"],
			"warnings": [],
		}

		for attempt in range(1, max_attempts + 1):
			self._write_status_snapshot(
				current_book=index,
				current_attempt=attempt,
				current_stage="book_start",
			)
			result = self._run_single_isolated(index, attempt=attempt)
			result["attempt"] = attempt
			result["max_attempts"] = max_attempts
			if result.get("success"):
				return result

			if attempt < max_attempts:
				self.logger.warning(
					"Book %s/%s failed at attempt %s/%s. Retrying whole book...",
					index,
					self.total_books,
					attempt,
					max_attempts,
				)
				self._write_status_snapshot(
					last_error=self._extract_error_summary(result),
					current_stage="retrying",
				)
				cleanup_torch()
				gc.collect()

		return result

	def _run_batch(self) -> Dict[str, object]:
		"""執行批次生成多本書，並顯示進度。"""
		total = self.total_books
		results: List[Dict[str, object]] = []
		for idx in range(1, total + 1):
			try:
				result = self._run_single_with_retries(idx)
			except KeyboardInterrupt:
				self.logger.warning("Batch interrupted by user")
				self._write_status_snapshot(state="stopped", current_stage="interrupted")
				break
			results.append(result)
			self._log_batch_progress(idx, results)
			self._write_status_snapshot(last_error=self._extract_error_summary(result))
			# [FIX] Enforce strict isolation: Cleanup after EVERY book
			self.logger.info("Releasing resources after book %s", idx)
			cleanup_torch()
			gc.collect()
		return {
			"total": len(results),
			"success": sum(1 for r in results if r["success"]),
			"results": results,
		}

	def _run_single_isolated(self, index: int, attempt: int = 1) -> Dict[str, object]:
		"""為每一本書初始化獨立的 Observability Session 與 Run 目錄 (確保資源隔離)。"""
		# 1. 準備該本書專用的 run directory
		book_run_dir = self._prepare_run_directories(index, self.total_books)
		run_logs_dir = book_run_dir / "logs"
		run_observability_dir = book_run_dir / "observability"
		
		# 2. 重設 logger 到新的目錄 (可選，但為了日誌分流建議這樣做)
		# 注意：我們保留 console 輸出，但將 file handler 切換到新目錄
		log_path = run_logs_dir / "chief.log"
		self.logger = setup_logging("chief", log_path, console=True)
		self.logger.info(
			"Starting Book %d/%d (Attempt %d). Artifacts: %s",
			index,
			self.total_books,
			attempt,
			book_run_dir,
		)
		self._write_status_snapshot(
			state="running",
			current_book=index,
			current_attempt=attempt,
			current_stage="init",
		)

		# 3. 初始化 Observability
		self.observability = self._init_observability(self.seed + index, run_observability_dir) # 使用不同 seed 避免重複
		self.observability.infra.record_hardware_snapshot()
		self._record_pipeline_baseline()
		
		report_source = self.observability.output_path
		try:
			return self._run_single(index)
		finally:

				# 4. 生成該本書的專屬報表與進階分析
				try:
					self._generate_observability_reports(report_source)
					
					# 自動執行進階觀測與效能分析 (產生 Markdown 報告與紀錄)
					self.logger.info("Running automatic observability analysis...")
					import sys
					from pathlib import Path
					
					root_dir = Path(__file__).parent.parent
					if str(root_dir) not in sys.path:
						sys.path.insert(0, str(root_dir))
						
					from scripts.analyze_observability import ObservabilityAnalyzer
					if report_source and Path(report_source).exists():
						analyzer = ObservabilityAnalyzer()
						analyzer.analyze(Path(report_source), run_observability_dir)
						self.logger.info("Observability analysis completed.")
				except Exception as exc:
					self.logger.warning("Failed to generate observability reports or analysis: %s", exc)
				finally:
					self.observability = None # 保證清理參照
					gc.collect()

	def _run_single(self, index: int) -> Dict[str, object]:
		"""執行單本書的全部子流程並回傳結果摘要 (含錯誤報告)。"""
		# 確保 observability 已初始化
		if not self.observability:
			raise RuntimeError("Observability session not initialized for _run_single")
			
		if torch.cuda.is_available():
			torch.cuda.reset_peak_memory_stats()

		trace_id = self.observability.new_trace_id()
		with self._segment_timer(
			trace_id,
			"preprocess",
			"orchestration",
			metadata={"stage": "profile_init"},
		):
			profile = self._build_story_profile()
		book_context = build_book_context(index, profile, trace_id)
		self._active_requests += 1
		current_concurrency = self._active_requests
		self.observability.workload.record_concurrency(trace_id, current_concurrency)
		request_meta = build_request_meta(
			trace_id=trace_id,
			index=index,
			profile=profile,
			options=self.options,
			photo_config=self.photo_config,
			translation_target_langs=list(self.options.languages or self.translation_base.target_langs),
			total_books=self.total_books,
			seed=self.seed,
			concurrency_level=current_concurrency,
		)
		self.observability.workload.register_request(trace_id, request_meta)
		self.observability.strategy.record_state(
			build_strategy_state(
				index=index,
				total_books=self.total_books,
				profile=profile,
				mode=self.options.mode,
				trace_id=trace_id,
				concurrency_level=current_concurrency,
			)
		)
		self.observability.memory.snapshot(label="book_start", metadata=book_context)
		self._voice_languages_used = []
		result = build_initial_result(index, profile, trace_id)
		workload_summary: Dict[str, Any] = {"trace_id": trace_id, "request_index": index}
		workload_complexity: Dict[str, Any] = {}
		self._log_book_header(index, profile)
		start = time.time()
		story_meta: Optional[Dict[str, object]] = None
		try:
			try:
				story_meta = self._run_pipeline_stages(
					index,
					profile,
					trace_id,
					book_context,
					result,
					workload_summary,
					workload_complexity,
					start,
				)
			except _PipelineEarlyExit:
				return result
			return result
		finally:
			if torch.cuda.is_available():
				result["peak_vram_mb"] = torch.cuda.max_memory_allocated() / (1024 * 1024)
			self.observability.strategy.record_reward(
				{
					"book_index": index,
					"duration_sec": result["duration_sec"],
					"errors": len(result["errors"]),
					"warnings": len(result["warnings"]),
					"success": result["success"],
					"trace_id": trace_id,
				}
			)
			if workload_complexity:
				self.observability.workload.record_input_complexity(trace_id, workload_complexity)
			workload_summary = update_workload_summary(workload_summary, result, story_meta)
			self.observability.workload.finalize_request(trace_id, workload_summary)
			self._active_requests = max(0, self._active_requests - 1)
			self._write_status_snapshot(
				current_stage="book_done",
				last_error=self._extract_error_summary(result),
			)

	def _init_observability(self, seed: int, output_dir: Optional[Path] = None) -> ObsSession:
		return init_observability(
			self.options,
			run_dir=output_dir or self.run_dir,
			seed=seed,
		)

	def _apply_observability_overrides(self, config: ObsConfig) -> None:
		"""相容包裝：observability override 邏輯已移出。"""
		from .chief_observability import apply_observability_overrides
		overrides = apply_observability_overrides(config)
		if overrides:
			self.logger.info("Observability overrides: %s", ", ".join(overrides))

	def _record_pipeline_baseline(self) -> None:
		"""記錄管線的基本配置資訊到可觀測性系統。"""
		record_pipeline_baseline(
			self.observability,
			self.options,
			total_books=self.total_books,
			seed=self.seed,
		)

	def _build_llm_complexity(self, profile: StoryProfile, story_meta: Dict[str, object]) -> Dict[str, Any]:
		"""計算 LLM 生成的複雜度指標。"""
		return build_llm_complexity(profile, story_meta)

	def _collect_image_prompt_stats(self, story_root: Path) -> Dict[str, Any]:
		"""收集圖像提示詞的統計資訊。"""
		return collect_image_prompt_stats(
			story_root,
			estimate_tokens=estimate_tokens,
			style_keywords=STYLE_KEYWORDS,
		)

	def _collect_translation_stats(self, outputs: Dict[str, List[Path]]) -> Dict[str, Any]:
		"""收集翻譯輸出的統計資訊。"""
		return collect_translation_stats(outputs, estimate_tokens=estimate_tokens)

	def _collect_tts_text_stats(self, story_root: Path) -> Dict[str, Any]:
		"""收集語音合成文本的統計資訊。"""
		return collect_tts_text_stats(
			story_root,
			voice_language=self._primary_voice_language(),
			page_start=self.voice_config.page_start,
			page_end=self.voice_config.page_end,
			punctuation_pattern=PUNCTUATION_PATTERN,
			estimate_tokens=estimate_tokens,
		)

	def _maybe_record_tts_clipping(self, trace_id: str, story_root: Path) -> None:
		"""檢測並記錄 TTS 音訊是否有裁切失真 (Clipping) 問題。
		
		Args:
			trace_id: 追蹤 ID
			story_root: 故事根目錄
		"""
		maybe_record_tts_clipping(
			self.observability,
			trace_id=trace_id,
			stats=self._detect_tts_clipping(story_root),
		)

	def _detect_tts_clipping(self, story_root: Path) -> Optional[Dict[str, Any]]:
		"""檢測音訊檔案的裁切狀況。"""
		return detect_tts_clipping(
			story_root,
			voice_language=self._primary_voice_language(),
			audio_dir_name=self.voice_config.audio_dir,
			audio_format=self.voice_config.format,
		)

	def _record_stage_outcome(
		self,
		trace_id: str,
		stage: str,
		start_time: float,
		status: str,
		error_type: Optional[str] = None,
		details: Optional[str] = None,
		degradation: Optional[Dict[str, Any]] = None,
	) -> None:
		record_stage_outcome(
			self.observability,
			trace_id=trace_id,
			stage=stage,
			start_time=start_time,
			status=status,
			error_type=error_type,
			details=details,
			degradation=degradation,
		)

	@staticmethod
	def _clip_details(details: Optional[str], limit: int = 400) -> Optional[str]:
		if not details:
			return details
		return details if len(details) <= limit else f"{details[:limit]}..."

	def _generate_observability_reports(self, jsonl_path: Optional[Path]) -> None:
		generate_observability_reports(
			jsonl_path,
			observability=self.observability,
			logger=self.logger,
		)

	def _build_story_profile(self) -> StoryProfile:
		"""透過 Knowledge Graph (KG) 產生故事題材與屬性配置。
		
		Returns:
			包含年齡層、類別、主題等資訊的 StoryProfile
		"""
		category = self.options.main_category or self.random.choice(tuple(CATEGORY_CHOICES))
		age = self.options.age_group or self.random.choice(tuple(AGE_CHOICES))
		return build_story_profile(
			language=self.options.story_language,
			age=age,
			category=category,
			subcategory=self.options.story_subcategory,
			theme=self.options.story_theme,
			rng=self.random,
		)

	def _create_story(self, profile: StoryProfile) -> tuple[Optional[Path], Optional[Dict[str, object]], List[Dict[str, Any]]]:
		"""呼叫 Story 模組產生主語言的文本，並回傳儲存路徑與 Metadata。
		
		在此版本中，為了徹底釋放 GPTQ/Transformers 佔用的 GPU VRAM，我們強制使用子行程 (Subprocess)
		來執行文本生成邏輯。
		"""
		ctx = mp.get_context("spawn")
		queue = ctx.Queue()
		seed = self.random.randint(1, 10**9)
		
		self.logger.info("Spawning story generation subprocess to guarantee VRAM release...")
		p = ctx.Process(
			target=_story_worker_process,
			args=(profile, self.options, seed, queue)
		)
		p.start()
		p.join()
		
		if p.exitcode != 0:
			self.logger.error("Story generation subprocess failed with exit code %s", p.exitcode)
			return None, None, []
			
		if not queue.empty():
			final_story_root, meta, step_history, err_trace = queue.get()
			if err_trace is not None:
				self.logger.error("Story generation subprocess raised exception:\n%s", err_trace)
				return None, None, []
			return final_story_root, meta, step_history
			
		self.logger.error("Story generation subprocess returned no result.")
		return None, None, []

	def _run_photo(self, story_root: Path) -> bool:
		"""觸發 Image 模組為指定故事產生插圖。
		
		Args:
			story_root: 故事根目錄
			
		Returns:
			成功返回 True，失敗返回 False
		"""
		return self._run_with_exception_logging(
			"Photo generation",
			story_root,
			lambda: generate_photos_for_story(
				story_root,
				self.photo_config,
				progress_label="圖像生成",
				console=False,
				kernel_recorder=self.observability.kernel,
			),
		)

	def _run_translation(self, story_root: Path) -> Optional[Dict[str, List[Path]]]:
		"""呼叫 Translation 模組將故事轉換成多國語言，並回傳輸出檔案列表。
		
		Args:
			story_root: 故事根目錄
			
		Returns:
			語言代碼到翻譯檔案路徑列表的映射，失敗返回 None
		"""
		base = self.translation_base
		config = replace(
			base,
			target_langs=self.options.languages or base.target_langs,
		)
		try:
			return translate_story(story_root, config, console=False)
		except Exception as exc:  # pragma: no cover
			self.logger.exception("Translation failed for %s: %s", story_root, exc)
			return None

	def _run_voice(self, story_root: Path) -> bool:
		"""呼叫 Voice 模組產出語音旁白。
		
		Args:
			story_root: 故事根目錄
			
		Returns:
			成功返回 True，失敗返回 False
		"""
		available_languages = set(detect_story_languages(story_root))
		target_languages = [lang for lang in self.voice_languages if lang in available_languages]
		if not target_languages and self.options.voice_language in available_languages:
			target_languages = [self.options.voice_language]

		if not target_languages:
			self._voice_languages_used = []
			self.logger.error(
				"Voice generation skipped: no narration language available. planned=%s available=%s story=%s",
				self.voice_languages,
				sorted(available_languages),
				story_root,
			)
			return False

		self._voice_languages_used = list(target_languages)
		all_ok = True
		for language in target_languages:
			voice_config = replace(self.voice_config, language=language)
			ok = self._run_with_exception_logging(
				f"Voice generation [{language}]",
				story_root,
				lambda cfg=voice_config: generate_narration_for_story(story_root, cfg, console=False),
			)
			all_ok = all_ok and ok
		return all_ok

	def _run_with_exception_logging(
		self,
		label: str,
		story_root: Path,
		action: Callable[[], bool],
	) -> bool:
		"""執行動作並記錄例外狀況。
		
		Args:
			label: 動作標籤
			story_root: 故事根目錄
			action: 要執行的動作
			
		Returns:
			動作執行結果
		"""
		try:
			return action()
		except Exception as exc:  # pragma: no cover
			self.logger.exception("%s failed for %s: %s", label, story_root, exc)
			return False

	def _verify_story(
		self,
		story_root: Path,
		expect_translation: bool,
		expect_voice: bool,
		expect_photo: bool,
	) -> bool:
		"""嚴格檢查產出物是否齊全。"""
		return verify_story(
			story_root,
			story_language=self.options.story_language,
			voice_languages=self._voice_languages_used or self.voice_languages,
			audio_dir_name=self.voice_config.audio_dir,
			audio_format=self.voice_config.format,
			target_languages=self.options.languages,
			expect_translation=expect_translation,
			expect_voice=expect_voice,
			expect_photo=expect_photo,
			logger=self.logger,
		)

	def _log_book_header(self, index: int, profile: StoryProfile) -> None:
		prefix = book_prefix(index, self.total_books, profile)
		self.logger.info("%s | Theme %s", prefix, profile.theme_label)

	def _log_stage(self, index: int, profile: StoryProfile, stage: str, status: str) -> None:
		prefix = book_prefix(index, self.total_books, profile)
		self.logger.info("%s | Stage %s -> %s", prefix, stage, status.upper())
		self._write_status_snapshot(
			current_book=index,
			current_stage=f"{stage}:{status.lower()}",
		)

	def _log_batch_progress(self, completed: int, results: List[Dict[str, object]]) -> None:
		summary = summarize_batch_results(results)
		self.logger.info(
			"Progress %s/%s | Success: %s | Fail: %s",
			completed,
			self.total_books,
			summary["success"],
			summary["fail"],
		)
		self._write_status_snapshot(
			completed_books=completed,
			success_books=summary["success"],
			failed_books=summary["fail"],
		)


def main(options: Optional[ChiefOptions] = None) -> None:
	"""相容入口：將 CLI/entry 委派到 `pipeline.entry`。"""

	from .entry import main as entry_main

	entry_main(options)


if __name__ == "__main__":
	main()
