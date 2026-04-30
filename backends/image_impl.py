"""圖像模型後端層。"""

from __future__ import annotations

import gc
import logging
import os
import torch
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence

from PIL import Image
from diffusers import DPMSolverMultistepScheduler

from backends.common import resolve_torch_runtime
from utils import cleanup_torch


def _enable_sentencepiece_protobuf_python_fallback() -> None:
    """Work around protobuf 4.x incompatibilities in sentencepiece tokenizer conversion.

    FLUX / SD3 pipelines may load T5-style tokenizers that import sentencepiece protobuf
    descriptors generated against older protoc versions. Setting this environment variable
    before tokenizer construction forces the pure-Python protobuf runtime, which is slower
    during tokenizer load but avoids the hard crash.
    """
    if os.environ.get("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"):
        return
    os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"


def _normalize_flux_quantization_mode(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {"", "none", "off", "false", "0"}:
        return "none"
    if token in {"fp8", "float8", "qfloat8"}:
        return "float8"
    if token in {"fp4", "int4", "4bit", "qint4"}:
        # Quanto supports int4 weights, not a native fp4 mode.
        return "int4"
    return token


class BaseImageBackend:
    """圖像生成後端介面。"""

    def load_base(self) -> None:
        raise NotImplementedError

    def run_base_step(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
        output_latents: bool = True,
    ) -> Any:
        raise NotImplementedError

    def run_refiner_step(
        self,
        latents: Any,
        prompt: str,
        seed: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Image.Image:
        raise NotImplementedError

    def cleanup(self) -> None:
        raise NotImplementedError


class DiffusersSDXLBackend(BaseImageBackend):
    """Diffusers SDXL 圖像生成後端。"""

    def __init__(self, config: Any) -> None:
        self.config = config
        self.config.device, self.config.dtype = resolve_torch_runtime(
            self.config.device,
            self.config.dtype,
            module_name="Image pipeline",
        )
        self.base = None
        self.refiner = None
        self._current_model = None

    def _ensure_base_loaded(self) -> None:
        if self._current_model == "base" and self.base is not None:
            return
        if self.refiner is not None and self.config.low_vram:
            logging.info("Unloading SDXL Refiner to free memory...")
            del self.refiner
            self.refiner = None
            gc.collect()
            cleanup_torch()
        if self.base is not None:
            self._current_model = "base"
            return

        logging.info("Loading SDXL Base model from %s...", self.config.base_model_dir)
        try:
            from diffusers import StableDiffusionXLPipeline
        except ImportError as exc:
            raise RuntimeError("diffusers is required") from exc

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            if self.config.base_model_dir.is_file():
                self.base = StableDiffusionXLPipeline.from_single_file(
                    str(self.config.base_model_dir),
                    torch_dtype=self.config.dtype,
                    use_safetensors=True,
                )
            else:
                self.base = StableDiffusionXLPipeline.from_pretrained(
                    str(self.config.base_model_dir),
                    torch_dtype=self.config.dtype,
                    use_safetensors=True,
                    variant="fp16",
                )
            self.base.scheduler = DPMSolverMultistepScheduler.from_config(
                self.base.scheduler.config,
                use_karras_sigmas=True,
                algorithm_type="sde-dpmsolver++",
            )

        self.base.to(self.config.device)
        if hasattr(self.base, "enable_vae_slicing"):
            self.base.enable_vae_slicing()
        if hasattr(self.base, "enable_vae_tiling"):
            self.base.enable_vae_tiling()
        self._current_model = "base"
        logging.info("SDXL Base model loaded successfully")

    def _ensure_refiner_loaded(self) -> None:
        if self._current_model == "refiner" and self.refiner is not None:
            return
        if self.base is not None and self.config.low_vram:
            logging.info("Unloading SDXL Base to free memory...")
            del self.base
            self.base = None
            gc.collect()
            cleanup_torch()
        if self.refiner is not None:
            self._current_model = "refiner"
            return

        logging.info("Loading SDXL Refiner model...")
        try:
            from diffusers import StableDiffusionXLImg2ImgPipeline
        except ImportError as exc:
            raise RuntimeError("diffusers is required") from exc

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.refiner = StableDiffusionXLImg2ImgPipeline.from_pretrained(
                str(self.config.refiner_model_dir),
                torch_dtype=self.config.dtype,
                use_safetensors=True,
                variant="fp16",
            )
            self.refiner.scheduler = DPMSolverMultistepScheduler.from_config(
                self.refiner.scheduler.config,
                use_karras_sigmas=True,
            )

        self.refiner.to(self.config.device)
        if hasattr(self.refiner, "enable_vae_slicing"):
            self.refiner.enable_vae_slicing()
        if hasattr(self.refiner, "enable_vae_tiling"):
            self.refiner.enable_vae_tiling()
        self._current_model = "refiner"
        logging.info("SDXL Refiner model loaded successfully")

    def load_base(self) -> None:
        self._ensure_base_loaded()

    def load_refiner(self) -> None:
        self._ensure_refiner_loaded()

    def run_base_step(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
        output_latents: bool = True,
    ) -> Any:
        self._ensure_base_loaded()
        from utils import ResourceManager

        generator = ResourceManager.setup_torch_generator(self.config.device, seed)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            output = self.base(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                generator=generator,
                guidance_scale=guidance,
                num_inference_steps=steps,
                output_type="latent" if output_latents else "pil",
            )
        return output.images.cpu() if output_latents else output.images[0]

    def run_refiner_step(
        self,
        latents: Any,
        prompt: str,
        seed: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Image.Image:
        self._ensure_refiner_loaded()
        from utils import ResourceManager

        generator = ResourceManager.setup_torch_generator(self.config.device, seed)
        latents = latents.to(self.config.device)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            output = self.refiner(
                prompt=prompt,
                negative_prompt=negative_prompt,
                image=latents,
                generator=generator,
                guidance_scale=guidance,
                num_inference_steps=steps,
            )
        return output.images[0]

    def offload_model(self, target: str = "cpu") -> None:
        if self.base is not None:
            logging.info("Offloading SDXL Base to %s...", target)
            self.base.to(target)
            torch.cuda.empty_cache()
        if self.refiner is not None:
            logging.info("Offloading SDXL Refiner to %s...", target)
            self.refiner.to(target)
            torch.cuda.empty_cache()

    def generate_image(
        self,
        prompt: str,
        seed: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        negative_prompt: Optional[str] = None,
        skip_refiner: Optional[bool] = None,
        refiner_steps: Optional[int] = None,
    ) -> Image.Image:
        steps = num_inference_steps or self.config.steps
        final_guidance = guidance_scale or self.config.guidance
        width = width or self.config.width
        height = height or self.config.height
        neg_prompt = negative_prompt if negative_prompt is not None else self.config.negative_prompt
        use_refiner = not (skip_refiner if skip_refiner is not None else self.config.skip_refiner)
        refiner_steps = refiner_steps or self.config.refiner_steps or max(1, steps // 4)

        from utils import ResourceManager

        generator = ResourceManager.setup_torch_generator(self.config.device, seed)
        self._ensure_base_loaded()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            base_output = self.base(
                prompt=prompt,
                negative_prompt=neg_prompt or None,
                width=width,
                height=height,
                generator=generator,
                guidance_scale=final_guidance,
                num_inference_steps=steps,
                output_type="latent" if use_refiner else "pil",
            )
        if not use_refiner:
            return base_output.images[0]

        latents = base_output.images
        self._ensure_refiner_loaded()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            refined = self.refiner(
                prompt=prompt,
                negative_prompt=neg_prompt or None,
                image=latents,
                generator=generator,
                guidance_scale=final_guidance,
                num_inference_steps=max(1, refiner_steps),
            )
        return refined.images[0]

    def stream(
        self,
        prompt: str,
        seed: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        negative_prompt: Optional[str] = None,
    ) -> Iterator[Dict[str, Any]]:
        self._ensure_base_loaded()
        pipe = self.base

        h = height or self.config.height
        w = width or self.config.width
        steps = num_inference_steps or self.config.steps
        guidance = guidance_scale or self.config.guidance
        neg_prompt = negative_prompt or self.config.negative_prompt

        (
            prompt_embeds,
            neg_prompt_embeds,
            pooled_embeds,
            neg_pooled_embeds,
        ) = pipe.encode_prompt(
            prompt=prompt,
            negative_prompt=neg_prompt,
            device=pipe.device,
        )

        pipe.scheduler.set_timesteps(steps, device=pipe.device)
        timesteps = pipe.scheduler.timesteps
        latents = pipe.prepare_latents(
            1,
            pipe.unet.config.in_channels,
            h,
            w,
            prompt_embeds.dtype,
            pipe.device,
            torch.Generator(device=pipe.device).manual_seed(seed),
        )

        add_text_embeds = pooled_embeds
        add_time_ids = pipe._get_add_time_ids(
            (h, w), (0, 0), (h, w), dtype=prompt_embeds.dtype
        ).to(pipe.device)

        if pipe.do_classifier_free_guidance:
            prompt_embeds = torch.cat([neg_prompt_embeds, prompt_embeds], dim=0)
            add_text_embeds = torch.cat([neg_pooled_embeds, add_text_embeds], dim=0)
            add_time_ids = torch.cat([add_time_ids, add_time_ids], dim=0)

        for i, t in enumerate(timesteps):
            latent_model_input = torch.cat([latents] * 2) if pipe.do_classifier_free_guidance else latents
            latent_model_input = pipe.scheduler.scale_model_input(latent_model_input, t)

            added_cond_kwargs = {
                "text_embeds": add_text_embeds,
                "time_ids": add_time_ids,
            }
            with torch.no_grad():
                noise_pred = pipe.unet(
                    latent_model_input,
                    t,
                    encoder_hidden_states=prompt_embeds,
                    timestep_cond=None,
                    cross_attention_kwargs=None,
                    added_cond_kwargs=added_cond_kwargs,
                    return_dict=False,
                )[0]

            if pipe.do_classifier_free_guidance:
                noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
                noise_pred = noise_pred_uncond + guidance * (noise_pred_text - noise_pred_uncond)

            latents = pipe.scheduler.step(noise_pred, t, latents, return_dict=False)[0]
            yield {
                "step": i + 1,
                "total": len(timesteps),
                "latents": latents.detach().clone().cpu(),
                "end": False,
            }

        needs_upcast = pipe.vae.dtype == torch.float16 and pipe.vae.config.force_upcast
        if needs_upcast:
            pipe.upcast_vae()
            latents = latents.to(next(iter(pipe.vae.post_quant_conv.parameters())).dtype)

        with torch.no_grad():
            image = pipe.vae.decode(latents / pipe.vae.config.scaling_factor, return_dict=False)[0]

        if needs_upcast:
            pipe.vae.to(dtype=torch.float16)

        image = pipe.image_processor.postprocess(image, output_type="pil")[0]
        yield {
            "step": len(timesteps),
            "total": len(timesteps),
            "image": image,
            "end": True,
        }

    def cleanup(self) -> None:
        from utils import ResourceManager

        if self.base is not None:
            ResourceManager.cleanup_model(self.base, aggressive=True)
            self.base = None
        if self.refiner is not None:
            ResourceManager.cleanup_model(self.refiner, aggressive=True)
            self.refiner = None
        self._current_model = None


class _SingleStageDiffusersBackend(BaseImageBackend):
    """Base class for single-stage diffusers image pipelines such as FLUX and SD3."""

    pipeline_cls_name: str = ""
    pipeline_module: str = "diffusers"
    max_sequence_length: Optional[int] = None

    def __init__(self, config: Any) -> None:
        self.config = config
        self.config.device, self.config.dtype = resolve_torch_runtime(
            self.config.device,
            self.config.dtype,
            module_name="Image pipeline",
        )
        self.pipeline = None
        self.applied_quantization_mode = "none"

    def _load_pipeline_class(self):
        module = __import__(self.pipeline_module, fromlist=[self.pipeline_cls_name])
        pipeline_cls = getattr(module, self.pipeline_cls_name, None)
        if pipeline_cls is None:
            raise RuntimeError(f"{self.pipeline_cls_name} is not available from {self.pipeline_module}")
        return pipeline_cls

    def _create_pipeline(self):
        pipeline_cls = self._load_pipeline_class()
        model_dir = getattr(self.config, "base_model_dir", None)
        if model_dir is None:
            raise RuntimeError("base_model_dir is required for image generation")
        family = str(getattr(self.config, "model_family", "") or "").lower()
        if family.startswith("flux") or family.startswith("sd3"):
            _enable_sentencepiece_protobuf_python_fallback()
        return pipeline_cls.from_pretrained(
            str(model_dir),
            torch_dtype=self.config.dtype,
            use_safetensors=True,
        )

    def _prepare_pipeline(self, pipeline: Any) -> Any:
        if hasattr(pipeline, "set_progress_bar_config"):
            try:
                pipeline.set_progress_bar_config(disable=True)
            except Exception:
                pass
        if hasattr(pipeline, "enable_vae_slicing"):
            try:
                pipeline.enable_vae_slicing()
            except Exception:
                pass
        if hasattr(pipeline, "enable_vae_tiling"):
            try:
                pipeline.enable_vae_tiling()
            except Exception:
                pass

        target_device = str(self.config.device or "cpu")
        if target_device.startswith("cuda") and getattr(self.config, "low_vram", False) and hasattr(pipeline, "enable_model_cpu_offload"):
            pipeline.enable_model_cpu_offload()
        else:
            pipeline.to(target_device)
        return pipeline

    def _ensure_pipeline_loaded(self) -> None:
        if self.pipeline is not None:
            return
        logging.info("Loading %s model from %s...", self.pipeline_cls_name, self.config.base_model_dir)
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            self.pipeline = self._prepare_pipeline(self._create_pipeline())
        logging.info("%s loaded successfully", self.pipeline_cls_name)

    def _pipeline_call_kwargs(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Dict[str, Any]:
        from utils import ResourceManager

        generator = ResourceManager.setup_torch_generator(self.config.device, seed)
        kwargs: Dict[str, Any] = {
            "prompt": prompt,
            "width": width,
            "height": height,
            "generator": generator,
            "num_inference_steps": steps,
            "guidance_scale": guidance,
        }
        if negative_prompt:
            kwargs["negative_prompt"] = negative_prompt
        if self.max_sequence_length is not None:
            kwargs["max_sequence_length"] = int(self.max_sequence_length)
        return kwargs

    def load_base(self) -> None:
        self._ensure_pipeline_loaded()

    def load_refiner(self) -> None:
        return None

    def run_base_step(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
        output_latents: bool = True,
    ) -> Any:
        self._ensure_pipeline_loaded()
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            output = self.pipeline(**self._pipeline_call_kwargs(prompt, seed, width, height, steps, guidance, negative_prompt))
        return output.images[0]

    def run_refiner_step(
        self,
        latents: Any,
        prompt: str,
        seed: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Image.Image:
        if isinstance(latents, Image.Image):
            return latents
        raise RuntimeError(f"{self.pipeline_cls_name} does not support a separate refiner stage")

    def offload_model(self, target: str = "cpu") -> None:
        if self.pipeline is not None and hasattr(self.pipeline, "to"):
            try:
                self.pipeline.to(target)
            except Exception:
                pass
            torch.cuda.empty_cache()

    def generate_image(
        self,
        prompt: str,
        seed: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        negative_prompt: Optional[str] = None,
        skip_refiner: Optional[bool] = None,
        refiner_steps: Optional[int] = None,
    ) -> Image.Image:
        del skip_refiner, refiner_steps
        return self.run_base_step(
            prompt=prompt,
            seed=seed,
            width=width or self.config.width,
            height=height or self.config.height,
            steps=num_inference_steps or self.config.steps,
            guidance=guidance_scale if guidance_scale is not None else self.config.guidance,
            negative_prompt=negative_prompt if negative_prompt is not None else self.config.negative_prompt,
            output_latents=False,
        )

    def cleanup(self) -> None:
        from utils import ResourceManager

        if self.pipeline is not None:
            ResourceManager.cleanup_model(self.pipeline, aggressive=True)
            self.pipeline = None


class DiffusersFluxBackend(_SingleStageDiffusersBackend):
    pipeline_cls_name = "FluxPipeline"
    max_sequence_length = 512

    def _create_pipeline(self):
        pipeline_cls = self._load_pipeline_class()
        model_dir = getattr(self.config, "base_model_dir", None)
        if model_dir is None:
            raise RuntimeError("base_model_dir is required for image generation")
        _enable_sentencepiece_protobuf_python_fallback()

        quant_mode = _normalize_flux_quantization_mode(getattr(self.config, "quantization_mode", None))
        if quant_mode == "none":
            self.applied_quantization_mode = "none"
            return pipeline_cls.from_pretrained(
                str(model_dir),
                torch_dtype=self.config.dtype,
                use_safetensors=True,
            )

        from diffusers import FluxTransformer2DModel, QuantoConfig

        logging.info("Loading quantized FLUX transformer from %s with Quanto %s...", model_dir, quant_mode)
        quant_config = QuantoConfig(weights_dtype=quant_mode)
        transformer = FluxTransformer2DModel.from_pretrained(
            str(model_dir),
            subfolder="transformer",
            quantization_config=quant_config,
            torch_dtype=self.config.dtype,
            use_safetensors=True,
        )
        self.applied_quantization_mode = quant_mode
        return pipeline_cls.from_pretrained(
            str(model_dir),
            transformer=transformer,
            torch_dtype=self.config.dtype,
            use_safetensors=True,
        )

    def _pipeline_call_kwargs(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Dict[str, Any]:
        kwargs = super()._pipeline_call_kwargs(prompt, seed, width, height, steps, guidance, negative_prompt)
        kwargs.pop("negative_prompt", None)
        family = str(getattr(self.config, "model_family", "") or "").lower()
        if family == "flux":
            kwargs["guidance_scale"] = max(3.5, float(kwargs.get("guidance_scale", guidance)))
            kwargs["num_inference_steps"] = max(int(kwargs.get("num_inference_steps", steps)), 28)
            kwargs["max_sequence_length"] = 512
        else:
            kwargs["guidance_scale"] = 0.0
            kwargs["num_inference_steps"] = min(max(int(steps), 1), 4)
            kwargs["max_sequence_length"] = 256
        return kwargs


class DiffusersSD3Backend(_SingleStageDiffusersBackend):
    pipeline_cls_name = "StableDiffusion3Pipeline"
    max_sequence_length = 256

    def _pipeline_call_kwargs(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Dict[str, Any]:
        kwargs = super()._pipeline_call_kwargs(prompt, seed, width, height, steps, guidance, negative_prompt)
        family = str(getattr(self.config, "model_family", "") or "").lower()
        if family == "sd3_turbo":
            kwargs["guidance_scale"] = min(max(float(guidance), 0.0), 2.0)
            kwargs["num_inference_steps"] = min(max(int(steps), 4), 10)
            kwargs["max_sequence_length"] = 256
        else:
            kwargs["guidance_scale"] = max(3.0, float(kwargs.get("guidance_scale", guidance)))
            kwargs["num_inference_steps"] = max(int(kwargs.get("num_inference_steps", steps)), 20)
        return kwargs


class DiffusersPixArtBackend(_SingleStageDiffusersBackend):
    pipeline_cls_name = "PixArtSigmaPipeline"
    max_sequence_length = 300

    def _load_pipeline_class(self):
        from diffusers import PixArtSigmaPipeline

        return PixArtSigmaPipeline

    def _pipeline_call_kwargs(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Dict[str, Any]:
        kwargs = super()._pipeline_call_kwargs(prompt, seed, width, height, steps, guidance, negative_prompt)
        kwargs["guidance_scale"] = max(3.0, float(kwargs.get("guidance_scale", guidance)))
        kwargs["num_inference_steps"] = max(int(kwargs.get("num_inference_steps", steps)), 14)
        kwargs["use_resolution_binning"] = True
        kwargs["clean_caption"] = True
        return kwargs


class DiffusersSanaBackend(_SingleStageDiffusersBackend):
    pipeline_cls_name = "SanaPipeline"
    max_sequence_length = 300

    def _load_pipeline_class(self):
        from diffusers import SanaPipeline

        return SanaPipeline

    def _pipeline_call_kwargs(
        self,
        prompt: str,
        seed: int,
        width: int,
        height: int,
        steps: int,
        guidance: float,
        negative_prompt: str,
    ) -> Dict[str, Any]:
        kwargs = super()._pipeline_call_kwargs(prompt, seed, width, height, steps, guidance, negative_prompt)
        family = str(getattr(self.config, "model_family", "") or "").lower()
        kwargs["guidance_scale"] = max(4.0, float(kwargs.get("guidance_scale", guidance)))
        kwargs["num_inference_steps"] = max(int(kwargs.get("num_inference_steps", steps)), 16 if family == "sana_600m" else 18)
        kwargs["use_resolution_binning"] = True
        kwargs["clean_caption"] = False
        return kwargs


ImageBackendBuilder = Callable[[Any], BaseImageBackend]

_IMAGE_BACKEND_BUILDERS: Dict[str, ImageBackendBuilder] = {}
_IMAGE_BACKEND_CANONICAL: Dict[str, str] = {}


def register_image_provider(
    name: str,
    builder: ImageBackendBuilder,
    aliases: Sequence[str] = (),
) -> None:
    canonical = name.strip().lower()
    _IMAGE_BACKEND_BUILDERS[canonical] = builder
    _IMAGE_BACKEND_CANONICAL[canonical] = canonical
    for alias in aliases:
        normalized = alias.strip().lower()
        _IMAGE_BACKEND_BUILDERS[normalized] = builder
        _IMAGE_BACKEND_CANONICAL[normalized] = canonical


def available_image_providers() -> List[str]:
    return sorted(set(_IMAGE_BACKEND_CANONICAL.values()))


def build_image_backend(config: Any) -> BaseImageBackend:
    provider = (getattr(config, "provider", None) or "diffusers_flux").strip().lower()
    canonical = _IMAGE_BACKEND_CANONICAL.get(provider, provider)
    builder = _IMAGE_BACKEND_BUILDERS.get(canonical)
    if builder is None:
        raise ValueError(
            f"Unknown image provider '{getattr(config, 'provider', None)}'. Available providers: {', '.join(available_image_providers())}"
        )
    return builder(config)


register_image_provider(
    "diffusers_flux",
    DiffusersFluxBackend,
    aliases=(
        "flux",
        "diffusers",
        "sdxl",
        "diffusers_sdxl",
        "sd3",
        "stable-diffusion-3",
        "diffusers_sd3",
        "pixart",
        "pixart_sigma",
        "diffusers_pixart",
        "sana",
        "diffusers_sana",
    ),
)


Generator = DiffusersFluxBackend
