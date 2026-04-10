"""商用評分治理工具。

在不依賴外部標註資料與人類評分校準的前提下，
對每次評分結果補上可營運的治理資訊：
- 信心分數（confidence）
- 風險旗標（risk flags）
- 覆核建議（review recommendation）
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


EXPECTED_DIMENSIONS = (
    "readability",
    "emotional_impact",
    "coherence",
    "entity_consistency",
    "completeness",
    "factuality",
    "multimodal_alignment",
)

DEFAULT_CONFIG: Dict[str, Any] = {
    "thresholds": {
        "coverage_ratio_warn": 0.84,
        "coverage_ratio_confidence_floor": 0.85,
        "calibration_shift_warn": 6.0,
        "calibration_shift_high": 10.0,
        "overall_structure_overall_threshold": 82.0,
        "overall_structure_coherence_min": 58.0,
        "overall_structure_completeness_min": 55.0,
        "entity_consistency_low": 52.0,
        "emotional_gap_high": 92.0,
        "emotional_gap_coherence_min": 60.0,
        "slow_processing_seconds": 240.0,
    },
    "confidence": {
        "start": 1.0,
        "failed_dim_penalty": 0.18,
        "degraded_dim_penalty": 0.08,
        "coverage_penalty": 0.25,
        "calibration_shift_penalty": 0.02,
        "calibration_shift_free_range": 3.0,
        "slow_processing_penalty": 0.04,
        "severity_penalty": {
            "critical": 0.18,
            "high": 0.10,
            "medium": 0.05,
            "low": 0.02,
        },
        "clamp_min": 0.05,
        "clamp_max": 0.98,
    },
    "risk": {
        "medium_confidence_threshold": 0.70,
        "manual_review_confidence_threshold": 0.62,
        "spot_check_confidence_threshold": 0.78,
    },
}


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _flag(severity: str, code: str, message: str) -> Dict[str, str]:
    return {"severity": severity, "code": code, "message": message}


def _merge_config(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged: Dict[str, Any] = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_config(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def _load_governance_config() -> Dict[str, Any]:
    config_path = os.environ.get("GOVERNANCE_CONFIG_PATH")
    if config_path:
        path = Path(config_path)
    else:
        path = Path(__file__).resolve().parents[1] / "config" / "governance.yaml"

    if yaml is None or (not path.exists()):
        return DEFAULT_CONFIG

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            return DEFAULT_CONFIG
        return _merge_config(DEFAULT_CONFIG, loaded)
    except Exception:
        return DEFAULT_CONFIG


def build_score_governance(
    *,
    overall_score: float,
    raw_score: float,
    calibrated_score: float,
    dimension_scores: Dict[str, float],
    dimension_results: Iterable[Any],
    processing_summary: Optional[Dict[str, Any]] = None,
    degradation_report: Optional[Dict[str, Any]] = None,
    alignment_details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """建立分數治理資訊。"""
    config = _load_governance_config()
    thresholds = config.get("thresholds", {})
    confidence_cfg = config.get("confidence", {})
    risk_cfg = config.get("risk", {})

    processing_summary = processing_summary or {}
    degradation_report = degradation_report or {}
    alignment_details = alignment_details or {}

    flags: List[Dict[str, str]] = []

    expected_total = len(EXPECTED_DIMENSIONS)
    present_total = len([d for d in EXPECTED_DIMENSIONS if d in dimension_scores])
    coverage_ratio = (present_total / expected_total) if expected_total else 0.0

    failed_count = 0
    degraded_count = 0
    success_count = 0
    for result in dimension_results:
        status = getattr(result, "status", "unknown")
        if status == "failed":
            failed_count += 1
        elif status == "degraded":
            degraded_count += 1
        elif status == "success":
            success_count += 1

    if failed_count > 0:
        flags.append(_flag("critical", "dimension_failed", f"{failed_count} 個維度評估失敗"))
    if degraded_count > 0:
        flags.append(_flag("high", "dimension_degraded", f"{degraded_count} 個維度使用降級流程"))
    if coverage_ratio < _safe_float(thresholds.get("coverage_ratio_warn"), 0.84):
        flags.append(_flag("high", "low_coverage", f"維度覆蓋率偏低：{coverage_ratio:.0%}"))

    # 校準偏移幅度檢查（即使已停用校準，仍作為一致性風險監測）
    calibration_shift = abs(calibrated_score - raw_score)
    if calibration_shift >= _safe_float(thresholds.get("calibration_shift_high"), 10.0):
        flags.append(_flag("high", "large_alignment_shift", f"raw/calibrated 差距過大：{calibration_shift:.1f}"))
    elif calibration_shift >= _safe_float(thresholds.get("calibration_shift_warn"), 6.0):
        flags.append(_flag("medium", "alignment_shift", f"raw/calibrated 差距偏大：{calibration_shift:.1f}"))

    # 分數結構合理性
    coherence = _safe_float(dimension_scores.get("coherence"), -1.0)
    completeness = _safe_float(dimension_scores.get("completeness"), -1.0)
    entity_consistency = _safe_float(dimension_scores.get("entity_consistency"), -1.0)
    emotional = _safe_float(dimension_scores.get("emotional_impact"), -1.0)
    multimodal = _safe_float(dimension_scores.get("multimodal_alignment"), -1.0)

    if (
        coherence >= 0
        and completeness >= 0
        and overall_score >= _safe_float(thresholds.get("overall_structure_overall_threshold"), 82.0)
        and (
            coherence < _safe_float(thresholds.get("overall_structure_coherence_min"), 58.0)
            or completeness < _safe_float(thresholds.get("overall_structure_completeness_min"), 55.0)
        )
    ):
        flags.append(_flag("high", "high_overall_low_structure", "總分偏高但連貫性/完整性偏低"))
    if entity_consistency >= 0 and entity_consistency < _safe_float(thresholds.get("entity_consistency_low"), 52.0):
        flags.append(_flag("medium", "entity_consistency_low", "實體一致性偏低，建議人工覆核角色設定"))
    if (
        emotional >= 0
        and emotional > _safe_float(thresholds.get("emotional_gap_high"), 92.0)
        and coherence >= 0
        and coherence < _safe_float(thresholds.get("emotional_gap_coherence_min"), 60.0)
    ):
        flags.append(_flag("medium", "emotion_structure_gap", "情感分過高但結構分偏低，可能存在偏置"))
    if multimodal >= 0 and multimodal < 58.0:
        flags.append(_flag("medium", "multimodal_alignment_low", "圖片品質或圖文對位偏弱，建議人工覆核圖片輸出"))

    # 退化報告
    if degradation_report:
        flags.append(_flag("medium", "degradation_present", "偵測到來源或模型降級路徑"))

    # 置信度分數（0~1）
    confidence = _safe_float(confidence_cfg.get("start"), 1.0)
    confidence -= _safe_float(confidence_cfg.get("failed_dim_penalty"), 0.18) * failed_count
    confidence -= _safe_float(confidence_cfg.get("degraded_dim_penalty"), 0.08) * degraded_count
    confidence -= _safe_float(confidence_cfg.get("coverage_penalty"), 0.25) * max(
        0.0,
        _safe_float(thresholds.get("coverage_ratio_confidence_floor"), 0.85) - coverage_ratio,
    )
    confidence -= _safe_float(confidence_cfg.get("calibration_shift_penalty"), 0.02) * max(
        0.0,
        calibration_shift - _safe_float(confidence_cfg.get("calibration_shift_free_range"), 3.0),
    )

    total_processing_time = _safe_float(processing_summary.get("total_processing_time"), 0.0)
    if total_processing_time > _safe_float(thresholds.get("slow_processing_seconds"), 240.0):
        confidence -= _safe_float(confidence_cfg.get("slow_processing_penalty"), 0.04)

    sev_penalty = confidence_cfg.get("severity_penalty", {})
    for item in flags:
        confidence -= _safe_float(sev_penalty.get(item.get("severity", "low"), 0.02), 0.02)

    confidence = _clamp(
        confidence,
        _safe_float(confidence_cfg.get("clamp_min"), 0.05),
        _safe_float(confidence_cfg.get("clamp_max"), 0.98),
    )
    confidence_score = round(confidence * 100.0, 1)

    critical_count = sum(1 for item in flags if item["severity"] == "critical")
    high_count = sum(1 for item in flags if item["severity"] == "high")

    if critical_count > 0:
        risk_level = "critical"
    elif high_count >= 2:
        risk_level = "high"
    elif high_count == 1 or confidence < _safe_float(risk_cfg.get("medium_confidence_threshold"), 0.70):
        risk_level = "medium"
    else:
        risk_level = "low"

    if risk_level in ("critical", "high") or confidence < _safe_float(
        risk_cfg.get("manual_review_confidence_threshold"),
        0.62,
    ):
        review_recommendation = "manual_review_required"
    elif risk_level == "medium" or confidence < _safe_float(
        risk_cfg.get("spot_check_confidence_threshold"),
        0.78,
    ):
        review_recommendation = "spot_check_recommended"
    else:
        review_recommendation = "auto_accept_recommended"

    return {
        "confidence": round(confidence, 4),
        "confidence_score": confidence_score,
        "risk_level": risk_level,
        "review_recommendation": review_recommendation,
        "risk_flags": flags,
        "audit": {
            "coverage_ratio": round(coverage_ratio, 4),
            "expected_dimensions": expected_total,
            "present_dimensions": present_total,
            "success_count": success_count,
            "degraded_count": degraded_count,
            "failed_count": failed_count,
            "calibration_shift": round(calibration_shift, 3),
            "total_processing_time": round(total_processing_time, 3),
            "alignment_mode": alignment_details.get("mode"),
        },
    }
