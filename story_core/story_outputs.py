"""Story pipeline 輸出產物協調工具。"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from utils import write_json_or_raise


def select_canonical_branch(generated_branches_ids: List[str], root_branch_id: str) -> str:
    """選出作為 canonical metadata / cover 來源的分支。"""

    if "option_1" in generated_branches_ids:
        return "option_1"
    if generated_branches_ids:
        return generated_branches_ids[0]
    return root_branch_id


def collect_branch_pages(language_root: Path, branch_id: str, total_pages: int, *, logger=None) -> List[str]:
    """直接從指定分支目錄收集頁面內容，不經 inheritance。"""

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
    """讀取指定分支的 full_story 內容。"""

    full_story_path = language_root / "branches" / branch_id / "full_story.txt"
    if not full_story_path.exists():
        return ""
    try:
        return full_story_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""


def build_cover_context(
    *,
    cover_source: str,
    outline: str,
    title: str,
    age: str,
    character_descriptions: str,
    cover_guidelines: str,
) -> Dict[str, str]:
    """建立 cover prompt 需要的完整上下文。"""

    return {
        "cover_source": cover_source,
        "story_outline": outline,
        "story_title": title,
        "age": age,
        "character_descriptions": character_descriptions,
        "cover_guidelines": cover_guidelines,
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
    """建立 story metadata 內容。"""

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
    """將 story metadata 寫入標準 resource 位置。"""

    resource_dir = language_root / "resource"
    resource_dir.mkdir(parents=True, exist_ok=True)
    meta_path = resource_dir / "story_meta.json"
    write_json_or_raise(meta_path, meta)
    return meta_path
