#!/usr/bin/env python3
"""營運監控摘要產生器。

從 output 內的 assessment_report.json 聚合出商用監控指標，
可作為日常巡檢與告警前置資料。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any, Dict, List
from pathlib import Path

from ..shared.story_data import load_story_records
from ..shared.stats_utils import mean, median


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def build_ops_dashboard(roots: List[str]) -> Dict[str, Any]:
    records = load_story_records(roots, require_report=True)

    overall_scores = []
    latencies = []
    confidence_values = []

    risk_counter = Counter()
    review_counter = Counter()
    flag_counter = Counter()

    for record in records:
        report = record.get("report") or {}
        overall = report.get("overall_score")
        if isinstance(overall, (int, float)):
            overall_scores.append(float(overall))

        processing_summary = report.get("processing_summary") or {}
        latency = processing_summary.get("total_processing_time")
        if isinstance(latency, (int, float)):
            latencies.append(float(latency))

        governance = report.get("governance") or {}
        if isinstance(governance, dict) and governance:
            risk_counter[str(governance.get("risk_level") or "unknown")] += 1
            review_counter[str(governance.get("review_recommendation") or "unknown")] += 1

            conf = governance.get("confidence")
            if isinstance(conf, (int, float)):
                confidence_values.append(float(conf))

            for flag in governance.get("risk_flags") or []:
                if not isinstance(flag, dict):
                    continue
                code = str(flag.get("code") or "unknown")
                flag_counter[code] += 1

    total = len(records)
    governance_coverage = sum(risk_counter.values()) / total if total else 0.0

    def _p(values: List[float], q: float) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        idx = int((len(ordered) - 1) * q)
        return ordered[idx]

    dashboard = {
        "meta": {
            "total_reports": total,
            "governance_coverage": round(governance_coverage, 4),
            "roots": roots,
        },
        "scores": {
            "mean": round(mean(overall_scores), 4) if overall_scores else None,
            "median": round(median(overall_scores), 4) if overall_scores else None,
            "min": round(min(overall_scores), 4) if overall_scores else None,
            "max": round(max(overall_scores), 4) if overall_scores else None,
        },
        "latency_seconds": {
            "mean": round(mean(latencies), 4) if latencies else None,
            "p50": round(_safe_float(_p(latencies, 0.50), 0.0), 4) if latencies else None,
            "p95": round(_safe_float(_p(latencies, 0.95), 0.0), 4) if latencies else None,
            "max": round(max(latencies), 4) if latencies else None,
        },
        "governance": {
            "confidence_mean": round(mean(confidence_values), 4) if confidence_values else None,
            "confidence_median": round(median(confidence_values), 4) if confidence_values else None,
            "risk_distribution": dict(sorted(risk_counter.items())),
            "review_distribution": dict(sorted(review_counter.items())),
            "top_risk_flags": dict(flag_counter.most_common(10)),
        },
    }

    return dashboard


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ops dashboard from assessment reports.")
    parser.add_argument(
        "--roots",
        nargs="+",
        default=["output"],
        help="Report roots to scan (default: output).",
    )
    parser.add_argument(
        "--output",
        default="reports/evaluation/ops_dashboard.json",
        help="Output dashboard JSON path.",
    )
    args = parser.parse_args()

    dashboard = build_ops_dashboard(args.roots)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    meta = dashboard.get("meta", {})
    print(
        f"ops dashboard generated: reports={meta.get('total_reports')} "
        f"coverage={meta.get('governance_coverage')} output={output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
