"""Story pipeline 的分支工作區與頁面繼承工具。"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Dict, Optional

from utils import BranchInfo, read_text as read_text_file


def create_branch(
    branches: Dict[str, BranchInfo],
    *,
    new_branch_id: str,
    divergence_point: int,
    root_branch_id: str,
    logger,
    parent_id: Optional[str] = None,
) -> None:
    """建立一個新分支並註冊。"""

    if new_branch_id in branches:
        logger.warning("Branch %s already exists.", new_branch_id)
        return
    parent_id = root_branch_id if parent_id is None else parent_id
    branches[new_branch_id] = BranchInfo(
        id=new_branch_id,
        parent_id=parent_id,
        divergence_point=divergence_point,
        convergence_point=None,
    )
    logger.info(
        "Created branch '%s' diverging from '%s' at page %s",
        new_branch_id,
        parent_id,
        divergence_point,
    )


def switch_branch(branches: Dict[str, BranchInfo], *, branch_id: str, file_manager, logger):
    """切換當前工作的目標分支，並更新檔案管理器狀態。"""

    if branch_id not in branches:
        raise ValueError(f"Unknown branch: {branch_id}")
    file_manager.set_branch(branch_id)
    logger.info("Switched to branch: %s", branch_id)
    return branch_id, file_manager.paths


def get_page_owner(
    branches: Dict[str, BranchInfo],
    *,
    page_idx: int,
    current_branch_id: str,
    branch_id: Optional[str] = None,
) -> str:
    """遞迴判斷某頁面歸屬於哪個分支。"""

    bid = branch_id or current_branch_id
    info = branches.get(bid)
    if not info:
        raise ValueError(f"Unknown branch in ownership lookup: {bid}")
    if page_idx < info.divergence_point:
        if info.parent_id:
            return get_page_owner(
                branches,
                page_idx=page_idx,
                current_branch_id=current_branch_id,
                branch_id=info.parent_id,
            )
        raise ValueError(f"No parent branch for page {page_idx} in branch {bid}")
    return bid


def read_page_content(
    branches: Dict[str, BranchInfo],
    *,
    idx: int,
    current_branch_id: str,
    file_manager,
    logger,
) -> Optional[str]:
    """讀取指定頁面的內容，自動處理分支繼承關係。"""

    owner_branch = get_page_owner(
        branches,
        page_idx=idx,
        current_branch_id=current_branch_id,
    )
    pipeline_branch = current_branch_id
    try:
        if file_manager.current_branch != owner_branch:
            file_manager.set_branch(owner_branch)
        path = file_manager.page_file(idx)
        if not path or not path.exists():
            logger.debug("Page %s file not found in branch %s, path: %s", idx, owner_branch, path)
            return None
        return read_text_file(path)
    except Exception as exc:
        logger.warning("Failed to read page %s from branch %s: %s", idx, owner_branch, exc)
        return None
    finally:
        if file_manager.current_branch != pipeline_branch:
            try:
                file_manager.set_branch(pipeline_branch)
            except Exception:
                logger.warning("Failed to restore file_manager branch to %s", pipeline_branch)


def current_branch_value_focus(*, profile, current_branch_id: str, fallback: str) -> str:
    """Resolve a neutral value-focus identifier for the current branch."""

    layout = profile.layout if profile else None
    branch_id = current_branch_id or ""
    if not layout or not layout.branch_slots:
        return fallback
    try:
        if branch_id.startswith("option_"):
            idx = int(branch_id.split("_")[-1]) - 1
            if 0 <= idx < len(layout.branch_slots):
                slot = layout.branch_slots[idx]
                return slot.get("type") or slot.get("label") or fallback
    except Exception:
        return fallback
    return fallback


def compile_full_story(branch_dir: Path, *, total_pages: int, logger) -> None:
    """Compiles Page 1..Total into full_story.txt in the branch dir."""

    try:
        full_text = []
        for i in range(1, total_pages + 1):
            page_path = branch_dir / f"page_{i}.txt"
            if page_path.exists():
                content = page_path.read_text(encoding="utf-8", errors="replace").strip()
                full_text.append(content)
            else:
                full_text.append(f"[Page {i} Missing]")
        (branch_dir / "full_story.txt").write_text("\n\n".join(full_text), encoding="utf-8")
    except Exception as exc:
        logger.error("Failed to compile full_story.txt in %s: %s", branch_dir, exc)


def _copy_branch_artifacts(src_dir: Path, dst_dir: Path, *, page_num: int, logger, dst_bid: str) -> None:
    """Copy page file, plan, structure and state snapshot for one page.
    Uses hardlinks where applicable to speed up branching and save space.
    """

    def robust_copy(src: Path, dst: Path, modify_callback=None):
        if not src.exists():
            return False
        # If there's a modification needed, we must physically read/write, avoiding hardlinks
        if modify_callback:
            try:
                shutil.copy2(src, dst)
                modify_callback(dst)
                return True
            except Exception as exc:
                logger.error("Copy/Modify failed %s: %s", src.name, exc)
                return False
        
        # Fast path: Hardlink
        try:
            os.link(src, dst)
            return True
        except Exception:
            # Fallback for systems/drives that do not support hardlinks
            try:
                shutil.copy2(src, dst)
                return True
            except Exception as exc:
                logger.error("Copy failed %s: %s", src.name, exc)
                return False

    filename = f"page_{page_num}.txt"
    if not robust_copy(src_dir / filename, dst_dir / filename):
        logger.warning("Page %s missing in source %s", page_num, src_dir.name)

    plan_filename = f"page_{page_num}_plan.txt"
    robust_copy(src_dir / plan_filename, dst_dir / plan_filename)

    struct_filename = f"page_{page_num}_struct.json"
    def mutate_struct(dst_file: Path):
        try:
            struct_payload = json.loads(dst_file.read_text(encoding="utf-8"))
            struct_payload["branch_id"] = dst_bid
            dst_file.write_text(json.dumps(struct_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
            
    robust_copy(src_dir / struct_filename, dst_dir / struct_filename, modify_callback=mutate_struct)

    state_filename = f"page_{page_num}_state.json"
    robust_copy(src_dir / state_filename, dst_dir / state_filename)


def copy_branch_state(file_manager, *, logger, src_bid: str, dst_bid: str, decision_page: int) -> None:
    """物理複製主線頁面與中介檔從來源分支到目標分支。"""

    root = file_manager.language_root
    if not root:
        return
    src_dir = root / "branches" / src_bid
    dst_dir = root / "branches" / dst_bid
    if not src_dir.exists():
        logger.error("Source branch %s dir not found: %s", src_bid, src_dir)
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for page_num in range(1, decision_page + 1):
        _copy_branch_artifacts(src_dir, dst_dir, page_num=page_num, logger=logger, dst_bid=dst_bid)


def copy_branch_pages(
    file_manager,
    *,
    logger,
    src_bid: str,
    dst_bid: str,
    start_page: int,
    end_page: int,
) -> None:
    """Copy a range of pages and related metadata from src to dst branch."""

    if start_page > end_page:
        return
    root = file_manager.language_root
    if not root:
        return
    src_dir = root / "branches" / src_bid
    dst_dir = root / "branches" / dst_bid
    if not src_dir.exists():
        logger.error("Source branch %s dir not found: %s", src_bid, src_dir)
        return
    dst_dir.mkdir(parents=True, exist_ok=True)
    for page_num in range(start_page, end_page + 1):
        _copy_branch_artifacts(src_dir, dst_dir, page_num=page_num, logger=logger, dst_bid=dst_bid)
