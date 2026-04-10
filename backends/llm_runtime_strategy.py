"""LLM 模型能力、runtime readiness 與 selection policy。"""

from __future__ import annotations

import glob
import importlib.util
import json
import platform
import re
import shutil
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Dict, List, Optional


STATUS_PRIORITY = {
    "preferred": 0,
    "usable": 1,
    "degraded": 2,
    "blocked": 3,
}


@dataclass(frozen=True)
class CandidatePreset:
    path: Path
    source: str
    cuda_quantization: Optional[str]
    cpu_quantization: Optional[str]


@dataclass(frozen=True)
class ModelCandidate:
    path: Path
    requested_quantization: Optional[str]
    source: str


@dataclass
class ModelAssessment:
    candidate: ModelCandidate
    status: str
    effective_quantization: Optional[str]
    reasons: List[str]
    model_type: Optional[str]
    quant_method: Optional[str]


DEFAULT_MODEL_PRESETS = [
    CandidatePreset(
        path=Path("models/Qwen3-14B-AWQ"),
        source="preferred_qwen3_awq",
        cuda_quantization=None,
        cpu_quantization=None,
    ),
    CandidatePreset(
        path=Path("models/Qwen2.5-14B-Instruct-GPTQ-Int4"),
        source="preferred_gptq",
        cuda_quantization="gptq",
        cpu_quantization=None,
    ),
    CandidatePreset(
        path=Path("models/Qwen3-8B"),
        source="fallback_qwen3",
        cuda_quantization="4bit",
        cpu_quantization=None,
    ),
    CandidatePreset(
        path=Path("models/Qwen3.5-9B"),
        source="fallback_qwen35",
        cuda_quantization="4bit",
        cpu_quantization=None,
    ),
]


def _parse_version_tuple(version_text: Optional[str]) -> tuple[int, int, int]:
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


def _parse_msvc_toolset_from_path(path_text: str) -> Optional[tuple[int, int, int]]:
    match = re.search(r"[\\/]MSVC[\\/](\d+)\.(\d+)\.(\d+)[\\/]", path_text)
    if not match:
        return None
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def _parse_vs_major_from_path(path_text: str) -> Optional[int]:
    match = re.search(r"Microsoft Visual Studio[\\/](\d+)[\\/]", path_text)
    if not match:
        fallback = re.search(r"BuildTools(\d+)", path_text, re.IGNORECASE)
        if not fallback:
            return None
        return int(fallback.group(1))
    return int(match.group(1))


def _collect_windows_cl_candidates() -> List[str]:
    candidates: List[str] = []
    patterns = [
        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe",
        r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe",
        r"C:\Program Files (x86)\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
        r"C:\BuildTools*\VC\Tools\MSVC\*\bin\HostX64\x64\cl.exe",
        r"C:\BuildTools*\VC\Tools\MSVC\*\bin\Hostx64\x64\cl.exe",
    ]
    for pattern in patterns:
        for path_text in glob.glob(pattern):
            if Path(path_text).is_file():
                candidates.append(path_text)
    return sorted(set(candidates))


def _is_supported_msvc_for_jit(version: tuple[int, int, int], vs_major: Optional[int]) -> bool:
    if vs_major is not None and vs_major >= 18:
        return False
    if version[0] > 14:
        return False
    return True


def _assess_windows_host_compiler() -> tuple[str, Optional[str]]:
    candidates = _collect_windows_cl_candidates()
    if not candidates and shutil.which("cl") is None:
        return "missing", None

    supported: List[tuple[tuple[int, int, int], Optional[int], str]] = []
    unsupported: List[tuple[tuple[int, int, int], Optional[int], str]] = []
    for cl_path in candidates:
        version = _parse_msvc_toolset_from_path(cl_path)
        if version is None:
            continue
        vs_major = _parse_vs_major_from_path(cl_path)
        if _is_supported_msvc_for_jit(version, vs_major):
            supported.append((version, vs_major, cl_path))
        else:
            unsupported.append((version, vs_major, cl_path))

    if supported:
        version, vs_major, _ = max(supported, key=lambda item: item[0])
        return "supported", f"VS {vs_major if vs_major is not None else 'unknown'}, toolset {version[0]}.{version[1]}.{version[2]}"

    if unsupported:
        version, vs_major, _ = max(unsupported, key=lambda item: item[0])
        return "unsupported", f"VS {vs_major if vs_major is not None else 'unknown'}, toolset {version[0]}.{version[1]}.{version[2]}"

    # cl.exe exists but was not parseable from known Visual Studio layout.
    if shutil.which("cl") is not None:
        return "present_unknown", shutil.which("cl")
    return "missing", None


def read_model_config(model_path: Path) -> Dict[str, object]:
    """讀取模型 config.json。"""

    cfg_path = model_path / "config.json"
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def detect_model_quant_method(model_path: Path) -> Optional[str]:
    """從 config.json 偵測預量化方法。"""

    cfg = read_model_config(model_path)
    qcfg = cfg.get("quantization_config")
    if not isinstance(qcfg, dict):
        return None
    method = qcfg.get("quant_method") or qcfg.get("quantization_method")
    if isinstance(method, str):
        return method.lower()
    return None


def _assess_model_type_support(model_type: Optional[str]) -> tuple[str, List[str]]:
    """評估目前 transformers 對 model_type 的支援程度。"""

    if not model_type:
        return "usable", []
    if importlib.util.find_spec("transformers") is None:
        return "blocked", ["transformers package is missing"]

    try:
        import transformers
        from transformers.models.auto.configuration_auto import CONFIG_MAPPING
    except Exception as exc:
        return "blocked", [f"failed to inspect transformers model registry: {exc}"]

    transformers_ver = getattr(transformers, "__version__", None)
    if model_type in CONFIG_MAPPING:
        return "preferred", []

    legacy_aliases = {
        "qwen3": "qwen2",
        "qwen3_5": "qwen2",
        "phi4": "phi3",
    }
    alias_target = legacy_aliases.get(model_type)
    if alias_target and alias_target in CONFIG_MAPPING and _parse_version_tuple(transformers_ver) < (4, 51, 0):
        return (
            "degraded",
            [f"transformers=={transformers_ver or 'missing'} will use legacy {alias_target} fallback for {model_type}"],
        )

    return (
        "blocked",
        [f"transformers=={transformers_ver or 'missing'} does not recognize model_type '{model_type}'"],
    )


def normalize_quantization(quantization: Optional[str]) -> Optional[str]:
    """正規化量化字串。"""

    value = (quantization or "").strip().lower() or None
    if value == "none":
        return None
    return value


def build_candidate_pool(
    requested_model_path: Path,
    requested_quantization: Optional[str],
    *,
    device: str,
) -> List[ModelCandidate]:
    """建立模型候選池。"""

    candidates: List[ModelCandidate] = [
        ModelCandidate(
            path=requested_model_path,
            requested_quantization=normalize_quantization(requested_quantization),
            source="requested",
        )
    ]

    seen = {requested_model_path.resolve() if requested_model_path.exists() else requested_model_path}
    for preset in DEFAULT_MODEL_PRESETS:
        candidate_path = preset.path
        dedupe_key = candidate_path.resolve() if candidate_path.exists() else candidate_path
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        candidates.append(
            ModelCandidate(
                path=candidate_path,
                requested_quantization=(
                    preset.cuda_quantization if device.startswith("cuda") else preset.cpu_quantization
                ),
                source=preset.source,
            )
        )
    return candidates


def _escalate_status(current: str, new_status: str) -> str:
    return new_status if STATUS_PRIORITY[new_status] > STATUS_PRIORITY[current] else current


def _is_gptq_acceleration_unavailable(assessment: ModelAssessment) -> bool:
    if assessment.effective_quantization != "gptq":
        return False
    if not assessment.reasons:
        return False
    reasons_text = " | ".join(assessment.reasons).lower()
    indicators = (
        "unsupported host compiler",
        "missing build tools",
        "exllamav2 acceleration package missing",
        "nvcc",
        "cl.exe",
    )
    return any(indicator in reasons_text for indicator in indicators)


def _assessment_sort_key(assessment: ModelAssessment, candidates: List[ModelCandidate]) -> tuple[int, int]:
    return (STATUS_PRIORITY[assessment.status], candidates.index(assessment.candidate))


def assess_candidate(candidate: ModelCandidate, *, device: str) -> ModelAssessment:
    """評估單一模型候選的 runtime readiness。"""

    if not candidate.path.exists():
        return ModelAssessment(
            candidate=candidate,
            status="blocked",
            effective_quantization=normalize_quantization(candidate.requested_quantization),
            reasons=[f"model directory missing: {candidate.path}"],
            model_type=None,
            quant_method=None,
        )

    cfg = read_model_config(candidate.path)
    model_type = cfg.get("model_type") if isinstance(cfg.get("model_type"), str) else None
    quant_method = detect_model_quant_method(candidate.path)
    effective_quantization = normalize_quantization(candidate.requested_quantization)
    reasons: List[str] = []
    status = "preferred"

    if quant_method == "gptq":
        if effective_quantization not in {None, "gptq"}:
            reasons.append(
                f"model metadata is gptq-prequantized; requested quantization '{effective_quantization}' will be ignored"
            )
        effective_quantization = "gptq"

    if effective_quantization == "gptq" and quant_method != "gptq":
        return ModelAssessment(
            candidate=candidate,
            status="blocked",
            effective_quantization=effective_quantization,
            reasons=["requested GPTQ load, but model metadata is not marked as gptq"],
            model_type=model_type,
            quant_method=quant_method,
        )

    if effective_quantization in {"4bit", "8bit"} and not device.startswith("cuda"):
        return ModelAssessment(
            candidate=candidate,
            status="blocked",
            effective_quantization=effective_quantization,
            reasons=[f"quantization '{effective_quantization}' requires CUDA"],
            model_type=model_type,
            quant_method=quant_method,
        )

    if effective_quantization == "gptq":
        if not device.startswith("cuda"):
            return ModelAssessment(
                candidate=candidate,
                status="blocked",
                effective_quantization=effective_quantization,
                reasons=["GPTQ inference requires CUDA"],
                model_type=model_type,
                quant_method=quant_method,
            )
        missing_runtime = []
        if importlib.util.find_spec("optimum") is None:
            missing_runtime.append("optimum")
        if importlib.util.find_spec("auto_gptq") is None:
            missing_runtime.append("auto-gptq")
        if missing_runtime:
            return ModelAssessment(
                candidate=candidate,
                status="blocked",
                effective_quantization=effective_quantization,
                reasons=["missing runtime packages: " + ", ".join(missing_runtime)],
                model_type=model_type,
                quant_method=quant_method,
            )
        if importlib.util.find_spec("exllamav2") is None:
            status = _escalate_status(status, "usable")
            reasons.append("exllamav2 acceleration package missing; AutoGPTQ fallback may be slower")
        if platform.system().lower().startswith("win"):
            missing_tools: List[str] = []
            compiler_state, compiler_detail = _assess_windows_host_compiler()
            if compiler_state == "missing":
                missing_tools.append("cl.exe")
            elif compiler_state == "unsupported":
                status = _escalate_status(status, "usable")
                reasons.append(
                    "unsupported host compiler: "
                    + (compiler_detail or "unknown")
                    + " (exllamav2 JIT will be skipped; slower fallback can still work)"
                )
            if shutil.which("nvcc") is None:
                missing_tools.append("nvcc")
            if missing_tools:
                status = _escalate_status(status, "usable")
                reasons.append(
                    "missing build tools: "
                    + ", ".join(missing_tools)
                    + " (exllamav2 JIT may be unavailable, but slower fallback can still work)"
                )

    support_status, support_reasons = _assess_model_type_support(model_type)
    status = _escalate_status(status, support_status)
    reasons.extend(support_reasons)

    return ModelAssessment(
        candidate=candidate,
        status=status,
        effective_quantization=effective_quantization,
        reasons=reasons,
        model_type=model_type,
        quant_method=quant_method,
    )


def resolve_model_selection(
    requested_model_path: Path,
    requested_quantization: Optional[str],
    *,
    device: str,
) -> ModelAssessment:
    """依 candidate pool 與 runtime readiness 選出最佳模型。"""

    candidates = build_candidate_pool(
        requested_model_path,
        requested_quantization,
        device=device,
    )
    assessments = [assess_candidate(candidate, device=device) for candidate in candidates]

    # If requested GPTQ cannot use accelerated kernels on this host, prefer any available
    # non-GPTQ CUDA path to avoid very slow pseudo-fallback behavior.
    gptq_unavailable = any(_is_gptq_acceleration_unavailable(item) for item in assessments)
    if gptq_unavailable:
        alternatives = [
            item
            for item in assessments
            if item.effective_quantization != "gptq" and item.status != "blocked"
        ]
        if alternatives:
            alternatives.sort(key=lambda item: _assessment_sort_key(item, candidates))
            selected = alternatives[0]
            selected.reasons = list(selected.reasons) + [
                "requested GPTQ candidate was bypassed because accelerated GPTQ kernels are unavailable on this host"
            ]
            return selected

    assessments.sort(key=lambda item: _assessment_sort_key(item, candidates))
    return assessments[0]
