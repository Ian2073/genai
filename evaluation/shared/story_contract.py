"""Generation-aware story contract used by the evaluation quality gate.

This module intentionally stays lightweight: it scans the files already
produced by the story pipeline and normalizes them into one dictionary shape
that every evaluation dimension can consume.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _safe_load_json(path: Union[str, Path]) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return {}
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _read_text(path: Union[str, Path]) -> str:
    file_path = Path(path)
    if not file_path.exists() or not file_path.is_file():
        return ""
    try:
        return file_path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _extract_page_number(path: Path) -> int:
    match = re.search(r"page_(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def _dedupe_paths(paths: Sequence[Path]) -> List[Path]:
    deduped: List[Path] = []
    seen: set[str] = set()
    for path in paths:
        key = os.fspath(path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(path)
    return deduped


def _find_story_root(branch_dir: Path, story_dir: Optional[Union[str, Path]]) -> Path:
    if story_dir:
        return Path(story_dir)
    parts = list(branch_dir.parts)
    lowered = [part.lower() for part in parts]
    if "branches" in lowered:
        idx = lowered.index("branches")
        if idx >= 2:
            return Path(*parts[: idx - 1])
    return branch_dir


def _resolve_branch_dir(
    story_dir: Optional[Union[str, Path]],
    branch_id: str,
    source_document: Optional[Union[str, Path]],
) -> Tuple[Path, Path]:
    if source_document:
        source_path = Path(source_document)
        branch_dir = source_path.parent
        return _find_story_root(branch_dir, story_dir), branch_dir

    root = Path(story_dir or ".")
    branch_token = str(branch_id or "canonical").strip()
    candidates: List[Path] = []
    if branch_token.lower() in {"canonical", "auto", ""}:
        candidates.extend(sorted(root.glob("**/branches/option_1")))
        candidates.extend([root / "en", root])
    else:
        candidates.extend(sorted(root.glob(f"**/branches/{branch_token}")))

    for candidate in candidates:
        if (candidate / "full_story.txt").exists() or (candidate / "draft_story.txt").exists():
            return root, candidate
    return root, candidates[0] if candidates else root


def _metadata_candidates(story_root: Path, branch_dir: Path) -> List[Path]:
    return _dedupe_paths(
        [
            branch_dir / "metadata.json",
            branch_dir / "resource" / "story_meta.json",
            story_root / "metadata.json",
            story_root / "resource" / "story_meta.json",
            story_root / "en" / "resource" / "story_meta.json",
        ]
    )


def _manifest_candidates(story_root: Path, branch_dir: Path) -> List[Path]:
    return _dedupe_paths(
        [
            branch_dir / "assessment_input.json",
            branch_dir / "resource" / "generation_manifest.json",
            story_root / "resource" / "generation_manifest.json",
            story_root / "en" / "resource" / "generation_manifest.json",
        ]
    )


def _load_first_json(paths: Sequence[Path]) -> Dict[str, Any]:
    for path in paths:
        data = _safe_load_json(path)
        if data:
            data["_source_path"] = os.fspath(path)
            return data
    return {}


def _load_page_quality(branch_dir: Path) -> Dict[int, Dict[str, Any]]:
    payload = _safe_load_json(branch_dir / "page_quality.json")
    raw_pages = payload.get("pages") if isinstance(payload, dict) else None
    if not isinstance(raw_pages, list):
        return {}
    quality: Dict[int, Dict[str, Any]] = {}
    for item in raw_pages:
        if not isinstance(item, dict):
            continue
        try:
            page_number = int(item.get("page") or item.get("page_num") or 0)
        except Exception:
            page_number = 0
        if page_number > 0:
            quality[page_number] = item
    return quality


def _collect_page_records(branch_dir: Path) -> List[Dict[str, Any]]:
    quality_by_page = _load_page_quality(branch_dir)
    pages: List[Dict[str, Any]] = []
    for page_path in sorted(branch_dir.glob("page_*.txt"), key=_extract_page_number):
        name = page_path.name.lower()
        if any(suffix in name for suffix in ("_dialogue", "_narration", "_plan", "_state", "_struct")):
            continue
        page_number = _extract_page_number(page_path)
        if page_number <= 0:
            continue
        struct_path = branch_dir / f"page_{page_number}_struct.json"
        state_path = branch_dir / f"page_{page_number}_state.json"
        plan_path = branch_dir / f"page_{page_number}_plan.txt"
        narration_path = branch_dir / f"page_{page_number}_narration.txt"
        dialogue_path = branch_dir / f"page_{page_number}_dialogue.txt"
        prompt_path = branch_dir / "resource" / f"page_{page_number}_prompt.txt"
        image_path = branch_dir / "image" / "main" / f"page_{page_number}_scene.png"

        text = _read_text(page_path)
        tokens = re.findall(r"[A-Za-z']+|[\u4e00-\u9fff]", text)
        pages.append(
            {
                "page": page_number,
                "text_path": os.fspath(page_path),
                "text": text,
                "word_count": len(tokens),
                "structure_path": os.fspath(struct_path) if struct_path.exists() else None,
                "structure": _safe_load_json(struct_path),
                "state_path": os.fspath(state_path) if state_path.exists() else None,
                "state": _safe_load_json(state_path),
                "plan_path": os.fspath(plan_path) if plan_path.exists() else None,
                "narration_path": os.fspath(narration_path) if narration_path.exists() else None,
                "dialogue_path": os.fspath(dialogue_path) if dialogue_path.exists() else None,
                "image_prompt_path": os.fspath(prompt_path) if prompt_path.exists() else None,
                "image_prompt": _read_text(prompt_path),
                "image_path": os.fspath(image_path) if image_path.exists() else None,
                "quality": quality_by_page.get(page_number, {}),
            }
        )
    return pages


def collect_story_bundle(
    story_dir: Optional[Union[str, Path]],
    *,
    branch_id: str = "canonical",
    source_document: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Collect generation-aware context for one story branch."""

    story_root, branch_dir = _resolve_branch_dir(story_dir, branch_id, source_document)
    metadata = _load_first_json(_metadata_candidates(story_root, branch_dir))
    manifest = _load_first_json(_manifest_candidates(story_root, branch_dir))
    asset_manifest = _safe_load_json(branch_dir / "asset_manifest.json")
    branch_metadata = _safe_load_json(branch_dir / "metadata.json")
    pages = _collect_page_records(branch_dir)

    layout = {}
    if isinstance(metadata.get("layout"), dict):
        layout.update(metadata.get("layout") or {})
    if isinstance(manifest.get("layout"), dict):
        layout.update(manifest.get("layout") or {})
    if branch_metadata:
        for key in ("total_pages", "decision_page", "layout_id"):
            if key in branch_metadata and key not in layout:
                layout[key] = branch_metadata[key]

    story_input = {}
    for source in (metadata.get("input"), manifest.get("input")):
        if isinstance(source, dict):
            story_input.update(source)

    return {
        "schema_version": "1.0",
        "story_root": os.fspath(story_root),
        "branch_dir": os.fspath(branch_dir),
        "branch_id": branch_metadata.get("branch_id") or branch_id or "canonical",
        "source_document": os.fspath(source_document) if source_document else None,
        "metadata": metadata,
        "manifest": manifest,
        "asset_manifest": asset_manifest,
        "branch": branch_metadata,
        "input": story_input,
        "layout": layout,
        "pages": pages,
    }


def summarize_story_bundle(bundle: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Return a compact, report-safe summary of a StoryBundle."""

    if not isinstance(bundle, dict) or not bundle:
        return {}
    pages = bundle.get("pages") if isinstance(bundle.get("pages"), list) else []
    page_word_counts = [
        int(page.get("word_count") or 0)
        for page in pages
        if isinstance(page, dict)
    ]
    missing_images = [
        int(page.get("page") or 0)
        for page in pages
        if isinstance(page, dict) and page.get("image_prompt") and not page.get("image_path")
    ]
    return {
        "schema_version": bundle.get("schema_version"),
        "story_root": bundle.get("story_root"),
        "branch_dir": bundle.get("branch_dir"),
        "branch_id": bundle.get("branch_id"),
        "source_document": bundle.get("source_document"),
        "input": bundle.get("input") or {},
        "layout": bundle.get("layout") or {},
        "page_count": len(pages),
        "total_words": sum(page_word_counts),
        "min_page_words": min(page_word_counts) if page_word_counts else 0,
        "missing_image_pages": [page for page in missing_images if page > 0],
    }
