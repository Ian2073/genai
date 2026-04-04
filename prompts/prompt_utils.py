"""Prompt/template helpers for the story pipeline.

This module keeps prompt-related concerns together:
- which template files exist
- how templates are rendered
- how chat-style prompt sections are loaded
- how model output is cleaned back into usable text

Keeping these helpers separate makes the main pipeline easier to read, especially
for students who want to understand prompt flow before reading model/runtime code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from string import Formatter
from typing import Any, Dict, List, Optional, Tuple, Union

from utils import read_text as read_text_file


PROMPT_FILES: Dict[str, str] = {
    "outline": "prompts/A2_story_outline.txt",
    "title": "prompts/A1_story_title.txt",
    "story_plan": "prompts/A3_a_story_plan.txt",
    "story_write": "prompts/A3_b_story_write.txt",
    "narration": "prompts/A4_story_narration.txt",
    "dialogue": "prompts/A5_story_dialogue.txt",
    "scene": "prompts/B5_scene_descriptions.txt",
    "pose": "prompts/C3_character_poses.txt",
    "cover": "prompts/B3_book_cover.txt",
}

PAGE_TEMPLATE = "page_{}.txt"

STEP_TAGS = {
    "outline": "<outline>",
    "title": "",
    "story_plan": "<plan>\n**Transition**: ",
    "story_write": "<story>",
    "narration": "<narration>",
    "dialogue": "<dialogue>",
    "scene": "<scene>",
    "pose": "<pose>",
    "cover": "<cover>",
}

EXTRACTION_TAGS = [tag for tag in list(STEP_TAGS.values()) + ["<story>"] if tag]

CHAT_SYSTEM_MARKER = "###SYSTEM"
CHAT_USER_MARKER = "###USER"
THINK_BLOCK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


@dataclass
class ChatPrompt:
    """Simple container for system/user prompt text."""

    system_prompt: str
    user_prompt: str

    def to_messages(self) -> List[Dict[str, str]]:
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
        ]


def _as_path(value: Union[str, Path]) -> Path:
    """Convert user input into a `Path` object."""
    return value if isinstance(value, Path) else Path(value)


def render_prompt(template: str, context: Dict[str, Any]) -> str:
    """Render a prompt template using Python format syntax."""

    class _FormatContext(dict):
        def __init__(self, data: Dict[str, Any]):
            self.data = data

        def __missing__(self, key: str) -> str:
            return ""

        def __getitem__(self, key: str) -> Any:
            value: Any = self.data
            for part in key.split("."):
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = getattr(value, part, None)
                if value is None:
                    return ""
            return value

    formatter = Formatter()
    return formatter.vformat(template, (), _FormatContext(context))


def load_template(path: Path) -> str:
    """Load a template from disk and fail loudly if it is missing."""
    content = read_text_file(path)
    if content is None:
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return content


@lru_cache(maxsize=None)
def _load_chat_sections(path_str: str) -> Tuple[str, str]:
    """Split a template into `###SYSTEM` and `###USER` sections."""
    path = Path(path_str)
    text = load_template(path)
    try:
        system_part = text.split(CHAT_SYSTEM_MARKER, 1)[1].split(CHAT_USER_MARKER, 1)[0].strip()
        user_part = text.split(CHAT_USER_MARKER, 1)[1].strip()
    except IndexError as exc:
        raise ValueError(
            f"Template format error in {path}: missing {CHAT_SYSTEM_MARKER} or {CHAT_USER_MARKER}"
        ) from exc
    return system_part, user_part


def load_step_prompts(
    template_path: Union[str, Path],
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Tuple[str, str]:
    """Load one prompt template and render both chat sections."""
    path = _as_path(template_path)
    system_template, user_template = _load_chat_sections(str(path.resolve()))
    render_context: Dict[str, Any] = dict(context or {})
    render_context.update(kwargs)
    filled_system = render_prompt(system_template, render_context)
    filled_user = render_prompt(user_template, render_context)
    return filled_system, filled_user


def _strip_page_prefix(text: str) -> str:
    """Remove leading `Page X:`/`Chapter X:` style prefixes conservatively."""
    if not text:
        return text
    pattern = r"^\s*(?:Page|Chapter)\s+\d+(?:[:\-\.]|\s*\n)\s*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE).strip()


def strip_hidden_thoughts(text: str) -> str:
    """Remove hidden thinking blocks and conversational wrappers from model output."""
    if not text:
        return text

    cleaned = THINK_BLOCK_PATTERN.sub("", text)
    cleaned = cleaned.replace("<think>", "").replace("</think>", "")

    conversational_prefixes = [
        r"^Okay, .+?(\n|$)",
        r"^Sure, .+?(\n|$)",
        r"^Here is (the|a) .+?(\n|$)",
        r"^Certainly.+?(\n|$)",
        r"^(Let's|Let me) (tackle|start|write|think|break).+?(\n|$)",
        r"^The user wants.+?(\n|$)",
        r"^The instructions (mention|say|ask).+?(\n|$)",
        r"^Based on the.+?(\n|$)",
        r"^For the title,.+?(\n|$)",
        r"^Wait, .+?(\n|$)",
        r"^Original user message.+?(\n|$)",
        r"^First, .+?(\n|$)",
        r"^Next, .+?(\n|$)",
        r"^I need to.+?(\n|$)",
        r"^Title:[\s]*",
        r"^Here is a title.+?(\n|$)",
        r"^Suggested Title:[\s]*",
        r"^Story Title:[\s]*",
        r"^(Okay|Sure|Alright|So), (I|we) need to.+?(\n\n|\n)",
        r"^Then grammar and flow.+?(\n|$)",
        r"^Also, the example.+?(\n|$)",
        r"^So the refined text.+?(\n|$)",
        r"^Refined Text:[\s]*",
        r"^Great choice! Here is.+?(\n|$)",
        r"^Here's the (story|outline|plan|segment).+?(\n|$)",
    ]

    for tag in EXTRACTION_TAGS:
        tag_name = tag.strip("<>")
        escaped_tag = re.escape(tag_name)
        tag_match = re.search(rf"<{escaped_tag}>(.*?)(?:</|$)", cleaned, re.DOTALL | re.IGNORECASE)
        if tag_match:
            cleaned = tag_match.group(1).strip()
            break

    cleaned = cleaned.strip()
    while True:
        original_len = len(cleaned)
        for pattern in conversational_prefixes:
            match = re.match(pattern, cleaned, re.IGNORECASE | re.DOTALL)
            if match:
                cleaned = cleaned[match.end() :].strip()

        page_prefix_match = re.match(r"^\s*(?:Page|Chapter)\s+\d+\s*[:\-\.]?\s*", cleaned, re.IGNORECASE)
        if page_prefix_match:
            cleaned = cleaned[page_prefix_match.end() :].strip()

        if len(cleaned) == original_len:
            break

    if cleaned.startswith('"') and cleaned.endswith('"'):
        cleaned = cleaned[1:-1].strip()

    return _strip_page_prefix(cleaned)


__all__ = [
    "CHAT_SYSTEM_MARKER",
    "CHAT_USER_MARKER",
    "ChatPrompt",
    "EXTRACTION_TAGS",
    "PAGE_TEMPLATE",
    "PROMPT_FILES",
    "STEP_TAGS",
    "THINK_BLOCK_PATTERN",
    "_load_chat_sections",
    "load_step_prompts",
    "load_template",
    "render_prompt",
    "strip_hidden_thoughts",
]
