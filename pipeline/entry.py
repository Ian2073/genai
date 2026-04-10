"""Pipeline 的公開入口與 CLI 參數解析。"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Optional

from .options import DEFAULT_CHIEF_OPTIONS, ChiefOptions, build_arg_parser


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _summary_exit_code(summary: Any) -> int:
    if not isinstance(summary, dict):
        return 0
    total = _safe_int(summary.get("total"), 0)
    success = _safe_int(summary.get("success"), 0)
    if total <= 0:
        return 0
    return 0 if success >= total else 1


def resolve_options(options: Optional[ChiefOptions] = None) -> ChiefOptions:
    """由外部傳入 options 或 CLI 參數解析出最終設定。"""

    if options is not None:
        return options

    args = build_arg_parser().parse_args()
    return resolve_options_from_args(args)


def resolve_options_from_args(args: Any) -> ChiefOptions:
    """由已解析的 CLI args 轉成 ChiefOptions。"""

    count = max(1, args.count)
    mode = "batch" if count > 1 else "single"
    option_updates = {
        "count": count,
        "resume": getattr(args, 'resume', None),
        "mode": mode,
        "model_plan": getattr(args, "model_plan", "auto"),
        "age_group": args.age,
        "main_category": args.category,
        "story_input_mode": getattr(args, "story_input_mode", None) or DEFAULT_CHIEF_OPTIONS.story_input_mode,
        "story_theme": args.theme,
        "story_subcategory": args.subcategory,
        "story_pages_expected": args.pages,
        "seed": args.seed,
        "pre_eval_policy": getattr(args, "pre_eval_policy", "stop"),
        "pre_eval_profile": getattr(args, "pre_eval_profile", "balanced"),
        "pre_eval_threshold": getattr(args, "pre_eval_threshold", 65.0),
    }
    if args.story_prompt is not None:
        option_updates["story_user_prompt"] = str(args.story_prompt).strip()
    if args.story_materials is not None:
        option_updates["story_user_materials"] = str(args.story_materials).strip()
    if args.story_device is not None:
        option_updates["story_device"] = args.story_device
    if args.story_dtype is not None:
        option_updates["story_dtype"] = args.story_dtype
    if args.story_quantization is not None:
        option_updates["story_quantization"] = None if args.story_quantization == "none" else args.story_quantization
    if getattr(args, "outline_candidates", None) is not None:
        option_updates["story_outline_candidates"] = max(1, int(args.outline_candidates))
    if getattr(args, "title_candidates", None) is not None:
        option_updates["story_title_candidates"] = max(1, int(args.title_candidates))
    if getattr(args, "key_page_candidates", None) is not None:
        option_updates["story_key_page_candidates"] = max(1, int(args.key_page_candidates))
    if args.low_vram is not None:
        option_updates["low_vram"] = args.low_vram
    if args.max_retries is not None:
        option_updates["max_book_retries"] = max(0, int(args.max_retries))
    if args.status_file is not None:
        option_updates["status_json_path"] = args.status_file
    if getattr(args, "speaker_wav", None) is not None:
        option_updates["speaker_wav"] = args.speaker_wav
    if getattr(args, "speaker_dir", None) is not None:
        option_updates["speaker_dir"] = args.speaker_dir

    for field_name in (
        "photo_enabled",
        "translation_enabled",
        "voice_enabled",
        "verify_enabled",
        "strict_translation",
        "strict_voice",
    ):
        value = getattr(args, field_name, None)
        if value is not None:
            option_updates[field_name] = value
    return replace(DEFAULT_CHIEF_OPTIONS, **option_updates)


def main(options: Optional[ChiefOptions] = None) -> int:
    """系統主程式進入點。"""
    if options is None:
        args = build_arg_parser().parse_args()
        if getattr(args, "dashboard", False):
            from .dashboard import run_dashboard_server

            run_dashboard_server(
                host=args.dashboard_host,
                port=args.dashboard_port,
                auto_open=not args.dashboard_no_open,
            )
            return 0
        selected_options = resolve_options_from_args(args)
    else:
        selected_options = resolve_options(options)
    from .chief_runner import ChiefRunner

    runner = ChiefRunner(selected_options)
    summary = runner.run()
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return _summary_exit_code(summary)
