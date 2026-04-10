"""分數策略層：共識融合與跨維度硬約束。"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_POLICY: Dict[str, Any] = {
    "consensus": {
        "enabled": True,
        "alpha": 0.25,
        "max_pull": 6.0,
        "trimmed_mean_ratio": 0.2,
    },
    "constraints": {
        "enabled": True,
        "hard_caps": [
            {
                "name": "low_structure_cap",
                "if": {
                    "coherence_lt": 55.0,
                    "completeness_lt": 52.0,
                },
                "cap": 74.0,
            },
            {
                "name": "very_low_entity_cap",
                "if": {
                    "entity_consistency_lt": 45.0,
                },
                "cap": 76.0,
            },
            {
                "name": "low_readability_cap",
                "if": {
                    "readability_lt": 58.0,
                },
                "cap": 78.0,
            },
            {
                "name": "low_completeness_cap",
                "if": {
                    "completeness_lt": 48.0,
                },
                "cap": 75.0,
            },
            {
                "name": "emotion_dominance_cap",
                "if": {
                    "emotional_impact_gt": 90.0,
                    "coherence_lt": 58.0,
                },
                "cap": 80.0,
            },
            {
                "name": "low_multimodal_cap",
                "if": {
                    "multimodal_alignment_lt": 52.0,
                },
                "cap": 82.0,
            },
        ],
    },
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def get_score_policy_config() -> Dict[str, Any]:
    env_path = os.environ.get("SCORE_POLICY_CONFIG_PATH")
    if env_path:
        path = Path(env_path)
    else:
        path = Path(__file__).resolve().parents[1] / "config" / "score_policy.yaml"

    if yaml is None or not path.exists():
        return DEFAULT_POLICY

    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            return DEFAULT_POLICY
        return _merge(DEFAULT_POLICY, loaded)
    except Exception:
        return DEFAULT_POLICY


def _condition_match(condition: Dict[str, Any], scores: Dict[str, float]) -> bool:
    for key, threshold in condition.items():
        if key.endswith("_lt"):
            dim = key[:-3]
            if _safe_float(scores.get(dim), 1e9) >= _safe_float(threshold):
                return False
        elif key.endswith("_gt"):
            dim = key[:-3]
            if _safe_float(scores.get(dim), -1e9) <= _safe_float(threshold):
                return False
        else:
            return False
    return True


def _condition_dimensions(condition: Dict[str, Any]) -> List[str]:
    dims: List[str] = []
    for key in condition.keys():
        if key.endswith("_lt") or key.endswith("_gt"):
            dims.append(key[:-3])
    return dims


def _normalize_confidence_map(confidence_map: Optional[Dict[str, float]], scores: Dict[str, float]) -> Dict[str, float]:
    normalized: Dict[str, float] = {}
    confidence_map = confidence_map or {}
    for dim in scores.keys():
        raw = _safe_float(confidence_map.get(dim), 0.6)
        if raw > 1.0:
            raw = raw / 100.0
        normalized[dim] = _clamp(raw, 0.0, 1.0)
    return normalized


def apply_cross_dimension_constraints(
    score: float,
    scores: Dict[str, float],
    *,
    confidence_map: Optional[Dict[str, float]] = None,
    degraded_dimensions: Optional[List[str]] = None,
) -> Tuple[float, Dict[str, Any]]:
    config = get_score_policy_config()
    constraints = config.get("constraints", {})
    confidence = _normalize_confidence_map(confidence_map, scores)
    degraded = set(degraded_dimensions or [])

    if not bool(constraints.get("enabled", True)):
        return score, {"enabled": False, "applied_rules": []}

    applied_rules = []
    adjusted = float(score)

    for rule in constraints.get("hard_caps", []):
        condition = rule.get("if")
        cap = _safe_float(rule.get("cap"), 100.0)
        if not isinstance(condition, dict):
            continue
        if _condition_match(condition, scores):
            trigger_dims = _condition_dimensions(condition)
            trigger_conf_values = [confidence.get(dim, 0.6) for dim in trigger_dims if dim in confidence]
            trigger_conf = sum(trigger_conf_values) / len(trigger_conf_values) if trigger_conf_values else 0.6
            has_degraded_trigger = any(dim in degraded for dim in trigger_dims)

            effective_cap = cap
            # 低信心觸發時，放寬硬上限，降低誤殺率。
            if trigger_conf < 0.45:
                effective_cap += 2.0
            # 高信心觸發時，收緊硬上限，抑制明顯失衡輸出。
            elif trigger_conf > 0.75:
                effective_cap -= 2.0
            # 若觸發維度本身降級，維持保守，避免高分誤放行。
            if has_degraded_trigger:
                effective_cap -= 2.0

            effective_cap = _clamp(effective_cap, 50.0, 100.0)
            before = adjusted
            adjusted = min(adjusted, effective_cap)
            if adjusted < before:
                applied_rules.append(
                    {
                        "name": rule.get("name", "unnamed_rule"),
                        "type": "cap",
                        "cap": cap,
                        "effective_cap": round(effective_cap, 3),
                        "trigger_confidence": round(trigger_conf, 3),
                        "trigger_degraded": has_degraded_trigger,
                        "before": round(before, 3),
                        "after": round(adjusted, 3),
                    }
                )

    return adjusted, {
        "enabled": True,
        "applied_rules": applied_rules,
    }


def compute_consensus_adjustment(
    score: float,
    scores: Dict[str, float],
    *,
    confidence_map: Optional[Dict[str, float]] = None,
    degraded_dimensions: Optional[List[str]] = None,
) -> Tuple[float, Dict[str, Any]]:
    config = get_score_policy_config()
    consensus = config.get("consensus", {})
    confidence = _normalize_confidence_map(confidence_map, scores)
    degraded = set(degraded_dimensions or [])

    if not bool(consensus.get("enabled", True)):
        return score, {"enabled": False}

    values = [float(v) for v in scores.values() if isinstance(v, (int, float))]
    if not values:
        return score, {"enabled": True, "reason": "no_dimension_values"}

    values_sorted = sorted(values)
    n = len(values_sorted)
    trim_ratio = _safe_float(consensus.get("trimmed_mean_ratio"), 0.2)
    trim_n = int(n * trim_ratio)
    if n > 2 and trim_n > 0 and (n - 2 * trim_n) > 0:
        trimmed = values_sorted[trim_n : n - trim_n]
    else:
        trimmed = values_sorted

    trimmed_mean = sum(trimmed) / len(trimmed)
    med = float(median(values_sorted))
    weighted_numer = 0.0
    weighted_denom = 0.0
    for dim, val in scores.items():
        if not isinstance(val, (int, float)):
            continue
        w = max(0.2, confidence.get(dim, 0.6))
        weighted_numer += float(val) * w
        weighted_denom += w
    weighted_mean = (weighted_numer / weighted_denom) if weighted_denom > 0 else trimmed_mean

    consensus_center = (trimmed_mean * 0.5) + (med * 0.3) + (weighted_mean * 0.2)

    alpha = _safe_float(consensus.get("alpha"), 0.25)
    max_pull = _safe_float(consensus.get("max_pull"), 6.0)

    avg_conf = sum(confidence.values()) / max(1, len(confidence))
    degraded_ratio = len([d for d in scores.keys() if d in degraded]) / max(1, len(scores))

    effective_alpha = alpha * (0.75 + 0.5 * avg_conf)
    effective_alpha = _clamp(effective_alpha, 0.05, 0.6)

    effective_max_pull = max_pull * (0.7 + 0.6 * avg_conf)
    effective_max_pull *= (1.0 - 0.4 * degraded_ratio)
    effective_max_pull = _clamp(effective_max_pull, 2.0, max_pull)

    raw_new = float(score) * (1.0 - effective_alpha) + consensus_center * effective_alpha
    pull = _clamp(raw_new - float(score), -effective_max_pull, effective_max_pull)
    adjusted = float(score) + pull

    return adjusted, {
        "enabled": True,
        "median": round(med, 3),
        "trimmed_mean": round(trimmed_mean, 3),
        "weighted_mean": round(weighted_mean, 3),
        "consensus_center": round(consensus_center, 3),
        "alpha": round(effective_alpha, 4),
        "max_pull": round(effective_max_pull, 4),
        "base_alpha": alpha,
        "base_max_pull": max_pull,
        "avg_confidence": round(avg_conf, 3),
        "degraded_ratio": round(degraded_ratio, 3),
        "pull": round(pull, 3),
        "before": round(float(score), 3),
        "after": round(adjusted, 3),
    }
