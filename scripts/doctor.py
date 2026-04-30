#!/usr/bin/env python3
"""Runtime environment diagnostics for this project.

This script checks Python, NVIDIA driver visibility, PyTorch CUDA readiness,
key package versions, and required model directories.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import List, Optional, Tuple

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))


@dataclass
class CheckResult:
    level: str  # PASS, WARN, FAIL
    title: str
    detail: str


KEY_PACKAGES = [
    "transformers",
    "optimum",
    "auto-gptq",
    "exllamav2",
    "diffusers",
    "TTS",
    "sentencepiece",
    "fastapi",
    "fastcoref",
    "pydantic",
    "ultralytics",
]


def _run_capture(cmd: List[str]) -> Tuple[int, str]:
    try:
        output = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
        return 0, output.strip()
    except subprocess.CalledProcessError as exc:
        return exc.returncode, (exc.output or "").strip()
    except Exception as exc:  # pragma: no cover
        return 1, str(exc)


def _pkg_version(name: str) -> Optional[str]:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return None


def _parse_version_tuple(version_text: Optional[str]) -> Tuple[int, int, int]:
    if not version_text:
        return (0, 0, 0)
    parts = (version_text.split(".") + ["0", "0", "0"])[:3]
    numbers = []
    for part in parts:
        digits = []
        for ch in part:
            if ch.isdigit():
                digits.append(ch)
            else:
                break
        numbers.append(int("".join(digits) or "0"))
    return tuple(numbers)  # type: ignore[return-value]


def check_python() -> CheckResult:
    major, minor, patch = sys.version_info[:3]
    detail = f"Python {major}.{minor}.{patch} ({sys.executable})"
    if (major, minor) != (3, 11):
        return CheckResult(
            "WARN",
            "Python version",
            detail + " | Recommended: Python 3.11.x for stable wheel resolution.",
        )
    return CheckResult("PASS", "Python version", detail)


def check_nvidia_smi() -> Tuple[Optional[CheckResult], List[str], Optional[str]]:
    if shutil.which("nvidia-smi") is None:
        return (
            CheckResult(
                "WARN",
                "NVIDIA driver visibility",
                "nvidia-smi not found in PATH. If this is a GPU machine, install/update NVIDIA driver.",
            ),
            [],
            None,
        )

    rc_driver, driver_out = _run_capture(
        ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"]
    )
    rc_name, gpu_out = _run_capture(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])

    if rc_driver != 0 or rc_name != 0:
        return (
            CheckResult(
                "FAIL",
                "NVIDIA driver visibility",
                "nvidia-smi is present but query failed. Check driver installation and reboot.",
            ),
            [],
            None,
        )

    gpu_names = [line.strip() for line in gpu_out.splitlines() if line.strip()]
    driver_versions = [line.strip() for line in driver_out.splitlines() if line.strip()]
    driver = driver_versions[0] if driver_versions else None

    if not gpu_names:
        return (
            CheckResult(
                "WARN",
                "NVIDIA GPU detection",
                "No GPU listed by nvidia-smi.",
            ),
            [],
            driver,
        )

    detail = f"Detected GPUs: {', '.join(gpu_names)}"
    if driver:
        detail += f" | Driver: {driver}"
    return (CheckResult("PASS", "NVIDIA GPU detection", detail), gpu_names, driver)


def check_torch(expect_cuda: bool, gpu_names: List[str]) -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        import torch  # type: ignore
    except Exception as exc:
        results.append(
            CheckResult("FAIL", "PyTorch import", f"Failed to import torch: {exc}")
        )
        return results

    torch_ver = getattr(torch, "__version__", "unknown")
    torch_cuda_build = getattr(torch.version, "cuda", None)
    cuda_ok = bool(torch.cuda.is_available())
    device_count = torch.cuda.device_count() if cuda_ok else 0

    detail = (
        f"torch={torch_ver}, torch.version.cuda={torch_cuda_build}, "
        f"cuda_available={cuda_ok}, device_count={device_count}"
    )
    results.append(CheckResult("PASS", "PyTorch runtime", detail))

    if expect_cuda and gpu_names and not cuda_ok:
        results.append(
            CheckResult(
                "FAIL",
                "CUDA runtime readiness",
                "GPU detected by nvidia-smi but torch.cuda.is_available() is False. "
                "Most common causes: mismatched torch CUDA wheel vs driver, missing runtime libraries, wrong Python env.",
            )
        )
    elif expect_cuda and cuda_ok:
        names = [torch.cuda.get_device_name(i) for i in range(device_count)]
        results.append(
            CheckResult("PASS", "CUDA runtime readiness", f"Usable CUDA devices: {', '.join(names)}")
        )
    elif not expect_cuda and not cuda_ok:
        results.append(
            CheckResult("PASS", "CUDA runtime readiness", "CPU-only mode expected and confirmed.")
        )
    else:
        results.append(
            CheckResult(
                "WARN",
                "CUDA runtime readiness",
                "CUDA is available but checks were configured for CPU-only mode.",
            )
        )

    return results


def check_key_packages() -> List[CheckResult]:
    found: List[str] = []
    missing: List[str] = []

    for pkg in KEY_PACKAGES:
        ver = _pkg_version(pkg)
        if ver is None:
            missing.append(pkg)
        else:
            found.append(f"{pkg}=={ver}")

    results: List[CheckResult] = []
    if found:
        results.append(CheckResult("PASS", "Installed key packages", ", ".join(found)))
    if missing:
        results.append(
            CheckResult(
                "WARN",
                "Missing key packages",
                "Missing: " + ", ".join(missing),
            )
        )
    return results


def apply_safe_fixes(workspace_root: Path, *, install_missing_packages: bool) -> List[str]:
    """執行低風險自動修復。"""

    applied: List[str] = []

    required_dirs = [
        workspace_root / "output",
        workspace_root / "logs",
        workspace_root / "runs",
        workspace_root / "reports",
        workspace_root / "models",
    ]
    for folder in required_dirs:
        if not folder.exists():
            folder.mkdir(parents=True, exist_ok=True)
            applied.append(f"created directory: {folder}")

    if install_missing_packages:
        missing = [pkg for pkg in KEY_PACKAGES if _pkg_version(pkg) is None]
        if missing:
            cmd = [sys.executable, "-m", "pip", "install", *missing]
            rc, out = _run_capture(cmd)
            if rc == 0:
                applied.append("installed missing packages: " + ", ".join(missing))
            else:
                applied.append(
                    "package auto-install failed: "
                    + ", ".join(missing)
                    + f" | detail: {out[:240]}"
                )

    return applied


def check_model_dirs(workspace_root: Path) -> CheckResult:
    preferred_flux_schnell = workspace_root / "models" / "FLUX.1-schnell"
    preferred_text_model = workspace_root / "models" / "Qwen2.5-14B-Instruct-GPTQ-Int4"
    cpu_text_model = workspace_root / "models" / "Qwen3-8B"
    required_dirs = [
        workspace_root / "models" / "nllb-200-3.3B",
        workspace_root / "models" / "XTTS-v2",
    ]
    missing = [str(p.relative_to(workspace_root)) for p in required_dirs if not p.exists()]
    if not preferred_flux_schnell.exists():
        missing.append("models/FLUX.1-schnell")
    if not preferred_text_model.exists() and not cpu_text_model.exists():
        missing.append(
            "models/Qwen2.5-14B-Instruct-GPTQ-Int4 or models/Qwen3-8B (cpu-only)"
        )
    if missing:
        return CheckResult("WARN", "Model directories", "Missing: " + ", ".join(missing))

    detail = "All required model directories exist."
    if preferred_flux_schnell.exists():
        detail += " Preferred image model found: models/FLUX.1-schnell."
    if preferred_text_model.exists():
        detail += " Preferred text model found: models/Qwen2.5-14B-Instruct-GPTQ-Int4."
    elif cpu_text_model.exists():
        detail += " GPU primary text model missing, but CPU-only text model exists: models/Qwen3-8B."
    return CheckResult("PASS", "Model directories", detail)


def check_recommended_model_plan(workspace_root: Path) -> Optional[CheckResult]:
    try:
        from pipeline.model_plan import resolve_model_plan
        from pipeline.options import DEFAULT_CHIEF_OPTIONS
        from utils import ProjectPaths

        resolved = resolve_model_plan(DEFAULT_CHIEF_OPTIONS, ProjectPaths.discover(workspace_root))
    except Exception as exc:
        return CheckResult("WARN", "Recommended model plan", f"Failed to resolve runtime model plan: {exc}")

    if resolved is None:
        return CheckResult("WARN", "Recommended model plan", "Automatic model plan resolution is disabled.")

    detail = (
        f"Selected '{resolved.selected_plan}' from requested '{resolved.requested_plan}'. "
        f"Story model: {resolved.story_model or '<unchanged>'} "
        f"(quantization={resolved.story_quantization or 'none'}). "
        f"Hardware: {resolved.hardware.summary()}."
    )
    if resolved.notes:
        detail += " Notes: " + " | ".join(resolved.notes)
    return CheckResult("PASS", "Recommended model plan", detail)


def _detect_model_quant_method(model_dir: Path) -> Optional[str]:
    config_path = model_dir / "config.json"
    if not config_path.exists():
        return None
    try:
        config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    qcfg = config_data.get("quantization_config")
    if not isinstance(qcfg, dict):
        return None
    method = qcfg.get("quant_method") or qcfg.get("quantization_method")
    if isinstance(method, str):
        return method.lower()
    return None


def check_gptq_runtime(workspace_root: Path, expect_cuda: bool, gpu_names: List[str]) -> List[CheckResult]:
    results: List[CheckResult] = []
    gptq_model_dir = workspace_root / "models" / "Qwen2.5-14B-Instruct-GPTQ-Int4"
    q_method = _detect_model_quant_method(gptq_model_dir) if gptq_model_dir.exists() else None

    if not gptq_model_dir.exists():
        results.append(
            CheckResult(
                "WARN",
                "GPTQ model path",
                "models/Qwen2.5-14B-Instruct-GPTQ-Int4 not found. GPTQ path will be unavailable.",
            )
        )
        return results

    if q_method == "gptq":
        results.append(
            CheckResult(
                "PASS",
                "GPTQ model metadata",
                "Detected GPTQ quantized model config.",
            )
        )
    else:
        results.append(
            CheckResult(
                "WARN",
                "GPTQ model metadata",
                "Model exists but config quantization method is not clearly marked as gptq.",
            )
        )

    optimum_ver = _pkg_version("optimum")
    autogptq_ver = _pkg_version("auto-gptq")
    exllamav2_ver = _pkg_version("exllamav2")
    missing_runtime = []
    if optimum_ver is None:
        missing_runtime.append("optimum")
    if autogptq_ver is None:
        missing_runtime.append("auto-gptq")
    if exllamav2_ver is None:
        missing_runtime.append("exllamav2")

    if missing_runtime:
        results.append(
            CheckResult(
                "FAIL",
                "GPTQ Python runtime",
                "Missing runtime packages: " + ", ".join(missing_runtime),
            )
        )
    else:
        results.append(
            CheckResult(
                "PASS",
                "GPTQ Python runtime",
                f"optimum=={optimum_ver}, auto-gptq=={autogptq_ver}, exllamav2=={exllamav2_ver}",
            )
        )

    if expect_cuda and gpu_names:
        if shutil.which("nvidia-smi") is None:
            results.append(
                CheckResult("FAIL", "GPTQ CUDA runtime", "CUDA expected but nvidia-smi is unavailable.")
            )
        else:
            results.append(CheckResult("PASS", "GPTQ CUDA runtime", "NVIDIA runtime is visible."))

    if platform.system().lower().startswith("win"):
        tools_missing = []
        if shutil.which("cl") is None:
            tools_missing.append("cl.exe")
        if shutil.which("nvcc") is None:
            tools_missing.append("nvcc")
        if tools_missing:
            results.append(
                CheckResult(
                    "WARN",
                    "GPTQ build toolchain",
                    "Missing tools: "
                    + ", ".join(tools_missing)
                    + ". Some exllamav2 paths may fail on first-run JIT.",
                )
            )
        else:
            results.append(CheckResult("PASS", "GPTQ build toolchain", "cl.exe and nvcc found."))

    return results


def collect_results(workspace_root: Path, expect_cuda_mode: str) -> List[CheckResult]:
    results: List[CheckResult] = []
    results.append(check_python())

    nvidia_result, gpu_names, _driver = check_nvidia_smi()
    if nvidia_result is not None:
        results.append(nvidia_result)

    if expect_cuda_mode == "yes":
        expect_cuda = True
    elif expect_cuda_mode == "no":
        expect_cuda = False
    else:
        expect_cuda = bool(gpu_names)

    results.extend(check_torch(expect_cuda=expect_cuda, gpu_names=gpu_names))
    results.extend(check_key_packages())
    results.extend(check_gptq_runtime(workspace_root=workspace_root, expect_cuda=expect_cuda, gpu_names=gpu_names))
    results.append(check_model_dirs(workspace_root))
    plan_result = check_recommended_model_plan(workspace_root)
    if plan_result is not None:
        results.append(plan_result)
    return results


def print_results_block(results: List[CheckResult], title: str = "Results") -> Tuple[int, int]:
    fail_count = 0
    warn_count = 0

    print(f"\n{title}:")
    for item in results:
        print(f"[{item.level}] {item.title}: {item.detail}")
        if item.level == "FAIL":
            fail_count += 1
        elif item.level == "WARN":
            warn_count += 1

    print("\nSummary:")
    print(f"FAIL={fail_count}, WARN={warn_count}, TOTAL={len(results)}")
    return fail_count, warn_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Diagnose runtime and CUDA readiness.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root path",
    )
    parser.add_argument(
        "--expect-cuda",
        choices=["auto", "yes", "no"],
        default="auto",
        help="Whether CUDA is expected in this environment.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if WARN/FAIL is present.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply safe automatic fixes and rerun diagnosis.",
    )
    parser.add_argument(
        "--fix-packages",
        action="store_true",
        help="When used with --fix, install missing key Python packages automatically.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = args.workspace_root.resolve()

    print("=" * 72)
    print("GenAI Doctor")
    print("=" * 72)
    print(f"Platform: {platform.platform()}")
    print(f"Workspace: {workspace_root}")

    results = collect_results(workspace_root, args.expect_cuda)
    fail_count, warn_count = print_results_block(results, title="Results")

    if args.fix:
        print("\nApplying safe fixes...")
        applied = apply_safe_fixes(
            workspace_root,
            install_missing_packages=args.fix_packages,
        )
        if applied:
            for item in applied:
                print(f"[FIXED] {item}")
        else:
            print("No safe fixes were required.")

        results = collect_results(workspace_root, args.expect_cuda)
        fail_count, warn_count = print_results_block(results, title="Post-fix Results")

    if fail_count > 0:
        return 2
    if args.strict and warn_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
