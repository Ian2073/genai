#!/usr/bin/env python3
"""一鍵營運管線：validate + report + ops dashboard。"""

from __future__ import annotations

import argparse
import subprocess
import sys


def _run_step(command: list[str], name: str) -> int:
    print(f"[pipeline] running: {name}")
    print(f"[pipeline] cmd: {' '.join(command)}")
    result = subprocess.run(command)
    if result.returncode != 0:
        print(f"[pipeline] failed: {name} (code={result.returncode})")
        return result.returncode
    print(f"[pipeline] done: {name}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ops pipeline for governance-oriented quality checks.")
    parser.add_argument("--evaluated-dir", default="output", help="Evaluated stories directory (generation output root).")
    parser.add_argument("--with-synthetic", action="store_true", help="Run synthetic tests in validate stage.")
    parser.add_argument("--report-dir", default="reports/evaluation", help="Reports directory.")
    parser.add_argument("--skip-report", action="store_true", help="Skip scripts/report.py step.")
    args = parser.parse_args()

    py = sys.executable

    validate_cmd = [py, "-m", "evaluation.scripts.validate", "--evaluated-dir", args.evaluated_dir]
    if args.with_synthetic:
        validate_cmd.append("--synthetic")

    steps = [
        (validate_cmd, "validate"),
    ]

    if not args.skip_report:
        steps.append(([
            py,
            "-m",
            "evaluation.scripts.report",
            "--roots",
            args.evaluated_dir,
            "--output-dir",
            args.report_dir,
        ], "report"))

    steps.append(
        (
            [
                py,
                "-m",
                "evaluation.scripts.ops_dashboard",
                "--roots",
                args.evaluated_dir,
                "--output",
                f"{args.report_dir}/ops_dashboard.json",
            ],
            "ops_dashboard",
        )
    )

    for command, name in steps:
        code = _run_step(command, name)
        if code != 0:
            return code

    print("[pipeline] all steps completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
