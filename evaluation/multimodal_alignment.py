from __future__ import annotations

import json
import logging
import math
import os
import re
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image


logger = logging.getLogger(__name__)

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "she",
    "that",
    "the",
    "their",
    "them",
    "there",
    "they",
    "this",
    "to",
    "was",
    "were",
    "with",
    "would",
    "you",
    "your",
}

_ACTION_HINTS = {
    "ask",
    "carry",
    "chase",
    "climb",
    "dance",
    "explore",
    "find",
    "follow",
    "gather",
    "help",
    "hold",
    "jump",
    "kneel",
    "knock",
    "listen",
    "look",
    "open",
    "play",
    "point",
    "push",
    "read",
    "run",
    "share",
    "sit",
    "smile",
    "stand",
    "talk",
    "walk",
    "wave",
    "whisper",
}

_CHILD_SAFETY_FLAGS = {
    "blood",
    "corpse",
    "dead",
    "gore",
    "gun",
    "injury",
    "knife",
    "monster",
    "nightmare",
    "violence",
    "weapon",
}

_GEMMA4_CANDIDATES: Tuple[str, ...] = (
    "models/gemma-4-E4B-it",
    "models/gemma-4-E4B",
    "models/gemma-4-E2B-it",
    "models/gemma-4-E2B",
)


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except Exception:
        return float(default)
    if math.isnan(number) or math.isinf(number):
        return float(default)
    return float(number)


def _read_text(path: Optional[str]) -> str:
    if not path:
        return ""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except Exception:
        return ""


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z'\-]+|[\u4e00-\u9fff]", str(text or "").lower())


def _content_tokens(text: str) -> List[str]:
    tokens = []
    for token in _tokenize(text):
        if token in _STOPWORDS:
            continue
        if len(token) <= 1 and not re.fullmatch(r"[\u4e00-\u9fff]", token):
            continue
        tokens.append(token)
    return tokens


def _keyword_counter(text: str, *, top_k: int = 24) -> Counter[str]:
    counter: Counter[str] = Counter(_content_tokens(text))
    if top_k <= 0:
        return counter
    return Counter(dict(counter.most_common(top_k)))


def _overlap_ratio(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = {item for item in left if item}
    right_set = {item for item in right if item}
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / max(1, len(left_set | right_set))


def _score_prompt_specificity(prompt_text: str) -> Tuple[float, Dict[str, Any]]:
    prompt = str(prompt_text or "").strip()
    tokens = _content_tokens(prompt)
    unique_tokens = len(set(tokens))
    action_hits = sorted({token for token in tokens if token in _ACTION_HINTS})
    comma_segments = [segment.strip() for segment in prompt.split(",") if segment.strip()]
    score = 35.0
    score += min(24.0, len(tokens) * 1.25)
    score += min(18.0, unique_tokens * 0.8)
    score += min(10.0, len(comma_segments) * 2.2)
    if action_hits:
        score += 8.0
    if len(tokens) < 10:
        score -= 18.0
    elif len(tokens) < 14:
        score -= 8.0
    if unique_tokens < 8:
        score -= 10.0
    if not re.search(r"[.!?,]", prompt):
        score -= 3.0
    return _clamp(score), {
        "token_count": len(tokens),
        "unique_token_count": unique_tokens,
        "action_hits": action_hits,
        "segment_count": len(comma_segments),
    }


def _score_text_alignment(reference_text: str, prompt_text: str) -> Tuple[float, Dict[str, Any]]:
    reference_counter = _keyword_counter(reference_text, top_k=32)
    prompt_counter = _keyword_counter(prompt_text, top_k=24)
    reference_tokens = list(reference_counter.keys())
    prompt_tokens = list(prompt_counter.keys())
    overlap = _overlap_ratio(reference_tokens, prompt_tokens)
    prompt_actions = {token for token in prompt_tokens if token in _ACTION_HINTS}
    reference_actions = {token for token in reference_tokens if token in _ACTION_HINTS}
    action_overlap = _overlap_ratio(prompt_actions, reference_actions)
    score = 40.0 + overlap * 45.0 + action_overlap * 15.0
    if len(prompt_tokens) < 8:
        score -= 10.0
    if overlap < 0.12:
        score -= 12.0
    return _clamp(score), {
        "keyword_overlap": round(overlap, 3),
        "action_overlap": round(action_overlap, 3),
        "reference_keywords": reference_tokens[:8],
        "prompt_keywords": prompt_tokens[:8],
    }


def _score_child_safety(prompt_text: str) -> Tuple[float, List[str]]:
    lowered = str(prompt_text or "").lower()
    hits = sorted(flag for flag in _CHILD_SAFETY_FLAGS if flag in lowered)
    score = 100.0 - min(45.0, len(hits) * 18.0)
    return _clamp(score), hits


def _score_image_metrics(image_path: str) -> Tuple[float, Dict[str, Any]]:
    path = Path(image_path)
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        rgb_arr = np.asarray(rgb, dtype=np.float32)
        gray = np.asarray(rgb.convert("L"), dtype=np.float32) / 255.0

    dx = np.diff(gray, axis=1)
    dy = np.diff(gray, axis=0)
    sharpness_raw = float(np.var(dx) + np.var(dy))
    contrast_raw = float(np.std(gray))
    saturation_raw = float(np.mean(np.max(rgb_arr, axis=2) - np.min(rgb_arr, axis=2)) / 255.0)
    brightness_raw = float(np.mean(gray))

    sharpness_score = _clamp(18.0 + sharpness_raw * 26000.0)
    contrast_score = _clamp(contrast_raw * 360.0)
    saturation_score = _clamp(100.0 - abs(saturation_raw - 0.24) * 240.0)

    min_edge = min(width, height)
    if min_edge >= 896:
        resolution_score = 100.0
    elif min_edge >= 768:
        resolution_score = 92.0
    elif min_edge >= 640:
        resolution_score = 80.0
    else:
        resolution_score = 65.0

    exposure_penalty = 0.0
    if brightness_raw < 0.22 or brightness_raw > 0.84:
        exposure_penalty = 8.0

    final = _clamp(
        sharpness_score * 0.35
        + contrast_score * 0.25
        + saturation_score * 0.2
        + resolution_score * 0.2
        - exposure_penalty
    )

    return final, {
        "width": width,
        "height": height,
        "sharpness_raw": round(sharpness_raw, 6),
        "contrast_raw": round(contrast_raw, 6),
        "saturation_raw": round(saturation_raw, 6),
        "brightness_raw": round(brightness_raw, 6),
        "sharpness_score": round(sharpness_score, 2),
        "contrast_score": round(contrast_score, 2),
        "saturation_score": round(saturation_score, 2),
        "resolution_score": round(resolution_score, 2),
    }


def _score_style_consistency(image_metrics: Sequence[Dict[str, Any]]) -> float:
    if len(image_metrics) <= 1:
        return 78.0
    contrasts = [_safe_float(item.get("contrast_raw"), 0.0) for item in image_metrics]
    saturations = [_safe_float(item.get("saturation_raw"), 0.0) for item in image_metrics]
    widths = [_safe_float(item.get("width"), 0.0) for item in image_metrics]
    heights = [_safe_float(item.get("height"), 0.0) for item in image_metrics]
    contrast_std = float(np.std(contrasts))
    saturation_std = float(np.std(saturations))
    width_std = float(np.std(widths))
    height_std = float(np.std(heights))
    score = 100.0
    score -= min(18.0, contrast_std * 220.0)
    score -= min(14.0, saturation_std * 220.0)
    score -= min(10.0, width_std / 32.0)
    score -= min(10.0, height_std / 32.0)
    return _clamp(score)


def _parse_generation_speed(log_text: str) -> Dict[str, Any]:
    text = str(log_text or "")
    if not text.strip():
        return {}
    task_match = re.search(r"Found\s+(\d+)\s+tasks total", text)
    image_match = re.search(r"Successfully generated\s+(\d+)\s+images", text)
    elapsed_matches = [float(item) for item in re.findall(r"elapsed\s+([0-9.]+)s", text)]
    images = int(image_match.group(1)) if image_match else (int(task_match.group(1)) if task_match else 0)
    elapsed = max(elapsed_matches) if elapsed_matches else None
    avg_sec = (elapsed / images) if (elapsed and images) else None
    return {
        "task_count": int(task_match.group(1)) if task_match else None,
        "image_count": images or None,
        "elapsed_seconds": round(elapsed, 2) if elapsed is not None else None,
        "avg_sec_per_image": round(avg_sec, 2) if avg_sec is not None else None,
    }


class Gemma4VisionReviewer:
    def __init__(self, model_path: Optional[str] = None) -> None:
        self.mode = str(os.environ.get("EVAL_MULTIMODAL_GEMMA4", "auto")).strip().lower() or "auto"
        self.model_path = model_path or self._resolve_model_path()
        self.max_images = max(1, int(os.environ.get("EVAL_MULTIMODAL_GEMMA4_MAX_IMAGES", "2")))
        self.max_new_tokens = max(96, int(os.environ.get("EVAL_MULTIMODAL_GEMMA4_MAX_NEW_TOKENS", "220")))
        self._model = None
        self._processor = None
        self._load_error: Optional[str] = None

    def _resolve_model_path(self) -> Optional[str]:
        explicit = os.environ.get("EVAL_MULTIMODAL_GEMMA4_PATH")
        candidates = [explicit] if explicit else []
        candidates.extend(_GEMMA4_CANDIDATES)
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate)
            if path.exists() and path.is_dir():
                return os.fspath(path)
        return None

    def is_enabled(self) -> bool:
        return self.mode != "off"

    def is_available(self) -> bool:
        if not self.is_enabled():
            self._load_error = "disabled"
            return False
        if not self.model_path:
            self._load_error = "model_not_found"
            return False
        return True

    def _ensure_loaded(self) -> bool:
        if self._model is not None and self._processor is not None:
            return True
        if not self.is_available():
            return False
        try:
            import torch  # type: ignore
            from transformers import AutoModelForMultimodalLM, AutoProcessor  # type: ignore
        except Exception as exc:
            self._load_error = f"missing_dependency:{exc}"
            return False

        try:
            self._processor = AutoProcessor.from_pretrained(self.model_path)
            self._model = AutoModelForMultimodalLM.from_pretrained(
                self.model_path,
                dtype="auto",
                device_map="auto",
                low_cpu_mem_usage=True,
            )
            if hasattr(torch, "cuda") and torch.cuda.is_available():
                logger.info("Loaded Gemma 4 multimodal reviewer from %s", self.model_path)
            return True
        except Exception as exc:
            self._load_error = str(exc)
            self._model = None
            self._processor = None
            logger.warning("Gemma 4 reviewer unavailable: %s", exc)
            return False

    def describe_error(self) -> Optional[str]:
        return self._load_error

    def review_pairs(self, story_title: str, pairs: Sequence[Dict[str, Any]], story_text: str) -> Optional[Dict[str, Any]]:
        if not self._ensure_loaded():
            return None
        assert self._model is not None
        assert self._processor is not None

        sampled_pairs = [pair for pair in pairs if pair.get("image_path")][: self.max_images]
        if not sampled_pairs:
            return None

        results: List[Dict[str, Any]] = []
        for pair in sampled_pairs:
            prompt_text = str(pair.get("prompt_text") or "").strip()
            reference_text = str(pair.get("page_text") or story_text or "").strip()
            prompt = (
                "Return compact JSON only with keys alignment, child_safety, visual_clarity, issues, summary. "
                f"Story title: {story_title}. "
                f"Reference text: {reference_text[:420]} "
                f"Image prompt: {prompt_text[:260]} "
                "Judge whether the image matches the story page, remains child-safe, and is visually clear for a children's storybook."
            )
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "path": str(pair["image_path"])},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            try:
                try:
                    inputs = self._processor.apply_chat_template(
                        messages,
                        tokenize=True,
                        return_dict=True,
                        return_tensors="pt",
                        add_generation_prompt=True,
                        enable_thinking=False,
                    )
                except TypeError:
                    inputs = self._processor.apply_chat_template(
                        messages,
                        tokenize=True,
                        return_dict=True,
                        return_tensors="pt",
                        add_generation_prompt=True,
                    )
                model_device = getattr(self._model, "device", None)
                if model_device is not None and hasattr(inputs, "to"):
                    try:
                        inputs = inputs.to(model_device)
                    except Exception:
                        pass
                outputs = self._model.generate(**inputs, max_new_tokens=self.max_new_tokens)
                input_len = int(inputs["input_ids"].shape[-1])
                decoded = self._processor.decode(outputs[0][input_len:], skip_special_tokens=True)
                parsed = self._parse_json(decoded)
                if parsed:
                    parsed["image_path"] = str(pair["image_path"])
                    parsed["kind"] = pair.get("kind")
                    results.append(parsed)
            except Exception as exc:
                self._load_error = f"inference_failed:{exc}"
                logger.warning("Gemma 4 multimodal review failed for %s: %s", pair.get("image_path"), exc)
                return None

        if not results:
            return None

        alignment = mean(_safe_float(item.get("alignment"), 0.0) for item in results)
        child_safety = mean(_safe_float(item.get("child_safety"), 0.0) for item in results)
        clarity = mean(_safe_float(item.get("visual_clarity"), 0.0) for item in results)
        issues: List[str] = []
        for item in results:
            raw = item.get("issues")
            if isinstance(raw, list):
                issues.extend(str(entry).strip() for entry in raw if str(entry).strip())
        return {
            "available": True,
            "model_path": self.model_path,
            "sampled_images": len(results),
            "scores": {
                "alignment": round(alignment, 2),
                "child_safety": round(child_safety, 2),
                "visual_clarity": round(clarity, 2),
                "final": round(alignment * 0.55 + child_safety * 0.2 + clarity * 0.25, 2),
            },
            "issues": sorted(dict.fromkeys(issues)),
            "raw": results,
        }

    @staticmethod
    def _parse_json(decoded: str) -> Optional[Dict[str, Any]]:
        text = str(decoded or "").strip()
        if not text:
            return None
        match = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = match.group(0) if match else text
        try:
            payload = json.loads(candidate)
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None


class MultimodalAlignmentChecker:
    def __init__(self) -> None:
        self.gemma4 = Gemma4VisionReviewer()

    def get_documents_for_multimodal_alignment(self, available_documents: Dict[str, str]) -> Dict[str, str]:
        if "full_story.txt" in available_documents:
            return {"full_story.txt": available_documents["full_story.txt"]}
        return available_documents

    def get_document_weights_for_multimodal_alignment(self) -> Dict[str, float]:
        return {"full_story.txt": 1.0}

    def check(
        self,
        story_text: str,
        story_title: str,
        *,
        image_paths: Optional[List[str]] = None,
        image_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context = image_context or {}
        pairs = list(context.get("pairs") or [])
        image_paths = [str(path) for path in (image_paths or context.get("image_paths") or []) if path]
        image_metrics: List[Dict[str, Any]] = []
        issues: List[str] = []
        recommendations: List[str] = []

        if not image_paths:
            recommendations.append("No story illustration assets were found. Regenerate images before trusting final visual quality.")
            return {
                "dimension": "multimodal_alignment",
                "score": 58.0,
                "status": "degraded",
                "error": "missing_image_assets",
                "issues": ["missing_image_assets"],
                "recommendations": recommendations,
                "scores": {
                    "prompt_specificity": 0.0,
                    "story_prompt_alignment": 0.0,
                    "image_quality": 0.0,
                    "style_consistency": 0.0,
                    "child_safety": 100.0,
                    "final": 58.0,
                },
                "coverage": {
                    "image_count": 0,
                    "pair_count": 0,
                    "paired_prompts": 0,
                },
            }

        prompt_specificity_scores: List[float] = []
        alignment_scores: List[float] = []
        child_safety_scores: List[float] = []
        pair_breakdown: List[Dict[str, Any]] = []

        if not pairs:
            pairs = [{"kind": "page", "image_path": path, "prompt_text": "", "page_text": ""} for path in image_paths]

        for pair in pairs:
            image_path = str(pair.get("image_path") or "").strip()
            if not image_path:
                continue
            prompt_text = str(pair.get("prompt_text") or "").strip()
            reference_text = str(pair.get("page_text") or story_text or "").strip()
            prompt_score, prompt_meta = _score_prompt_specificity(prompt_text)
            align_score, align_meta = _score_text_alignment(reference_text, prompt_text)
            if not prompt_text:
                align_score = min(align_score, 45.0)
            safety_score, safety_hits = _score_child_safety(prompt_text)
            try:
                image_score, metrics = _score_image_metrics(image_path)
            except Exception as exc:
                logger.warning("Failed to inspect image %s: %s", image_path, exc)
                image_score = 55.0
                metrics = {"error": str(exc)}
                issues.append(f"image_inspection_failed:{Path(image_path).name}")

            prompt_specificity_scores.append(prompt_score)
            alignment_scores.append(align_score)
            child_safety_scores.append(safety_score)
            image_metrics.append({"image_path": image_path, "score": image_score, **metrics})

            pair_breakdown.append(
                {
                    "kind": pair.get("kind"),
                    "page": pair.get("page"),
                    "image_path": image_path,
                    "prompt_path": pair.get("prompt_path"),
                    "prompt_specificity": round(prompt_score, 2),
                    "story_prompt_alignment": round(align_score, 2),
                    "child_safety": round(safety_score, 2),
                    "image_quality": round(image_score, 2),
                    "prompt_meta": prompt_meta,
                    "alignment_meta": align_meta,
                    "safety_hits": safety_hits,
                }
            )
            if prompt_meta.get("token_count", 0) < 12:
                issues.append(f"thin_prompt:{Path(image_path).name}")
            if not prompt_text:
                issues.append(f"missing_prompt:{Path(image_path).name}")
            if align_score < 58.0:
                issues.append(f"story_image_drift:{Path(image_path).name}")
            if image_score < 56.0:
                issues.append(f"low_visual_fidelity:{Path(image_path).name}")
            if safety_hits:
                issues.append(f"child_safety_prompt_flag:{Path(image_path).name}")

        style_consistency = _score_style_consistency(image_metrics)
        avg_image_quality = mean(item["score"] for item in image_metrics) if image_metrics else 55.0
        avg_prompt_specificity = mean(prompt_specificity_scores) if prompt_specificity_scores else 55.0
        avg_alignment = mean(alignment_scores) if alignment_scores else 55.0
        avg_child_safety = mean(child_safety_scores) if child_safety_scores else 100.0

        heuristic_final = _clamp(
            avg_prompt_specificity * 0.24
            + avg_alignment * 0.28
            + avg_image_quality * 0.28
            + style_consistency * 0.12
            + avg_child_safety * 0.08
        )

        gemma4_result = self.gemma4.review_pairs(story_title, pairs, story_text)
        gemma_available = bool(gemma4_result and gemma4_result.get("scores"))
        gemma_final = _safe_float((gemma4_result or {}).get("scores", {}).get("final"), heuristic_final)
        final_score = _clamp(heuristic_final * 0.72 + gemma_final * 0.28) if gemma_available else heuristic_final

        runtime_diag = self._build_runtime_diagnostic(
            image_context=context,
            avg_prompt_specificity=avg_prompt_specificity,
            avg_alignment=avg_alignment,
            avg_image_quality=avg_image_quality,
            style_consistency=style_consistency,
        )

        if avg_prompt_specificity < 66.0:
            recommendations.append("Increase scene prompt density before diffusion. Current prompts are too thin for reliable storybook illustration quality.")
        if avg_alignment < 64.0:
            recommendations.append("Tighten page-level prompt generation. Several image prompts drift away from the corresponding page text.")
        if avg_image_quality < 62.0:
            recommendations.append("Raise image fidelity settings or move away from the current fast SDXL path for final deliverables.")
        if style_consistency < 72.0:
            recommendations.append("Lock style anchors and sampling settings more tightly across pages to reduce visual drift.")
        if runtime_diag.get("sdxl_suitability", {}).get("status") in {"borderline", "legacy_limited"}:
            recommendations.append("Treat SDXL as a fallback baseline, not the final-quality default, for stories that need production-ready illustrations.")
        if not gemma_available and self.gemma4.is_enabled():
            recommendations.append("Install a local Gemma 4 multimodal checkpoint plus transformers/torch if you want model-based image review instead of heuristics only.")

        status = "success"
        if not gemma_available and self.gemma4.is_enabled():
            status = "degraded"
        if avg_alignment < 50.0 or avg_image_quality < 48.0:
            status = "degraded"

        unique_issues = sorted(dict.fromkeys(issues))
        unique_recommendations = list(dict.fromkeys(recommendations))[:6]
        confidence = 0.82 if gemma_available else 0.63
        if len(image_paths) < 3:
            confidence -= 0.08
        if not pairs:
            confidence -= 0.08
        confidence = max(0.25, min(0.94, confidence))

        return {
            "dimension": "multimodal_alignment",
            "score": round(final_score, 2),
            "status": status,
            "issues": unique_issues,
            "recommendations": unique_recommendations,
            "confidence": round(confidence, 3),
            "coverage": {
                "image_count": len(image_paths),
                "pair_count": len(pairs),
                "paired_prompts": len([pair for pair in pairs if pair.get("prompt_text")]),
            },
            "scores": {
                "prompt_specificity": round(avg_prompt_specificity, 2),
                "story_prompt_alignment": round(avg_alignment, 2),
                "image_quality": round(avg_image_quality, 2),
                "style_consistency": round(style_consistency, 2),
                "child_safety": round(avg_child_safety, 2),
                "gemma4_review": round(gemma_final, 2) if gemma_available else None,
                "final": round(final_score, 2),
            },
            "pair_breakdown": pair_breakdown[:16],
            "runtime_diagnostics": runtime_diag,
            "gemma4_review": gemma4_result or {
                "available": False,
                "mode": self.gemma4.mode,
                "reason": self.gemma4.describe_error(),
            },
        }

    def _build_runtime_diagnostic(
        self,
        *,
        image_context: Dict[str, Any],
        avg_prompt_specificity: float,
        avg_alignment: float,
        avg_image_quality: float,
        style_consistency: float,
    ) -> Dict[str, Any]:
        raw_photo_log = image_context.get("photo_log") or {}
        photo_log = _parse_generation_speed(raw_photo_log) if isinstance(raw_photo_log, str) else dict(raw_photo_log or {})
        generation_speed = {
            "avg_sec_per_image": photo_log.get("avg_sec_per_image"),
            "elapsed_seconds": photo_log.get("elapsed_seconds"),
            "image_count": photo_log.get("image_count"),
        }
        models_dir = Path("models")
        installed_modern = [
            name
            for name in ("FLUX.1-dev", "FLUX.1-schnell", "stable-diffusion-3.5-large", "stable-diffusion-3.5-large-turbo")
            if (models_dir / name).exists()
        ]
        sdxl_base = (models_dir / "stable-diffusion-xl-base-1.0").exists()
        sdxl_refiner = (models_dir / "stable-diffusion-xl-refiner-1.0").exists()
        story_meta = image_context.get("story_meta") or {}
        avg_sec_per_image = _safe_float(photo_log.get("avg_sec_per_image"), 0.0)

        status = "unknown"
        summary = "Image generator lineage could not be confirmed from artifacts."
        notes: List[str] = []
        if sdxl_base:
            status = "serviceable"
            summary = "SDXL remains a usable baseline, but it is no longer the strongest final-quality default for children's storybook illustration."
            if avg_prompt_specificity < 66.0 or avg_alignment < 64.0:
                status = "borderline"
                summary = "Current SDXL outputs are being limited by prompt quality and story-to-image drift."
            if avg_image_quality < 60.0:
                status = "borderline"
                summary = "Current SDXL outputs are visually below bar for direct-use storybook delivery."
            if avg_sec_per_image and avg_sec_per_image < 3.0 and avg_image_quality < 65.0:
                status = "legacy_limited"
                summary = "The current SDXL path appears tuned too aggressively for speed, which is hurting image fidelity."
                notes.append("generation_speed_bias")
            if not sdxl_refiner:
                notes.append("refiner_missing")
            if installed_modern:
                notes.append("newer_checkpoints_present_but_runtime_not_using_them")
        else:
            notes.append("sdxl_not_detected_locally")

        if not story_meta:
            notes.append("image_runtime_metadata_missing")
        else:
            if not isinstance(story_meta.get("image_model"), dict):
                notes.append("image_model_not_recorded_in_story_meta")

        if style_consistency < 72.0:
            notes.append("style_drift")

        return {
            "sdxl_suitability": {
                "status": status,
                "summary": summary,
                "sdxl_base_installed": sdxl_base,
                "sdxl_refiner_installed": sdxl_refiner,
                "newer_local_candidates": installed_modern,
                "notes": notes,
            },
            "generation_speed": generation_speed,
        }
