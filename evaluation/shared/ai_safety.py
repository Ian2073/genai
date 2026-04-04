from __future__ import annotations

import math
from typing import Any


DIMENSION_FALLBACK_SCORES = {
    "readability": 60.0,
    "emotional_impact": 55.0,
    "coherence": 55.0,
    "entity_consistency": 50.0,
    "completeness": 55.0,
    "factuality": 60.0,
}


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def normalize_score_0_100(value: Any, fallback: float) -> float:
    number = _to_float(value)
    if number is None:
        number = fallback
    return max(0.0, min(100.0, float(number)))


def normalize_confidence_0_1(value: Any, fallback: float = 0.6) -> float:
    number = _to_float(value)
    if number is None:
        number = fallback
    return max(0.0, min(1.0, float(number)))


def normalize_confidence_0_100(value: Any, fallback: float = 50.0) -> float:
    number = _to_float(value)
    if number is None:
        number = fallback
    return max(0.0, min(100.0, float(number)))


def get_dimension_fallback_score(dimension: str, default: float = 55.0) -> float:
    return float(DIMENSION_FALLBACK_SCORES.get(dimension, default))


def build_dimension_fallback_payload(dimension: str, reason: str, score: float) -> dict:
    safe_score = normalize_score_0_100(score, 55.0)
    return {
        "dimension": dimension,
        "score": safe_score,
        "status": "degraded",
        "error": reason,
        "recommendations": [f"{dimension} 使用降級評分：{reason}"],
    }
