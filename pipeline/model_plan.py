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


_TEXT_QUALITY_CHAIN: Tuple[StoryModelOption, ...] = (
    StoryModelOption("Qwen3-14B-AWQ", "qwen3-14b-awq", None),
    StoryModelOption("Qwen3-14B", "qwen3-14b", "4bit"),
    StoryModelOption("Mistral-Small-3.1-24B-Instruct-2503", "mistral-small-3.1-24b-instruct-2503", "4bit"),
    StoryModelOption("gemma-3-12b-it", "gemma-3-12b-it", "4bit"),
    StoryModelOption("Qwen2.5-14B-Instruct-GPTQ-Int4", "qwen2.5-14b-instruct-gptq-int4", "gptq"),
    StoryModelOption("Qwen3.5-9B", "qwen3.5-9b-instruct", "4bit"),
    StoryModelOption("Qwen3-8B", "qwen3-8b-instruct", "4bit"),
)

_TEXT_BALANCED_CHAIN: Tuple[StoryModelOption, ...] = (
    StoryModelOption("Qwen3-14B-AWQ", "qwen3-14b-awq", None),
    StoryModelOption("Qwen3-14B", "qwen3-14b", "4bit"),
    StoryModelOption("Qwen3.5-9B", "qwen3.5-9b-instruct", "4bit"),
    StoryModelOption("gemma-3-12b-it", "gemma-3-12b-it", "4bit"),
    StoryModelOption("Qwen2.5-14B-Instruct", "qwen2.5-14b-instruct", "4bit"),
    StoryModelOption("Qwen3-8B", "qwen3-8b-instruct", "4bit"),
    StoryModelOption("Qwen2.5-14B-Instruct-GPTQ-Int4", "qwen2.5-14b-instruct-gptq-int4", "gptq"),
)

_TEXT_PORTABLE_CHAIN: Tuple[StoryModelOption, ...] = (
    StoryModelOption("Qwen3.5-9B", "qwen3.5-9b-instruct", "4bit"),
    StoryModelOption("Qwen3-14B-AWQ", "qwen3-14b-awq", None),
    StoryModelOption("gemma-3-12b-it", "gemma-3-12b-it", "4bit"),
    StoryModelOption("Qwen3-8B", "qwen3-8b-instruct", "4bit"),
    StoryModelOption("Qwen2.5-14B-Instruct-GPTQ-Int4", "qwen2.5-14b-instruct-gptq-int4", "gptq"),
)

_TEXT_CPU_CHAIN: Tuple[StoryModelOption, ...] = (
    StoryModelOption("gemma-3-12b-it", "gemma-3-12b-it", None),
    StoryModelOption("Qwen3-8B", "qwen3-8b-instruct", None),
    StoryModelOption("Qwen3.5-9B", "qwen3.5-9b-instruct", None),
    StoryModelOption("Qwen3-14B", "qwen3-14b", None),
    StoryModelOption("Qwen2.5-14B-Instruct-GPTQ-Int4", "qwen2.5-14b-instruct-gptq-int4", None),
)

SUPPORTED_IMAGE_PROVIDERS: Tuple[str, ...] = ("diffusers_sdxl", "diffusers_flux", "diffusers_sd3", "diffusers_pixart", "diffusers_sana")

IMAGE_MODEL_REGISTRY: Tuple[ImageModelSpec, ...] = (
    ImageModelSpec(
        path="stable-diffusion-3.5-large",
        provider="diffusers_sd3",
        family="sd3",
        label="Stable Diffusion 3.5 Large",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="stable-diffusion-3.5-large-turbo",
        provider="diffusers_sd3",
        family="sd3_turbo",
        label="Stable Diffusion 3.5 Large Turbo",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="stable-diffusion-3.5-medium",
        provider="diffusers_sd3",
        family="sd3",
        label="Stable Diffusion 3.5 Medium",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="FLUX.1-dev",
        provider="diffusers_flux",
        family="flux",
        label="FLUX.1-dev",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="FLUX.1-schnell",
        provider="diffusers_flux",
        family="flux_schnell",
        label="FLUX.1-schnell",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="PixArt-Sigma-XL-2-1024-MS",
        provider="diffusers_pixart",
        family="pixart_sigma",
        label="PixArt-Sigma XL 2 1024 MS",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="Sana_1600M_1024px_MultiLing_diffusers",
        provider="diffusers_sana",
        family="sana_1600m",
        label="Sana 1600M 1024 MultiLing",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="Sana_600M_1024px_diffusers",
        provider="diffusers_sana",
        family="sana_600m",
        label="Sana 600M 1024",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="stable-diffusion-xl-base-1.0",
        provider="diffusers_sdxl",
        family="sdxl_base",
        label="Stable Diffusion XL Base 1.0",
        supports_refiner=True,
    ),
    ImageModelSpec(
        path="Mann-E_Art",
        provider="diffusers_sdxl",
        family="sdxl_finetune",
        label="Mann-E Art",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="SSD-1B",
        provider="diffusers_sdxl",
        family="distilled_fast",
        label="SSD-1B",
        supports_refiner=False,
    ),
    ImageModelSpec(
        path="dreamshaperXL_lightningDPMSDE.safetensors",
        provider="diffusers_sdxl",
        family="sdxl_distilled",
        label="DreamShaper XL Lightning",
        deprecated=True,
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


def _iter_installed_image_models(models_dir: Path) -> List[Tuple[ImageModelSpec, Path]]:
    installed: List[Tuple[ImageModelSpec, Path]] = []
    for spec in IMAGE_MODEL_REGISTRY:
        path = models_dir / spec.path
        if path.exists():
            installed.append((spec, path))
    return installed


def _image_family_preference(plan_key: str, hardware: HardwareProfile) -> Tuple[str, ...]:
    if plan_key == "quality" and hardware.has_cuda and hardware.gpu_vram_gb >= 20.0 and hardware.system_ram_gb >= 48.0:
        return ("flux", "flux_schnell", "sd3", "sana_1600m", "pixart_sigma", "sd3_turbo", "sana_600m", "sdxl_finetune", "sdxl_base", "sdxl_like", "distilled_fast")
    if plan_key == "quality":
        return ("flux_schnell", "flux", "sana_1600m", "pixart_sigma", "sana_600m", "sd3_turbo", "sdxl_finetune", "sdxl_base", "sdxl_like", "distilled_fast", "sd3")
    if plan_key == "portable":
        return ("flux_schnell", "sana_600m", "distilled_fast", "pixart_sigma", "sdxl_finetune", "sdxl_base", "sdxl_like", "sd3_turbo", "sana_1600m", "flux", "sd3")
    return ("flux_schnell", "flux", "sana_1600m", "pixart_sigma", "sana_600m", "sd3_turbo", "sdxl_finetune", "sdxl_base", "sdxl_like", "distilled_fast", "sd3")


def _resolve_image_base(
    models_dir: Path,
    *,
    plan_key: str,
    hardware: HardwareProfile,
) -> Tuple[Optional[Path], Tuple[str, ...]]:
    notes: List[str] = []
    installed = _iter_installed_image_models(models_dir)
    if not installed:
        return None, tuple(notes)

    unsupported_labels = [spec.label for spec, _ in installed if spec.provider not in SUPPORTED_IMAGE_PROVIDERS]
    selected: Optional[Tuple[ImageModelSpec, Path]] = None
    preferred_families = _image_family_preference(plan_key, hardware)

    for family in preferred_families:
        for spec, path in installed:
            if spec.provider in SUPPORTED_IMAGE_PROVIDERS and spec.family == family and not spec.deprecated:
                selected = (spec, path)
                break
        if selected is not None:
            break
    if selected is None:
        for spec, path in installed:
            if spec.provider in SUPPORTED_IMAGE_PROVIDERS:
                selected = (spec, path)
                if spec.deprecated:
                    notes.append(f"using deprecated legacy image checkpoint as fallback: {spec.label}")
                break

    if unsupported_labels:
        labels = ", ".join(unsupported_labels[:3])
        if len(unsupported_labels) > 3:
            labels += f" (+{len(unsupported_labels) - 3} more)"
        notes.append(
            "modern image checkpoints detected but skipped because their provider is not enabled in the current runtime: "
            + labels
        )

    if selected is None:
        return None, tuple(notes)
    return selected[1], tuple(notes)


def classify_image_model(image_base: Optional[Path]) -> str:
    token = str(image_base or "").strip().lower()
    if not token:
        return "unknown"
    if "ssd-1b" in token or "segmind" in token:
        return "distilled_fast"
    if "mann-e_art" in token or "mann-e" in token:
        return "sdxl_finetune"
    if "flux.1-schnell" in token or "flux-1-schnell" in token or "schnell" in token:
        return "flux_schnell"
    if "flux" in token:
        return "flux"
    if "stable-diffusion-3.5" in token and "turbo" in token:
        return "sd3_turbo"
    if "sd3" in token and "turbo" in token:
        return "sd3_turbo"
    if "stable-diffusion-3.5" in token or "sd3" in token:
        return "sd3"
    if "sana_1600m" in token or "sana-1600m" in token:
        return "sana_1600m"
    if "sana_600m" in token or "sana-600m" in token:
        return "sana_600m"
    if "sana" in token:
        return "sana_600m"
    if "pixart-sigma" in token or "pixart" in token:
        return "pixart_sigma"
    if "lightning" in token or "turbo" in token:
        return "distilled_fast"
    if "stable-diffusion-xl-base" in token:
        return "sdxl_base"
    if "dreamshaper" in token:
        return "sdxl_finetune"
    if "sdxl" in token:
        return "sdxl_like"
    return "generic"


def classify_image_provider(image_base: Optional[Path]) -> str:
    family = classify_image_model(image_base)
    if family.startswith("flux"):
        return "diffusers_flux"
    if family.startswith("sd3"):
        return "diffusers_sd3"
    if family.startswith("sana"):
        return "diffusers_sana"
    if family.startswith("pixart"):
        return "diffusers_pixart"
    return "diffusers_sdxl"


def tune_image_profile(
    image_profile: ImageProfile,
    image_base: Optional[Path],
    image_refiner: Optional[Path],
) -> Tuple[ImageProfile, Tuple[str, ...]]:
    family = classify_image_model(image_base)
    tuned = image_profile
    notes: List[str] = []

    if family == "sdxl_base":
        tuned = replace(
            tuned,
            steps=max(tuned.steps, 12),
            guidance=max(tuned.guidance, 4.6),
            refiner_steps=max(4, tuned.refiner_steps or 0) if image_refiner is not None else tuned.refiner_steps,
        )
        if tuned != image_profile:
            notes.append("vanilla SDXL base detected; using a higher-guidance SDXL profile instead of legacy lightning defaults")
    elif family in {"sdxl_finetune", "sdxl_like"}:
        tuned = replace(
            tuned,
            steps=max(tuned.steps, 11),
            guidance=max(tuned.guidance, 4.2),
        )
        if tuned != image_profile:
            notes.append("SDXL-compatible finetune detected; raised guidance and steps for cleaner children's-book renders")
    elif family == "distilled_fast":
        bounded_guidance = min(max(tuned.guidance, 1.0), 2.5)
        bounded_steps = min(max(tuned.steps, 4), 8)
        tuned = replace(tuned, steps=bounded_steps, guidance=bounded_guidance, skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("distilled/turbo image model detected; keeping a compact low-step profile and disabling refiner")
    elif family == "flux_schnell":
        tuned = replace(tuned, steps=min(max(tuned.steps, 4), 4), guidance=0.0, skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("FLUX.1-schnell detected; using the official 1-4 step zero-guidance single-stage profile")
    elif family == "flux":
        tuned = replace(tuned, steps=max(tuned.steps, 28), guidance=max(3.5, tuned.guidance), skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("FLUX.1-dev style checkpoint detected; using a 28-step 3.5-guidance single-stage profile without refiner")
    elif family == "sd3_turbo":
        tuned = replace(tuned, steps=min(max(tuned.steps, 6), 10), guidance=min(max(tuned.guidance, 1.5), 2.0), skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("SD3 turbo detected; using a short single-stage profile without refiner")
    elif family == "sd3":
        tuned = replace(tuned, steps=max(tuned.steps, 18), guidance=max(4.0, tuned.guidance), skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("SD3 detected; using a stronger single-stage profile without refiner")
    elif family == "pixart_sigma":
        tuned = replace(tuned, steps=max(tuned.steps, 16), guidance=max(4.5, tuned.guidance), skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("PixArt-Sigma detected; using a longer prompt-aware single-stage profile without refiner")
    elif family == "sana_1600m":
        tuned = replace(tuned, steps=max(tuned.steps, 18), guidance=max(4.5, tuned.guidance), skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("Sana 1600M detected; using a multilingual single-stage profile without refiner")
    elif family == "sana_600m":
        tuned = replace(tuned, steps=max(tuned.steps, 16), guidance=max(4.0, tuned.guidance), skip_refiner=True, refiner_steps=None)
        if tuned != image_profile:
            notes.append("Sana 600M detected; using an efficient single-stage profile without refiner")

    if (not tuned.skip_refiner) and image_refiner is None:
        tuned = replace(tuned, skip_refiner=True)
        notes.append("image refiner missing; forcing skip_refiner for this host")

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
    image_refiner = models_dir / "stable-diffusion-xl-refiner-1.0"
    if not image_refiner.exists() or classify_image_model(image_base) not in {"sdxl_base", "sdxl_finetune", "sdxl_like"}:
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
