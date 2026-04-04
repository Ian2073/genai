#!/usr/bin/env python3
"""Phase 0 smoke gate for local project contracts.

This script validates the non-breaking entrypoint contract and optional runtime checks.
Run it inside the intended runtime environment (recommended: conda env `genai`).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Sequence


@dataclass
class StepResult:
    name: str
    ok: bool
    detail: str
    duration_sec: float


def run_command(name: str, cmd: Sequence[str], cwd: Path, timeout: int = 120) -> StepResult:
    start = time.perf_counter()
    try:
        completed = subprocess.run(
            list(cmd),
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        ok = completed.returncode == 0
        output = (completed.stdout or "").strip()
        tail = "\n".join(output.splitlines()[-12:]) if output else ""
        detail = f"exit={completed.returncode}"
        if tail:
            detail += f"\n{tail}"
        return StepResult(name=name, ok=ok, detail=detail, duration_sec=round(time.perf_counter() - start, 3))
    except subprocess.TimeoutExpired:
        return StepResult(
            name=name,
            ok=False,
            detail=f"timeout after {timeout}s",
            duration_sec=round(time.perf_counter() - start, 3),
        )


def check_dashboard(py: str, cwd: Path, port: int, timeout: int) -> StepResult:
    name = "dashboard_health"
    start = time.perf_counter()
    proc = None
    try:
        proc = subprocess.Popen(
            [py, "-m", "pipeline", "--dashboard", "--dashboard-no-open", "--dashboard-port", str(port)],
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        url = f"http://127.0.0.1:{port}/api/status"
        deadline = time.time() + timeout
        last_error = ""
        while time.time() < deadline:
            if proc.poll() is not None:
                output = ""
                if proc.stdout:
                    output = proc.stdout.read() or ""
                return StepResult(
                    name=name,
                    ok=False,
                    detail=f"dashboard process exited early (code={proc.returncode})\n{output[-1200:]}",
                    duration_sec=round(time.perf_counter() - start, 3),
                )
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:  # nosec B310 - local endpoint
                    body = resp.read().decode("utf-8", errors="replace")
                    payload = json.loads(body)
                    state = payload.get("runner", {}).get("state", "unknown")
                    return StepResult(
                        name=name,
                        ok=True,
                        detail=f"status endpoint reachable on :{port}, runner.state={state}",
                        duration_sec=round(time.perf_counter() - start, 3),
                    )
            except Exception as exc:  # noqa: BLE001
                last_error = str(exc)
                time.sleep(0.8)

        return StepResult(
            name=name,
            ok=False,
            detail=f"status endpoint not ready within {timeout}s, last_error={last_error}",
            duration_sec=round(time.perf_counter() - start, 3),
        )
    finally:
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Phase 0 smoke gate checks")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use")
    parser.add_argument("--workspace", default=".", help="Workspace root")
    parser.add_argument("--dashboard-port", type=int, default=8785, help="Temporary dashboard port for health check")
    parser.add_argument("--dashboard-timeout", type=int, default=30, help="Seconds to wait for dashboard readiness")
    parser.add_argument("--skip-dashboard", action="store_true", help="Skip dashboard health check")
    parser.add_argument("--skip-eval", action="store_true", help="Skip integrated evaluation checks")
    parser.add_argument("--skip-root-policy", action="store_true", help="Skip root layout policy check")
    parser.add_argument("--skip-archive-policy", action="store_true", help="Skip archive boundary policy check")
    parser.add_argument(
        "--run-functional",
        action="store_true",
        help="Run one minimal functional generation (slow; requires models/runtime ready)",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    cwd = Path(args.workspace).resolve()
    py = args.python

    steps: List[StepResult] = []
    steps.append(run_command("chief_help", [py, "chief.py", "--help"], cwd))
    steps.append(run_command("pipeline_help", [py, "-m", "pipeline", "--help"], cwd))
    steps.append(run_command("doctor_help", [py, "scripts/doctor.py", "--help"], cwd))
    if not args.skip_eval:
        steps.append(run_command("eval_help", [py, "evaluation/main.py", "--help"], cwd))
        steps.append(
            run_command(
                "eval_smoke",
                [
                    py,
                    "evaluation/main.py",
                    "--input",
                    "evaluation/fixtures/stories/Thumbelina",
                    "--aspects",
                    "readability",
                    "--branch",
                    "canonical",
                    "--post-process",
                    "none",
                ],
                cwd,
                timeout=900,
            )
        )
    if not args.skip_root_policy:
        steps.append(
            run_command(
                "root_layout_policy",
                [py, "scripts/check_root_layout.py", "--workspace-root", str(cwd), "--strict"],
                cwd,
            )
        )
    if not args.skip_archive_policy:
        steps.append(
            run_command(
                "archive_boundary_policy",
                [py, "scripts/check_archive_boundaries.py", "--workspace-root", str(cwd), "--strict"],
                cwd,
            )
        )

    if not args.skip_dashboard:
        steps.append(check_dashboard(py, cwd, args.dashboard_port, args.dashboard_timeout))

    if args.run_functional:
        steps.append(
            run_command(
                "functional_minimal",
                [
                    py,
                    "-m",
                    "pipeline",
                    "--count",
                    "1",
                    "--max-retries",
                    "0",
                    "--no-photo",
                    "--no-translation",
                    "--no-voice",
                    "--no-verify",
                ],
                cwd,
                timeout=1800,
            )
        )

    failed = [s for s in steps if not s.ok]
    summary = {
        "total": len(steps),
        "passed": len(steps) - len(failed),
        "failed": len(failed),
        "steps": [s.__dict__ for s in steps],
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("=" * 72)
        print("Phase 0 Smoke Gate")
        print("=" * 72)
        for step in steps:
            status = "PASS" if step.ok else "FAIL"
            print(f"[{status}] {step.name} ({step.duration_sec}s)")
            if step.detail:
                print(step.detail)
                print("-" * 72)
        print(f"RESULT: passed={summary['passed']} failed={summary['failed']} total={summary['total']}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
