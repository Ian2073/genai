"""圖像模型後端層。"""

from __future__ import annotations

import gc
import logging
import torch
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence

from PIL import Image
from diffusers import DPMSolverMultistepScheduler

from backends.common import resolve_torch_runtime
from utils import cleanup_torch


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
    provider = (getattr(config, "provider", None) or "diffusers_sdxl").strip().lower()
    canonical = _IMAGE_BACKEND_CANONICAL.get(provider, provider)
    builder = _IMAGE_BACKEND_BUILDERS.get(canonical)
    if builder is None:
        raise ValueError(
            f"Unknown image provider '{getattr(config, 'provider', None)}'. Available providers: {', '.join(available_image_providers())}"
        )
    return builder(config)


register_image_provider(
    "diffusers_sdxl",
    DiffusersSDXLBackend,
    aliases=("sdxl", "diffusers"),
)


Generator = DiffusersSDXLBackend
