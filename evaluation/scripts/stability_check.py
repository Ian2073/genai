#!/usr/bin/env python3
"""無標註穩定性檢查腳本。

目標：在不依賴人類評分資料集的前提下，
透過可控擾動驗證評估器是否具備基本單調性與穩定性。
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from ..main import evaluate_all
except ImportError:
    from main import evaluate_all


@dataclass
class TestCase:
    name: str
    transform: Callable[[str], str]
    expectation: str
    dimension: str
    min_delta: float


def _split_paragraphs(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]


def _shuffle_middle_paragraphs(text: str) -> str:
    parts = _split_paragraphs(text)
    if len(parts) < 4:
        return text
    middle = parts[1:-1]
    random.seed(42)
    random.shuffle(middle)
    return "\n\n".join([parts[0]] + middle + [parts[-1]])


def _remove_last_quarter(text: str) -> str:
    words = text.split()
    if len(words) < 120:
        return text
    keep = int(len(words) * 0.75)
    return " ".join(words[:keep])


def _inject_typo_noise(text: str) -> str:
    tokens = text.split()
    if len(tokens) < 80:
        return text
    random.seed(17)
    indices = random.sample(range(len(tokens)), k=max(5, len(tokens) // 20))
    noisy = list(tokens)
    for idx in indices:
        token = noisy[idx]
        if len(token) > 4:
            noisy[idx] = token[:-1]
    return " ".join(noisy)


def _repeat_generic_filler(text: str) -> str:
    filler = "It was good and everyone was happy. "
    return text + "\n\n" + (filler * 20)


def _score(text: str, title: str) -> Dict:
    return evaluate_all(text, story_title=title)


def run_stability_suite(text: str, title: str) -> Dict:
    baseline = _score(text, title)

    tests = [
        TestCase(
            name="shuffle_middle_paragraphs",
            transform=_shuffle_middle_paragraphs,
            expectation="decrease",
            dimension="coherence",
            min_delta=3.0,
        ),
        TestCase(
            name="remove_last_quarter",
            transform=_remove_last_quarter,
            expectation="decrease",
            dimension="completeness",
            min_delta=3.0,
        ),
        TestCase(
            name="inject_typo_noise",
            transform=_inject_typo_noise,
            expectation="decrease",
            dimension="readability",
            min_delta=2.0,
        ),
        TestCase(
            name="repeat_generic_filler",
            transform=_repeat_generic_filler,
            expectation="decrease",
            dimension="overall_score",
            min_delta=1.5,
        ),
    ]

    baseline_dims = baseline.get("dimension_scores") or {}
    results = []
    passed = 0

    for case in tests:
        variant_text = case.transform(text)
        variant = _score(variant_text, f"{title}__{case.name}")
        variant_dims = variant.get("dimension_scores") or {}

        if case.dimension == "overall_score":
            base_value = float(baseline.get("overall_score", 0.0))
            new_value = float(variant.get("overall_score", 0.0))
        else:
            base_value = float(baseline_dims.get(case.dimension, 0.0))
            new_value = float(variant_dims.get(case.dimension, 0.0))

        delta = round(new_value - base_value, 3)
        if case.expectation == "decrease":
            ok = delta <= (-case.min_delta)
        else:
            ok = delta >= case.min_delta

        if ok:
            passed += 1

        results.append(
            {
                "case": case.name,
                "dimension": case.dimension,
                "expectation": case.expectation,
                "min_delta": case.min_delta,
                "baseline": round(base_value, 3),
                "variant": round(new_value, 3),
                "delta": delta,
                "passed": ok,
            }
        )

    ratio = passed / len(tests) if tests else 0.0
    if ratio >= 0.85:
        status = "good"
    elif ratio >= 0.6:
        status = "warning"
    else:
        status = "bad"

    return {
        "baseline": {
            "overall_score": baseline.get("overall_score"),
            "dimension_scores": baseline.get("dimension_scores"),
            "governance": baseline.get("governance"),
        },
        "stability_results": results,
        "summary": {
            "passed": passed,
            "total": len(tests),
            "pass_ratio": round(ratio, 3),
            "status": status,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run perturbation-based stability checks.")
    parser.add_argument("--input", required=True, help="Path to full story text file.")
    parser.add_argument("--title", default="stability_test_story", help="Story title.")
    parser.add_argument("--output", default="reports/evaluation/stability_check_report.json", help="Output JSON path.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_file():
        print(f"[error] missing input file: {input_path}")
        return 1

    text = input_path.read_text(encoding="utf-8")
    if len(text.strip()) < 200:
        print("[error] input text too short for stability checks")
        return 1

    report = run_stability_suite(text, args.title)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = report.get("summary", {})
    print(
        f"stability status={summary.get('status')} "
        f"pass={summary.get('passed')}/{summary.get('total')} "
        f"ratio={summary.get('pass_ratio')}"
    )
    print(f"report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
