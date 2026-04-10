"""Chief pipeline 的 request/runtime 組裝輔助。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from utils import StoryProfile

from .options import ChiefOptions


def build_book_context(index: int, profile: StoryProfile, trace_id: str) -> Dict[str, Any]:
	"""建立單本書執行期共用的上下文。"""

	return {
		"index": index,
		"language": profile.language,
		"category": profile.category_label,
		"subcategory": profile.subcategory_label,
		"age_group": profile.age_label,
		"theme": profile.theme_label,
		"trace_id": trace_id,
	}


def build_initial_result(index: int, profile: StoryProfile, trace_id: str) -> Dict[str, object]:
	"""建立單本書執行結果的初始骨架。"""

	return {
		"index": index,
		"config": profile.to_dict(),
		"story_root": None,
		"duration_sec": 0.0,
		"errors": [],
		"warnings": [],
		"success": False,
		"trace_id": trace_id,
	}


def describe_request_mode(options: ChiefOptions) -> str:
	"""描述當前請求啟用的模組組合。"""

	parts = ["story"]
	if options.photo_enabled:
		parts.append("image")
	if options.translation_enabled:
		parts.append("translation")
	if options.voice_enabled:
		parts.append("tts")
	if options.verify_enabled:
		parts.append("verify")
	return "+".join(parts)


def build_request_meta(
	*,
	trace_id: str,
	index: int,
	profile: StoryProfile,
	options: ChiefOptions,
	photo_config: Any,
	translation_target_langs: List[str],
	total_books: int,
	seed: int,
	concurrency_level: int,
) -> Dict[str, Any]:
	"""建立 workload/request metadata。"""

	return {
		"trace_id": trace_id,
		"request_index": index,
		"mode": describe_request_mode(options),
		"features": {
			"photo": options.photo_enabled,
			"translation": options.translation_enabled,
			"voice": options.voice_enabled,
			"verify": options.verify_enabled,
		},
		"llm": {
			"language": profile.language,
			"temperature": options.story_temperature,
			"top_p": options.story_top_p,
			"top_k": options.story_top_k,
			"max_tokens": options.story_max_tokens,
			"dtype": options.story_dtype,
			"device": options.story_device,
			"model_plan": getattr(options, "model_plan", "auto"),
		},
		"sdxl": {
			"width": photo_config.width,
			"height": photo_config.height,
			"steps": photo_config.steps,
			"guidance": photo_config.guidance,
			"refiner_steps": photo_config.refiner_steps or 0,
			"skip_refiner": photo_config.skip_refiner,
		},
		"translation": {
			"languages": list(translation_target_langs),
			"beam_size": options.translation_beam_size,
			"length_penalty": options.translation_length_penalty,
			"dtype": options.translation_dtype,
		},
		"tts": {
			"language": options.voice_language,
			"speaker": str(options.speaker_wav or options.speaker_dir or ""),
			"volume_gain": options.voice_volume_gain,
			"page_range": (options.voice_page_start, options.voice_page_end),
		},
		"run": {
			"seed": seed,
			"story_language": options.story_language,
			"expected_pages": options.story_pages_expected,
			"concurrency_level": concurrency_level,
			"total_requests": total_books,
		},
	}


def build_strategy_state(
	*,
	index: int,
	total_books: int,
	profile: StoryProfile,
	mode: str,
	trace_id: str,
	concurrency_level: int,
) -> Dict[str, Any]:
	"""建立 strategy recorder 所需的執行狀態。"""

	return {
		"book_index": index,
		"remaining_queue": max(0, total_books - index),
		"category": profile.category_label,
		"language": profile.language,
		"mode": mode,
		"trace_id": trace_id,
		"concurrency": concurrency_level,
	}


def update_workload_summary(
	workload_summary: Dict[str, Any],
	result: Dict[str, object],
	story_meta: Optional[Dict[str, object]],
) -> Dict[str, Any]:
	"""將執行結果回填到 workload summary。"""

	workload_summary["success"] = result["success"]
	workload_summary["duration_sec"] = result["duration_sec"]
	if story_meta:
		content_stats = story_meta.get("content_stats") or {}
		workload_summary["token_total"] = content_stats.get("story_tokens")
		workload_summary["pages_actual"] = story_meta.get("summary", {}).get("pages_actual")
	workload_summary["errors"] = len(result["errors"])
	workload_summary["warnings"] = len(result["warnings"])
	return workload_summary


def book_prefix(index: int, total_books: int, profile: StoryProfile) -> str:
	"""回傳單本書在 log 中的固定前綴。"""

	return (
		f"Book {index}/{total_books} | Age {profile.age_label} | "
		f"Category {profile.category_label}"
	)


def summarize_batch_results(results: List[Dict[str, object]]) -> Dict[str, int]:
	"""彙整批次執行成功/失敗數。"""

	success = sum(1 for result in results if result.get("success"))
	return {
		"total": len(results),
		"success": success,
		"fail": len(results) - success,
	}
