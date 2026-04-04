"""Story pipeline 的頁面生成流程輔助。"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple

from utils import write_text_or_raise


def resolve_page_range(
    *,
    existing_page_numbers: List[int],
    total_pages: int,
    start_page_override: Optional[int] = None,
    end_page_limit: Optional[int] = None,
) -> Tuple[int, int]:
    """根據 override 與現有頁面狀態決定本輪生成區間。"""

    if start_page_override:
        start_page = start_page_override
    else:
        current_max = max(existing_page_numbers) if existing_page_numbers else 0
        start_page = current_max + 1

    end_page = end_page_limit if end_page_limit else total_pages
    return start_page, end_page


def preload_existing_pages(
    *,
    start_page: int,
    read_page_content: Callable[[int], str],
    sanitize_text: Callable[[str], str],
) -> List[str]:
    """為後續 smart context 建立既有頁面歷史。"""

    pages: List[str] = []
    for page_idx in range(1, start_page):
        content = read_page_content(page_idx)
        if content:
            pages.append(sanitize_text(content))
    return pages


def format_decision_options(page_structure: Dict[str, Any]) -> str:
    """將 decision options 轉成 prompt 內可直接使用的文字。"""

    decision_options = []
    for opt in page_structure.get("decision_options", []):
        label = opt.get("label", "")
        desc = opt.get("desc", "")
        decision_options.append(f"{label} - {desc}" if desc else label)

    decision_lines = [
        f"Option {idx}: {text}"
        for idx, text in enumerate(decision_options, start=1)
    ]
    return "\n".join(decision_lines) if decision_lines else ""


def append_system_announcement(
    context: Dict[str, Any],
    message: str,
    *,
    system_assumptions: str = "",
) -> None:
    """把 critique / retry 指示附加到 system_announcement。"""

    if context.get("system_announcement"):
        context["system_announcement"] += "\n\n" + message
    else:
        context["system_announcement"] = (
            f"{system_assumptions}\n\n{message}" if system_assumptions else message
        )


def build_structural_fallback_state(event: str, page_structure: Dict[str, Any]) -> Dict[str, Any]:
    """當 `<state_json>` 缺失時，建立保守可用的 fallback state。"""

    return {
        "character_goal": event or "",
        "character_emotion": "neutral",
        "world_constraint": "",
        "world_condition": "",
        "branch_trait": page_structure.get("branch_trait", ""),
        "branch_divergence": "none" if not page_structure.get("is_branch_start") else "diverged",
    }


def finalize_story_pages(story_path, full_story_path, pages: List[str]) -> str:
    """將頁面列表彙整為 full story 並寫入標準輸出。"""

    full_story_lines = [f"Page {idx}: {text}" for idx, text in enumerate(pages, start=1)]
    combined = "\n\n".join(full_story_lines)
    write_text_or_raise(story_path, combined)
    write_text_or_raise(full_story_path, combined)
    return combined
