"""Hardware-aware runtime model plan selection.

This module keeps model selection policy in one place so the project can move
between machines with different GPU/CPU budgets while staying predictable.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import logging
import shutil
import subprocess
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import psutil
except Exception:  # pragma: no cover - optional dependency guard
    psutil = None

try:
    import torch
except Exception:  # pragma: no cover - optional dependency guard
    torch = None

from .options import ChiefOptions, DEFAULT_CHIEF_OPTIONS
from utils import ProjectPaths


@dataclass(frozen=True)
class StoryModelOption:
    path: str
    model_name: str
    quantization: Optional[str]


@dataclass(frozen=True)
class ImageProfile:
    width: int
    height: int
    steps: int
    guidance: float
    skip_refiner: bool
    refiner_steps: Optional[int] = None


@dataclass(frozen=True)
class ImageModelSpec:
    path: str
    provider: str
    family: str
    label: str
    deprecated: bool = False
    supports_refiner: bool = False


@dataclass(frozen=True)
class ModelPlanSpec:
    key: str
    description: str
    story_candidates: Tuple[StoryModelOption, ...]
    image_profile: ImageProfile
    low_vram: bool
    translation_beam_size: int
    outline_candidates: int = 1
    title_candidates: int = 1
    key_page_candidates: int = 1
    pre_eval_profile: str = "balanced"
    story_device: str = "auto"
    translation_device: str = "auto"
    photo_device: str = "auto"
    voice_device: str = "auto"


@dataclass(frozen=True)
class HardwareProfile:
    accelerator: str
    gpu_names: Tuple[str, ...]
    gpu_vram_gb: float
    system_ram_gb: float
    gpu_count: int
    cuda_version: Optional[str]

    @property
    def has_cuda(self) -> bool:
        return self.accelerator == "cuda"

    def summary(self) -> str:
        gpu_text = ", ".join(self.gpu_names) if self.gpu_names else "none"
        return (
            f"accelerator={self.accelerator}, gpu_count={self.gpu_count}, "
            f"gpu_vram_gb={self.gpu_vram_gb:.1f}, system_ram_gb={self.system_ram_gb:.1f}, "
            f"cuda={self.cuda_version or 'n/a'}, gpus={gpu_text}"
        )


@dataclass(frozen=True)
class ResolvedModelPlan:
    requested_plan: str
    selected_plan: str
    description: str
    hardware: HardwareProfile
    story_model: Optional[Path]
    story_model_name: str
    story_quantization: Optional[str]
    image_base: Optional[Path]
    image_refiner: Optional[Path]
    image_profile: ImageProfile
    notes: Tuple[str, ...]

    def summary(self) -> str:
        parts = [
            f"plan={self.selected_plan}",
            self.description,
            f"story={self.story_model or '<unchanged>'}",
        ]
        if self.story_quantization:
            parts.append(f"quantization={self.story_quantization}")
        parts.append(self.hardware.summary())
        if self.notes:
            parts.append("notes=" + " | ".join(self.notes))
        return " | ".join(parts)


_TEXT_GPU_PRIMARY_CHAIN: Tuple[StoryModelOption, ...] = (
    StoryModelOption("Qwen2.5-14B-Instruct-GPTQ-Int4", "qwen2.5-14b-instruct-gptq-int4", "gptq"),
)

_TEXT_QUALITY_CHAIN: Tuple[StoryModelOption, ...] = _TEXT_GPU_PRIMARY_CHAIN

_TEXT_BALANCED_CHAIN: Tuple[StoryModelOption, ...] = _TEXT_GPU_PRIMARY_CHAIN

_TEXT_PORTABLE_CHAIN: Tuple[StoryModelOption, ...] = _TEXT_GPU_PRIMARY_CHAIN

_TEXT_CPU_CHAIN: Tuple[StoryModelOption, ...] = (
    StoryModelOption("Qwen3-8B", "qwen3-8b-instruct", None),
)

SUPPORTED_IMAGE_PROVIDERS: Tuple[str, ...] = ("diffusers_flux",)

IMAGE_MODEL_REGISTRY: Tuple[ImageModelSpec, ...] = (
    ImageModelSpec(
        path="FLUX.1-schnell",
        provider="diffusers_flux",
        family="flux_schnell",
        label="FLUX.1-schnell",
        supports_refiner=False,
    ),
)

MODEL_PLAN_SPECS: Dict[str, ModelPlanSpec] = {
    "quality": ModelPlanSpec(
        key="quality",
        description="Favor the strongest available story model and higher image fidelity.",
        story_candidates=_TEXT_QUALITY_CHAIN,
        image_profile=ImageProfile(width=1152, height=896, steps=16, guidance=5.0, skip_refiner=False, refiner_steps=6),
        low_vram=False,
        translation_beam_size=2,
        outline_candidates=3,
        title_candidates=3,
        key_page_candidates=2,
        pre_eval_profile="strict",
    ),
    "balanced": ModelPlanSpec(
        key="balanced",
        description="Balanced quality and portability for mainstream 12-16 GB GPUs.",
        story_candidates=_TEXT_BALANCED_CHAIN,
        image_profile=ImageProfile(width=1024, height=768, steps=12, guidance=4.6, skip_refiner=True, refiner_steps=4),
        low_vram=True,
        translation_beam_size=1,
        outline_candidates=2,
        title_candidates=2,
        key_page_candidates=2,
        pre_eval_profile="balanced",
    ),
    "portable": ModelPlanSpec(
        key="portable",
        description="Portable plan for tighter VRAM budgets while keeping all stages available.",
        story_candidates=_TEXT_PORTABLE_CHAIN,
        image_profile=ImageProfile(width=896, height=768, steps=9, guidance=4.0, skip_refiner=True, refiner_steps=3),
        low_vram=True,
        translation_beam_size=1,
        outline_candidates=1,
        title_candidates=1,
        key_page_candidates=1,
        pre_eval_profile="fast",
    ),
    "cpu": ModelPlanSpec(
        key="cpu",
        description="CPU-safe fallback. Throughput is lower, but behavior stays predictable.",
        story_candidates=_TEXT_CPU_CHAIN,
        image_profile=ImageProfile(width=768, height=768, steps=6, guidance=3.4, skip_refiner=True, refiner_steps=None),
        low_vram=True,
        translation_beam_size=1,
        outline_candidates=1,
        title_candidates=1,
        key_page_candidates=1,
        pre_eval_profile="fast",
        story_device="cpu",
        translation_device="cpu",
        photo_device="cpu",
        voice_device="cpu",
    ),
}

MODEL_PLAN_CHOICES: Tuple[str, ...] = ("auto", "quality", "balanced", "portable", "cpu", "off")


def _system_ram_gb() -> float:
    if psutil is not None:
        try:
            return float(psutil.virtual_memory().total) / (1024 ** 3)
        except Exception:
            pass
    return 0.0


def _query_gpu_from_torch() -> Tuple[List[str], float, int, Optional[str]]:
    if torch is None or not hasattr(torch, "cuda") or not torch.cuda.is_available():
        return [], 0.0, 0, None
    names: List[str] = []
    max_vram = 0.0
    try:
        count = int(torch.cuda.device_count())
    except Exception:
        count = 0
    for index in range(count):
        try:
            names.append(str(torch.cuda.get_device_name(index)))
            props = torch.cuda.get_device_properties(index)
            max_vram = max(max_vram, float(props.total_memory) / (1024 ** 3))
        except Exception:
            continue
    cuda_version = getattr(getattr(torch, "version", None), "cuda", None)
    return names, max_vram, count, cuda_version


def _query_gpu_from_nvidia_smi() -> Tuple[List[str], float, int]:
    if shutil.which("nvidia-smi") is None:
        return [], 0.0, 0
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.STDOUT,
        )
    except Exception:
        return [], 0.0, 0

    names: List[str] = []
    max_vram = 0.0
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [part.strip() for part in line.split(",")]
        if not parts:
            continue
        names.append(parts[0])
        if len(parts) >= 2:
            mem_text = parts[1].split()[0]
            try:
                max_vram = max(max_vram, float(mem_text) / 1024.0)
            except ValueError:
                pass
    return names, max_vram, len(names)


def detect_hardware_profile() -> HardwareProfile:
    names, vram_gb, gpu_count, cuda_version = _query_gpu_from_torch()
    torch_runtime_known = torch is not None
    accelerator = "cuda" if gpu_count > 0 else "cpu"
    if not names or not torch_runtime_known:
        smi_names, smi_vram_gb, smi_count = _query_gpu_from_nvidia_smi()
        if smi_names:
            if not names:
                names = smi_names
            vram_gb = max(vram_gb, smi_vram_gb)
            gpu_count = max(gpu_count, smi_count)
            if not torch_runtime_known:
                accelerator = "cuda"
    return HardwareProfile(
        accelerator=accelerator,
        gpu_names=tuple(names),
        gpu_vram_gb=float(vram_gb),
        system_ram_gb=_system_ram_gb(),
        gpu_count=int(gpu_count),
        cuda_version=cuda_version,
    )


def choose_plan_key(requested_plan: str, hardware: HardwareProfile) -> str:
    normalized = (requested_plan or "auto").strip().lower()
    if normalized in MODEL_PLAN_SPECS:
        return normalized
    if normalized in {"off", "none"}:
        return "off"

    if not hardware.has_cuda:
        return "cpu"
    if hardware.gpu_vram_gb >= 20.0 and hardware.system_ram_gb >= 48.0:
        return "quality"
    if hardware.gpu_vram_gb >= 14.0 and hardware.system_ram_gb >= 24.0:
        return "balanced"
    return "portable"


def _first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def _resolve_story_choice(
    models_dir: Path,
    story_candidates: Sequence[StoryModelOption],
) -> Tuple[Optional[Path], str, Optional[str], List[str]]:
    notes: List[str] = []
    for candidate in story_candidates:
        path = models_dir / candidate.path
        if path.exists():
            return path, candidate.model_name, candidate.quantization, notes
        notes.append(f"missing story model: {path}")
    return None, DEFAULT_CHIEF_OPTIONS.story_model_name, DEFAULT_CHIEF_OPTIONS.story_quantization, notes


def _resolve_image_base(
    models_dir: Path,
    *,
    plan_key: str,
    hardware: HardwareProfile,
) -> Tuple[Optional[Path], Tuple[str, ...]]:
    del plan_key, hardware
    image_base = models_dir / "FLUX.1-schnell"
    if image_base.exists():
        return image_base, tuple()
    return None, ("missing primary image model: models/FLUX.1-schnell",)


def classify_image_model(image_base: Optional[Path]) -> str:
    del image_base
    return "flux_schnell"


def classify_image_provider(image_base: Optional[Path]) -> str:
    del image_base
    return "diffusers_flux"


def tune_image_profile(
    image_profile: ImageProfile,
    image_base: Optional[Path],
    image_refiner: Optional[Path],
) -> Tuple[ImageProfile, Tuple[str, ...]]:
    del image_base, image_refiner
    tuned = replace(
        image_profile,
        steps=min(max(int(image_profile.steps), 1), 4),
        guidance=0.0,
        skip_refiner=True,
        refiner_steps=None,
    )
    notes: List[str] = []
    if tuned != image_profile:
        notes.append("FLUX.1-schnell is the only supported image model; using the fixed single-stage profile")
    return tuned, tuple(notes)


def resolve_image_defaults(
    requested_plan: str,
    *,
    models_dir: Path,
    hardware: Optional[HardwareProfile] = None,
) -> Tuple[str, Optional[Path], Optional[Path], ImageProfile, Tuple[str, ...]]:
    hw = hardware or detect_hardware_profile()
    plan_key = choose_plan_key(requested_plan, hw)
    spec = MODEL_PLAN_SPECS[plan_key]
    image_base, discovery_notes = _resolve_image_base(models_dir, plan_key=plan_key, hardware=hw)
    image_refiner = None
    tuned_profile, tune_notes = tune_image_profile(spec.image_profile, image_base, image_refiner)
    return plan_key, image_base, image_refiner, tuned_profile, tuple(list(discovery_notes) + list(tune_notes))


def _maybe_apply(
    current_value,
    default_value,
    planned_value,
):
    return planned_value if current_value == default_value else current_value


def resolve_model_plan(
    options: ChiefOptions,
    paths: ProjectPaths,
) -> Optional[ResolvedModelPlan]:
    requested_plan = getattr(options, "model_plan", "auto")
    if (requested_plan or "auto").strip().lower() in {"off", "none"}:
        return None

    hardware = detect_hardware_profile()
    plan_key = choose_plan_key(requested_plan, hardware)
    if plan_key == "off":
        return None
    spec = MODEL_PLAN_SPECS[plan_key]

    story_model, story_model_name, story_quantization, notes = _resolve_story_choice(
        paths.models_dir,
        spec.story_candidates,
    )
    _plan_key, image_base, image_refiner, image_profile, image_notes = resolve_image_defaults(
        plan_key,
        models_dir=paths.models_dir,
        hardware=hardware,
    )
    notes.extend(image_notes)

    if not hardware.has_cuda:
        notes.append("no CUDA runtime detected; CPU plan may be slow for story/image/translation stages")
        if hardware.gpu_names:
            notes.append("GPU hardware is visible, but the current Python runtime cannot use CUDA")

    return ResolvedModelPlan(
        requested_plan=requested_plan,
        selected_plan=plan_key,
        description=spec.description,
        hardware=hardware,
        story_model=story_model,
        story_model_name=story_model_name,
        story_quantization=story_quantization,
        image_base=image_base,
        image_refiner=image_refiner,
        image_profile=image_profile,
        notes=tuple(notes),
    )


def apply_model_plan(
    options: ChiefOptions,
    paths: ProjectPaths,
    *,
    logger: Optional[logging.Logger] = None,
) -> Tuple[ChiefOptions, Optional[ResolvedModelPlan]]:
    resolved = resolve_model_plan(options, paths)
    if resolved is None:
        return options, None

    spec = MODEL_PLAN_SPECS[resolved.selected_plan]
    image_profile = resolved.image_profile
    force_skip_refiner = image_profile.skip_refiner or resolved.image_refiner is None

    updated = replace(
        options,
        story_model=_maybe_apply(options.story_model, DEFAULT_CHIEF_OPTIONS.story_model, resolved.story_model or options.story_model),
        story_model_name=_maybe_apply(options.story_model_name, DEFAULT_CHIEF_OPTIONS.story_model_name, resolved.story_model_name),
        story_quantization=_maybe_apply(options.story_quantization, DEFAULT_CHIEF_OPTIONS.story_quantization, resolved.story_quantization),
        story_device=_maybe_apply(options.story_device, DEFAULT_CHIEF_OPTIONS.story_device, spec.story_device),
        translation_device=_maybe_apply(options.translation_device, DEFAULT_CHIEF_OPTIONS.translation_device, spec.translation_device),
        photo_device=_maybe_apply(options.photo_device, DEFAULT_CHIEF_OPTIONS.photo_device, spec.photo_device),
        voice_device=_maybe_apply(options.voice_device, DEFAULT_CHIEF_OPTIONS.voice_device, spec.voice_device),
        low_vram=_maybe_apply(options.low_vram, DEFAULT_CHIEF_OPTIONS.low_vram, spec.low_vram),
        photo_width=_maybe_apply(options.photo_width, DEFAULT_CHIEF_OPTIONS.photo_width, image_profile.width),
        photo_height=_maybe_apply(options.photo_height, DEFAULT_CHIEF_OPTIONS.photo_height, image_profile.height),
        photo_steps=_maybe_apply(options.photo_steps, DEFAULT_CHIEF_OPTIONS.photo_steps, image_profile.steps),
        photo_guidance=_maybe_apply(options.photo_guidance, DEFAULT_CHIEF_OPTIONS.photo_guidance, image_profile.guidance),
        photo_skip_refiner=_maybe_apply(options.photo_skip_refiner, DEFAULT_CHIEF_OPTIONS.photo_skip_refiner, force_skip_refiner),
        photo_refiner_steps=_maybe_apply(options.photo_refiner_steps, DEFAULT_CHIEF_OPTIONS.photo_refiner_steps, image_profile.refiner_steps),
        translation_beam_size=_maybe_apply(options.translation_beam_size, DEFAULT_CHIEF_OPTIONS.translation_beam_size, spec.translation_beam_size),
        pre_eval_profile=_maybe_apply(options.pre_eval_profile, DEFAULT_CHIEF_OPTIONS.pre_eval_profile, spec.pre_eval_profile),
        story_outline_candidates=_maybe_apply(options.story_outline_candidates, DEFAULT_CHIEF_OPTIONS.story_outline_candidates, spec.outline_candidates),
        story_title_candidates=_maybe_apply(options.story_title_candidates, DEFAULT_CHIEF_OPTIONS.story_title_candidates, spec.title_candidates),
        story_key_page_candidates=_maybe_apply(options.story_key_page_candidates, DEFAULT_CHIEF_OPTIONS.story_key_page_candidates, spec.key_page_candidates),
        sdxl_base=_maybe_apply(options.sdxl_base, DEFAULT_CHIEF_OPTIONS.sdxl_base, resolved.image_base or options.sdxl_base),
        sdxl_refiner=_maybe_apply(options.sdxl_refiner, DEFAULT_CHIEF_OPTIONS.sdxl_refiner, resolved.image_refiner or options.sdxl_refiner),
    )

    if logger is not None:
        logger.info("Runtime model plan selected: %s", resolved.summary())

    return updated, resolved
