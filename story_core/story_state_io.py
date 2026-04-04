"""Story pipeline 的 page structure / state snapshot I/O 工具。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from utils import write_json_or_raise


def structure_path(story_draft_path: Path, idx: int) -> Path:
    """回傳指定頁面的 structure JSON 路徑。"""

    return story_draft_path.parent / f"page_{idx}_struct.json"


def write_page_structure(story_draft_path: Path, idx: int, structure: Dict[str, Any]) -> None:
    """寫入 page structure。"""

    write_json_or_raise(structure_path(story_draft_path, idx), structure)


def read_page_structure(story_draft_path: Path, idx: int) -> Optional[Dict[str, Any]]:
    """讀取 page structure。"""

    path = structure_path(story_draft_path, idx)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def extract_state_snapshot(plan_text: str, *, logger=None) -> Optional[Dict[str, Any]]:
    """從 plan 文字中提取 `<state_json>` 區塊。"""

    if not plan_text:
        return None

    content = None
    match = re.search(r"<state_json>(.*?)</state_json>", plan_text, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
    else:
        match_open = re.search(r"<state_json>(.*)", plan_text, re.DOTALL | re.IGNORECASE)
        if match_open:
            content = match_open.group(1)

    if not content:
        return None

    json_match = re.search(r"(\{.*\})", content, re.DOTALL)
    if not json_match:
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start : end + 1]
        else:
            return None
    else:
        content = json_match.group(1)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        if logger:
            logger.warning("Failed to decode JSON from <state_json> block.")
        return None


def write_state_snapshot(story_draft_path: Path, idx: int, snapshot: Dict[str, Any]) -> None:
    """寫入每頁 state snapshot。"""

    state_path = story_draft_path.parent / f"page_{idx}_state.json"
    write_json_or_raise(state_path, snapshot)
