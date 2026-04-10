from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Sequence

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backends.image import build_image_backend
from pipeline.model_plan import (
    IMAGE_MODEL_REGISTRY,
    MODEL_PLAN_SPECS,
    classify_image_model,
    classify_image_provider,
    detect_hardware_profile,
    tune_image_profile,
)
from pipeline.options import DEFAULT_CHIEF_OPTIONS, parse_dtype


def _iter_installed_models(models_dir: Path, *, include_deprecated: bool = False) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    for spec in IMAGE_MODEL_REGISTRY:
        if spec.deprecated and not include_deprecated:
            continue
        path = models_dir / spec.path
        if not path.exists():
            continue
        results.append(
            {
                "label": spec.label,
                "path": str(path),
                "provider": spec.provider,
                "family": spec.family,
                "deprecated": str(bool(spec.deprecated)).lower(),
            }
        )
    return results


def _slug(text: str) -> str:
    keep = []
    for ch in str(text):
        if ch.isalnum():
            keep.append(ch.lower())
        elif ch in {" ", "-", "_", "."}:
            keep.append("-")
    value = "".join(keep).strip("-")
    while "--" in value:
        value = value.replace("--", "-")
    return value or "model"


def _build_backend_config(
    *,
    model_path: Path,
    provider: str,
    family: str,
    width: int,
    height: int,
    steps: int | None,
    guidance: float | None,
    low_vram: bool,
    negative_prompt: str,
) -> SimpleNamespace:
    base_profile = MODEL_PLAN_SPECS["balanced"].image_profile
    refiner = model_path.parent / "stable-diffusion-xl-refiner-1.0"
    refiner_path = refiner if refiner.exists() and family.startswith("sdxl") else None
    tuned, _notes = tune_image_profile(base_profile, model_path, refiner_path)
    final_steps = int(steps if steps is not None else tuned.steps)
    final_guidance = float(guidance if guidance is not None else tuned.guidance)
    return SimpleNamespace(
        provider=provider or classify_image_provider(model_path),
        model_family=family or classify_image_model(model_path),
        base_model_dir=model_path,
        refiner_model_dir=refiner_path or Path(""),
        device=str(DEFAULT_CHIEF_OPTIONS.photo_device),
        dtype=parse_dtype(str(DEFAULT_CHIEF_OPTIONS.photo_dtype)),
        width=width or int(tuned.width),
        height=height or int(tuned.height),
        steps=final_steps,
        guidance=final_guidance,
        refiner_steps=tuned.refiner_steps,
        skip_refiner=bool(tuned.skip_refiner or refiner_path is None),
        negative_prompt=negative_prompt or str(DEFAULT_CHIEF_OPTIONS.photo_negative_prompt),
        low_vram=low_vram,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark installed image checkpoints sequentially with the same prompt.")
    parser.add_argument("--prompt", type=str, default="", help="Prompt used for all model runs.")
    parser.add_argument("--negative-prompt", type=str, default=str(DEFAULT_CHIEF_OPTIONS.photo_negative_prompt))
    parser.add_argument("--models-dir", type=Path, default=Path("models"))
    parser.add_argument("--output-dir", type=Path, default=Path("runs") / "image_model_benchmarks")
    parser.add_argument("--include-deprecated", action="store_true")
    parser.add_argument("--model", action="append", dest="models_filter", default=[], help="Optional model label/path token filter. Repeatable.")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=768)
    parser.add_argument("--steps", type=int, default=None)
    parser.add_argument("--guidance", type=float, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--low-vram", action="store_true", default=True)
    parser.add_argument("--list", action="store_true", help="Only list installed image models.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    installed = _iter_installed_models(args.models_dir, include_deprecated=args.include_deprecated)

    if args.models_filter:
        filters = [token.strip().lower() for token in args.models_filter if token.strip()]
        installed = [
            item for item in installed
            if any(token in item["label"].lower() or token in item["path"].lower() for token in filters)
        ]

    if args.list:
        print(json.dumps({"installed_models": installed}, ensure_ascii=False, indent=2))
        return

    if not args.prompt.strip():
        raise SystemExit("--prompt is required unless --list is used")
    if not installed:
        raise SystemExit("No installed image models matched the current filter.")

    hardware = detect_hardware_profile()
    run_dir = args.output_dir / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    summary: List[Dict[str, object]] = []

    logging.info("Starting benchmark on %d image model(s) | hardware=%s", len(installed), hardware.summary())
    for item in installed:
        label = str(item["label"])
        model_path = Path(str(item["path"]))
        provider = str(item["provider"])
        family = str(item["family"])
        cfg = _build_backend_config(
            model_path=model_path,
            provider=provider,
            family=family,
            width=args.width,
            height=args.height,
            steps=args.steps,
            guidance=args.guidance,
            low_vram=bool(args.low_vram),
            negative_prompt=args.negative_prompt,
        )
        record: Dict[str, object] = {
            "label": label,
            "path": str(model_path),
            "provider": provider,
            "family": family,
            "steps": int(cfg.steps),
            "guidance": float(cfg.guidance),
            "width": int(cfg.width),
            "height": int(cfg.height),
            "skip_refiner": bool(cfg.skip_refiner),
        }
        started_at = time.perf_counter()
        backend = None
        try:
            logging.info("Benchmarking %s | provider=%s family=%s", label, provider, family)
            backend = build_image_backend(cfg)
            image = backend.generate_image(
                prompt=args.prompt.strip(),
                seed=int(args.seed),
                width=int(cfg.width),
                height=int(cfg.height),
                num_inference_steps=int(cfg.steps),
                guidance_scale=float(cfg.guidance),
                negative_prompt=str(cfg.negative_prompt),
                skip_refiner=bool(cfg.skip_refiner),
                refiner_steps=cfg.refiner_steps,
            )
            out_name = f"{_slug(label)}.png"
            out_path = run_dir / out_name
            image.save(out_path)
            elapsed = round(time.perf_counter() - started_at, 2)
            record.update({"ok": True, "elapsed_sec": elapsed, "output_path": str(out_path)})
            logging.info("Completed %s in %.2fs -> %s", label, elapsed, out_path)
        except Exception as exc:
            elapsed = round(time.perf_counter() - started_at, 2)
            record.update({"ok": False, "elapsed_sec": elapsed, "error": str(exc)})
            logging.exception("Benchmark failed for %s: %s", label, exc)
        finally:
            if backend is not None:
                try:
                    backend.cleanup()
                except Exception:
                    pass
        summary.append(record)

    summary_path = run_dir / "summary.json"
    summary_path.write_text(json.dumps({"hardware": hardware.summary(), "results": summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    logging.info("Benchmark summary saved to %s", summary_path)


if __name__ == "__main__":
    main()
