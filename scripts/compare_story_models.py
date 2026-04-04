from __future__ import annotations

import json
import re
import sys
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline import ChiefRunner, DEFAULT_CHIEF_OPTIONS
from utils import cleanup_torch, force_cleanup_models


@dataclass
class ModelSpec:
    key: str
    label: str
    model_path: Path
    model_name: str
    quantization: Optional[str]


def _extract_page_number(path: Path) -> int:
    match = re.search(r"page_(\d+)\.txt$", path.name)
    if not match:
        return 10**9
    return int(match.group(1))


def _read_json_if_exists(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _find_primary_branch(story_root: Path, language: str = "en") -> Optional[Path]:
    branches_dir = story_root / language / "branches"
    if not branches_dir.exists():
        return None
    options = sorted([p for p in branches_dir.iterdir() if p.is_dir() and p.name.startswith("option_")])
    if not options:
        return None
    for candidate in options:
        if candidate.name == "option_1":
            return candidate
    return options[0]


def _load_story_text(story_root: Path, language: str = "en") -> Tuple[str, str]:
    branch_dir = _find_primary_branch(story_root, language)
    if not branch_dir:
        return "", "<missing-branch>"

    candidates = [
        branch_dir / "full_story.txt",
        branch_dir / "draft_story.txt",
        branch_dir / "story.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8", errors="replace"), str(candidate)

    pages = sorted(branch_dir.glob("page_*.txt"), key=_extract_page_number)
    if pages:
        chunks: List[str] = []
        for page in pages:
            chunks.append(page.read_text(encoding="utf-8", errors="replace").strip())
        return "\n\n".join(chunks).strip(), f"{branch_dir}/page_*.txt(stitched)"

    recursive = sorted((story_root / language).rglob("full_story.txt"))
    if recursive:
        path = recursive[0]
        return path.read_text(encoding="utf-8", errors="replace"), str(path)

    return "", "<missing-story-text>"


def _find_story_meta(story_root: Path, language: str = "en") -> Optional[Path]:
    candidates = [
        story_root / "resource" / "story_meta.json",
        story_root / "story_meta.json",
        story_root / language / "resource" / "story_meta.json",
        story_root / language / "branches" / "option_1" / "resource" / "story_meta.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    recursive = sorted((story_root / language).rglob("story_meta.json"))
    return recursive[0] if recursive else None


def _compute_text_metrics(text: str) -> Dict[str, Any]:
    normalized = re.sub(r"\s+", " ", text).strip()
    char_count = len(normalized)

    word_tokens = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", normalized.lower())
    word_count = len(word_tokens)

    cjk_chars = re.findall(r"[\u4e00-\u9fff]", normalized)
    cjk_count = len(cjk_chars)

    sentence_chunks = [
        chunk.strip()
        for chunk in re.split(r"(?<=[\.!?])\s+|\n+", text)
        if chunk.strip()
    ]
    sentence_count = len(sentence_chunks)

    if word_count > 0:
        sentence_lengths = [len(re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", s)) for s in sentence_chunks]
    else:
        sentence_lengths = [len(re.findall(r"[\u4e00-\u9fff]", s)) for s in sentence_chunks]

    avg_sentence_len = round(sum(sentence_lengths) / max(1, len(sentence_lengths)), 2)

    long_sentence_ratio = 0.0
    short_sentence_ratio = 0.0
    if sentence_lengths:
        long_sentence_ratio = round(sum(1 for n in sentence_lengths if n >= 32) / len(sentence_lengths), 4)
        short_sentence_ratio = round(sum(1 for n in sentence_lengths if n <= 3) / len(sentence_lengths), 4)

    lexical_diversity = 0.0
    trigram_repeat_ratio = 0.0
    if word_count >= 3:
        lexical_diversity = round(len(set(word_tokens)) / word_count, 4)
        trigrams = [tuple(word_tokens[i : i + 3]) for i in range(word_count - 2)]
        counts = Counter(trigrams)
        repeated = sum(v - 1 for v in counts.values() if v > 1)
        trigram_repeat_ratio = round(repeated / max(1, len(trigrams)), 4)

    leakage_patterns = [
        r"<think>",
        r"</think>",
        r"as an ai",
        r"language model",
        r"prompt",
        r"cannot comply",
    ]
    leakage_hits = 0
    for pattern in leakage_patterns:
        leakage_hits += len(re.findall(pattern, text, flags=re.IGNORECASE))

    # Simple heuristic score for side-by-side comparison only.
    score = 100.0
    if char_count < 2500:
        score -= min(25.0, (2500 - char_count) / 100.0)
    score -= min(30.0, trigram_repeat_ratio * 180.0)
    if lexical_diversity > 0 and lexical_diversity < 0.28:
        score -= min(20.0, (0.28 - lexical_diversity) * 100.0)
    score -= min(18.0, abs(avg_sentence_len - 14.0) * 0.8)
    score -= min(15.0, long_sentence_ratio * 30.0)
    score -= min(15.0, short_sentence_ratio * 30.0)
    score -= min(25.0, leakage_hits * 10.0)
    score = round(max(0.0, min(100.0, score)), 2)

    return {
        "char_count": char_count,
        "word_count": word_count,
        "cjk_char_count": cjk_count,
        "sentence_count": sentence_count,
        "avg_sentence_len": avg_sentence_len,
        "long_sentence_ratio": long_sentence_ratio,
        "short_sentence_ratio": short_sentence_ratio,
        "lexical_diversity": lexical_diversity,
        "trigram_repeat_ratio": trigram_repeat_ratio,
        "leakage_hits": leakage_hits,
        "heuristic_quality_score": score,
    }


def _build_common_options(output_root: Path) -> Any:
    return replace(
        DEFAULT_CHIEF_OPTIONS,
        mode="single",
        count=1,
        age_group="6-8",
        main_category="educational",
        seed=20260319,
        story_language="en",
        story_device="auto",
        story_dtype="float16",
        story_pages_expected=0,
        photo_enabled=False,
        translation_enabled=False,
        voice_enabled=False,
        verify_enabled=True,
        low_vram=True,
        story_output_root=output_root,
    )


def _run_single_model(spec: ModelSpec, common_options: Any) -> Dict[str, Any]:
    options = replace(
        common_options,
        story_model=spec.model_path,
        story_model_name=spec.model_name,
        story_quantization=spec.quantization,
    )

    start = time.perf_counter()
    result: Dict[str, Any] = {
        "key": spec.key,
        "label": spec.label,
        "model_path": str(spec.model_path),
        "quantization": spec.quantization,
        "success": False,
        "duration_sec": None,
        "story_root": None,
        "text_source": None,
        "metrics": {},
        "errors": [],
        "warnings": [],
        "summary": {},
    }

    try:
        runner = ChiefRunner(options)
        summary = runner.run()
        result["summary"] = summary

        run_result = None
        if isinstance(summary, dict):
            runs = summary.get("results") or []
            if runs:
                run_result = runs[0]

        if run_result:
            result["success"] = bool(run_result.get("success"))
            result["errors"] = list(run_result.get("errors") or [])
            result["warnings"] = list(run_result.get("warnings") or [])
            story_root_value = run_result.get("story_root")
            if story_root_value:
                story_root = Path(story_root_value)
                result["story_root"] = str(story_root)
                text, source = _load_story_text(story_root, language=options.story_language)
                result["text_source"] = source
                result["metrics"] = _compute_text_metrics(text)

                meta_path = _find_story_meta(story_root, language=options.story_language)
                if meta_path:
                    meta_data = _read_json_if_exists(meta_path)
                    if meta_data:
                        summary_meta = meta_data.get("summary") or {}
                        layout_meta = meta_data.get("layout") or {}
                        result["story_meta"] = {
                            "path": str(meta_path),
                            "pages_expected": summary_meta.get("pages_expected"),
                            "pages_actual": summary_meta.get("pages_actual"),
                            "branch_count": layout_meta.get("branch_count"),
                            "layout_id": layout_meta.get("layout_id"),
                        }
        else:
            result["errors"].append("missing_run_result")
    except Exception as exc:
        result["errors"].append(f"exception:{exc.__class__.__name__}")
        result["warnings"].append(str(exc))
    finally:
        result["duration_sec"] = round(time.perf_counter() - start, 2)
        cleanup_torch()
        force_cleanup_models()

    return result


def _choose_winner(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    for item in results:
        if not item.get("success"):
            scored.append((-1e9, item))
            continue

        metrics = item.get("metrics") or {}
        score = float(metrics.get("heuristic_quality_score") or 0.0)

        meta = item.get("story_meta") or {}
        pages_expected = meta.get("pages_expected")
        pages_actual = meta.get("pages_actual")
        if isinstance(pages_expected, int) and isinstance(pages_actual, int) and pages_expected > 0:
            ratio = pages_actual / pages_expected
            if ratio < 0.9:
                score -= 6.0
            elif ratio > 1.2:
                score -= 2.0
            else:
                score += 2.0

        scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    winner_score, winner = scored[0]
    return {
        "winner_key": winner.get("key"),
        "winner_label": winner.get("label"),
        "winner_score": round(winner_score, 2),
        "ranked": [
            {
                "key": item.get("key"),
                "label": item.get("label"),
                "score": round(score, 2),
                "success": item.get("success"),
            }
            for score, item in scored
        ],
    }


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = Path("output") / "model_compare"
    output_root.mkdir(parents=True, exist_ok=True)

    specs = [
        ModelSpec(
            key="gptq_qwen25_14b",
            label="Qwen2.5-14B GPTQ Int4",
            model_path=Path("models/Qwen2.5-14B-Instruct-GPTQ-Int4"),
            model_name="qwen2.5-14b-instruct-gptq-int4",
            quantization="gptq",
        ),
        ModelSpec(
            key="qwen35_9b_4bit",
            label="Qwen3.5-9B + bitsandbytes 4bit",
            model_path=Path("models/Qwen3.5-9B"),
            model_name="qwen3.5-9b",
            quantization="4bit",
        ),
    ]

    common_options = _build_common_options(output_root=output_root)

    all_results: List[Dict[str, Any]] = []
    for spec in specs:
        print(f"[RUN] {spec.label}")
        all_results.append(_run_single_model(spec, common_options))

    decision = _choose_winner(all_results)
    report = {
        "timestamp": timestamp,
        "comparison_mode": "single_book_same_seed_same_prompts_text_only",
        "seed": common_options.seed,
        "settings": {
            "age_group": common_options.age_group,
            "main_category": common_options.main_category,
            "story_language": common_options.story_language,
            "photo_enabled": common_options.photo_enabled,
            "translation_enabled": common_options.translation_enabled,
            "voice_enabled": common_options.voice_enabled,
        },
        "results": all_results,
        "decision": decision,
        "note": "Heuristic scoring is for relative comparison only; final choice should include human reading review.",
    }

    report_path = output_root / f"model_compare_report_{timestamp}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[DONE] report:", report_path)
    print(json.dumps(decision, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
