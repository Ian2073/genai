"""ChiefRunner 的故事輸出驗證工具。"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List, Optional, Sequence

from runtime.story_files import (
    detect_story_languages,
    list_generated_audio_files,
    list_generated_image_files,
)
from utils import read_json


def verify_story(
    story_root: Path,
    *,
    story_language: str,
    voice_language: str,
    audio_dir_name: str,
    audio_format: str,
    target_languages: Sequence[str],
    expect_translation: bool,
    expect_voice: bool,
    expect_photo: bool,
    logger: Optional[logging.Logger] = None,
) -> bool:
    """嚴格檢查產出物是否齊全。"""

    missing: List[str] = []

    def _expect(condition: bool, message: str) -> None:
        if not condition:
            missing.append(message)

    base_lang_dir = story_root / story_language
    _expect(base_lang_dir.exists(), f"{story_language} 語系目錄缺少")

    meta_candidates = [
        story_root / "resource" / "story_meta.json",
        story_root / "story_meta.json",
        base_lang_dir / "resource" / "story_meta.json",
        base_lang_dir / "branches" / "option_1" / "resource" / "story_meta.json",
    ]
    meta_path = next((p for p in meta_candidates if p.exists()), None)
    _expect(meta_path is not None, "story_meta.json 缺少")

    meta_data = read_json(meta_path) if meta_path else None
    if meta_data:
        layout = meta_data.get("layout") or {}
        branch_count_expected = layout.get("branch_count", 0)
        layout_id_expected = layout.get("layout_id", "unknown")
        decision_page = layout.get("decision_page", 0)

        branches_dir = base_lang_dir / "branches"
        _expect(branches_dir.exists(), "Branches directory missing")

        if branches_dir.exists():
            actual_branches = [d.name for d in branches_dir.iterdir() if d.is_dir()]
            options_found = [b for b in actual_branches if b.startswith("option_")]
            expected_count = branch_count_expected if branch_count_expected > 0 else 1
            _expect(
                len(options_found) == expected_count,
                f"Branch count mismatch: Expected {expected_count}, Found {len(options_found)} {options_found}",
            )
            if "main" in actual_branches:
                missing.append("CRITICAL: Found legacy 'main' branch folder. Strict mode violation.")

            branch_states = {}
            for bid in options_found:
                branch_story_path = branches_dir / bid / "full_story.txt"
                branch_meta_path = branches_dir / bid / "metadata.json"
                _expect(branch_story_path.exists(), f"Branch {bid} missing full_story.txt")
                _expect(branch_meta_path.exists(), f"Branch {bid} missing metadata.json (SSOT requirement)")

                if branch_meta_path.exists():
                    branch_meta = read_json(branch_meta_path)
                    if branch_meta:
                        branch_layout_id = branch_meta.get("layout_id")
                        _expect(
                            branch_layout_id == layout_id_expected,
                            f"Layout mismatch in {bid}: expected {layout_id_expected}, got {branch_layout_id}",
                        )

                state_chain = []
                if branch_story_path.exists():
                    for page_num in range(1, (layout.get("total_pages") or 0) + 1):
                        if page_num <= decision_page:
                            continue
                        state_path = branches_dir / bid / f"page_{page_num}_state.json"
                        if not state_path.exists():
                            missing.append(f"Branch {bid} missing state snapshot for page {page_num}.")
                            continue
                        try:
                            state_chain.append(state_path.read_text(encoding="utf-8", errors="replace"))
                        except Exception:
                            missing.append(f"Branch {bid} failed to read state snapshot for page {page_num}.")
                branch_states[bid] = "\n".join(state_chain)

                if branch_meta_path.exists():
                    branch_meta = read_json(branch_meta_path) or {}
                    if not (branch_meta.get("meaning_tag") or branch_meta.get("branch_trait")):
                        missing.append(f"Branch {bid} missing trait metadata in metadata.json.")

            if (layout.get("branch_count", 0) > 0) and len(branch_states) > 1:
                hashes = set()
                for bid, state_blob in branch_states.items():
                    if not state_blob.strip():
                        missing.append(f"Branch {bid} has NO state snapshots after decision page {decision_page}!")
                    hashes.add(hashlib.sha256(state_blob.encode("utf-8")).hexdigest())

                _expect(len(hashes) > 1, f"Branches identical after Page {decision_page} based on state snapshots.")
                _expect(len(hashes) == len(branch_states), "Some branches have identical state snapshots!")

    if base_lang_dir.exists():
        branches_dir = base_lang_dir / "branches"
        canonical_branch = "option_1"
        if branches_dir.exists():
            options_found = [d.name for d in branches_dir.iterdir() if d.is_dir() and d.name.startswith("option_")]
            if options_found:
                canonical_branch = "option_1" if "option_1" in options_found else options_found[0]
        branch_root = branches_dir / canonical_branch
        for filename in ["outline.txt", "title.txt"]:
            _expect((branch_root / filename).exists(), f"{story_language}/branches/{canonical_branch}/{filename} 缺少")

    if expect_translation and target_languages:
        available_languages = set(detect_story_languages(story_root))
        for lang in target_languages:
            _expect(lang in available_languages, f"翻譯語系缺少: {lang}")

    if expect_photo:
        image_files = list_generated_image_files(story_root)
        if not image_files:
            missing.append("圖片檔案缺失")
        elif logger:
            logger.info("找到 %d 張圖片", len(image_files))

    if expect_voice:
        audio_files = list_generated_audio_files(
            story_root,
            voice_language,
            audio_dir_name,
            audio_format,
        )
        _expect(bool(audio_files), "voice/audio 目錄不存在且找不到語音檔案")
        if audio_files and logger:
            logger.info("找到 %d 個語音檔案", len(audio_files))

    if missing:
        if logger:
            logger.error("Story verification failed:\n%s", "\n".join(missing))
        return False
    if logger:
        logger.info("Story verification passed.")
    return True
