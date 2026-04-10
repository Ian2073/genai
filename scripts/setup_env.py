#!/usr/bin/env python3
"""Auto environment bootstrapper for this project.

Features:
- Detects GPU generation (RTX 40 / RTX 50) from nvidia-smi.
- Installs matching PyTorch profile automatically.
- Installs project dependencies from requirements.txt (filtered).
- Runs smoke tests (version checks + GPTQQuantizer init + run_experiment import).

Usage examples:
  python scripts/setup_env.py --env-path genai_env
  python scripts/setup_env.py --env-path genai_env_smoke --install-scope core
  python scripts/setup_env.py --gpu-series 50 --install-scope full
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional


@dataclass(frozen=True)
class TorchProfile:
    name: str
    torch: str
    torchvision: str
    torchaudio: str
    torchcodec: Optional[str]
    index_url: Optional[str]


# Notes:
# - RTX 50 (sm_120) should use cu128.
# - RTX 40 can run cu124/cu126/cu128; default to cu124 for wider legacy driver compatibility.
# - Override with --gpu-series if needed.
TORCH_PROFILES = {
    "50": TorchProfile(
        name="rtx50-cu128",
        torch="torch==2.8.0+cu128",
        torchvision="torchvision==0.23.0+cu128",
        torchaudio="torchaudio==2.8.0+cu128",
        torchcodec="torchcodec==0.7.0",
        index_url="https://download.pytorch.org/whl/cu128",
    ),
    "40": TorchProfile(
        name="rtx40-cu124",
        torch="torch==2.6.0+cu124",
        torchvision="torchvision==0.21.0+cu124",
        torchaudio="torchaudio==2.6.0+cu124",
        torchcodec="torchcodec==0.7.0",
        index_url="https://download.pytorch.org/whl/cu124",
    ),
    "cpu": TorchProfile(
        name="cpu",
        torch="torch==2.8.0",
        torchvision="torchvision==0.23.0",
        torchaudio="torchaudio==2.8.0",
        torchcodec=None,
        index_url="https://pypi.org/simple",
    ),
}

CORE_REQUIREMENTS = [
    "accelerate==1.12.0",
    "diffusers==0.35.1",
    "transformers==4.46.1",
    "tokenizers==0.20.3",
    "safetensors==0.4.3",
    "optimum==1.23.3",
    "optimum-quanto==0.2.7",
    "auto-gptq==0.7.1",
    "exllamav2==0.3.2",
    "peft==0.18.1",
    "numpy==1.26.4",
    "scipy==1.11.4",
    "pandas==1.5.3",
    "plotly==5.20.0",
    "networkx==2.8.8",
    "sentencepiece==0.1.99",
    "protobuf==3.20.3",
    "ftfy==6.3.1",
    "tqdm==4.66.5",
]

SKIP_REQUIREMENT_PREFIXES = (
    "torch==",
    "torchvision==",
    "torchaudio==",
    "torchcodec==",
    "--index-url",
    "--extra-index-url",
)

SPECIAL_REQUIREMENT_SPECS = {
    "en-core-web-sm": (
        "https://github.com/explosion/spacy-models/releases/download/"
        "en_core_web_sm-3.4.0/en_core_web_sm-3.4.0-py3-none-any.whl"
    ),
}

SPECIAL_NO_DEPS_REQUIREMENTS = {}

KNOWN_PIP_CHECK_WARNINGS = (
    "spacy-transformers 1.1.8 has requirement transformers<4.22.0,>=3.4.0",
)

BOOTSTRAP_PACKAGES = (
    "pip==26.0.1",
    "setuptools==80.9.0",
    "wheel==0.46.3",
)

# Apply these exact pins at the end to avoid dependency drift/overwrite.
CRITICAL_LOCK_PACKAGES = (
    "accelerate",
    "diffusers",
    "transformers",
    "tokenizers",
    "safetensors",
    "optimum",
    "auto-gptq",
    "exllamav2",
    "peft",
    "spacy",
    "spacy-experimental",
    "en-core-web-sm",
    "pyyaml",
)


def run(cmd: List[str], cwd: Optional[Path] = None) -> None:
    print("[cmd]", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def detect_gpu_series() -> str:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return "cpu"

    names = [line.strip() for line in output.splitlines() if line.strip()]
    if not names:
        return "cpu"

    primary = names[0].upper()
    # Match examples: RTX 5090, GeForce RTX 4090
    if re.search(r"RTX\s*50|RTX\s*5\d{3}", primary):
        return "50"
    if re.search(r"RTX\s*40|RTX\s*4\d{3}", primary):
        return "40"

    # Unknown NVIDIA GPU: prefer safer 40 profile, can be overridden.
    return "40"


def resolve_profile(gpu_series_arg: str) -> TorchProfile:
    if gpu_series_arg == "auto":
        detected = detect_gpu_series()
    else:
        detected = gpu_series_arg

    if detected not in TORCH_PROFILES:
        raise ValueError(f"Unsupported gpu-series: {detected}")

    profile = TORCH_PROFILES[detected]
    print(f"[info] GPU profile selected: {profile.name} ({detected})")
    return profile


def _run_capture(cmd: List[str]) -> str:
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    return out.strip()


def resolve_base_python(explicit: Optional[str]) -> str:
    if explicit:
        return explicit

    # Best case: already running on 3.11
    if sys.version_info.major == 3 and sys.version_info.minor == 11:
        return sys.executable

    # Windows launcher often has the right 3.11 interpreter.
    if os.name == "nt" and shutil.which("py"):
        try:
            py311 = _run_capture(["py", "-3.11", "-c", "import sys; print(sys.executable)"])
            if py311:
                return py311
        except Exception:
            pass

    # Conda fallback if active.
    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidate = Path(conda_prefix) / "python.exe"
        if candidate.exists():
            return str(candidate)

    # Common Windows conda locations fallback (when shell is not activated).
    if os.name == "nt":
        user_profile = os.environ.get("USERPROFILE")
        if user_profile:
            common = [
                Path(user_profile) / "miniconda3" / "envs" / "genai" / "python.exe",
                Path(user_profile) / "anaconda3" / "envs" / "genai" / "python.exe",
                Path(user_profile) / "miniforge3" / "envs" / "genai" / "python.exe",
            ]
            for candidate in common:
                if candidate.exists():
                    return str(candidate)

    # Last resort: current interpreter.
    return sys.executable


def create_venv(env_path: Path, base_python: str) -> Path:
    if not env_path.exists():
        run([base_python, "-m", "venv", str(env_path)])

    if os.name == "nt":
        py = env_path / "Scripts" / "python.exe"
    else:
        py = env_path / "bin" / "python"

    if not py.exists():
        raise FileNotFoundError(f"Python executable missing in venv: {py}")

    version = _run_capture([str(py), "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"])
    if version != "3.11":
        raise RuntimeError(
            "This project requires Python 3.11 for stable wheel resolution. "
            f"Detected venv Python: {version}. Use --base-python to point to Python 3.11."
        )

    run([str(py), "-m", "pip", "install", "--upgrade", *BOOTSTRAP_PACKAGES])
    return py


def write_filtered_requirements(requirements_path: Path, filtered_path: Path) -> None:
    lines_out: List[str] = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            lines_out.append(line)
            continue
        if stripped.startswith("#"):
            lines_out.append(line)
            continue
        if stripped.startswith(SKIP_REQUIREMENT_PREFIXES):
            continue
        name = stripped.split("==", 1)[0].strip().lower()
        if name in SPECIAL_REQUIREMENT_SPECS:
            continue
        if name in SPECIAL_NO_DEPS_REQUIREMENTS:
            continue
        lines_out.append(line)

    filtered_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")


def install_torch_profile(py: Path, profile: TorchProfile) -> None:
    cmd = [
        str(py),
        "-m",
        "pip",
        "install",
        profile.torch,
        profile.torchvision,
        profile.torchaudio,
    ]
    if profile.index_url:
        cmd.extend(["--index-url", profile.index_url])
    run(cmd)

    if profile.torchcodec:
        try:
            run([str(py), "-m", "pip", "install", profile.torchcodec])
        except subprocess.CalledProcessError:
            print(
                "[warn] Failed to install pinned torchcodec package "
                f"({profile.torchcodec}); retrying with latest available torchcodec."
            )
            run([str(py), "-m", "pip", "install", "torchcodec"])


def install_core_scope(py: Path) -> None:
    run([str(py), "-m", "pip", "install", *CORE_REQUIREMENTS])


def install_full_scope(py: Path, requirements_path: Path, workspace_root: Path) -> None:
    filtered = workspace_root / ".requirements.filtered.txt"
    write_filtered_requirements(requirements_path, filtered)
    try:
        run([str(py), "-m", "pip", "install", "-r", str(filtered)])
        for spec in SPECIAL_NO_DEPS_REQUIREMENTS.values():
            run([str(py), "-m", "pip", "install", "--no-deps", spec])
        for spec in SPECIAL_REQUIREMENT_SPECS.values():
            run([str(py), "-m", "pip", "install", spec])
    finally:
        if filtered.exists():
            filtered.unlink()


def run_pip_check(py: Path) -> None:
    cmd = [str(py), "-m", "pip", "check"]
    print("[cmd]", " ".join(cmd))
    proc = subprocess.run(
        cmd,
        check=False,
        text=True,
        capture_output=True,
    )
    output = (proc.stdout or "").strip()
    error = (proc.stderr or "").strip()

    # pip check uses exit code to indicate whether broken requirements exist.
    # Keep success output (e.g. "No broken requirements found.") as a pass.
    if proc.returncode == 0:
        if output:
            print(output)
        if error:
            print(error)
        return

    known_lines: List[str] = []
    unexpected_lines: List[str] = []
    for line in [line.strip() for line in output.splitlines() if line.strip()]:
        if any(known in line for known in KNOWN_PIP_CHECK_WARNINGS):
            known_lines.append(line)
        else:
            unexpected_lines.append(line)

    if error:
        print(error)
    if unexpected_lines:
        print("\n".join(unexpected_lines))
        raise subprocess.CalledProcessError(proc.returncode or 1, cmd)
    if known_lines:
        print("[warn] Accepted known pip check warnings:")
        print("\n".join(known_lines))
    elif output:
        print(output)


def clear_exllamav2_jit_cache(py: Path) -> None:
    """Clear stale torch extension artifacts for exllamav2.

    On Windows, old object files under torch_extensions can remain after
    MSVC toolset changes and later cause unresolved STL symbols at link time.
    Clearing this cache during environment rebuild avoids that failure mode.
    """

    code = (
        "from torch.utils.cpp_extension import _get_build_directory; "
        "print(_get_build_directory('exllamav2_ext', False))"
    )
    try:
        output = subprocess.check_output(
            [str(py), "-c", code],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception as exc:
        print(f"[warn] Unable to locate exllamav2 torch extension cache: {exc}")
        return

    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        print("[info] exllamav2 torch extension cache path not reported; skip cleanup.")
        return

    cache_dir = Path(lines[-1])
    cache_dir_str = str(cache_dir).lower().replace("\\", "/")
    if "torch_extensions" not in cache_dir_str or cache_dir.name != "exllamav2_ext":
        print(f"[warn] Unexpected exllamav2 cache path: {cache_dir}; skip cleanup for safety.")
        return

    if not cache_dir.exists():
        print(f"[info] exllamav2 cache not found (already clean): {cache_dir}")
        return

    try:
        shutil.rmtree(cache_dir)
        print(f"[info] Cleared stale exllamav2 JIT cache: {cache_dir}")
    except Exception as exc:
        print(f"[warn] Failed to clear exllamav2 JIT cache at {cache_dir}: {exc}")


def parse_exact_pins_from_requirements(requirements_path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("--"):
            continue
        match = re.match(r"^([A-Za-z0-9_.-]+)==(.+)$", line)
        if not match:
            continue
        name = match.group(1).strip().lower()
        version = match.group(2).strip()
        pins[name] = version
    return pins


def parse_exact_pins_from_specs(specs: Iterable[str]) -> dict[str, str]:
    pins: dict[str, str] = {}
    for spec in specs:
        match = re.match(r"^([A-Za-z0-9_.-]+)==(.+)$", spec.strip())
        if not match:
            continue
        name = match.group(1).strip().lower()
        version = match.group(2).strip()
        pins[name] = version
    return pins


def enforce_and_verify_exact_pins(py: Path, exact_pins: dict[str, str]) -> None:
    if not exact_pins:
        return

    lock_specs = [f"{name}=={version}" for name, version in sorted(exact_pins.items())]
    run([str(py), "-m", "pip", "install", "--upgrade", "--no-deps", *lock_specs])

    verify_code = "\n".join(
        [
            "import json",
            "from importlib.metadata import version",
            f"expected = json.loads({json.dumps(json.dumps(exact_pins))})",
            "mismatch = []",
            "for pkg, want in expected.items():",
            "    got = version(pkg)",
            "    if got != want:",
            "        mismatch.append(f'{pkg} expected {want}, got {got}')",
            "print('version-lock-ok' if not mismatch else '\\n'.join(mismatch))",
            "raise SystemExit(1 if mismatch else 0)",
        ]
    )
    run([str(py), "-c", verify_code])


def run_smoke_checks(py: Path, workspace_root: Path) -> None:
    run(
        [
            str(py),
            "-c",
            (
                "import torch; "
                "from importlib.metadata import version; "
                "print('torch', torch.__version__, 'cuda_available', torch.cuda.is_available()); "
                "print('transformers', version('transformers')); "
                "print('optimum', version('optimum')); "
                "print('auto-gptq', version('auto-gptq'))"
            ),
        ],
        cwd=workspace_root,
    )

    run(
        [
            str(py),
            "-c",
            "from optimum.gptq.quantizer import GPTQQuantizer; GPTQQuantizer(bits=4); print('GPTQQuantizer init OK')",
        ],
        cwd=workspace_root,
    )

    run(
        [
            str(py),
            "-c",
            "import scripts.run_experiment as run_experiment; print('scripts.run_experiment import OK')",
        ],
        cwd=workspace_root,
    )

    run(
        [
            str(py),
            "-c",
            (
                "import spacy; "
                "assert spacy.util.is_package('en_core_web_sm'), 'Missing spaCy model: en_core_web_sm'; "
                "print('spaCy evaluator model OK: en_core_web_sm')"
            ),
        ],
        cwd=workspace_root,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-setup environment with GPU-aware torch profile.")
    parser.add_argument("--env-path", type=Path, default=Path("genai_env"), help="Path to venv folder")
    parser.add_argument("--requirements", type=Path, default=Path("requirements.txt"), help="requirements file path")
    parser.add_argument(
        "--install-scope",
        choices=["full", "core"],
        default="full",
        help="Install full requirements or core-only smoke set",
    )
    parser.add_argument(
        "--gpu-series",
        choices=["auto", "40", "50", "cpu"],
        default="auto",
        help="GPU profile selection; auto uses nvidia-smi detection",
    )
    parser.add_argument("--skip-smoke", action="store_true", help="Skip smoke import tests")
    parser.add_argument(
        "--base-python",
        default=None,
        help="Path to Python executable used to create the venv (recommended: Python 3.11)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workspace_root = Path(__file__).resolve().parents[1]

    req_path = args.requirements
    if not req_path.is_absolute():
        req_path = workspace_root / req_path
    if not req_path.exists():
        raise FileNotFoundError(f"Requirements file not found: {req_path}")

    env_path = args.env_path
    if not env_path.is_absolute():
        env_path = workspace_root / env_path

    profile = resolve_profile(args.gpu_series)
    base_python = resolve_base_python(args.base_python)
    print(f"[info] Base Python for venv: {base_python}")
    py = create_venv(env_path, base_python)

    install_torch_profile(py, profile)

    if args.install_scope == "full":
        install_full_scope(py, req_path, workspace_root)
        req_pins = parse_exact_pins_from_requirements(req_path)
        critical_pins = {
            name: req_pins[name] for name in CRITICAL_LOCK_PACKAGES if name in req_pins
        }
    else:
        install_core_scope(py)
        core_pins = parse_exact_pins_from_specs(CORE_REQUIREMENTS)
        critical_pins = {
            name: core_pins[name] for name in CRITICAL_LOCK_PACKAGES if name in core_pins
        }

    enforce_and_verify_exact_pins(py, critical_pins)

    clear_exllamav2_jit_cache(py)

    run_pip_check(py)

    if not args.skip_smoke:
        run_smoke_checks(py, workspace_root)

    print("\n[done] Environment setup completed successfully.")
    print(f"[done] Venv path: {env_path}")


if __name__ == "__main__":
    main()
