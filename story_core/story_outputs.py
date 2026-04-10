"""Helpers for persisting story pipeline outputs."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from utils import write_json_or_raise


def select_canonical_branch(generated_branches_ids: List[str], root_branch_id: str) -> str:
    """Choose the branch used for canonical metadata and cover artifacts."""

    if "option_1" in generated_branches_ids:
        return "option_1"
    if generated_branches_ids:
        return generated_branches_ids[0]
    return root_branch_id


def collect_branch_pages(language_root: Path, branch_id: str, total_pages: int, *, logger=None) -> List[str]:
    """Load non-empty page text files from a branch."""

    branch_pages: List[str] = []
    branch_dir = language_root / "branches" / branch_id
    if not branch_dir.exists():
        if logger:
            logger.error("Branch directory not found: %s", branch_dir)
        return branch_pages

    for page_idx in range(1, total_pages + 1):
        page_file = branch_dir / f"page_{page_idx}.txt"
        if not page_file.exists():
            if logger:
                logger.warning("Page %s file not found in branch %s", page_idx, branch_id)
            continue
        try:
            content = page_file.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as exc:
            if logger:
                logger.error("Failed to read page %s in branch %s: %s", page_idx, branch_id, exc)
            continue
        if content:
            branch_pages.append(content)
        elif logger:
            logger.warning("Page %s is empty in branch %s", page_idx, branch_id)
    return branch_pages


def load_full_story_text(language_root: Path, branch_id: str) -> str:
    """Load the compiled full story text for a branch if present."""

    full_story_path = language_root / "branches" / branch_id / "full_story.txt"
    if not full_story_path.exists():
        return ""
    try:
        return full_story_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def _trim_cover_source(text: str, limit: int = 900) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""
    if len(cleaned) <= limit:
        return cleaned
    shortened = cleaned[:limit].rsplit(" ", 1)[0].strip()
    return (shortened or cleaned[:limit]).rstrip(",;:.") + "..."


def build_cover_context(
    *,
    cover_source: str,
    outline: str,
    title: str,
    age: str,
    character_descriptions: str,
    cover_guidelines: str,
    category: str = "",
    theme: str = "",
    visual_style: str = "",
    cover_source_label: str = "",
) -> Dict[str, str]:
    """Build cover prompt context with a bounded source excerpt."""

    source_label = (cover_source_label or "story").strip() or "story"
    source_excerpt = _trim_cover_source(cover_source)
    return {
        "cover_source": source_excerpt,
        "cover_source_excerpt": source_excerpt,
        "cover_source_label": source_label,
        "story_outline": outline,
        "story_title": title,
        "age": age,
        "story_category": category,
        "story_theme": theme,
        "character_descriptions": character_descriptions,
        "cover_guidelines": cover_guidelines,
        "image_style_lock": visual_style,
        "rag_context": "",
    }


def build_story_meta(
    *,
    story_id: str,
    story_title: str,
    relative_path: str,
    inputs: Any,
    options: Any,
    profile: Any,
    generated_branches_ids: List[str],
    start_time: float,
) -> Dict[str, Any]:
    """Build persisted story metadata."""

    elapsed = time.perf_counter() - start_time if start_time else 0
    created_at = datetime.now(timezone.utc).isoformat()

    return {
        "version": "3.0",
        "story_id": story_id,
        "story_title": story_title,
        "relative_path": relative_path,
        "timestamps": {
            "created_at": created_at,
            "generation_time_sec": round(elapsed, 2),
        },
        "input": {
            "language": inputs.language,
            "age_group": inputs.age_group,
            "category": inputs.category,
            "subcategory": inputs.subcategory,
            "theme": inputs.theme,
        },
        "model": {
            "name": options.model_name,
            "prompt_set": options.prompt_set,
        },
        "layout": profile.layout.to_dict() if profile and profile.layout else {},
        "branches": generated_branches_ids,
    }


def persist_story_meta(language_root: Path, meta: Dict[str, Any]) -> Path:
    """Persist story metadata under the resource directory."""

    resource_dir = language_root / "resource"
    resource_dir.mkdir(parents=True, exist_ok=True)
    meta_path = resource_dir / "story_meta.json"
    write_json_or_raise(meta_path, meta)
    return meta_path
