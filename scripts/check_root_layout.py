#!/usr/bin/env python3
"""Root layout policy check for keeping workspace structure clean.

This script enforces a lightweight allowlist for top-level files/folders.
It is intended for refactor gates, not for strict security controls.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set


ALLOWED_ROOT_FILES: Set[str] = {
    ".dockerignore",
    ".gitignore",
    "README.md",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "system_config.json",
    "Build_GenAI.bat",
    "Build_GenAI_Docker.bat",
    "Build_GenAI_DevTools.bat",
    "Start_GenAI.bat",
    "Start_GenAI_Docker.bat",
    "chief.py",
    "story.py",
    "image.py",
    "trans.py",
    "voice.py",
    "kg.py",
    "utils.py",
}

ALLOWED_ROOT_DIRS: Set[str] = {
    ".git",
    ".vscode",
    "__pycache__",
    "backends",
    "backups",
    "docs",
    "evaluation",
    "genai_env",
    "logs",
    "models",
    "observability",
    "output",
    "pipeline",
    "prompts",
    "reports",
    "runs",
    "runtime",
    "scripts",
    "story_core",
}

DISALLOWED_LEGACY_ROOT_NAMES: Set[str] = {
    "paper",
}


@dataclass
class CheckSummary:
    unexpected_files: List[str]
    unexpected_dirs: List[str]
    legacy_root_hits: List[str]

    @property
    def ok(self) -> bool:
        return not self.unexpected_files and not self.unexpected_dirs and not self.legacy_root_hits

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "unexpected_files": self.unexpected_files,
            "unexpected_dirs": self.unexpected_dirs,
            "legacy_root_hits": self.legacy_root_hits,
        }


def scan_root(workspace_root: Path) -> CheckSummary:
    unexpected_files: List[str] = []
    unexpected_dirs: List[str] = []
    legacy_root_hits: List[str] = []

    for entry in sorted(workspace_root.iterdir(), key=lambda p: p.name.lower()):
        name = entry.name

        if name in DISALLOWED_LEGACY_ROOT_NAMES:
            legacy_root_hits.append(name)

        if entry.is_file():
            if name not in ALLOWED_ROOT_FILES:
                unexpected_files.append(name)
            continue

        if entry.is_dir():
            if name not in ALLOWED_ROOT_DIRS:
                unexpected_dirs.append(name)

    return CheckSummary(
        unexpected_files=unexpected_files,
        unexpected_dirs=unexpected_dirs,
        legacy_root_hits=legacy_root_hits,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check root layout policy")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when violations exist")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    summary = scan_root(workspace_root)

    if args.json:
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("=" * 72)
        print("Root Layout Policy Check")
        print("=" * 72)
        print(f"workspace: {workspace_root}")

        if summary.unexpected_files:
            print("[WARN] unexpected root files:")
            for name in summary.unexpected_files:
                print(f"  - {name}")

        if summary.unexpected_dirs:
            print("[WARN] unexpected root dirs:")
            for name in summary.unexpected_dirs:
                print(f"  - {name}")

        if summary.legacy_root_hits:
            print("[WARN] legacy root names detected:")
            for name in summary.legacy_root_hits:
                print(f"  - {name}")

        if summary.ok:
            print("[PASS] root layout policy check")
        else:
            print("[FAIL] root layout policy check")

    return 1 if (args.strict and not summary.ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())
