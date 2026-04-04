#!/usr/bin/env python3
"""Archive boundary policy check.

This gate prevents active runtime/tooling code from depending on archive areas
(`backups/` and `research/`).
"""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence, Set


ARCHIVE_MODULE_ROOTS: Set[str] = {"backups", "research"}

RUNTIME_TARGETS: Sequence[str] = (
    "chief.py",
    "story.py",
    "image.py",
    "trans.py",
    "voice.py",
    "kg.py",
    "utils.py",
    "evaluator.py",
    "pipeline",
    "backends",
    "runtime",
    "observability",
    "story_core",
    "scripts",
)


@dataclass
class Violation:
    file: str
    line: int
    module: str
    statement: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "file": self.file,
            "line": self.line,
            "module": self.module,
            "statement": self.statement,
        }


@dataclass
class CheckSummary:
    scanned_files: int
    syntax_errors: List[str]
    violations: List[Violation]

    @property
    def ok(self) -> bool:
        return not self.syntax_errors and not self.violations

    def to_dict(self) -> Dict[str, object]:
        return {
            "ok": self.ok,
            "scanned_files": self.scanned_files,
            "syntax_errors": self.syntax_errors,
            "violations": [v.to_dict() for v in self.violations],
        }


def _collect_python_files(workspace_root: Path) -> List[Path]:
    files: List[Path] = []
    for relative in RUNTIME_TARGETS:
        target = workspace_root / relative
        if target.is_file() and target.suffix == ".py":
            files.append(target)
            continue
        if target.is_dir():
            files.extend(sorted(target.rglob("*.py")))
    return files


def _extract_forbidden_imports(tree: ast.AST, file_rel: str) -> List[Violation]:
    violations: List[Violation] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                root = module_name.split(".", 1)[0]
                if root in ARCHIVE_MODULE_ROOTS:
                    violations.append(
                        Violation(
                            file=file_rel,
                            line=getattr(node, "lineno", 1),
                            module=module_name,
                            statement=f"import {module_name}",
                        )
                    )

        if isinstance(node, ast.ImportFrom):
            module_name = node.module or ""
            if not module_name:
                continue
            root = module_name.split(".", 1)[0]
            if root in ARCHIVE_MODULE_ROOTS:
                violations.append(
                    Violation(
                        file=file_rel,
                        line=getattr(node, "lineno", 1),
                        module=module_name,
                        statement=f"from {module_name} import ...",
                    )
                )

    return violations


def scan_archive_boundaries(workspace_root: Path) -> CheckSummary:
    python_files = _collect_python_files(workspace_root)
    syntax_errors: List[str] = []
    violations: List[Violation] = []

    for file_path in python_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            syntax_errors.append(f"{file_path.relative_to(workspace_root)}: read error ({exc})")
            continue

        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            syntax_errors.append(
                f"{file_path.relative_to(workspace_root)}:{exc.lineno or 1}: syntax error ({exc.msg})"
            )
            continue

        file_rel = str(file_path.relative_to(workspace_root)).replace("\\", "/")
        violations.extend(_extract_forbidden_imports(tree, file_rel))

    return CheckSummary(
        scanned_files=len(python_files),
        syntax_errors=syntax_errors,
        violations=violations,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check archive boundary policy")
    parser.add_argument("--workspace-root", default=".", help="Workspace root path")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when violations exist")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    summary = scan_archive_boundaries(workspace_root)

    if args.json:
        print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("=" * 72)
        print("Archive Boundary Policy Check")
        print("=" * 72)
        print(f"workspace: {workspace_root}")
        print(f"scanned python files: {summary.scanned_files}")

        if summary.syntax_errors:
            print("[WARN] syntax/read errors:")
            for item in summary.syntax_errors:
                print(f"  - {item}")

        if summary.violations:
            print("[WARN] forbidden archive imports detected:")
            for item in summary.violations:
                print(f"  - {item.file}:{item.line} -> {item.statement}")

        if summary.ok:
            print("[PASS] archive boundary policy check")
        else:
            print("[FAIL] archive boundary policy check")

    return 1 if (args.strict and not summary.ok) else 0


if __name__ == "__main__":
    raise SystemExit(main())