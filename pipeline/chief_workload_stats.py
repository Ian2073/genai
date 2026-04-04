"""ChiefRunner 共用的統計與音訊檢測工具。"""

from __future__ import annotations

import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from runtime.story_files import (
    collect_narration_pages,
    filter_narration_pages,
    find_primary_audio_file,
    find_story_resource_dir,
)
from utils import list_character_prompt_files, list_page_prompt_files, load_prompt


def build_llm_complexity(profile: Any, story_meta: Dict[str, object]) -> Dict[str, Any]:
    """計算 LLM 生成的複雜度指標。"""

    stats = story_meta.get("content_stats") or {}
    summary = story_meta.get("summary") or {}
    return {
        "language": profile.language,
        "story_tokens": stats.get("story_tokens"),
        "outline_tokens": stats.get("outline_tokens"),
        "pages_actual": summary.get("pages_actual"),
        "narration_tokens": stats.get("narration_tokens"),
    }


def collect_image_prompt_stats(
    story_root: Path,
    *,
    estimate_tokens,
    style_keywords: Sequence[str],
) -> Dict[str, Any]:
    """收集圖像提示詞統計資訊。"""

    resources_dir = find_story_resource_dir(story_root)
    prompts: List[str] = []
    cover_path = resources_dir / "book_cover_prompt.txt"
    if cover_path.exists():
        prompts.append(load_prompt(cover_path))
    for path in list_character_prompt_files(resources_dir):
        prompts.append(load_prompt(path))
    for path in list_page_prompt_files(resources_dir):
        prompts.append(load_prompt(path))
    prompts = [p for p in prompts if p]
    if not prompts:
        return {}

    char_lengths = [len(p) for p in prompts]
    token_lengths = [estimate_tokens(p) for p in prompts]
    style_hits = sum(1 for text in prompts for keyword in style_keywords if keyword in text.lower())
    return {
        "prompt_count": len(prompts),
        "avg_chars": round(statistics.mean(char_lengths), 2),
        "max_chars": max(char_lengths),
        "avg_tokens": round(statistics.mean(token_lengths), 2),
        "max_tokens": max(token_lengths),
        "style_keyword_hits": style_hits,
    }


def collect_translation_stats(outputs: Dict[str, List[Path]], *, estimate_tokens) -> Dict[str, Any]:
    """收集翻譯輸出統計資訊。"""

    if not outputs:
        return {}
    char_totals: Dict[str, int] = {}
    token_totals: Dict[str, int] = {}
    for lang, paths in outputs.items():
        total_chars = 0
        total_tokens = 0
        for file_path in paths:
            try:
                text = file_path.read_text(encoding="utf-8")
            except Exception:
                continue
            total_chars += len(text)
            total_tokens += estimate_tokens(text)
        char_totals[lang] = total_chars
        token_totals[lang] = total_tokens
    char_values = list(char_totals.values())
    return {
        "languages": len(outputs),
        "avg_chars": round(statistics.mean(char_values), 2) if char_values else 0,
        "char_totals": char_totals,
        "token_totals": token_totals,
    }


def collect_tts_text_stats(
    story_root: Path,
    *,
    voice_language: str,
    page_start: Optional[int],
    page_end: Optional[int],
    punctuation_pattern,
    estimate_tokens,
) -> Dict[str, Any]:
    """收集語音合成文本統計資訊。"""

    narration_dir = story_root / voice_language
    pages = collect_narration_pages(narration_dir) if narration_dir.exists() else []
    pages = filter_narration_pages(pages, page_start, page_end)
    if not pages:
        return {}

    total_chars = 0
    total_tokens = 0
    punctuation = 0
    for _, path in pages:
        text = load_prompt(path)
        if not text:
            continue
        total_chars += len(text)
        total_tokens += estimate_tokens(text)
        punctuation += len(punctuation_pattern.findall(text))
    return {
        "pages": len(pages),
        "total_chars": total_chars,
        "total_tokens": total_tokens,
        "punctuation_density": round(punctuation / max(1, total_chars), 4),
    }


def detect_tts_clipping(
    story_root: Path,
    *,
    voice_language: str,
    audio_dir_name: str,
    audio_format: str,
) -> Optional[Dict[str, Any]]:
    """檢測音訊檔案的裁切狀況。"""

    try:
        import soundfile as sf  # type: ignore
    except Exception:
        return None

    audio_path = find_primary_audio_file(
        story_root,
        voice_language,
        audio_dir_name,
        audio_format,
    )
    if not audio_path:
        return None
    try:
        data, _ = sf.read(audio_path)
    except Exception:
        return None
    if hasattr(data, "max"):
        max_amp = float(abs(data).max())
    else:
        max_amp = float(max(abs(sample) for sample in data))
    return {"path": str(audio_path), "max_amplitude": max_amp}
