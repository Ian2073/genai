"""ChiefRunner 的 observability 輔助工具。"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch

from observability import Config as ObsConfig, Session as ObsSession
from observability.reporting import from_jsonl


def init_observability(options, *, run_dir: Path, seed: int) -> ObsSession:
    """建立 observability session。"""

    config = ObsConfig(
        run_name="chief",
        output_dir=run_dir,
        nest_run_dir=False,
        enable_gpu_monitor=torch.cuda.is_available(),
        tags={
            "mode": options.mode,
            "story_language": options.story_language,
            "photo_enabled": str(options.photo_enabled),
            "translation_enabled": str(options.translation_enabled),
            "voice_enabled": str(options.voice_enabled),
        },
    )
    apply_observability_overrides(config)
    run_metadata = {
        "seed": seed,
        "mode": options.mode,
        "story_model": str(options.story_model),
        "story_device": options.story_device,
        "story_dtype": options.story_dtype,
        "translation_model": str(options.translation_model),
        "translation_device": options.translation_device,
        "translation_dtype": options.translation_dtype,
        "voice_device": options.voice_device,
        "photo_device": options.photo_device,
        "photo_dtype": options.photo_dtype,
        "sdxl_base": str(options.sdxl_base),
        "sdxl_refiner": str(options.sdxl_refiner),
        "driver": torch.version.cuda if torch.cuda.is_available() else "cpu",
    }
    return ObsSession(config, run_metadata=run_metadata)


def apply_observability_overrides(config: ObsConfig) -> List[str]:
    """從環境變數讀取並應用 observability 配置覆寫。"""

    env = os.environ
    overrides: List[str] = []

    def _parse_float(value: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_int(value: Optional[str]) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _parse_bool(value: Optional[str]) -> Optional[bool]:
        if value is None:
            return None
        return value.strip().lower() in {"1", "true", "yes", "on"}

    channel_envs = {
        "OBS_KERNEL_SAMPLE": "kernel",
        "OBS_MEMORY_SAMPLE": "memory",
        "OBS_WORKLOAD_SAMPLE": "workload",
        "OBS_INFRA_SAMPLE": "infra",
    }
    for key, channel in channel_envs.items():
        value = _parse_float(env.get(key))
        if value is None:
            continue
        clamped = max(0.0, min(1.0, value))
        config.sampling_rates[channel] = clamped
        overrides.append(f"{channel}_sample={clamped}")

    bools = {
        "OBS_CAPTURE_ALLOC": "capture_torch_allocator",
        "OBS_ENABLE_KERNEL": "enable_kernel",
        "OBS_ENABLE_MEMORY": "enable_memory",
        "OBS_ENABLE_INFRA": "enable_infra",
    }
    for key, attr in bools.items():
        value = _parse_bool(env.get(key))
        if value is None:
            continue
        setattr(config, attr, value)
        overrides.append(f"{attr}={value}")

    event_limit = _parse_int(env.get("OBS_KERNEL_EVENT_LIMIT"))
    if event_limit is not None and event_limit > 0:
        config.kernel_profile_event_limit = event_limit
        overrides.append(f"kernel_event_limit={event_limit}")
    return overrides


def record_pipeline_baseline(observability: ObsSession, options, *, total_books: int, seed: int) -> None:
    """記錄管線的基本配置資訊到 observability 系統。"""

    state = {
        "batch_size": 1 if options.mode == "single" else options.count,
        "micro_batch_size": options.story_pages_expected,
        "queue_depth": total_books,
        "precision": {
            "story": options.story_dtype,
            "photo": options.photo_dtype,
            "translation": options.translation_dtype,
        },
        "devices": {
            "story": options.story_device,
            "photo": options.photo_device,
            "translation": options.translation_device,
            "voice": options.voice_device,
        },
        "streams": torch.cuda.device_count() if torch.cuda.is_available() else 0,
        "mode": options.mode,
        "pages_expected": options.story_pages_expected,
        "photo_steps": options.photo_steps,
        "photo_refiner_steps": options.photo_refiner_steps,
        "voice_enabled": options.voice_enabled,
        "photo_enabled": options.photo_enabled,
        "translation_enabled": options.translation_enabled,
        "seed": seed,
    }
    observability.pipeline.record_pipeline_state(state)


def clip_details(details: Optional[str], limit: int = 400) -> Optional[str]:
    """裁切過長的錯誤細節。"""

    if not details:
        return details
    return details if len(details) <= limit else f"{details[:limit]}..."


def record_stage_outcome(
    observability: ObsSession,
    *,
    trace_id: str,
    stage: str,
    start_time: float,
    status: str,
    error_type: Optional[str] = None,
    details: Optional[str] = None,
    degradation: Optional[Dict[str, Any]] = None,
) -> None:
    """記錄 stage outcome。"""

    duration = max(0.0, time.perf_counter() - start_time)
    observability.reliability.record_stage_outcome(
        trace_id=trace_id,
        stage=stage,
        status=status,
        duration_sec=round(duration, 6),
        error_type=error_type,
        details=clip_details(details) if details else None,
        degradation=degradation,
    )


def maybe_record_tts_clipping(observability: ObsSession, *, trace_id: str, stats: Optional[Dict[str, Any]]) -> None:
    """依音訊裁切統計決定是否記錄 anomaly。"""

    if not stats:
        return
    max_amp = stats.get("max_amplitude")
    if max_amp is None:
        return
    if max_amp >= 0.98:
        observability.reliability.record_numeric_anomaly(
            trace_id,
            "TTS",
            indicator="audio_clipping",
            value=max_amp,
            threshold=0.98,
        )


def generate_observability_reports(
    jsonl_path: Optional[Path],
    *,
    observability: Optional[ObsSession],
    logger,
) -> None:
    """輸出 observability reports。"""

    if not jsonl_path:
        return
    try:
        config = observability.config if observability else None
        formats = config.auto_report_formats if config else ("parquet", "sqlite", "excel")
        jsonl_path = Path(jsonl_path)
        if not jsonl_path.exists():
            return
        output_dir = jsonl_path.parent
        outputs = {
            jsonl_path.stem: from_jsonl(
                jsonl_path,
                output_dir=output_dir,
                formats=formats,
            )
        }
        if not outputs.get(jsonl_path.stem):
            return
        logger.info(
            "Observability reports exported: %s",
            {k: {fmt: str(path) for fmt, path in files.items()} for k, files in outputs.items()},
        )
    except Exception as exc:
        logger.warning("Failed to export observability reports: %s", exc)
