"""Pipeline package exports for orchestration entrypoints.

Keep package import light so submodules can be imported independently without
pulling the whole orchestration stack into memory.
"""

from __future__ import annotations

__all__ = [
    "ChiefOptions",
    "ChiefRunner",
    "DEFAULT_CHIEF_OPTIONS",
    "create_story_root",
    "generate_story_id",
    "main",
    "resolve_options",
]


def __getattr__(name: str):
    if name in {"main", "resolve_options"}:
        from .entry import main, resolve_options

        return {
            "main": main,
            "resolve_options": resolve_options,
        }[name]
    if name in {"DEFAULT_CHIEF_OPTIONS", "ChiefOptions"}:
        from .options import DEFAULT_CHIEF_OPTIONS, ChiefOptions

        return {
            "DEFAULT_CHIEF_OPTIONS": DEFAULT_CHIEF_OPTIONS,
            "ChiefOptions": ChiefOptions,
        }[name]
    if name == "ChiefRunner":
        from .chief_runner import ChiefRunner

        return ChiefRunner
    if name in {"generate_story_id", "create_story_root"}:
        from story import create_story_root, generate_story_id

        return {
            "generate_story_id": generate_story_id,
            "create_story_root": create_story_root,
        }[name]
    raise AttributeError(f"module 'pipeline' has no attribute {name!r}")
