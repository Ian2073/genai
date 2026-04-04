"""評分欄位工具。

集中處理 assessment report 中 raw/calibrated/legacy 欄位的解析，
避免不同腳本各自維護欄位優先順序。
"""

from __future__ import annotations

from typing import Any, Dict, Optional


def extract_raw_score(report: Dict[str, Any]) -> Optional[float]:
    """提取未對齊（Raw）總分。"""
    if not isinstance(report, dict):
        return None
    try:
        value = (report.get("score") or {}).get("base", report.get("overall_score_raw"))
        if isinstance(value, (int, float)):
            return float(value)
        for key in ["original_overall_score", "overall_score_before_alignment", "base_overall_score"]:
            fallback = report.get(key)
            if isinstance(fallback, (int, float)):
                return float(fallback)
    except Exception:
        return None
    return None


def extract_calibrated_score(report: Dict[str, Any]) -> Optional[float]:
    """提取對齊後（Calibrated）總分。"""
    if not isinstance(report, dict):
        return None
    try:
        value = (report.get("score") or {}).get("aligned", report.get("overall_score_calibrated"))
        if isinstance(value, (int, float)):
            return float(value)
        legacy = report.get("overall_score")
        if isinstance(legacy, (int, float)):
            return float(legacy)
    except Exception:
        return None
    return None


def normalize_score_fields(report: Dict[str, Any]) -> Dict[str, Any]:
    """補齊報告中的標準 score 區塊與相容頂層欄位。"""
    normalized = dict(report or {})
    raw = extract_raw_score(normalized)
    calibrated = extract_calibrated_score(normalized)

    if raw is not None:
        normalized["overall_score_raw"] = float(raw)
    if calibrated is not None:
        normalized["overall_score_calibrated"] = float(calibrated)
        normalized["overall_score"] = float(calibrated)

    score_block = dict(normalized.get("score") or {})
    if raw is not None:
        score_block["base"] = float(raw)
    if calibrated is not None:
        score_block["aligned"] = float(calibrated)
    if score_block:
        normalized["score"] = score_block

    return normalized
