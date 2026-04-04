"""故事檔案樹的共用掃描、定位與排序工具。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple


def page_sort_key(path: Path) -> int:
    """由檔名取得頁碼數字，供排序使用。"""

    match = re.search(r"page_(\d+)", path.stem)
    return int(match.group(1)) if match else 0


def gather_language_files(language_dir: Path) -> List[Path]:
    """收集指定語系底下所有要翻譯的檔案，支援遞迴搜尋子目錄。"""

    entries: List[Path] = []
    for filename in ("title.txt", "outline.txt", "full_story.txt", "narration.txt", "dialogue.txt"):
        entries.extend(sorted(language_dir.rglob(filename)))

    page_texts = [
        path
        for path in language_dir.rglob("page_*.txt")
        if "_narration" not in path.stem
        and "_dialogue" not in path.stem
        and "_plan" not in path.stem
        and "_state" not in path.stem
    ]
    entries.extend(sorted(page_texts, key=page_sort_key))
    entries.extend(sorted(language_dir.rglob("page_*_narration.txt"), key=page_sort_key))
    entries.extend(sorted(language_dir.rglob("page_*_dialogue.txt"), key=page_sort_key))
    return entries


def relative_to_language(path: Path, language_dir: Path) -> Path:
    """將語言根目錄內的檔案轉成相對路徑。"""

    return path.relative_to(language_dir)


def collect_narration_pages(narration_dir: Path) -> List[Tuple[int, Path]]:
    """掃描語言目錄中所有 `page_X_narration.txt` 並按頁碼排序。"""

    pattern = re.compile(r"page_(\d+)_narration\.txt")
    result: List[Tuple[int, Path]] = []
    for path in narration_dir.rglob("*.txt"):
        match = pattern.match(path.name)
        if match:
            result.append((int(match.group(1)), path))
    result.sort(key=lambda item: item[0])
    return result


def filter_narration_pages(
    pages: List[Tuple[int, Path]],
    page_start: Optional[int] = None,
    page_end: Optional[int] = None,
) -> List[Tuple[int, Path]]:
    """依頁碼範圍過濾 narration 頁面清單。"""

    if page_start is None and page_end is None:
        return pages
    start = page_start or 1
    end = page_end or 10**9
    return [item for item in pages if start <= item[0] <= end]


def resolve_narration_dir(
    story_root: Path,
    language: str,
    fallback_subdir: str = "",
) -> Optional[Path]:
    """解析語音模組要讀取的 narration 目錄。"""

    language_dir = story_root / language
    fallback_dir = story_root / fallback_subdir if fallback_subdir else None
    for candidate in (language_dir, fallback_dir):
        if candidate and candidate.exists():
            return candidate
    return None


def detect_story_languages(story_root: Path) -> List[str]:
    """偵測故事資料夾下有哪些語言已有 narration 文字稿。"""

    if not story_root.exists():
        return []

    languages: List[str] = []
    for item in story_root.iterdir():
        if item.is_dir() and any(item.rglob("page_*_narration.txt")):
            languages.append(item.name)
    return sorted(languages)


def find_latest_story_root(output_root: Path) -> Optional[Path]:
    """遞迴尋找 output 根目錄下修改時間最新的故事資料夾。"""

    if not output_root.exists():
        return None

    story_dirs = set()
    for txt_path in output_root.rglob("page_*_narration.txt"):
        if txt_path.parent.parent.name != output_root.name:
            story_dirs.add(txt_path.parent.parent)

    if not story_dirs:
        return None

    try:
        return max(story_dirs, key=lambda path: path.stat().st_mtime)
    except ValueError:
        return None


def find_story_resource_dir(story_root: Path) -> Path:
    """取得故事的 resource 目錄，支援根目錄與巢狀結構搜尋。"""

    for name in ("resource", "resources"):
        candidate = story_root / name
        if candidate.exists():
            return candidate

    candidates = sorted(story_root.rglob("resource"), key=lambda path: len(path.parts))
    if candidates:
        return candidates[0]
    return story_root / "resource"


def list_generated_image_files(story_root: Path) -> List[Path]:
    """列出故事目錄下已生成的圖片檔案，支援巢狀結構。"""

    image_dir = story_root / "image" / "main"
    if image_dir.exists():
        direct_files = sorted(image_dir.glob("*.png"))
        if direct_files:
            return direct_files

    nested_files = sorted(story_root.rglob("image/main/*.png"))
    if nested_files:
        return nested_files
    return sorted(story_root.rglob("image/original/*.png"))


def list_generated_audio_files(
    story_root: Path,
    language: str,
    audio_dir_name: str,
    audio_format: str = "wav",
) -> List[Path]:
    """列出故事目錄下已生成的語音檔案，支援語系目錄與 fallback 搜尋。"""

    audio_dir = story_root / language / audio_dir_name
    if audio_dir.exists():
        direct_files = sorted(audio_dir.rglob(f"*.{audio_format}"))
        if direct_files:
            return direct_files

    return sorted((story_root / language).rglob(f"*.{audio_format}"))


def find_primary_audio_file(
    story_root: Path,
    language: str,
    audio_dir_name: str,
    audio_format: str = "wav",
) -> Optional[Path]:
    """找出優先用來檢測的主音訊檔案。"""

    audio_dir = story_root / language / audio_dir_name
    full_path = audio_dir / f"narration_full.{audio_format}"
    if full_path.exists():
        return full_path

    candidates = list_generated_audio_files(story_root, language, audio_dir_name, audio_format)
    return candidates[0] if candidates else None
