"""Image generation pipeline for story covers, character references, and page scenes."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import logging
import platform
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

try:
	import torch
except Exception:  # pragma: no cover - test environments may not have torch
	class _TorchFallback:
		dtype = object
		float16 = "float16"

	torch = _TorchFallback()  # type: ignore[assignment]
from PIL import Image
from tqdm import tqdm



from utils import (
	ensure_dir,
	list_character_prompt_files,
	list_page_prompt_files,
	load_or_create_seed,
	load_prompt,
	page_number_from_prompt,
	resolve_story_root,
	setup_logging,
	write_json_or_raise,
)
if platform.system().lower().startswith("win") or platform.system().lower().startswith("darwin"):
	logging.getLogger("torch.distributed.elastic").setLevel(logging.ERROR)

# Keep tokenizer and diffusers logging quiet during image generation.
logging.getLogger("transformers.tokenization_utils_base").setLevel(logging.ERROR)
logging.getLogger("transformers.models.clip.tokenization_clip").setLevel(logging.ERROR)

UNITY_CHARACTER_POSES: Sequence[str] = ("neutral", "walk", "reach", "hold", "surprised", "joyful", "sad")
UNITY_CHARACTER_FACINGS: Sequence[str] = ("front", "left_3q", "right_3q")
UNITY_ASSEMBLY_ORDER: Sequence[str] = ("backdrop", "midground_objects", "characters", "props", "foreground_overlay")
ProgressCallback = Optional[Callable[[Dict[str, Any]], None]]

@dataclass
class Config:
	"""Image generation configuration for story illustrations."""

	provider: str = "diffusers_flux"
	model_family: Optional[str] = "flux_schnell"
	base_model_dir: Path = Path("models/FLUX.1-schnell")
	refiner_model_dir: Path = Path("models/__disabled_refiner__")
	device: str = "auto"
	dtype: torch.dtype = getattr(torch, "bfloat16", torch.float16)
	quantization_mode: Optional[str] = "fp8"
	output_mode: str = "dual"
	asset_granularity: str = "page_bundle"
	bg_removal_policy: str = "characters_props"
	reuse_strategy: str = "page_bundle_first"
	width: int = 1024
	height: int = 768
	char_width: int = 1024
	char_height: int = 1024
	steps: int = 4
	guidance: float = 0.0
	refiner_steps: Optional[int] = None
	skip_refiner: bool = True
	negative_prompt: str = (
		"text, letters, words, watermark, signature, logo, frame, border, blurry, cropped, "
		"bad anatomy, bad hands, missing fingers, extra fingers, extra limbs, duplicated features, "
		"deformed, distorted face"
	)
	cover_prompt_suffix: str = (
		"children's picture-book cover illustration, readable thumbnail, clear focal subject, no text lettering"
	)
	character_prompt_suffix: str = (
		"children's picture-book character sheet, full body, clean silhouette, readable face, light plain background"
	)
	scene_prompt_suffix: str = (
		"children's picture-book scene illustration, layered depth, readable faces, coherent lighting, no text"
	)
	seed: Optional[int] = None
	remove_bg: bool = True
	low_vram: bool = True


@dataclass
class TaskRenderSettings:
	steps: int
	guidance: float
	skip_refiner: bool
	refiner_steps: Optional[int]


@dataclass
class RunConfig:
	"""Top-level runtime configuration for the image pipeline."""

	story_root: Optional[Path] = None
	output_root: Path = Path("output")
	log_level: int = logging.INFO
	log_format: str = "%(asctime)s [%(levelname)s] %(message)s"
	progress_label: str = "Generating images"
	sdxl: Config = field(default_factory=Config)



_rembg_session = None

def remove_background(input_path: Path, output_path: Path) -> bool:
	"""Remove the background from a generated character image when possible."""
	global _rembg_session
	try:
		from rembg import remove, new_session
	except ImportError:
		logging.warning("rembg not installed; skipping background removal for %s", input_path)
		return False

	try:
		if _rembg_session is None:
			_rembg_session = new_session("u2net", providers=["CUDAExecutionProvider", "CPUExecutionProvider"])
		image = Image.open(input_path).convert("RGBA")
		result = remove(image, session=_rembg_session)
		output_path.parent.mkdir(parents=True, exist_ok=True)
		result.save(output_path)
		return True
	except Exception as exc:  # pragma: no cover - best effort
		logging.warning("Failed to remove background for %s: %s", input_path, exc)
		return False
def _save_image(image: Image.Image, *paths: Path) -> None:
	"""Persist a generated image to each requested output path."""
	for path in paths:
		ensure_dir(path.parent)
		image.save(path)


def _safe_load_json(path: Path) -> Dict[str, Any]:
	try:
		if path.exists():
			payload = json.loads(path.read_text(encoding="utf-8"))
			if isinstance(payload, dict):
				return payload
	except Exception:
		return {}
	return {}


def _normalize_character_name(value: str) -> str:
	text = re.sub(r"\s+", " ", str(value or "")).strip()
	if not text:
		return ""
	text = re.sub(r"\([^)]*\)", "", text).strip()
	return text


def _unique_segments(parts: Sequence[str]) -> List[str]:
	seen: set[str] = set()
	result: List[str] = []
	for raw_part in parts:
		part = re.sub(r"\s+", " ", str(raw_part or "")).strip(" ,")
		if not part:
			continue
		key = part.lower()
		if key in seen:
			continue
		seen.add(key)
		result.append(part)
	return result


def _stable_task_seed(story_seed: int, namespace: str) -> int:
	digest = hashlib.sha256(f"{story_seed}:{namespace}".encode("utf-8")).digest()
	return int.from_bytes(digest[:8], "big") % 2147483646 + 1


def _load_page_visual_plan(resources_dir: Path, page_number: int) -> Dict[str, Any]:
	return _safe_load_json(resources_dir / f"page_{page_number}_visual_plan.json")


def _load_page_asset_plan(resources_dir: Path, page_number: int) -> Dict[str, Any]:
	return _safe_load_json(resources_dir / f"page_{page_number}_asset_plan.json")


def _canonical_asset_id(value: str, fallback: str = "asset") -> str:
	token = re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")
	return token or fallback


def _normalize_output_mode(value: str) -> str:
	token = str(value or "").strip().lower()
	return token if token in {"illustration_only", "dual", "unity_assets_only"} else "dual"


def _task_prompt_role(task_type: str) -> str:
	token = str(task_type or "").strip().lower()
	if token in {"cover"}:
		return "cover"
	if token in {"character", "character_pose_variant", "prop_sprite"}:
		return "character"
	return "page"


def _story_bundle_root(image_root: Path) -> Path:
	return image_root.parent


def _relative_output_path(bundle_root: Path, target: Path) -> str:
	try:
		return target.relative_to(bundle_root).as_posix()
	except ValueError:
		return target.as_posix()


def _index_character_bible(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
	result: Dict[str, Dict[str, Any]] = {}
	for item in payload.get("characters") or []:
		if not isinstance(item, dict):
			continue
		name = _normalize_character_name(item.get("name") or item.get("label") or "")
		if name:
			result[name] = item
	return result


def _string_list(value: Any) -> List[str]:
	if isinstance(value, str):
		text = re.sub(r"\s+", " ", value).strip(" ,.")
		return [text] if text else []
	if isinstance(value, list):
		return [re.sub(r"\s+", " ", str(item or "")).strip(" ,.") for item in value if str(item or "").strip()]
	return []


def _load_visual_story_context(resources_dir: Path) -> Dict[str, Any]:
	meta = _safe_load_json(resources_dir / "story_meta.json")
	profile = _safe_load_json(resources_dir / "kg_profile.json")
	character_bible = _safe_load_json(resources_dir / "character_bible.json")
	world_style_lock = _safe_load_json(resources_dir / "world_style_lock.json")
	input_meta = meta.get("input") if isinstance(meta.get("input"), dict) else {}
	theme_meta = profile.get("theme") if isinstance(profile.get("theme"), dict) else {}
	category_meta = profile.get("category") if isinstance(profile.get("category"), dict) else {}
	subcategory_meta = profile.get("subcategory") if isinstance(profile.get("subcategory"), dict) else {}
	raw_characters = []
	kg_payload = profile.get("kg_payload")
	if isinstance(kg_payload, dict):
		raw_characters = kg_payload.get("characters") or []
	characters = []
	character_profiles: Dict[str, str] = {}
	for item in raw_characters:
		name = _normalize_character_name(item.get("label") if isinstance(item, dict) else item)
		if name and name not in characters:
			characters.append(name)
		if isinstance(item, dict) and name:
			profile_bits = _unique_segments(
				[
					str(item.get("role") or "").strip(),
					str(item.get("appearance") or "").strip(),
					str(item.get("description") or "").strip(),
					str(item.get("outfit") or "").strip(),
				]
			)
			if profile_bits:
				character_profiles[name] = ", ".join(profile_bits[:3])
	scenes = []
	if isinstance(kg_payload, dict):
		for item in (kg_payload.get("scenes") or []):
			text = re.sub(r"\s+", " ", str(item or "")).strip(" ,.")
			if text:
				scenes.append(text)
	return {
		"title": str(meta.get("story_title") or "").strip(),
		"age_label": str(input_meta.get("age_group") or "").strip(),
		"category": str(category_meta.get("label") or input_meta.get("category") or "").strip(),
		"subcategory": str(subcategory_meta.get("label") or input_meta.get("subcategory") or "").strip(),
		"theme": str(theme_meta.get("label") or input_meta.get("theme") or "").strip(),
		"visual_style": str(profile.get("visual_style") or "").strip(),
		"characters": characters,
		"character_profiles": character_profiles,
		"scenes": scenes[:3],
		"character_bible": character_bible,
		"character_bible_map": _index_character_bible(character_bible),
		"world_style_lock": world_style_lock,
	}


def _classify_image_model(config: Config) -> str:
	return "flux_schnell"


def _default_style_anchor(task_type: str) -> str:
	if task_type == "cover":
		return "warm storybook gouache cover art, crisp focal silhouette, luminous contrast, readable thumbnail"
	if task_type == "character":
		return "storybook character illustration, clean silhouette, readable face detail, consistent outfit colors"
	return "warm storybook gouache illustration, clear focal subject, layered depth, painterly texture"


def _age_visual_anchor(age_label: str) -> str:
	token = str(age_label or "").strip().lower()
	if "2-3" in token:
		return "simple shapes, large readable faces, gentle palette, minimal clutter"
	if "4-5" in token:
		return "warm gouache watercolor texture, cozy palette, clear expressions, soft contrast"
	if "6-8" in token:
		return "richer environmental detail, cinematic framing, luminous atmosphere, readable action"
	return "child-safe storybook illustration, readable faces, gentle painterly texture"


def _task_composition_anchor(task_type: str) -> str:
	if task_type == "cover":
		return "single iconic focal moment, uncluttered composition, clear prop hook"
	if task_type == "character":
		return "full-body view, readable hands, centered silhouette, plain light background"
	return "clear foreground midground background separation, readable hands and faces, child-safe composition"


def _prompt_word_budget(task_type: str, model_family: str) -> int:
	if model_family == "flux_schnell":
		if task_type == "cover":
			return 44
		if task_type == "character":
			return 38
		return 52
	if task_type == "character":
		return 72
	return 84


def _family_suffix(suffix: str, task_type: str, model_family: str) -> str:
	if model_family == "flux_schnell":
		if task_type == "cover":
			return "children's picture-book cover illustration, readable thumbnail, clear focal subject, no text lettering"
		if task_type == "character":
			return "children's picture-book character sheet, full body, clean silhouette, readable face, light plain background"
		return "children's picture-book scene illustration, layered depth, readable faces, coherent lighting, no text"
	return suffix


def _resolve_negative_prompt(config: Config, task_type: str) -> str:
	model_family = _classify_image_model(config)
	if model_family == "flux_schnell":
		return ""
	return str(config.negative_prompt or "").strip()


def _trim_prompt_words(text: str, max_words: int) -> str:
	words = [chunk for chunk in re.split(r"\s+", text.strip()) if chunk]
	if len(words) <= max_words:
		return " ".join(words)
	return " ".join(words[:max_words]).rstrip(",;:.")


def _compose_descriptive_prompt(base_prompt: str, extras: Sequence[str]) -> str:
	lead = re.sub(r"\s+", " ", str(base_prompt or "").strip()).strip(" ,")
	lead = lead.rstrip(".")
	extra_parts = _unique_segments(extras)
	if lead and extra_parts:
		text = f"{lead}, with " + ", ".join(extra_parts)
	elif lead:
		text = lead
	else:
		text = ", ".join(extra_parts)
	text = re.sub(r"\s+", " ", text).strip(" ,")
	if text and text[-1] not in ".!?":
		text += "."
	return text


def _resolve_task_render_settings(task: Dict[str, Any], config: Config) -> TaskRenderSettings:
	model_family = _classify_image_model(config)
	steps = max(1, int(config.steps))
	guidance = float(config.guidance)
	skip_refiner = bool(config.skip_refiner)
	refiner_steps = config.refiner_steps

	if model_family == "flux_schnell":
		steps = min(max(steps, 1), 4)
		guidance = 0.0
		skip_refiner = True
		refiner_steps = None

	return TaskRenderSettings(
		steps=steps,
		guidance=round(guidance, 2),
		skip_refiner=skip_refiner,
		refiner_steps=refiner_steps,
	)


def _compact_character_lock(entry: Dict[str, Any]) -> str:
	parts = [
		str(entry.get("name") or "").strip(),
		str(entry.get("hair") or "").strip(),
		str(entry.get("outfit_core") or "").strip(),
		", ".join(_string_list(entry.get("color_lock"))),
		str(entry.get("expression_style") or "").strip(),
	]
	return ", ".join(_unique_segments(parts[:5]))


def _constraint_phrase(constraints: Sequence[str]) -> str:
	formatted: List[str] = []
	for raw in constraints:
		text = re.sub(r"\s+", " ", str(raw or "")).strip(" ,.")
		if not text:
			continue
		lowered = text.casefold()
		if lowered.startswith(("no ", "without ")):
			formatted.append(text)
		else:
			formatted.append(f"no {text}")
	return ", ".join(_unique_segments(formatted[:6]))


def _build_task_control_metadata(
	*,
	task_type: str,
	base_prompt: str,
	context: Dict[str, Any],
	character_name: str = "",
	page_number: Optional[int] = None,
	page_plan: Optional[Dict[str, Any]] = None,
	task_role: Optional[str] = None,
) -> Dict[str, Any]:
	role = _task_prompt_role(task_role or task_type)
	characters = list(context.get("characters") or [])
	character_profiles = dict(context.get("character_profiles") or {})
	character_bible_map = dict(context.get("character_bible_map") or {})
	world_style_lock = dict(context.get("world_style_lock") or {})
	style = str(world_style_lock.get("style_lock") or context.get("visual_style") or "").strip() or _default_style_anchor(role)
	age_anchor = _age_visual_anchor(str(context.get("age_label") or ""))
	theme = str(context.get("theme") or "").strip()
	category = str(context.get("category") or "").strip()
	scenes = list(context.get("scenes") or [])

	if role == "cover":
		required_characters = characters[:2]
	elif role == "character":
		required_characters = [character_name] if character_name else characters[:1]
	else:
		required_characters = _string_list((page_plan or {}).get("required_characters")) or characters[:2]

	character_lock = []
	for name in required_characters:
		entry = character_bible_map.get(name) or {}
		lock = _compact_character_lock(entry) if entry else str(character_profiles.get(name) or name).strip()
		if lock:
			character_lock.append(lock)

	if role == "page":
		scene_grammar = _unique_segments(
			[
				f"{page_plan.get('shot', 'mid')}-shot" if page_plan else "",
				f"{page_plan.get('lighting', 'bright')} light" if page_plan else "",
				f"{page_plan.get('stage', 'action')} beat" if page_plan else "",
				f"focus on {page_plan.get('focus_subject', 'character')}" if page_plan else "",
				f"{page_plan.get('motion_level', 'light')} motion" if page_plan else "",
				f"{page_plan.get('emotion_density', 'calm')} mood" if page_plan else "",
				f"{page_plan.get('composition_balance', 'centered')} layout" if page_plan else "",
			]
		)
		scene_layout = _unique_segments(
			[
				f"foreground {', '.join(_string_list(page_plan.get('foreground_subjects')))}" if page_plan and page_plan.get("foreground_subjects") else "",
				f"midground {', '.join(_string_list(page_plan.get('midground_subjects')))}" if page_plan and page_plan.get("midground_subjects") else "",
				f"background {', '.join(_string_list(page_plan.get('background_subjects')))}" if page_plan and page_plan.get("background_subjects") else "",
			]
		)
		negative_constraints = _string_list((page_plan or {}).get("forbidden_elements")) or ["text", "watermark", "extra characters"]
		page_event = str((page_plan or {}).get("scene_core") or (page_plan or {}).get("scene_goal") or base_prompt).strip()
	else:
		scene_grammar = _unique_segments(
			[
				"single iconic cover moment" if role == "cover" else "full-body character reference",
				"clear subject hierarchy",
				"child-readable composition",
				_task_composition_anchor(role),
			]
		)
		scene_layout = _unique_segments(
			[
				f"world anchor {scenes[0]}" if role == "cover" and scenes else "",
				"plain light background" if role == "character" else "",
			]
		)
		negative_constraints = list(world_style_lock.get("forbidden_styles") or ["text overlay"])
		if role == "cover":
			negative_constraints.extend(["text lettering", "watermark"])
		else:
			negative_constraints.extend(["busy background", "extra characters", "text"])
		page_event = base_prompt

	if role == "page":
		style_lock = _unique_segments(
			[
				style,
				"readable picture-book frame",
				f"{theme} tone" if theme else "",
			]
		)
	else:
		style_lock = _unique_segments(
			[
				style,
				str(world_style_lock.get("render_principle") or "").strip(),
				age_anchor,
				f"{theme} mood" if theme else "",
				f"{category} picture-book world" if category else "",
				"one-glance child-readable story moment",
			]
		)
	return {
		"style_lock": style_lock,
		"character_lock": character_lock,
		"scene_grammar": scene_grammar,
		"page_event": page_event,
		"scene_layout": scene_layout,
		"negative_constraints": _unique_segments(negative_constraints),
		"required_characters": required_characters,
		"world_anchor": str((page_plan or {}).get("world_anchor") or (scenes[0] if scenes else "")).strip(),
		"continuity_keys": dict((page_plan or {}).get("continuity_keys") or {}),
		"task_type": task_type,
		"task_role": role,
		"page_number": page_number,
	}


def _build_visual_prompt(
	base_prompt: str,
	*,
	task_type: str,
	suffix: str,
	context: Dict[str, Any],
	character_name: str = "",
	page_number: Optional[int] = None,
	control_metadata: Optional[Dict[str, Any]] = None,
	task_role: Optional[str] = None,
) -> str:
	role = _task_prompt_role(task_role or task_type)
	model_family = str(context.get("image_model_family") or "").strip().lower()
	final_suffix = _family_suffix(suffix, role, model_family)
	control = dict(control_metadata or {})
	page_event = str(control.get("page_event") or base_prompt or "").strip()
	extras = _unique_segments(
		[
			*list(control.get("character_lock") or []),
			*list(control.get("scene_grammar") or []),
			*list(control.get("scene_layout") or []),
			_constraint_phrase(control.get("negative_constraints") or []),
			*list(control.get("style_lock") or []),
			final_suffix,
		]
	)
	word_budget = _prompt_word_budget(role, model_family)
	if model_family in {"flux_schnell", "flux"}:
		return _trim_prompt_words(_compose_descriptive_prompt(page_event, extras), word_budget)
	return _trim_prompt_words(", ".join(_unique_segments([page_event, *extras])), word_budget)


def _build_character_prompt_from_context(name: str, context: Dict[str, Any]) -> str:
	style = str(context.get("visual_style") or "").strip()
	theme = str(context.get("theme") or "").strip()
	category = str(context.get("category") or "").strip()
	character_profiles = dict(context.get("character_profiles") or {})
	profile_text = str(character_profiles.get(name) or "").strip()
	segments = [
		f"{name}, signature outfit and features kept consistent across pages",
		profile_text,
		f"{category} story character" if category else "storybook character",
		f"theme: {theme}" if theme else "",
		style,
		"warm expression, readable silhouette, full body, clear hands and face",
	]
	return ", ".join(_unique_segments(segments))


def _select_unity_character_catalog(
	asset_plans: Sequence[Dict[str, Any]],
	context: Dict[str, Any],
) -> List[Dict[str, Any]]:
	appearance_counts: Counter[str] = Counter()
	label_by_id: Dict[str, str] = {}
	for plan in asset_plans:
		for item in plan.get("characters") or []:
			character_id = _canonical_asset_id(str(item.get("character_id") or ""), "character")
			label = _normalize_character_name(item.get("label") or "")
			if not label:
				label = _normalize_character_name(item.get("character_name") or "")
			if character_id:
				appearance_counts[character_id] += 1
				if label:
					label_by_id[character_id] = label
	for name in context.get("characters") or []:
		label = _normalize_character_name(name)
		if label:
			label_by_id.setdefault(_canonical_asset_id(label, "character"), label)
	for item in (context.get("character_bible") or {}).get("characters") or []:
		label = _normalize_character_name(item.get("name") or item.get("label") or "")
		if label:
			label_by_id.setdefault(_canonical_asset_id(label, "character"), label)
	ordered_ids: List[str] = []
	for name in context.get("characters") or []:
		character_id = _canonical_asset_id(_normalize_character_name(name), "character")
		if character_id not in ordered_ids:
			ordered_ids.append(character_id)
	for character_id in appearance_counts:
		if character_id not in ordered_ids:
			ordered_ids.append(character_id)
	primary_ids = ordered_ids[:2]
	recurring_ids = {character_id for character_id, count in appearance_counts.items() if count >= 2}
	for item in (context.get("character_bible") or {}).get("characters") or []:
		role = str(item.get("role") or "").strip().casefold()
		label = _normalize_character_name(item.get("name") or item.get("label") or "")
		if label and "recurring" in role:
			recurring_ids.add(_canonical_asset_id(label, "character"))
	selected: List[Dict[str, Any]] = []
	for character_id in ordered_ids:
		if character_id not in primary_ids and character_id not in recurring_ids and appearance_counts.get(character_id, 0) <= 0:
			continue
		selected.append(
			{
				"character_id": character_id,
				"label": label_by_id.get(character_id, character_id.replace("_", " ").title()),
			}
		)
	return selected


def _pose_phrase(pose_id: str) -> str:
	return {
		"neutral": "standing calmly",
		"walk": "walking with a clear readable step",
		"reach": "reaching toward a story object",
		"hold": "holding a prop carefully",
		"surprised": "showing a surprised open reaction",
		"joyful": "showing a bright joyful smile",
		"sad": "showing a soft sad expression",
	}.get(str(pose_id or "").strip().lower(), "standing calmly")


def _facing_phrase(facing: str) -> str:
	return {
		"front": "front-facing",
		"left_3q": "left three-quarter view",
		"right_3q": "right three-quarter view",
	}.get(str(facing or "").strip().lower(), "front-facing")


def _build_unity_character_variant_prompt(
	*,
	character_name: str,
	base_prompt: str,
	pose_id: str,
	facing: str,
	context: Dict[str, Any],
	config: Config,
) -> tuple[str, Dict[str, Any]]:
	control = _build_task_control_metadata(
		task_type="character_pose_variant",
		base_prompt=base_prompt,
		context=context,
		character_name=character_name,
		task_role="character",
	)
	control["page_event"] = f"{character_name}, {_pose_phrase(pose_id)}, {_facing_phrase(facing)}, reusable character sprite"
	control["scene_grammar"] = _unique_segments(
		list(control.get("scene_grammar") or [])
		+ [f"{pose_id} pose", _facing_phrase(facing), "full body sprite", "isolated character asset"]
	)
	control["scene_layout"] = _unique_segments(["plain light background", "centered silhouette", "transparent-friendly framing"])
	control["negative_constraints"] = _unique_segments(list(control.get("negative_constraints") or []) + ["busy background", "extra characters", "cropped feet"])
	prompt = _build_visual_prompt(
		base_prompt,
		task_type="character_pose_variant",
		suffix=config.character_prompt_suffix,
		context=context,
		character_name=character_name,
		control_metadata=control,
		task_role="character",
	)
	return prompt, control


def _build_unity_scene_layer_prompt(
	*,
	task_type: str,
	base_prompt: str,
	context: Dict[str, Any],
	config: Config,
	page_number: int,
	page_plan: Dict[str, Any],
	scene_layout: Sequence[str],
	extra_negative: Sequence[str],
) -> tuple[str, Dict[str, Any]]:
	plan_payload = dict(page_plan or {})
	if task_type in {"page_backdrop", "page_foreground_overlay"}:
		plan_payload["required_characters"] = []
	control = _build_task_control_metadata(
		task_type=task_type,
		base_prompt=base_prompt,
		context=context,
		page_number=page_number,
		page_plan=plan_payload,
		task_role="page",
	)
	control["page_event"] = base_prompt
	control["scene_layout"] = _unique_segments(list(scene_layout))
	control["negative_constraints"] = _unique_segments(list(control.get("negative_constraints") or []) + list(extra_negative))
	prompt = _build_visual_prompt(
		base_prompt,
		task_type=task_type,
		suffix=config.scene_prompt_suffix,
		context=context,
		page_number=page_number,
		control_metadata=control,
		task_role="page",
	)
	return prompt, control


def _build_unity_object_prompt(
	*,
	task_type: str,
	base_prompt: str,
	character_name: str,
	context: Dict[str, Any],
	config: Config,
	page_number: Optional[int] = None,
	page_plan: Optional[Dict[str, Any]] = None,
) -> tuple[str, Dict[str, Any]]:
	control = _build_task_control_metadata(
		task_type=task_type,
		base_prompt=base_prompt,
		context=context,
		character_name=character_name,
		page_number=page_number,
		page_plan=page_plan,
		task_role="character",
	)
	control["page_event"] = base_prompt
	control["scene_grammar"] = _unique_segments(list(control.get("scene_grammar") or []) + ["isolated reusable storybook object", "clean silhouette"])
	control["scene_layout"] = _unique_segments(["plain light background", "single centered asset", "transparent-friendly framing"])
	control["negative_constraints"] = _unique_segments(list(control.get("negative_constraints") or []) + ["extra characters", "busy background", "cropped object"])
	prompt = _build_visual_prompt(
		base_prompt,
		task_type=task_type,
		suffix=config.character_prompt_suffix,
		context=context,
		character_name=character_name,
		page_number=page_number,
		control_metadata=control,
		task_role="character",
	)
	return prompt, control


def _unity_remove_bg(task_type: str, config: Config) -> bool:
	task_key = str(task_type or "").strip().lower()
	if task_key == "character":
		return bool(config.remove_bg)
	if task_key in {"page_backdrop", "page_preview", "cover"}:
		return False
	if task_key in {"character_pose_variant", "prop_sprite", "page_foreground_overlay", "page_midground_object"}:
		return str(getattr(config, "bg_removal_policy", "characters_props") or "characters_props").strip().lower() != "none"
	return False


def _unity_raw_path(image_root: Path, final_path: Path) -> Path:
	unity_root = image_root / "unity"
	try:
		relative = final_path.relative_to(unity_root)
	except ValueError:
		relative = Path(final_path.name)
	return unity_root / "_original" / relative


def _safe_emit_progress(callback: ProgressCallback, **payload: Any) -> None:
	if callback is None:
		return
	try:
		callback(dict(payload))
	except Exception:
		return


def _task_progress_label(task: Dict[str, Any]) -> str:
	task_type = str(task.get("type") or "").strip().lower()
	metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
	page = metadata.get("page")
	char_name = str(metadata.get("char") or "").strip()
	canonical_id = str(metadata.get("canonical_id") or "").strip()
	pose_id = str(metadata.get("pose_id") or "").strip()
	facing = str(metadata.get("facing") or "").strip()
	if task_type == "cover":
		return "cover"
	if task_type == "character":
		return f"character {char_name or metadata.get('char_id') or task.get('id')}"
	if task_type == "character_pose_variant":
		pose_bits = "/".join(bit for bit in (pose_id, facing) if bit)
		return f"sprite {char_name or metadata.get('char_id') or task.get('id')} {pose_bits}".strip()
	if task_type == "page":
		return f"page {page} preview"
	if task_type == "page_backdrop":
		return f"page {page} backdrop"
	if task_type == "page_foreground_overlay":
		return f"page {page} foreground overlay"
	if task_type == "page_midground_object":
		return f"page {page} midground {canonical_id or task.get('id')}"
	if task_type == "prop_sprite":
		return f"prop {canonical_id or metadata.get('label') or task.get('id')}"
	return str(task.get("id") or task_type or "task")


def _task_progress_payload(
	*,
	task: Optional[Dict[str, Any]],
	phase: str,
	event: str,
	completed_units: int,
	total_units: int,
	task_index: int,
	task_total: int,
) -> Dict[str, Any]:
	payload: Dict[str, Any] = {
		"stage": "IMAGE",
		"phase": str(phase or "").strip().lower(),
		"event": str(event or "").strip().lower(),
		"completed_units": int(max(0, completed_units)),
		"total_units": int(max(0, total_units)),
		"task_index": int(max(0, task_index)),
		"task_total": int(max(0, task_total)),
		"updated_at": time.time(),
	}
	if task is None:
		return payload
	metadata = task.get("metadata") if isinstance(task.get("metadata"), dict) else {}
	payload.update(
		{
			"task_id": str(task.get("id") or ""),
			"task_type": str(task.get("type") or ""),
			"task_label": _task_progress_label(task),
			"page_number": metadata.get("page"),
		}
	)
	return payload


def _collect_generation_tasks(
	story_root: Path,
	resources_dir: Path,
	config: Config,
	logger: logging.Logger,
	output_root_override: Optional[Path] = None,
) -> List[Dict[str, Any]]:
	"""Collect all image-generation tasks from one resource directory."""

	if output_root_override:
		image_root = output_root_override
	else:
		image_root = story_root / "image"

	image_main_dir = image_root / "main"
	image_original_dir = image_root / "original"
	image_nobg_dir = image_root / "nobg"
	unity_root = image_root / "unity"
	unity_characters_dir = unity_root / "characters"
	unity_props_dir = unity_root / "props"
	unity_pages_dir = unity_root / "pages"
	bundle_root = _story_bundle_root(image_root)

	for d in (image_main_dir, image_original_dir, image_nobg_dir, unity_characters_dir, unity_props_dir, unity_pages_dir):
		ensure_dir(d)

	story_seed = config.seed if config.seed is not None else load_or_create_seed(resources_dir)
	story_context = _load_visual_story_context(resources_dir)
	story_context["image_model_family"] = _classify_image_model(config)
	story_meta = _safe_load_json(resources_dir / "story_meta.json")
	output_mode = _normalize_output_mode(getattr(config, "output_mode", "dual"))
	emit_legacy = output_mode in {"illustration_only", "dual"}
	emit_unity = output_mode in {"dual", "unity_assets_only"}
	manifest_dir = resources_dir / "render_manifests"
	ensure_dir(manifest_dir)
	tasks: List[Dict[str, Any]] = []

	def _fallback_asset_plan(page_number: int, page_plan: Dict[str, Any]) -> Dict[str, Any]:
		required_characters = _string_list(page_plan.get("required_characters")) or list(story_context.get("characters") or [])[:1]
		world_anchor = str(page_plan.get("world_anchor") or page_plan.get("location") or "").strip()
		characters = [
			{
				"character_id": _canonical_asset_id(name, "character"),
				"label": name,
				"pose_id": "neutral",
				"facing": "front",
				"layer": "characters",
				"slot": "center" if index == 0 else "right",
				"scale_hint": "medium",
				"remove_bg": True,
			}
			for index, name in enumerate(required_characters[:3])
		]
		backdrop_subject = world_anchor or str(page_plan.get("scene_core") or page_plan.get("scene_goal") or "storybook backdrop").strip()
		foreground_subject = ", ".join(_string_list(page_plan.get("foreground_subjects"))) or "soft foreground decor"
		return {
			"page_number": page_number,
			"branch_id": str(page_plan.get("branch_id") or resources_dir.parent.name),
			"world_anchor": world_anchor,
			"shot": str(page_plan.get("shot") or "mid"),
			"lighting": str(page_plan.get("lighting") or "bright"),
			"stage": str(page_plan.get("stage") or "action"),
			"story_readability_goal": str(page_plan.get("story_readability_goal") or "one clear child-readable story moment").strip(),
			"backdrop_prompt": f"{backdrop_subject}, storybook backdrop, no characters, open stage space for Unity assembly",
			"foreground_overlay_prompt": f"{foreground_subject}, foreground overlay only, no characters, transparent-friendly decor layer",
			"midground_objects": [],
			"characters": characters,
			"props": [],
			"interactives": [],
			"assembly_order": list(UNITY_ASSEMBLY_ORDER),
			"continuity_keys": dict(page_plan.get("continuity_keys") or {}),
		}

	def _add_task(
		*,
		task_type: str,
		task_id: str,
		prompt: str,
		seed: int,
		width: int,
		height: int,
		output_paths: Sequence[Path],
		manifest_path: Path,
		manifest: Dict[str, Any],
		metadata: Dict[str, Any],
		remove_bg: bool,
		nobg_path: Optional[Path] = None,
		bg_input_path: Optional[Path] = None,
	) -> None:
		task: Dict[str, Any] = {
			"type": task_type,
			"id": task_id,
			"prompt": prompt,
			"seed": seed,
			"width": width,
			"height": height,
			"output_paths": list(output_paths),
			"metadata": metadata,
			"control_metadata": manifest.get("control_metadata") or metadata.get("control_metadata") or {},
			"manifest": manifest,
			"manifest_path": manifest_path,
			"remove_bg": remove_bg,
		}
		if nobg_path is not None:
			task["nobg_path"] = nobg_path
		if bg_input_path is not None:
			task["bg_input_path"] = bg_input_path
		write_json_or_raise(manifest_path, manifest)
		tasks.append(task)

	unity_story_manifest: Dict[str, Any] = {
		"story_id": str(story_meta.get("story_id") or bundle_root.name),
		"story_title": str(story_meta.get("story_title") or story_context.get("title") or bundle_root.name),
		"branch_id": "",
		"characters": [],
		"props": [],
		"pages": [],
	}
	unity_character_index: Dict[str, Dict[str, Any]] = {}
	unity_prop_index: Dict[str, Dict[str, Any]] = {}

	# Cover Task
	cover_prompt_path = resources_dir / "book_cover_prompt.txt"
	if cover_prompt_path.exists():
		prompt_text = load_prompt(cover_prompt_path)
		if prompt_text:
			control_metadata = _build_task_control_metadata(
				task_type="cover",
				base_prompt=prompt_text,
				context=story_context,
			)
			task_seed = _stable_task_seed(story_seed, "cover")
			final_prompt = _build_visual_prompt(
				prompt_text,
				task_type="cover",
				suffix=config.cover_prompt_suffix,
				context=story_context,
				control_metadata=control_metadata,
			)
			manifest = {
				"status": "planned",
				"task_id": "cover",
				"task_type": "cover",
				"surface_prompt": final_prompt,
				"source_prompt": prompt_text,
				"control_metadata": control_metadata,
				"seed_bundle": {"story_seed": story_seed, "cover_seed": task_seed},
				"output_files": ["book_cover.png"],
			}
			cover_outputs = [image_original_dir / "book_cover.png", image_main_dir / "book_cover.png"]
			_add_task(
				task_type="cover",
				task_id="cover",
				prompt=final_prompt,
				seed=task_seed,
				width=config.width,
				height=config.height,
				output_paths=cover_outputs,
				manifest_path=manifest_dir / "cover_render_manifest.json",
				manifest=manifest,
				metadata={"type": "cover", "control_metadata": control_metadata, "seed_bundle": manifest["seed_bundle"]},
				remove_bg=False,
			)
			if emit_unity:
				unity_story_manifest["cover"] = {
					"path": _relative_output_path(bundle_root, image_main_dir / "book_cover.png"),
					"title_safe_area": {"x": 0.1, "y": 0.08, "width": 0.8, "height": 0.22},
				}

	# Character Tasks
	character_files = list_character_prompt_files(resources_dir)
	character_prompts: Dict[str, str] = {}
	for char_path in character_files:
		prompt_text = load_prompt(char_path)
		if not prompt_text:
			logger.warning("Character prompt empty: %s", char_path)
			continue
		char_name = char_path.stem.replace("character_", "")
		character_prompts[char_name] = prompt_text

	if not character_prompts:
		for char_name in (story_context.get("characters") or []):
			character_prompts[str(char_name)] = _build_character_prompt_from_context(str(char_name), story_context)

	if emit_legacy:
		for char_name, prompt_text in character_prompts.items():
			safe_char_id = re.sub(r"[^A-Za-z0-9]+", "_", char_name).strip("_") or "character"
			control_metadata = _build_task_control_metadata(
				task_type="character",
				base_prompt=prompt_text,
				context=story_context,
				character_name=char_name,
			)
			task_seed = _stable_task_seed(story_seed, f"character:{safe_char_id}")
			final_prompt = _build_visual_prompt(
				prompt_text,
				task_type="character",
				suffix=config.character_prompt_suffix,
				context=story_context,
				character_name=char_name,
				control_metadata=control_metadata,
			)
			filename = f"character_{safe_char_id}.png"
			manifest = {
				"status": "planned",
				"task_id": f"char_{safe_char_id}",
				"task_type": "character",
				"surface_prompt": final_prompt,
				"source_prompt": prompt_text,
				"control_metadata": control_metadata,
				"seed_bundle": {"story_seed": story_seed, "character_seed": task_seed},
				"output_files": [filename],
			}
			_add_task(
				task_type="character",
				task_id=f"char_{safe_char_id}",
				prompt=final_prompt,
				seed=task_seed,
				width=config.char_width,
				height=config.char_height,
				output_paths=[image_original_dir / filename, image_main_dir / filename],
				manifest_path=manifest_dir / f"character_{safe_char_id}_render_manifest.json",
				manifest=manifest,
				metadata={
					"char": char_name,
					"char_id": safe_char_id,
					"control_metadata": control_metadata,
					"seed_bundle": manifest["seed_bundle"],
				},
				remove_bg=_unity_remove_bg("character", config),
				nobg_path=image_nobg_dir / filename,
			)

	# Page and Unity Tasks
	page_files = list_page_prompt_files(resources_dir)
	page_numbers = [page_number_from_prompt(page_path) for page_path in page_files]
	page_visual_plans: Dict[int, Dict[str, Any]] = {}
	page_asset_plans: Dict[int, Dict[str, Any]] = {}
	for page_path in page_files:
		prompt_text = load_prompt(page_path)
		if not prompt_text:
			logger.warning("Page prompt empty: %s", page_path)
			continue
		page_number = page_number_from_prompt(page_path)
		page_plan = _load_page_visual_plan(resources_dir, page_number)
		page_visual_plans[page_number] = page_plan
		page_asset_plan = _load_page_asset_plan(resources_dir, page_number) or _fallback_asset_plan(page_number, page_plan)
		page_asset_plans[page_number] = page_asset_plan
		unity_story_manifest["branch_id"] = str(page_asset_plan.get("branch_id") or unity_story_manifest.get("branch_id") or resources_dir.parent.name)
		if emit_legacy:
			control_metadata = _build_task_control_metadata(
				task_type="page",
				base_prompt=prompt_text,
				context=story_context,
				page_number=page_number,
				page_plan=page_plan,
			)
			task_seed = _stable_task_seed(story_seed, f"page:{page_number}")
			final_prompt = _build_visual_prompt(
				prompt_text,
				task_type="page",
				suffix=config.scene_prompt_suffix,
				context=story_context,
				page_number=page_number,
				control_metadata=control_metadata,
			)
			filename = f"page_{page_number}_scene.png"
			manifest = {
				"status": "planned",
				"task_id": f"page_{page_number}",
				"task_type": "page_preview",
				"surface_prompt": final_prompt,
				"source_prompt": prompt_text,
				"control_metadata": control_metadata,
				"page_visual_plan": page_plan,
				"seed_bundle": {"story_seed": story_seed, "page_seed": task_seed},
				"output_files": [filename],
			}
			_add_task(
				task_type="page",
				task_id=f"page_{page_number}",
				prompt=final_prompt,
				seed=task_seed,
				width=config.width,
				height=config.height,
				output_paths=[image_original_dir / filename, image_main_dir / filename],
				manifest_path=manifest_dir / f"page_{page_number}_render_manifest.json",
				manifest=manifest,
				metadata={
					"page": page_number,
					"task_variant": "page_preview",
					"control_metadata": control_metadata,
					"seed_bundle": manifest["seed_bundle"],
					"shot": page_plan.get("shot"),
					"lighting": page_plan.get("lighting"),
					"stage": page_plan.get("stage"),
				},
				remove_bg=False,
			)

	if emit_unity:
		selected_characters = _select_unity_character_catalog(list(page_asset_plans.values()), story_context)
		for entry in selected_characters:
			character_name = str(entry.get("label") or "").strip()
			character_id = str(entry.get("character_id") or _canonical_asset_id(character_name, "character")).strip()
			base_prompt = character_prompts.get(character_name) or _build_character_prompt_from_context(character_name, story_context)
			for pose_id in UNITY_CHARACTER_POSES:
				for facing in UNITY_CHARACTER_FACINGS:
					final_prompt, control_metadata = _build_unity_character_variant_prompt(
						character_name=character_name,
						base_prompt=base_prompt,
						pose_id=pose_id,
						facing=facing,
						context=story_context,
						config=config,
					)
					final_path = unity_characters_dir / character_id / f"{pose_id}__{facing}.png"
					remove_bg = _unity_remove_bg("character_pose_variant", config)
					raw_path = _unity_raw_path(image_root, final_path) if remove_bg else final_path
					task_seed = _stable_task_seed(story_seed, f"character_pose:{character_id}:{pose_id}:{facing}")
					manifest = {
						"status": "planned",
						"task_id": f"character_pose::{character_id}::{pose_id}::{facing}",
						"task_type": "character_pose_variant",
						"canonical_id": character_id,
						"surface_prompt": final_prompt,
						"source_prompt": base_prompt,
						"control_metadata": control_metadata,
						"page_number": None,
						"remove_bg": remove_bg,
						"seed_bundle": {"story_seed": story_seed, "character_seed": task_seed},
						"output_files": [_relative_output_path(bundle_root, final_path)],
					}
					_add_task(
						task_type="character_pose_variant",
						task_id=f"character_pose::{character_id}::{pose_id}::{facing}",
						prompt=final_prompt,
						seed=task_seed,
						width=config.char_width,
						height=config.char_height,
						output_paths=[raw_path],
						manifest_path=manifest_dir / f"character_pose_{character_id}__{pose_id}__{facing}_render_manifest.json",
						manifest=manifest,
						metadata={
							"char": character_name,
							"char_id": character_id,
							"pose_id": pose_id,
							"facing": facing,
							"control_metadata": control_metadata,
							"seed_bundle": manifest["seed_bundle"],
						},
						remove_bg=remove_bg,
						nobg_path=final_path if remove_bg else None,
						bg_input_path=raw_path,
					)
					unity_character_index.setdefault(
						character_id,
						{"character_id": character_id, "label": character_name, "variants": []},
					)["variants"].append(
						{
							"pose_id": pose_id,
							"facing": facing,
							"path": _relative_output_path(bundle_root, final_path),
						}
					)

		prop_catalog: Dict[str, Dict[str, Any]] = {}
		for page_number in page_numbers:
			page_asset_plan = page_asset_plans.get(page_number) or {}
			for item in list(page_asset_plan.get("props") or []) + list(page_asset_plan.get("interactives") or []):
				canonical_id = _canonical_asset_id(str(item.get("canonical_id") or item.get("label") or ""), "prop")
				if canonical_id in prop_catalog:
					if item.get("interactive"):
						prop_catalog[canonical_id]["interactive"] = True
					continue
				prop_catalog[canonical_id] = {
					"canonical_id": canonical_id,
					"label": str(item.get("label") or canonical_id).strip(),
					"prompt": str(item.get("prompt") or f"{item.get('label')}, isolated storybook prop sprite").strip(),
					"interactive": bool(item.get("interactive")),
				}

		for canonical_id, item in prop_catalog.items():
			base_prompt = str(item.get("prompt") or "").strip()
			final_prompt, control_metadata = _build_unity_object_prompt(
				task_type="prop_sprite",
				base_prompt=base_prompt,
				character_name=str(item.get("label") or canonical_id),
				context=story_context,
				config=config,
			)
			final_path = unity_props_dir / f"{canonical_id}.png"
			remove_bg = _unity_remove_bg("prop_sprite", config)
			raw_path = _unity_raw_path(image_root, final_path) if remove_bg else final_path
			task_seed = _stable_task_seed(story_seed, f"prop:{canonical_id}")
			manifest = {
				"status": "planned",
				"task_id": f"prop::{canonical_id}",
				"task_type": "prop_sprite",
				"canonical_id": canonical_id,
				"surface_prompt": final_prompt,
				"source_prompt": base_prompt,
				"control_metadata": control_metadata,
				"page_number": None,
				"remove_bg": remove_bg,
				"seed_bundle": {"story_seed": story_seed, "prop_seed": task_seed},
				"output_files": [_relative_output_path(bundle_root, final_path)],
			}
			_add_task(
				task_type="prop_sprite",
				task_id=f"prop::{canonical_id}",
				prompt=final_prompt,
				seed=task_seed,
				width=config.char_width,
				height=config.char_height,
				output_paths=[raw_path],
				manifest_path=manifest_dir / f"prop_{canonical_id}_render_manifest.json",
				manifest=manifest,
				metadata={
					"canonical_id": canonical_id,
					"label": item.get("label"),
					"control_metadata": control_metadata,
					"seed_bundle": manifest["seed_bundle"],
				},
				remove_bg=remove_bg,
				nobg_path=final_path if remove_bg else None,
				bg_input_path=raw_path,
			)
			unity_prop_index[canonical_id] = {
				"canonical_id": canonical_id,
				"label": str(item.get("label") or canonical_id),
				"path": _relative_output_path(bundle_root, final_path),
				"interactive": bool(item.get("interactive")),
			}

		for page_number in page_numbers:
			page_plan = page_visual_plans.get(page_number) or {}
			page_asset_plan = page_asset_plans.get(page_number) or _fallback_asset_plan(page_number, page_plan)
			page_dir = unity_pages_dir / f"page_{page_number}"
			midground_dir = page_dir / "midground"
			ensure_dir(midground_dir)

			backdrop_prompt, backdrop_control = _build_unity_scene_layer_prompt(
				task_type="page_backdrop",
				base_prompt=str(page_asset_plan.get("backdrop_prompt") or "storybook backdrop").strip(),
				context=story_context,
				config=config,
				page_number=page_number,
				page_plan=page_plan or page_asset_plan,
				scene_layout=[str(page_asset_plan.get("world_anchor") or "setting anchor").strip(), "empty stage area for characters"],
				extra_negative=["no characters", "no hand-held props", "no isolated cutout object"],
			)
			backdrop_path = page_dir / "backdrop.png"
			backdrop_seed = _stable_task_seed(story_seed, f"page_backdrop:{page_number}")
			backdrop_manifest = {
				"status": "planned",
				"task_id": f"page_backdrop::{page_number}",
				"task_type": "page_backdrop",
				"canonical_id": f"page_{page_number}_backdrop",
				"page_number": page_number,
				"surface_prompt": backdrop_prompt,
				"source_prompt": str(page_asset_plan.get("backdrop_prompt") or "").strip(),
				"control_metadata": backdrop_control,
				"remove_bg": False,
				"seed_bundle": {"story_seed": story_seed, "page_seed": backdrop_seed},
				"output_files": [_relative_output_path(bundle_root, backdrop_path)],
			}
			_add_task(
				task_type="page_backdrop",
				task_id=f"page_backdrop::{page_number}",
				prompt=backdrop_prompt,
				seed=backdrop_seed,
				width=config.width,
				height=config.height,
				output_paths=[backdrop_path],
				manifest_path=manifest_dir / f"page_{page_number}_backdrop_render_manifest.json",
				manifest=backdrop_manifest,
				metadata={"page": page_number, "control_metadata": backdrop_control, "seed_bundle": backdrop_manifest["seed_bundle"]},
				remove_bg=False,
			)

			overlay_prompt, overlay_control = _build_unity_scene_layer_prompt(
				task_type="page_foreground_overlay",
				base_prompt=str(page_asset_plan.get("foreground_overlay_prompt") or "foreground storybook decor overlay").strip(),
				context=story_context,
				config=config,
				page_number=page_number,
				page_plan=page_plan or page_asset_plan,
				scene_layout=["foreground overlay only", "near-camera decor layer", "transparent-friendly separation"],
				extra_negative=["no characters", "no midground scene", "no background plate"],
			)
			overlay_path = page_dir / "foreground_overlay.png"
			overlay_remove_bg = _unity_remove_bg("page_foreground_overlay", config)
			overlay_raw_path = _unity_raw_path(image_root, overlay_path) if overlay_remove_bg else overlay_path
			overlay_seed = _stable_task_seed(story_seed, f"page_foreground_overlay:{page_number}")
			overlay_manifest = {
				"status": "planned",
				"task_id": f"page_foreground_overlay::{page_number}",
				"task_type": "page_foreground_overlay",
				"canonical_id": f"page_{page_number}_foreground_overlay",
				"page_number": page_number,
				"surface_prompt": overlay_prompt,
				"source_prompt": str(page_asset_plan.get("foreground_overlay_prompt") or "").strip(),
				"control_metadata": overlay_control,
				"remove_bg": overlay_remove_bg,
				"seed_bundle": {"story_seed": story_seed, "page_seed": overlay_seed},
				"output_files": [_relative_output_path(bundle_root, overlay_path)],
			}
			_add_task(
				task_type="page_foreground_overlay",
				task_id=f"page_foreground_overlay::{page_number}",
				prompt=overlay_prompt,
				seed=overlay_seed,
				width=config.width,
				height=config.height,
				output_paths=[overlay_raw_path],
				manifest_path=manifest_dir / f"page_{page_number}_foreground_overlay_render_manifest.json",
				manifest=overlay_manifest,
				metadata={"page": page_number, "control_metadata": overlay_control, "seed_bundle": overlay_manifest["seed_bundle"]},
				remove_bg=overlay_remove_bg,
				nobg_path=overlay_path if overlay_remove_bg else None,
				bg_input_path=overlay_raw_path,
			)

			midground_entries: List[Dict[str, Any]] = []
			for item in page_asset_plan.get("midground_objects") or []:
				canonical_id = _canonical_asset_id(str(item.get("canonical_id") or item.get("label") or ""), "midground_object")
				base_prompt = str(item.get("prompt") or item.get("label") or canonical_id).strip()
				midground_prompt, midground_control = _build_unity_object_prompt(
					task_type="page_midground_object",
					base_prompt=base_prompt,
					character_name=str(item.get("label") or canonical_id),
					context=story_context,
					config=config,
					page_number=page_number,
					page_plan=page_plan or page_asset_plan,
				)
				final_path = midground_dir / f"{canonical_id}.png"
				remove_bg = _unity_remove_bg("page_midground_object", config)
				raw_path = _unity_raw_path(image_root, final_path) if remove_bg else final_path
				task_seed = _stable_task_seed(story_seed, f"page_midground_object:{page_number}:{canonical_id}")
				midground_manifest = {
					"status": "planned",
					"task_id": f"page_midground_object::{page_number}::{canonical_id}",
					"task_type": "page_midground_object",
					"canonical_id": canonical_id,
					"page_number": page_number,
					"surface_prompt": midground_prompt,
					"source_prompt": base_prompt,
					"control_metadata": midground_control,
					"remove_bg": remove_bg,
					"seed_bundle": {"story_seed": story_seed, "page_seed": task_seed},
					"output_files": [_relative_output_path(bundle_root, final_path)],
				}
				_add_task(
					task_type="page_midground_object",
					task_id=f"page_midground_object::{page_number}::{canonical_id}",
					prompt=midground_prompt,
					seed=task_seed,
					width=config.char_width,
					height=config.char_height,
					output_paths=[raw_path],
					manifest_path=manifest_dir / f"page_{page_number}_midground_{canonical_id}_render_manifest.json",
					manifest=midground_manifest,
					metadata={
						"page": page_number,
						"canonical_id": canonical_id,
						"control_metadata": midground_control,
						"seed_bundle": midground_manifest["seed_bundle"],
					},
					remove_bg=remove_bg,
					nobg_path=final_path if remove_bg else None,
					bg_input_path=raw_path,
				)
				midground_entries.append(
					{
						"canonical_id": canonical_id,
						"label": str(item.get("label") or canonical_id),
						"layer": str(item.get("layer") or "midground_objects"),
						"slot": str(item.get("slot") or "center"),
						"remove_bg": bool(item.get("remove_bg", True)),
						"path": _relative_output_path(bundle_root, final_path),
					}
				)

			page_character_entries: List[Dict[str, Any]] = []
			for item in page_asset_plan.get("characters") or []:
				character_id = _canonical_asset_id(str(item.get("character_id") or item.get("label") or ""), "character")
				label = str(item.get("label") or item.get("character_name") or character_id).strip()
				pose_id = str(item.get("pose_id") or "neutral").strip()
				facing = str(item.get("facing") or "front").strip()
				page_character_entries.append(
					{
						"character_id": character_id,
						"label": label,
						"pose_id": pose_id,
						"facing": facing,
						"layer": str(item.get("layer") or "characters"),
						"slot": str(item.get("slot") or "center"),
						"scale_hint": str(item.get("scale_hint") or "medium"),
						"remove_bg": bool(item.get("remove_bg", True)),
						"path": _relative_output_path(bundle_root, unity_characters_dir / character_id / f"{pose_id}__{facing}.png"),
					}
				)

			page_prop_entries: List[Dict[str, Any]] = []
			for item in page_asset_plan.get("props") or []:
				canonical_id = _canonical_asset_id(str(item.get("canonical_id") or item.get("label") or ""), "prop")
				page_prop_entries.append(
					{
						"canonical_id": canonical_id,
						"label": str(item.get("label") or canonical_id).strip(),
						"interactive": False,
						"layer": str(item.get("layer") or "props"),
						"slot": str(item.get("slot") or "center"),
						"remove_bg": bool(item.get("remove_bg", True)),
						"path": _relative_output_path(bundle_root, unity_props_dir / f"{canonical_id}.png"),
					}
				)

			page_interactive_entries: List[Dict[str, Any]] = []
			for item in page_asset_plan.get("interactives") or []:
				canonical_id = _canonical_asset_id(str(item.get("canonical_id") or item.get("label") or ""), "interactive")
				page_interactive_entries.append(
					{
						"canonical_id": canonical_id,
						"label": str(item.get("label") or canonical_id).strip(),
						"interactive": True,
						"layer": str(item.get("layer") or "props"),
						"slot": str(item.get("slot") or "center"),
						"remove_bg": bool(item.get("remove_bg", True)),
						"path": _relative_output_path(bundle_root, unity_props_dir / f"{canonical_id}.png"),
					}
				)

			page_manifest = {
				"page_number": page_number,
				"backdrop": {
					"path": _relative_output_path(bundle_root, backdrop_path),
					"shot": str(page_asset_plan.get("shot") or page_plan.get("shot") or "mid"),
					"lighting": str(page_asset_plan.get("lighting") or page_plan.get("lighting") or "bright"),
					"stage": str(page_asset_plan.get("stage") or page_plan.get("stage") or "action"),
				},
				"foreground_overlay": {
					"path": _relative_output_path(bundle_root, overlay_path),
				},
				"midground_objects": midground_entries,
				"characters": page_character_entries,
				"props": page_prop_entries,
				"interactives": page_interactive_entries,
				"assembly_order": list(page_asset_plan.get("assembly_order") or UNITY_ASSEMBLY_ORDER),
				"story_readability_goal": str(page_asset_plan.get("story_readability_goal") or "").strip(),
				"world_anchor": str(page_asset_plan.get("world_anchor") or "").strip(),
			}
			write_json_or_raise(page_dir / "page_assets.json", page_manifest)
			unity_story_manifest["pages"].append(page_manifest)

		unity_story_manifest["characters"] = list(unity_character_index.values())
		unity_story_manifest["props"] = list(unity_prop_index.values())
		write_json_or_raise(resources_dir / "unity_story_asset_manifest.json", unity_story_manifest)

	return tasks


def generate_photos_for_story(
	story_root: Path,
	config: Config,
	progress_label: str = "Generating photos",
	console: bool = True,
	kernel_recorder: Any = None,
	progress_callback: ProgressCallback = None,
) -> bool:
	"""Generate cover, character, and scene images for one story root."""
	log_path = story_root / "logs" / "photo.log"
	ensure_dir(log_path.parent)
	logger = setup_logging(f"photo_pipeline_{story_root.name}", log_path, console=console)
	
	# Discovery strategy: Support both linear (root/resource) and branched (nested/resource) structures
	resource_candidates = []
	
	# 1. Check root resource
	root_res = story_root / "resource"
	if root_res.exists():
		resource_candidates.append(root_res)
	else:
		root_res_alt = story_root / "resources"
		if root_res_alt.exists():
			resource_candidates.append(root_res_alt)
			
	# 2. Check recursive resources (e.g. inside branches)
	# Use set to avoid duplicates if root is handled by rglob (though rglob usually skips root depending on pattern)
	# rglob("resource") matches any file/folder named "resource"
	for p in story_root.rglob("resource"):
		if p.is_dir():
			resource_candidates.append(p)
			
	# Deduplicate based on absolute path
	unique_paths = {}
	for p in resource_candidates:
		unique_paths[p.resolve()] = p
	sorted_candidates = sorted(list(unique_paths.values()), key=lambda p: str(p))
	
	if not sorted_candidates:
		logger.error("Resources directory not found (searched recursively in %s)", story_root)
		return False
	
	# Collect tasks from ALL found resource directories
	tasks = []
	for res_dir in sorted_candidates:
		if res_dir.parent.resolve() == story_root.resolve():
			target_image_root = story_root / "image"
		elif res_dir.name in ("resource", "resources"):
			target_image_root = res_dir.parent / "image"
		else:
			target_image_root = story_root / "image"
			
		try:
			res_rel = res_dir.relative_to(story_root)
			img_rel = target_image_root.relative_to(story_root) if target_image_root.is_relative_to(story_root) else target_image_root
			logger.info("Scanning resources: %s -> Output: %s", res_rel, img_rel)
		except ValueError:
			logger.info("Scanning resources: %s -> Output: %s", res_dir, target_image_root)
		
		batch_tasks = _collect_generation_tasks(story_root, res_dir, config, logger, output_root_override=target_image_root)
		tasks.extend(batch_tasks)

	if not tasks:
		logger.error("No prompts found in any resource directories under %s", story_root)
		return False

	logger.info("Found %d tasks total across %d resource groups. Starting Generation...", len(tasks), len(sorted_candidates))
	for task in tasks:
		task["render"] = _resolve_task_render_settings(task, config)
		manifest = task.get("manifest")
		if isinstance(manifest, dict):
			render_cfg = task["render"]
			manifest["render"] = {
				"steps": int(render_cfg.steps),
				"guidance": float(render_cfg.guidance),
				"skip_refiner": bool(render_cfg.skip_refiner),
				"refiner_steps": int(render_cfg.refiner_steps) if render_cfg.refiner_steps is not None else None,
				"width": int(task["width"]),
				"height": int(task["height"]),
				"model_family": _classify_image_model(config),
				"base_model_dir": str(config.base_model_dir),
				"quantization_mode": str(getattr(config, "quantization_mode", "none") or "none"),
				"output_mode": str(getattr(config, "output_mode", "dual") or "dual"),
				"asset_granularity": str(getattr(config, "asset_granularity", "page_bundle") or "page_bundle"),
				"bg_removal_policy": str(getattr(config, "bg_removal_policy", "characters_props") or "characters_props"),
				"reuse_strategy": str(getattr(config, "reuse_strategy", "page_bundle_first") or "page_bundle_first"),
			}
			write_json_or_raise(task["manifest_path"], manifest)

	def _task_render(task: Dict[str, Any]) -> TaskRenderSettings:
		render = task.get("render")
		if isinstance(render, TaskRenderSettings):
			return render
		return _resolve_task_render_settings(task, config)

	model_family = _classify_image_model(config)
	refiner_path = getattr(config, "refiner_model_dir", None)
	logger.info(
		"Image config | model=%s | family=%s | quantization=%s | output_mode=%s | base_steps=%d | base_guidance=%.2f | default_refiner=%s | canvas=%dx%d",
		config.base_model_dir,
		model_family,
		str(getattr(config, "quantization_mode", "none") or "none"),
		str(getattr(config, "output_mode", "dual") or "dual"),
		int(config.steps),
		float(config.guidance),
		"on" if (refiner_path and Path(refiner_path).exists() and not config.skip_refiner) else "off",
		int(config.width),
		int(config.height),
	)

	from backends.image import build_image_backend

	generator = build_image_backend(config)
	
	try:
		# Base generation pass: latent generation plus optional save/post-processing.
		# Progress counts both base and refiner phases when refiner is enabled.
		refiner_task_count = sum(1 for task in tasks if not _task_render(task).skip_refiner)
		total_steps = len(tasks) + refiner_task_count + len(tasks)
		completed_units = 0
		_safe_emit_progress(
			progress_callback,
			**_task_progress_payload(
				task=None,
				phase="queue",
				event="planned",
				completed_units=completed_units,
				total_units=total_steps,
				task_index=0,
				task_total=len(tasks),
			),
		)
		progress = tqdm(total=total_steps, desc=progress_label, disable=not console, unit="step")
		base_started_at = time.perf_counter()
		progress_stride = max(1, len(tasks) // 10)

		logger.info("Phase 1: Generating Base Latents...")
		_safe_emit_progress(
			progress_callback,
			**_task_progress_payload(
				task=None,
				phase="base",
				event="phase_start",
				completed_units=completed_units,
				total_units=total_steps,
				task_index=0,
				task_total=len(tasks),
			),
		)
		generator.load_base()
		applied_quant_mode = str(getattr(generator, "applied_quantization_mode", getattr(config, "quantization_mode", "none")) or "none")
		logger.info("Image backend loaded with quantization=%s", applied_quant_mode)
		for task in tasks:
			manifest = task.get("manifest")
			if isinstance(manifest, dict) and isinstance(manifest.get("render"), dict):
				manifest["render"]["applied_quantization_mode"] = applied_quant_mode
				write_json_or_raise(task["manifest_path"], manifest)
		
		for idx, task in enumerate(tasks, start=1):
			render = _task_render(task)
			negative_prompt = _resolve_negative_prompt(config, str(task.get("type") or "page"))
			task_started_at = time.perf_counter()
			_safe_emit_progress(
				progress_callback,
				**_task_progress_payload(
					task=task,
					phase="base",
					event="task_start",
					completed_units=completed_units,
					total_units=total_steps,
					task_index=idx,
					task_total=len(tasks),
				),
			)
			if not console:
				logger.info(
					"Phase 1 task %d/%d | id=%s | type=%s | steps=%d | guidance=%.2f | size=%dx%d",
					idx,
					len(tasks),
					task.get("id"),
					task.get("type"),
					int(render.steps),
					float(render.guidance),
					int(task["width"]),
					int(task["height"]),
				)
			# Profiling wrapper
			def _run_base():
				return generator.run_base_step(
					prompt=task["prompt"],
					seed=task["seed"],
					width=task["width"],
					height=task["height"],
					steps=render.steps,
					guidance=render.guidance,
					negative_prompt=negative_prompt,
					output_latents=not render.skip_refiner
				)

			if kernel_recorder:
				with kernel_recorder.profile(story_root.name, f"image_base_{task['id']}", metadata=task["metadata"]):
					result = _run_base()
			else:
				result = _run_base()
			
			if render.skip_refiner:
				task["final_image"] = result
			else:
				task["latents"] = result

			if not console:
				logger.info(
					"Phase 1 task %d/%d complete | id=%s | elapsed %.1fs",
					idx,
					len(tasks),
					task.get("id"),
					time.perf_counter() - task_started_at,
				)
			completed_units += 1
			progress.update(1)
			_safe_emit_progress(
				progress_callback,
				**_task_progress_payload(
					task=task,
					phase="base",
					event="task_complete",
					completed_units=completed_units,
					total_units=total_steps,
					task_index=idx,
					task_total=len(tasks),
				),
			)
			if (not console) and (idx % progress_stride == 0 or idx == len(tasks)):
				elapsed = time.perf_counter() - base_started_at
				avg = elapsed / max(1, idx)
				eta = max(0.0, avg * (len(tasks) - idx))
				logger.info(
					"Phase 1 progress: %d/%d tasks | elapsed %.1fs | eta %.1fs",
					idx,
					len(tasks),
					elapsed,
					eta,
				)
		
		# Unload Base
		# Phase 2: optional refiner pass.
		# Base/refiner loading is delegated to the backend implementation.
		if any(not _task_render(task).skip_refiner for task in tasks):
			logger.info("Phase 2: Refining Images...")
			_safe_emit_progress(
				progress_callback,
				**_task_progress_payload(
					task=None,
					phase="refiner",
					event="phase_start",
					completed_units=completed_units,
					total_units=total_steps,
					task_index=0,
					task_total=refiner_task_count,
				),
			)
			generator.load_refiner()
			refiner_started_at = time.perf_counter()
			refiner_index = 0
			for idx, task in enumerate(tasks, start=1):
				render = _task_render(task)
				if task.get("latents") is None:
					continue
				refiner_index += 1
				negative_prompt = _resolve_negative_prompt(config, str(task.get("type") or "page"))
				task_started_at = time.perf_counter()
				_safe_emit_progress(
					progress_callback,
					**_task_progress_payload(
						task=task,
						phase="refiner",
						event="task_start",
						completed_units=completed_units,
						total_units=total_steps,
						task_index=refiner_index,
						task_total=refiner_task_count,
					),
				)
				if not console:
					logger.info(
						"Phase 2 task %d/%d | id=%s | refiner_steps=%d | guidance=%.2f",
						refiner_index,
						refiner_task_count,
						task.get("id"),
						int(render.refiner_steps or max(1, render.steps // 4)),
						float(render.guidance),
					)

				def _run_refiner():
					return generator.run_refiner_step(
						latents=task["latents"],
						prompt=task["prompt"],
						seed=task["seed"],
						steps=render.refiner_steps or max(1, render.steps // 4),
						guidance=render.guidance,
						negative_prompt=negative_prompt
					)

				if kernel_recorder:
					with kernel_recorder.profile(story_root.name, f"image_refine_{task['id']}", metadata=task["metadata"]):
						image = _run_refiner()
				else:
					image = _run_refiner()
				
				task["final_image"] = image
				# Release intermediate latents once the final image exists.
				task["latents"] = None
				if not console:
					logger.info(
						"Phase 2 task %d/%d complete | id=%s | elapsed %.1fs",
						refiner_index,
						refiner_task_count,
						task.get("id"),
						time.perf_counter() - task_started_at,
					)
				completed_units += 1
				progress.update(1)
				_safe_emit_progress(
					progress_callback,
					**_task_progress_payload(
						task=task,
						phase="refiner",
						event="task_complete",
						completed_units=completed_units,
						total_units=total_steps,
						task_index=refiner_index,
						task_total=refiner_task_count,
					),
				)
				if (not console) and (refiner_index % progress_stride == 0 or refiner_index == refiner_task_count):
					elapsed = time.perf_counter() - refiner_started_at
					avg = elapsed / max(1, refiner_index)
					eta = max(0.0, avg * (refiner_task_count - refiner_index))
					logger.info(
						"Phase 2 progress: %d/%d tasks | elapsed %.1fs | eta %.1fs",
						refiner_index,
						refiner_task_count,
						elapsed,
						eta,
					)

		# --- Phase 3: Saving & Post-processing ---
		logger.info("Phase 3: Saving Images...")
		_safe_emit_progress(
			progress_callback,
			**_task_progress_payload(
				task=None,
				phase="save",
				event="phase_start",
				completed_units=completed_units,
				total_units=total_steps,
				task_index=0,
				task_total=len(tasks),
			),
		)
		saved_count = 0
		for idx, task in enumerate(tasks, start=1):
			_safe_emit_progress(
				progress_callback,
				**_task_progress_payload(
					task=task,
					phase="save",
					event="task_start",
					completed_units=completed_units,
					total_units=total_steps,
					task_index=idx,
					task_total=len(tasks),
				),
			)
			image = task.get("final_image")
			if image:
				_save_image(image, *task["output_paths"])
				saved_count += 1

				if task["remove_bg"] and "nobg_path" in task:
					# Background removal is best-effort and should not fail the run.
					bg_input_path = Path(task.get("bg_input_path") or task["output_paths"][-1])
					final_alpha_path = Path(task["nobg_path"])
					removed = remove_background(bg_input_path, final_alpha_path)
					if not removed and bg_input_path != final_alpha_path:
						_save_image(image, final_alpha_path)
				manifest = task.get("manifest")
				if isinstance(manifest, dict):
					manifest["status"] = "rendered"
					manifest["output_files"] = [str(path) for path in task["output_paths"]]
					if task.get("nobg_path"):
						manifest["output_files"].append(str(task["nobg_path"]))
					write_json_or_raise(task["manifest_path"], manifest)
			else:
				logger.error("Task %s failed to produce image", task["id"])
			completed_units += 1
			progress.update(1)
			_safe_emit_progress(
				progress_callback,
				**_task_progress_payload(
					task=task,
					phase="save",
					event="task_complete",
					completed_units=completed_units,
					total_units=total_steps,
					task_index=idx,
					task_total=len(tasks),
				),
			)

		progress.close()

		if saved_count == 0:
			logger.error("No images were successfully generated")
			return False

		logger.info("Successfully generated %d images", saved_count)
		_safe_emit_progress(
			progress_callback,
			**_task_progress_payload(
				task=None,
				phase="done",
				event="complete",
				completed_units=completed_units,
				total_units=total_steps,
				task_index=len(tasks),
				task_total=len(tasks),
			),
		)
		return True
	finally:
		generator.cleanup()


DEFAULT_IMAGE_RUN = RunConfig()


def main(config: RunConfig = DEFAULT_IMAGE_RUN) -> None:
	"""CLI entry point for standalone image generation."""
	logging.basicConfig(level=config.log_level, format=config.log_format)
	story_root = resolve_story_root(config.story_root, config.output_root)
	logging.info("Generating images for %s", story_root.name)
	success = generate_photos_for_story(
		story_root,
		config.sdxl,
		progress_label=config.progress_label,
		console=True,
	)
	if not success:
		logging.error("Image generation failed for %s", story_root)
		raise SystemExit(1)
	logging.info("Image generation completed for %s", story_root)


if __name__ == "__main__":
	main()

