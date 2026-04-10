"""故事資料存取工具。

集中管理 story 目錄掃描、assessment_report/metadata 讀取與容錯，
供 scripts/report.py、scripts/validate.py 等腳本共用。
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union


def _safe_load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """安全讀取 JSON，失敗時回傳 None。"""
    if not file_path.exists() or not file_path.is_file():
        return None
    try:
        with file_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
            return data if isinstance(data, dict) else None
    except Exception:
        return None


def _read_text(file_path: Union[str, Path]) -> str:
    path = Path(file_path)
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def load_json_dict(file_path: Union[str, Path]) -> Optional[Dict[str, Any]]:
    """公開版 JSON 讀取：接受字串或 Path，失敗回傳 None。"""
    return _safe_load_json(Path(file_path))


def _extract_page_number(path: Path) -> int:
    match = re.search(r"page_(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def _branch_sort_key(branch_id: str) -> Tuple[int, int, str]:
    match = re.fullmatch(r"option_(\d+)", str(branch_id).strip())
    if match:
        return (0, int(match.group(1)), branch_id)
    return (1, 0, branch_id)


def _language_priority(path: Path, root: Path) -> int:
    """Canonical 選檔優先順序：en > 無語言層 > 其他語言。"""
    try:
        parts = list(path.relative_to(root).parts)
    except Exception:
        parts = list(path.parts)

    lowered = [part.lower() for part in parts]
    if "branches" in lowered:
        idx = lowered.index("branches")
        if idx >= 1:
            lang = lowered[idx - 1]
            if lang == "en":
                return 0
            return 2
    return 1


def _collect_branch_page_files(branch_dir: Path) -> List[Path]:
    pages = []
    for path in sorted(branch_dir.glob("page_*.txt"), key=_extract_page_number):
        name = path.name.lower()
        if "_narration" in name or "_dialogue" in name or "_plan" in name or "_state" in name:
            continue
        pages.append(path)
    return pages


def stitch_branch_pages(
    story_dir: Union[str, Path],
    *,
    branch_id: str,
    output_name: str = "full_story_stitched.txt",
) -> Optional[Path]:
    """將分支 page_*.txt 拼接為暫存全文，供評估 fallback 使用。"""
    root = Path(story_dir)
    branch_key = (branch_id or "canonical").strip()

    candidate_dirs: List[Path] = []
    if branch_key.lower() == "canonical":
        candidate_dirs.extend([root / "en", root])
        candidate_dirs.extend(sorted(root.glob("**/branches/option_1")))
    else:
        candidate_dirs.extend(sorted(root.glob(f"**/branches/{branch_key}")))

    seen: set[str] = set()
    for branch_dir in candidate_dirs:
        key = os.fspath(branch_dir)
        if key in seen or not branch_dir.exists() or not branch_dir.is_dir():
            continue
        seen.add(key)

        page_files = _collect_branch_page_files(branch_dir)
        if not page_files:
            continue

        chunks: List[str] = []
        for page_file in page_files:
            try:
                text = page_file.read_text(encoding="utf-8").strip()
            except Exception:
                continue
            if text:
                chunks.append(text)

        if not chunks:
            continue

        stitched_path = branch_dir / output_name
        try:
            stitched_path.write_text("\n\n".join(chunks) + "\n", encoding="utf-8")
            return stitched_path
        except Exception:
            continue

    return None


def discover_story_dirs(root_dirs: Sequence[str]) -> List[Path]:
    """掃描多個根目錄下的一層故事資料夾。"""
    story_dirs: List[Path] = []
    for root in root_dirs:
        root_path = Path(root)
        if not root_path.exists() or not root_path.is_dir():
            continue
        for candidate in sorted(root_path.iterdir()):
            if candidate.is_dir():
                story_dirs.append(candidate)
    return story_dirs


def collect_full_story_paths(
    story_dir: Union[str, Path],
    *,
    include_recursive_fallback: bool = True,
    include_branches: bool = False,
) -> List[Path]:
    """收集故事目錄內可用的 full_story.txt 候選路徑。"""
    root = Path(story_dir)
    candidates: List[Path] = []

    direct_path = root / "full_story.txt"
    localized_path = root / "en" / "full_story.txt"
    if direct_path.exists():
        candidates.append(direct_path)
    if localized_path.exists():
        candidates.append(localized_path)

    if not candidates and include_recursive_fallback and root.exists() and root.is_dir():
        candidates.extend(sorted(root.glob("**/full_story.txt")))

    if include_branches and root.exists() and root.is_dir():
        candidates.extend(sorted(root.glob("**/branches/*/full_story.txt")))
        candidates.extend(sorted(root.glob("**/branches/*/draft_story.txt")))

    deduped: List[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.fspath(candidate)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def collect_branch_story_paths(
    story_dir: Union[str, Path],
    *,
    branch_mode: str = "canonical",
    include_page_fallback: bool = True,
) -> List[Tuple[str, Path]]:
    """依分支模式回傳可評估的故事全文路徑。

    branch_mode:
      - canonical: 只回傳主線
      - all: 回傳所有分支（option_1, option_2...）
            - auto: 若可用分支 >= 2 則回傳 all，否則回傳 canonical
      - 其他字串: 指定單一分支
    """
    root = Path(story_dir)
    if not root.exists() or not root.is_dir():
        return []

    mode = (branch_mode or "canonical").strip()
    mode_lower = mode.lower()

    canonical_source: Optional[Tuple[int, int, Path]] = None
    branch_sources: Dict[str, Tuple[int, int, Path]] = {}

    def _register(source_map: Dict[str, Tuple[int, int, Path]], branch_id: str, path: Path, rank: int) -> None:
        key = branch_id.strip() or "canonical"
        lang_rank = _language_priority(path, root)
        existing = source_map.get(key)
        if existing is None or (rank, lang_rank) < (existing[0], existing[1]):
            source_map[key] = (rank, lang_rank, path)

    # Canonical 優先：root/en 下的 full_story，再 root/en 下的 draft
    canonical_full = [root / "full_story.txt", root / "en" / "full_story.txt"]
    canonical_draft = [root / "draft_story.txt", root / "en" / "draft_story.txt"]
    for path in canonical_full:
        if path.exists():
            canonical_source = (0, _language_priority(path, root), path)
            break
    if canonical_source is None:
        for path in canonical_draft:
            if path.exists():
                canonical_source = (1, _language_priority(path, root), path)
                break

    # 掃描分支資料夾
    for path in sorted(root.glob("**/branches/*/full_story.txt")):
        _register(branch_sources, path.parent.name, path, 0)
    for path in sorted(root.glob("**/branches/*/draft_story.txt")):
        _register(branch_sources, path.parent.name, path, 1)

    # Canonical 若沒有根目錄來源，嘗試映射到 option_1 或第一個分支
    if canonical_source is None:
        if "option_1" in branch_sources:
            canonical_source = branch_sources["option_1"]
        elif branch_sources:
            first_bid = sorted(branch_sources.keys(), key=_branch_sort_key)[0]
            canonical_source = branch_sources[first_bid]

    # 指定分支且未找到時，嘗試 page stitch fallback
    if include_page_fallback and mode_lower not in {"all", "*", "auto"}:
        target = "canonical" if mode_lower == "canonical" else mode
        has_target = bool(canonical_source) if target == "canonical" else target in branch_sources
        if not has_target:
            stitched = stitch_branch_pages(root, branch_id=target)
            if stitched is not None:
                if target == "canonical":
                    canonical_source = (2, _language_priority(stitched, root), stitched)
                else:
                    branch_sources[target] = (2, _language_priority(stitched, root), stitched)

    # all 模式下，若沒有任何候選，嘗試 canonical stitch fallback
    if include_page_fallback and mode_lower in {"all", "*"} and not branch_sources and canonical_source is None:
        stitched = stitch_branch_pages(root, branch_id="canonical")
        if stitched is not None:
            canonical_source = (2, _language_priority(stitched, root), stitched)

    if include_page_fallback and mode_lower == "auto" and not branch_sources and canonical_source is None:
        stitched = stitch_branch_pages(root, branch_id="canonical")
        if stitched is not None:
            canonical_source = (2, _language_priority(stitched, root), stitched)

    if mode_lower == "auto":
        if len(branch_sources) >= 2:
            items = sorted(branch_sources.items(), key=lambda item: _branch_sort_key(item[0]))
            return [(branch_id, source[2]) for branch_id, source in items]
        if canonical_source is not None:
            return [("canonical", canonical_source[2])]
        if branch_sources:
            first_bid = sorted(branch_sources.keys(), key=_branch_sort_key)[0]
            return [(first_bid, branch_sources[first_bid][2])]
        return []

    if mode_lower in {"all", "*"}:
        items = sorted(branch_sources.items(), key=lambda item: _branch_sort_key(item[0]))
        if items:
            return [(branch_id, source[2]) for branch_id, source in items]
        if canonical_source is not None:
            return [("canonical", canonical_source[2])]
        return []

    if mode_lower == "canonical":
        if canonical_source is not None:
            return [("canonical", canonical_source[2])]
        return []

    target_source = branch_sources.get(mode)
    if target_source is not None:
        return [(mode, target_source[2])]

    return []


def load_story_text_from_dir(story_dir: Union[str, Path]) -> str:
    """讀取故事目錄中的 full_story 內容並合併。"""
    parts: List[str] = []
    for file_path in collect_full_story_paths(story_dir):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if content:
            parts.append(content)
    return "\n\n".join(parts)


def find_metadata_for_story(
    document_paths: Dict[str, Union[str, List[str]]],
    story_title: str,
    *,
    fallback_roots: Sequence[str] = ("output", "evaluated", "pending"),
) -> Dict[str, Any]:
    """依故事文件路徑與標題尋找 metadata.json。

    搜尋順序：
    1. 由 document_paths 反推故事目錄（支援 en/ 子資料夾回退）
    2. 以標題推測 fallback_roots/<title>/metadata.json
    3. 若都找不到，回傳僅含 title 的最小字典
    """
    candidate_dirs: List[Path] = []

    def _register_dir(file_path: Optional[str]) -> None:
        if not file_path:
            return
        directory = Path(file_path).parent
        if not directory:
            return
        if directory.name.lower() == "en":
            directory = directory.parent
        candidate_dirs.append(directory)

    for value in document_paths.values():
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    _register_dir(item)
        elif isinstance(value, str):
            _register_dir(value)

    def _metadata_candidates(directory: Path) -> List[Path]:
        return [
            directory / "metadata.json",
            directory / "story_meta.json",
            directory / "resource" / "story_meta.json",
            directory / "en" / "resource" / "story_meta.json",
        ]

    checked: set[str] = set()
    for directory in candidate_dirs:
        current = directory
        for _ in range(5):
            key = os.fspath(current)
            if not key or key in checked:
                if current.parent == current:
                    break
                current = current.parent
                continue
            checked.add(key)
            for candidate in _metadata_candidates(current):
                metadata = _safe_load_json(candidate)
                if metadata is not None:
                    metadata.setdefault("title", story_title)
                    return metadata
            if current.parent == current:
                break
            current = current.parent

    safe_title = story_title.strip().replace("\\", "").replace("/", "")
    if safe_title:
        for root_dir in fallback_roots:
            base = Path(root_dir) / safe_title
            for candidate in _metadata_candidates(base):
                metadata = _safe_load_json(candidate)
                if metadata is not None:
                    metadata.setdefault("title", story_title)
                    return metadata

    return {"title": story_title}


def load_story_records(
    root_dirs: Sequence[str],
    *,
    require_report: bool = False,
    require_metadata: bool = False,
) -> List[Dict[str, Any]]:
    """載入故事記錄。

    回傳每筆包含：
    - story_name
    - story_dir
    - report_path / report
    - metadata_path / metadata
    """
    records: List[Dict[str, Any]] = []

    for story_dir in discover_story_dirs(root_dirs):
        report_path = story_dir / "assessment_report.json"
        metadata_path = story_dir / "metadata.json"

        report_data = _safe_load_json(report_path)
        metadata_data = _safe_load_json(metadata_path)

        if require_report and report_data is None:
            continue
        if require_metadata and metadata_data is None:
            continue

        records.append(
            {
                "story_name": story_dir.name,
                "story_dir": str(story_dir),
                "report_path": str(report_path),
                "metadata_path": str(metadata_path),
                "report": report_data,
                "metadata": metadata_data,
            }
        )

    return records


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


def _extract_visual_page_number(path: Path) -> int:
    match = re.search(r"page_(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def collect_story_visual_assets(
    story_dir: Union[str, Path],
    *,
    branch_id: str = "canonical",
    source_document: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Collect story-level image assets, paired prompts, and lightweight generation traces."""
    root = Path(story_dir)
    branch_token = str(branch_id or "canonical").strip()

    candidate_dirs: List[Path] = []
    if source_document:
        source_dir = Path(source_document).parent
        candidate_dirs.append(source_dir)
        if source_dir.name.lower() == "en":
            candidate_dirs.append(source_dir / "branches" / "option_1")
    if branch_token and branch_token.lower() not in {"canonical", "auto"}:
        candidate_dirs.extend(sorted(root.glob(f"**/branches/{branch_token}")))
    else:
        candidate_dirs.extend(sorted(root.glob("**/branches/option_1")))
        candidate_dirs.extend([root / "en", root])
    candidate_dirs = _dedupe_paths([directory for directory in candidate_dirs if directory and directory.exists()])

    selected_dir: Optional[Path] = None
    resource_dir: Optional[Path] = None
    image_dir: Optional[Path] = None

    for directory in candidate_dirs:
        local_resource = directory / "resource"
        local_image = directory / "image" / "main"
        if local_resource.exists() or local_image.exists():
            selected_dir = directory
            resource_dir = local_resource if local_resource.exists() else None
            image_dir = local_image if local_image.exists() else None
            if local_image.exists():
                break

    image_paths: List[Path] = []
    pairs: List[Dict[str, Any]] = []
    photo_log_text = ""
    story_meta: Dict[str, Any] = {}

    if image_dir and image_dir.exists():
        cover_path = image_dir / "book_cover.png"
        if cover_path.exists():
            image_paths.append(cover_path)
        image_paths.extend(sorted(image_dir.glob("page_*_scene.png"), key=_extract_visual_page_number))

    if resource_dir and resource_dir.exists():
        if not story_meta:
            story_meta = _safe_load_json(resource_dir / "story_meta.json") or {}

        prompt_map: Dict[str, Path] = {}
        for prompt_path in sorted(resource_dir.glob("*_prompt.txt")):
            prompt_map[prompt_path.stem.lower()] = prompt_path

        page_text_map: Dict[int, Path] = {}
        if selected_dir and selected_dir.exists():
            for page_path in sorted(selected_dir.glob("page_*.txt"), key=_extract_page_number):
                name = page_path.name.lower()
                if "_dialogue" in name or "_narration" in name or "_plan" in name or "_state" in name:
                    continue
                page_text_map[_extract_page_number(page_path)] = page_path

        if image_paths:
            for image_path in image_paths:
                stem = image_path.stem.lower()
                kind = "cover" if stem == "book_cover" else "page"
                page_number = _extract_visual_page_number(image_path) if kind == "page" else None
                prompt_path = prompt_map.get(f"page_{page_number}_prompt") if kind == "page" else prompt_map.get("book_cover_prompt")
                page_text_path = page_text_map.get(page_number) if kind == "page" else None
                pairs.append(
                    {
                        "kind": kind,
                        "page": page_number,
                        "image_path": os.fspath(image_path),
                        "prompt_path": os.fspath(prompt_path) if prompt_path else None,
                        "prompt_text": _read_text(os.fspath(prompt_path)) if prompt_path else "",
                        "page_text_path": os.fspath(page_text_path) if page_text_path else None,
                        "page_text": _read_text(os.fspath(page_text_path)) if page_text_path else "",
                    }
                )

    log_candidates = [
        root / "logs" / "photo.log",
    ]
    if selected_dir:
        log_candidates.append(selected_dir / "logs" / "generation.log")
    for candidate in _dedupe_paths(log_candidates):
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            continue
        if text:
            photo_log_text = text
            break

    if not story_meta:
        story_meta = find_metadata_for_story(
            {"full_story.txt": os.fspath(source_document)} if source_document else {},
            root.name,
            fallback_roots=(os.fspath(root.parent), "output", "evaluated", "pending"),
        )

    return {
        "selected_dir": os.fspath(selected_dir) if selected_dir else None,
        "resource_dir": os.fspath(resource_dir) if resource_dir else None,
        "image_dir": os.fspath(image_dir) if image_dir else None,
        "image_paths": [os.fspath(path) for path in image_paths],
        "pairs": pairs,
        "photo_log": photo_log_text,
        "story_meta": story_meta,
    }
