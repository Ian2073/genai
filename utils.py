"""全域工具：集中管理故事/影像/語音模組會共用的輔助函式。"""

from __future__ import annotations

import argparse
import json
import logging
import random
import re
import shutil
from typing import Any, Dict, Iterable, List, Optional, Sequence, Literal
from dataclasses import dataclass, field
from pathlib import Path

from kg import StoryGenerationKG


# ---------------------------------------------------------------------------
# 路徑相關：統一抓取專案的根目錄與主要資料夾


@dataclass(frozen=True)
class ProjectPaths:
	"""專案主要目錄路徑。"""

	root_dir: Path
	models_dir: Path
	output_dir: Path
	logs_dir: Path
	reports_dir: Path
	runs_dir: Path

	@classmethod
	def discover(cls, start: Optional[Path] = None) -> "ProjectPaths":
		"""根據工作目錄推算專案主要資料夾。"""

		base = start or Path.cwd()
		root = base
		return cls(
			root_dir=root,
			models_dir=root / "models",
			output_dir=root / "output",
			logs_dir=root / "logs",
			reports_dir=root / "reports",
			runs_dir=root / "runs",
		)


_KG_INSTANCE: Optional[StoryGenerationKG] = None


@dataclass
class StoryProfile:
	language: str
	age_value: int
	age_range: str
	age_group_id: str
	age_label: str
	category_id: str
	category_label: str
	subcategory_id: Optional[str]
	subcategory_label: str
	theme_id: str
	theme_label: str
	kg_version: str
	kg_payload: Dict[str, Any]
	prompt_guidelines: str
	raw_config: Dict[str, Any]
	pages_expected: int
	branch_config: Dict[str, Any]
	layout: Optional['BranchLayout'] = None
	interaction_plan: List['InteractionSlot'] = field(default_factory=list)
	visual_style: str = ""

	def to_dict(self) -> Dict[str, Any]:
		"""轉換為字典格式。"""
		return {
			"language": self.language,
			"age": {
				"value": self.age_value,
				"range": self.age_range,
				"label": self.age_label,
				"id": self.age_group_id,
			},
			"category": {
				"id": self.category_id,
				"label": self.category_label,
			},
			"subcategory": {
				"id": self.subcategory_id,
				"label": self.subcategory_label,
			},
			"theme": {
				"id": self.theme_id,
				"label": self.theme_label,
			},
			"kg_version": self.kg_version,
			"kg_payload": self.kg_payload,
			"prompt_guidelines": self.prompt_guidelines,
			"pages_expected": self.pages_expected,
			"branch_config": self.branch_config,
			"layout": self.layout.to_dict() if self.layout else None,
			"interaction_plan": [slot.to_dict() for slot in self.interaction_plan],
			"visual_style": self.visual_style,
		}

@dataclass
class InteractionSlot:
	kind: Literal["narrative", "decision", "action", "reflection"]
	interaction_type: Optional[Literal["gesture", "object", "voice", "touch"]] = None
	directive: str = ""
	metadata: Dict[str, Any] = field(default_factory=dict)

	def to_dict(self) -> Dict[str, Any]:
		return {
			"kind": self.kind,
			"interaction_type": self.interaction_type,
			"directive": self.directive,
			"metadata": self.metadata,
		}

@dataclass
class BranchLayout:
	trunk_pages: range
	decision_page: int
	branch_pages: range
	ending_pages: range
	total_pages: int
	branch_count: int
	layout_id: str
	description: str
	pacing: str
	pace_quota: Optional[PaceQuota] = None
	branch_slots: List[Dict[str, str]] = field(default_factory=list)
	visual_frame: Optional[VisualReferenceFrame] = None

	def to_dict(self) -> Dict[str, Any]:
		return {
			"trunk_pages": [str(self.trunk_pages.start), str(self.trunk_pages.stop)],
			"decision_page": self.decision_page,
			"branch_pages": [str(self.branch_pages.start), str(self.branch_pages.stop)],
			"ending_pages": [str(self.ending_pages.start), str(self.ending_pages.stop)],
			"total_pages": self.total_pages,
			"branch_count": self.branch_count,
			"pace_quota": self.pace_quota.to_dict() if self.pace_quota else None,
			"branch_slots": self.branch_slots,
			"visual_frame": self.visual_frame.to_dict() if self.visual_frame else None,
			"layout_id": self.layout_id,
			"description": self.description,
			"pacing": self.pacing,
		}

@dataclass
class StoryState:
	"""表示故事中特定時間點的敘事狀態 (Narrative State)。"""
	characters: List[str]
	current_event: str
	inventory: List[str] = field(default_factory=list)
	plot_points: List[str] = field(default_factory=list)
	mood: str = "neutral"
	
	def to_dict(self) -> Dict[str, Any]:
		return {
			"characters": self.characters,
			"current_event": self.current_event,
			"inventory": self.inventory,
			"plot_points": self.plot_points,
			"mood": self.mood
		}
	
	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "StoryState":
		return cls(
			characters=data.get("characters", []),
			current_event=data.get("current_event", ""),
			inventory=data.get("inventory", []),
			plot_points=data.get("plot_points", []),
			mood=data.get("mood", "neutral")
		)

@dataclass
class StoryNode:
	"""表示故事圖譜中的單一步驟 (頁面)。"""
	page_num: int
	content: str
	state: StoryState
	branch_id: str = "option_1"
	
	def to_dict(self) -> Dict[str, Any]:
		return {
			"page_num": self.page_num,
			"content": self.content,
			"state": self.state.to_dict(),
			"branch_id": self.branch_id
		}


@dataclass(frozen=True)
class SceneState:
	shot: Literal["far", "mid", "close"]
	lighting: Literal["bright", "dim"]
	stage: Literal["setup", "action", "result"]

	def to_dict(self) -> Dict[str, Any]:
		return {
			"shot": self.shot,
			"lighting": self.lighting,
			"stage": self.stage,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "SceneState":
		return cls(
			shot=data.get("shot", "mid"),
			lighting=data.get("lighting", "bright"),
			stage=data.get("stage", "action"),
		)


@dataclass
class PaceQuota:
	setup_min: int
	diverge_min: int
	closing_min: int
	total_target: int

	def validate(self) -> bool:
		return (self.setup_min + self.diverge_min + self.closing_min) <= self.total_target

	def to_dict(self) -> Dict[str, Any]:
		return {
			"setup_min": self.setup_min,
			"diverge_min": self.diverge_min,
			"closing_min": self.closing_min,
			"total_target": self.total_target,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "PaceQuota":
		return cls(
			setup_min=data.get("setup_min", 2),
			diverge_min=data.get("diverge_min", 3),
			closing_min=data.get("closing_min", 2),
			total_target=data.get("total_target", 8),
		)


@dataclass
class ValueLens:
	focus: str
	decision_basis: str
	emotion_approach: str
	action_pace: str

	def to_dict(self) -> Dict[str, Any]:
		return {
			"focus": self.focus,
			"decision_basis": self.decision_basis,
			"emotion_approach": self.emotion_approach,
			"action_pace": self.action_pace,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "ValueLens":
		return cls(
			focus=data.get("focus", "curiosity"),
			decision_basis=data.get("decision_basis", "logic"),
			emotion_approach=data.get("emotion_approach", "calm"),
			action_pace=data.get("action_pace", "measured"),
		)


@dataclass
class VisualReferenceFrame:
	viewpoint: Literal["tabletop", "diorama", "miniature"]
	stage_boundary: str
	depth_layers: Dict[str, str]

	def to_dict(self) -> Dict[str, Any]:
		return {
			"viewpoint": self.viewpoint,
			"stage_boundary": self.stage_boundary,
			"depth_layers": self.depth_layers,
		}

	@classmethod
	def from_dict(cls, data: Dict[str, Any]) -> "VisualReferenceFrame":
		return cls(
			viewpoint=data.get("viewpoint", "tabletop"),
			stage_boundary=data.get("stage_boundary", "contained scene box"),
			depth_layers=data.get("depth_layers", {
				"foreground": "interactive elements",
				"midground": "main action",
				"background": "environmental context",
			}),
		)


def assign_value_lenses(branch_count: int, theme: Optional[str] = None) -> List[ValueLens]:
	_ = theme
	lens_templates = [
		ValueLens(
			focus="safety",
			decision_basis="logic",
			emotion_approach="cautious",
			action_pace="deliberate",
		),
		ValueLens(
			focus="curiosity",
			decision_basis="intuition",
			emotion_approach="excited",
			action_pace="spontaneous",
		),
		ValueLens(
			focus="empathy",
			decision_basis="emotion",
			emotion_approach="calm",
			action_pace="measured",
		),
		ValueLens(
			focus="exploration",
			decision_basis="experience",
			emotion_approach="confident",
			action_pace="steady",
		),
	]
	if branch_count <= len(lens_templates):
		return lens_templates[:branch_count]
	lenses = lens_templates.copy()
	while len(lenses) < branch_count:
		lenses.append(lens_templates[len(lenses) % len(lens_templates)])
	return lenses[:branch_count]


class SceneStateManager:
	def __init__(self, seed: Optional[int] = None):
		self.rng = random.Random(seed)
		self.state_history: List[SceneState] = []

	def select_initial_state(self) -> SceneState:
		state = SceneState(shot="mid", lighting="bright", stage="setup")
		self.state_history.append(state)
		return state

	def select_next_state(
		self,
		current_state: SceneState,
		page_num: int,
		total_pages: int,
		pace_quota: PaceQuota,
		event_type: str = "narrative",
	) -> SceneState:
		_ = current_state
		if page_num <= pace_quota.setup_min:
			phase = "setup"
		elif page_num >= (total_pages - pace_quota.closing_min + 1):
			phase = "closing"
		else:
			phase = "divergence"

		if phase == "setup":
			shot = self.rng.choice(["mid", "far"])
			lighting = "bright"
			stage = self.rng.choice(["setup", "action"])
		elif phase == "closing":
			shot = self.rng.choice(["close", "mid"])
			lighting = self.rng.choice(["bright", "dim"])
			stage = "result"
		else:
			if event_type == "decision":
				shot = "close"
				lighting = self.rng.choice(["bright", "dim"])
				stage = "action"
			elif event_type == "action":
				shot = self.rng.choice(["mid", "close"])
				lighting = self.rng.choice(["bright", "dim"])
				stage = "action"
			else:
				shot = self.rng.choice(["far", "mid", "close"])
				lighting = self.rng.choice(["bright", "dim"])
				stage = self.rng.choice(["setup", "action", "result"])

		new_state = SceneState(shot=shot, lighting=lighting, stage=stage)
		if self.state_history and new_state == self.state_history[-1]:
			shots = ["far", "mid", "close"]
			if shot in shots:
				shots.remove(shot)
			new_state = SceneState(
				shot=self.rng.choice(shots),
				lighting=lighting,
				stage=stage,
			)
		self.state_history.append(new_state)
		return new_state

	def get_state_description(self, state: SceneState) -> Dict[str, str]:
		shot_desc = {
			"far": "full scene view (establish environment)",
			"mid": "group focus (character interactions)",
			"close": "character detail (emotions and reactions)",
		}
		lighting_desc = {
			"bright": "clear and welcoming atmosphere",
			"dim": "atmospheric and moody setting",
		}
		stage_desc = {
			"setup": "introduction (establishing the moment)",
			"action": "peak moment (main action occurring)",
			"result": "aftermath (consequences showing)",
		}
		return {
			"shot": shot_desc.get(state.shot, state.shot),
			"lighting": lighting_desc.get(state.lighting, state.lighting),
			"stage": stage_desc.get(state.stage, state.stage),
		}


class ValueLensManager:
	def get_lens_description(self, lens: ValueLens) -> str:
		focus_guidance = {
			"safety": "Emphasize caution, risk assessment, and protective instincts",
			"curiosity": "Emphasize wonder, questions, and exploratory impulse",
			"empathy": "Emphasize emotional connection, understanding others' feelings",
			"exploration": "Emphasize discovery, adventure, and new experiences",
		}
		decision_guidance = {
			"logic": "Base decisions on reasoning and practical outcomes",
			"emotion": "Base decisions on feelings and emotional responses",
			"intuition": "Base decisions on gut feelings and hunches",
			"experience": "Base decisions on past knowledge and learned patterns",
		}
		emotion_guidance = {
			"calm": "Process emotions with composure and steadiness",
			"excited": "Express emotions with enthusiasm and energy",
			"cautious": "Approach emotions with careful consideration",
			"confident": "Show emotions with self-assurance",
		}
		pace_guidance = {
			"deliberate": "Act with careful thought and planning",
			"spontaneous": "Act quickly with immediate response",
			"measured": "Act with balanced consideration",
			"steady": "Act with consistent, unhurried progression",
		}
		focus_text = focus_guidance.get(lens.focus, lens.focus)
		decision_text = decision_guidance.get(lens.decision_basis, lens.decision_basis)
		emotion_text = emotion_guidance.get(lens.emotion_approach, lens.emotion_approach)
		pace_text = pace_guidance.get(lens.action_pace, lens.action_pace)
		return (
			"\nVALUE LENS APPLICATION:\n"
			f"- Focus: {focus_text}\n"
			f"- Decision Style: {decision_text}\n"
			f"- Emotional Style: {emotion_text}\n"
			f"- Action Style: {pace_text}\n\n"
			"Apply this lens to HOW the character observes and responds to events, \n"
			"NOT to create different events.\n"
		)

	def get_lens_for_branch(self, branch_id: str, branch_count: int) -> ValueLens:
		try:
			branch_idx = int(branch_id.split("_")[-1]) - 1
		except Exception:
			branch_idx = 0
		lenses = assign_value_lenses(branch_count)
		if 0 <= branch_idx < len(lenses):
			return lenses[branch_idx]
		return lenses[0]


def get_story_kg() -> StoryGenerationKG:
	"""延遲初始化並共用同一個 StoryGenerationKG 實例。
	
	使用單例模式確保整個系統共用同一個 KG 實例，
	避免重複載入大量配置資料。
	
	Returns:
		StoryGenerationKG 實例。
	"""
	global _KG_INSTANCE
	if _KG_INSTANCE is None:
		_KG_INSTANCE = StoryGenerationKG()
	return _KG_INSTANCE


def _choose(seq: Iterable[Any], rng: Optional[random.Random]) -> Any:
	items = list(seq)
	if not items:
		raise ValueError("Sequence is empty; cannot choose value")
	roller = rng if isinstance(rng, random.Random) else random.Random()
	return roller.choice(items)


def _normalize_age_value(age: Optional[str | int], rng: Optional[random.Random]) -> int:
	if isinstance(age, int):
		return age
	if isinstance(age, str):
		match = re.search(r"(\d{1,2})(?:\D+(\d{1,2}))?", age)
		if match:
			start = int(match.group(1))
			end = int(match.group(2) or start)
			return max(2, min(8, (start + end) // 2))  # Clamp to max 8 since 9-10 is disabled
	return _choose([3, 4, 5, 6, 7, 8], rng)  # Removed 9 from random choices (9-10 disabled)


def _resolve_category_id(value: Optional[str]) -> Optional[str]:
	if not value:
		return None
	kg = get_story_kg()
	slug = value.strip().lower().replace(" ", "_")
	if slug in kg.nodes:
		return slug
	for node_id, node in kg.nodes.items():
		if node.type.name == "CATEGORY" and node.label.lower() == value.strip().lower():
			return node_id
	return None


def _resolve_theme_id(theme: Optional[str], themes: Dict[str, Dict[str, Any]], rng: Optional[random.Random]) -> str:
	if theme:
		candidate = theme.strip().lower().replace(" ", "_")
		if candidate in themes:
			return candidate
		for theme_id, info in themes.items():
			if info.get("label", "").strip().lower() == theme.strip().lower():
				return theme_id
	return _choose(themes.keys(), rng)


def _resolve_subcategory_id(
	subcategory: Optional[str],
	category_config: Dict[str, Any],
	rng: Optional[random.Random],
) -> Optional[str]:
	subcategories = category_config.get("subcategories", {})
	if not subcategories:
		return None
	if subcategory:
		slug = subcategory.strip().lower().replace(" ", "_")
		if slug in subcategories:
			return slug
	return _choose(subcategories.keys(), rng)


def _format_label(identifier: Optional[str]) -> str:
	if not identifier:
		return "General"
	return identifier.replace("_", " ").title()


def _collect_theme_scenes(theme_props: Dict[str, Any]) -> List[str]:
	scenes: List[str] = []
	for value in theme_props.values():
		if isinstance(value, list):
			scenes.extend(str(item) for item in value)
	return scenes


def slugify_name(text: str, fallback: str = "story", max_length: int = 80) -> str:
	"""將文本轉換為適合檔案系統的名稱，限制最大長度以避免路徑過長問題。
	
	Args:
		text: 待轉換的文本。
		fallback: 當文本無效時的預設值。
		max_length: 最大長度限制。
		
	Returns:
		處理後的檔案名稱。
	"""
	clean = re.sub(r"[^A-Za-z0-9]+", "_", text.strip())
	clean = re.sub(r"_+", "_", clean).strip("_")
	if not clean:
		return fallback
	# 限制長度以避免 Windows 路徑限制問題
	if len(clean) > max_length:
		clean = clean[:max_length].rstrip("_")
	return clean


def build_story_relative_path(profile: StoryProfile, title: str) -> str:
	"""依據主分類/年齡/標題建立新式階層式目錄（無 story/ 前綴）。
	
	Args:
		profile: 故事配置檔案。
		title: 故事標題。
		
	Returns:
		相對路徑字串，格式為 category/age/title。
	"""
	category_source = profile.category_label or profile.category_id or "category"
	category_part = slugify_name(category_source, "category")
	age_part = profile.age_range.replace(" ", "")
	title_part = slugify_name(title, "story")
	return str(Path(category_part) / age_part / title_part)


# --- Layout Generation (KG Driven, Strict) ---

def _generate_layout(age_value: int, seed: Optional[int] = None, layout_id: Optional[str] = None) -> BranchLayout:
	"""
	根據 KG 設定生成固定的頁面佈局 (Layout)。
	
	從知識圖譜中選擇適合的分支結構，決定各階段的頁數分配。
	使用新的 age_groups 中的 layout_config 結構。
	
	Args:
		age_value: 目標年齡值，用於選擇佈局。
		seed: 隨機種子（保留供未來 RNG 佈局變體使用）。
		layout_id: 指定的佈局 ID（保留供未來多範本支援使用）。
		
	Returns:
		BranchLayout 實例，包含完整的頁面佈局資訊。
	"""
	kg = get_story_kg()
	
	# Get layout configuration directly from KG age_group properties
	layout_config = kg.get_layout_config(age_value)
	
	if not layout_config:
		raise ValueError(f"CRITICAL: No layout configuration found for Age {age_value} in KG.")
	
	# Extract configuration
	total = layout_config.get("total_pages", 8)
	turning_point = layout_config.get("turning_point_page", 0)
	b_count = layout_config.get("branch_count", 0)
	desc = layout_config.get("description", "")
	structure = layout_config.get("structure", "linear")
	layout_template_id = f"{structure}_{total}"
	
	# 注意：實際的轉折點稍後將從大綱中檢測到
	# 這只是預設值/後備值
	
	if b_count == 0:
		# Linear structure (Age 2-3)
		trunk_pages = range(1, total + 1)
		branch_pages = range(0, 0)
		ending_pages = range(total, total + 1)  # Last page is ending
		if total > 1:
			trunk_pages = range(1, total)
	else:
		# Single turning point structure (Age 4-5, 6-7)
		# P1 到 turning_point: 主幹 (引導至選擇的共用敘事)
		# turning_point + 1 到 total: 分支特定內容
		# 最後一頁: 結局
		trunk_pages = range(1, turning_point + 1)
		branch_pages = range(turning_point + 1, total + 1)
		ending_pages = range(total, total + 1)
		
	return BranchLayout(
		trunk_pages=trunk_pages,
		decision_page=turning_point,  # Will be used as default if not detected from outline
		branch_pages=branch_pages,
		ending_pages=ending_pages,
		total_pages=total,
		branch_count=b_count,
		layout_id=layout_template_id,
		description=desc,
		pacing="balanced"
	)

def _generate_interaction_plan(layout: BranchLayout, age_value: int) -> List[InteractionSlot]:
	"""單一轉折點設計：僅在決策頁面 (Decision Page) 包含互動。"""
	plan = []
	
	for p in range(1, layout.total_pages + 1):
		if p == layout.decision_page and layout.branch_count > 0:
			# Turning point page: only interaction in the story
			slot = InteractionSlot(
				kind="decision",
				directive="Present the turning point where character action matters. Embed possibilities naturally in story flow."
			)
		elif p == layout.total_pages:
			# Final page: gentle closure
			slot = InteractionSlot(
				kind="narrative",
				directive="Provide warm, conclusive ending."
			)
		else:
			# All other pages: lightweight narrative
			slot = InteractionSlot(kind="narrative")
		
		plan.append(slot)
		
	return plan

def _determine_branch_config(age_value: int, layout: BranchLayout) -> Dict[str, Any]:
	"""
	已棄用的邏輯包裝器。現在純粹反映剛性的 Layout 設定。
	
	根據年齡和佈局設定返回分支配置。
	
	Args:
		age_value: 目標年齡值。
		layout: 頁面佈局物件。
		
	Returns:
		分支配置字典。
	"""
	if age_value <= 3:
		return {
			"enabled": False,
			"branch_count": 0,
			"divergence_point": 0,
			"style": "linear_companionship"
		}
	
	style = "system_hint_supportive" if age_value <= 5 else "preference_questioning"
	
	return {
		"enabled": True,
		"branch_count": layout.branch_count,
		"divergence_point": layout.decision_page,
		"style": style
	}


def build_story_profile(
	language: str = "en",
	age: Optional[str | int] = None,
	category: Optional[str] = None,
	subcategory: Optional[str] = None,
	theme: Optional[str] = None,
	rng: Optional[random.Random] = None,
) -> StoryProfile:
	"""根據給定參數從 KG 生成完整的故事配置檔案。
	
	整合 KG 的各種資訊（年齡、分類、主題、角色等），
	產生一個包含所有必要資訊的 StoryProfile 物件。
	
	Args:
		language: 故事語言。
		age: 目標年齡或年齡範圍。
		category: 主分類，未指定則隨機選擇。
		subcategory: 子分類，未指定則隨機選擇。
		theme: 故事主題，未指定則隨機選擇。
		rng: 隨機數生成器。
		
	Returns:
		StoryProfile 實例。
	"""
	kg = get_story_kg()
	age_value = _normalize_age_value(age, rng)
	category_id = _resolve_category_id(category)
	config = kg.get_random_story_config(age=age_value, category=category_id, rng=rng)
	age_config = config.get("age_config", {})
	age_min = age_config.get("min_age", age_value)
	age_max = age_config.get("max_age", age_value)
	age_range = f"{age_min}-{age_max}"
	age_label = config.get("age_group", f"Age {age_range}")
	age_group_id = config.get("age_group_id", slugify_name(age_label, "age"))
	category_id = config.get("category_id", category_id or "general")
	category_label = config.get("category", _format_label(category_id))
	themes = config.get("themes", {})
	if not themes:
		raise ValueError(f"Category {category_id} has no themes in KG")
	# Prefer KG-selected theme when user didn't specify one
	if not theme and isinstance(config.get("selected_theme_id"), str) and config.get("selected_theme_id") in themes:
		theme_id = config["selected_theme_id"]
	else:
		theme_id = _resolve_theme_id(theme, themes, rng)
	theme_entry = themes[theme_id]
	# Prefer KG-recommended subcategory when user didn't specify one
	if subcategory:
		subcategory_id = _resolve_subcategory_id(subcategory, config.get("category_config", {}), rng)
	else:
		# KG 只提供查詢結果，決策邏輯在應用層
		matching_subcats = kg.get_matching_subcategories(category=category_id, theme_id=theme_id)
		if matching_subcats:
			# 選擇評分最高的（如有多個同分則隨機）
			max_score = matching_subcats[0]['score']
			best_matches = [s for s in matching_subcats if s['score'] == max_score]
			chosen = rng.choice(best_matches) if rng else best_matches[0]
			subcategory_id = chosen['subcategory_id'] or _resolve_subcategory_id(None, config.get("category_config", {}), rng)
		else:
			subcategory_id = _resolve_subcategory_id(None, config.get("category_config", {}), rng)
	subcategory_label = _format_label(subcategory_id)
	prompt_guidelines = kg.get_enhanced_prompt_guidelines(age_range, category_id)
	
	# Inject rich quality guidelines from KG to match high standards
	try:
		quality_requirements = kg.get_text_quality_requirements(age_range)
		
		# 1. Complexity & Language
		complexity = age_config.get("complexity", "intermediate")
		extra_guidelines = [f"Language Complexity: Use {complexity} language appropriate for age {age_range}."]
		
		# 2. Character Naming
		character_rules = quality_requirements.get("character_naming", {})
		if character_rules:
			extra_guidelines.append(f"Character Naming Rules: {character_rules.get('rules', '')} Examples: {', '.join(character_rules.get('examples', []))}")
			
		# 3. Grammar
		grammar_rules = quality_requirements.get("grammar_requirements", {})
		if grammar_rules:
			extra_guidelines.append(f"Grammar Requirements: {grammar_rules.get('sentence_length', '')} {grammar_rules.get('punctuation', '')} {grammar_rules.get('article_usage', '')}")
			
		# 4. Consistency
		consistency_rules = quality_requirements.get("content_consistency", {})
		if consistency_rules:
			extra_guidelines.append(f"Consistency Rules: {consistency_rules.get('character_behavior', '')} {consistency_rules.get('plot_structure', '')}")
			
		# Merge into prompt_guidelines
		prompt_guidelines = "\n\n".join(extra_guidelines) + "\n\n" + prompt_guidelines
		
	except Exception as e:
		logging.warning(f"Failed to inject rich guidelines from KG: {e}")
	
	# [Refactor] 使用 Layout Library 決定結構 (单一真理來源)
	# Layout 定義了總頁數、決策點等
	# 提取種子以進行確定性的佈局選擇
	layout_seed = None
	if rng:
		# Try to get a consistent seed from RNG state if possible, otherwise just use a random int
		try:
			layout_seed = rng.randint(0, 999999)
		except:
			layout_seed = random.randint(0, 999999)
	else:
		layout_seed = random.randint(0, 999999)

	# Allow layout_id override if present in raw config (future proofing)
	target_layout_id = config.get("layout_id") 

	layout = _generate_layout(age_value, seed=layout_seed, layout_id=target_layout_id)
	pages_expected = layout.total_pages
	
	# [Phase 5] 動態分支策略注入 (Strict Authority)
	# 若佈局支援分支，我們必須在此預選原型 (Archetypes)。
	if layout.branch_count > 0:
		# Use the KG to pick distinct, child-friendly archetypes
		# based on the age group.
		selected_archetypes = kg.get_random_branch_archetypes(
			count=layout.branch_count,
			age_group=age_group_id, # e.g. "age_6_8"
			rng=rng
		)
		layout.branch_slots = selected_archetypes
		logging.info(f"Dynamic Branch Slots Selected: {[s['label'] for s in selected_archetypes]}")

	# [Phase 4] Inject Layout & Visual Attributes into Guidelines
	if layout.description or layout.pacing:
		layout_guide = f"Layout Structure: {layout.description}. Pacing: {layout.pacing}."
		prompt_guidelines = layout_guide + "\n\n" + prompt_guidelines
		
	# Inject Visual Style from KG if available
	visual_style = quality_requirements.get("visual_style", "") if 'quality_requirements' in locals() else ""
	if not visual_style:
		# Fallback query if not in quality_reqs structure
		try: 
			visual_style = kg._get_age_group_for_age(age_value).properties.get("visual_style", "")
		except: pass
		
	# [Adjust] Generate Interaction Plan based on Layout
	interaction_plan = _generate_interaction_plan(layout, age_value)

	# [Adjust] Branch config merely reflects the layout now
	branch_config = _determine_branch_config(age_value, layout)
	
	scenes = _collect_theme_scenes(theme_entry.get("properties", {}))
	# Prefer KG-native scene relations if available (theme -> scene)
	try:
		kg_scenes = kg.get_theme_scenes(theme_id)
		if kg_scenes:
			scenes = kg_scenes
	except Exception as exc:
		logging.warning("Failed to query KG theme scenes: %s", exc)
	characters: List[str] = []
	for data in config.get("characters", {}).values():
		label = data.get("label", "Unknown")
		role = data.get("properties", {}).get("role")
		characters.append(f"{label} ({role})" if role else label)
	kg_payload = {
		"characters": characters,
		"scenes": scenes,
		"moral": theme_entry.get("properties", {}).get("moral_value")
			or theme_entry.get("properties", {}).get("emotional_value")
			or theme_entry.get("label"),
		"guidelines": prompt_guidelines,
		"selected_variations": {
			"structure": config.get("selected_structure"),
			"dynamic": config.get("selected_dynamic"),
			"catalyst": config.get("selected_catalyst"),
			"subcategory": subcategory_id,
		},
	}

	# Append a compact KG selection summary to improve consistency and auditability
	try:
		structure_label = (config.get("selected_structure") or {}).get("label")
		dynamic_label = (config.get("selected_dynamic") or {}).get("label")
		catalyst_label = (config.get("selected_catalyst") or {}).get("label")
		
		# Extract enriched metadata from theme_entry
		related_emotions = theme_entry.get("related_emotions", [])
		related_objectives = theme_entry.get("related_objectives", [])
		related_cultural = theme_entry.get("related_cultural", [])
		
		prompt_guidelines = (
			prompt_guidelines
			+ "\n\nKG SELECTION SUMMARY (keep consistent):\n"
			+ f"- Category: {category_label}\n"
			+ f"- Theme: {theme_entry.get('label', _format_label(theme_id))}\n"
			+ f"- Subcategory: {subcategory_label}\n"
			+ f"- Structure: {structure_label or 'N/A'}\n"
			+ f"- Dynamic: {dynamic_label or 'N/A'}\n"
			+ f"- Catalyst: {catalyst_label or 'N/A'}\n"
		)
		
		# Add Branch Strategy Summary
		if layout.branch_slots:
			branch_summary = ", ".join([f"Option {i+1}: {slot['label']}" for i, slot in enumerate(layout.branch_slots)])
			prompt_guidelines += f"- Branch Strategy: {branch_summary}\n"

		if related_emotions:
			prompt_guidelines += f"- Key Emotions: {', '.join(related_emotions)}\n"
		if related_objectives:
			prompt_guidelines += f"- Learning Objectives: {', '.join(related_objectives)}\n"
		if related_cultural:
			prompt_guidelines += f"- Cultural Elements: {', '.join(related_cultural)}\n"
			
		prompt_guidelines += f"- Suggested scenes: {', '.join(scenes[:8])}\n"
		
		kg_payload["guidelines"] = prompt_guidelines
	except Exception as exc:
		logging.warning("Failed to append KG selection summary: %s", exc)
	return StoryProfile(
		language=language,
		age_value=age_value,
		age_range=age_range,
		age_group_id=age_group_id,
		age_label=age_label,
		category_id=category_id,
		category_label=category_label,
		subcategory_id=subcategory_id,
		subcategory_label=subcategory_label,
		theme_id=theme_id,
		theme_label=theme_entry.get("label", _format_label(theme_id)),
		kg_version=config.get("kg_version", "StoryGenerationKG-1.0"),
		kg_payload=kg_payload,
		prompt_guidelines=prompt_guidelines,
		raw_config=config,
		visual_style=visual_style,
		pages_expected=pages_expected,
		branch_config=branch_config,
		layout=layout,
		interaction_plan=interaction_plan,
	)


# ---------------------------------------------------------------------------
# 統一 Logging 設定


def setup_logging(
	module_name: str,
	log_path: Optional[Path] = None,
	level: int = logging.INFO,
	console: bool = True,
) -> logging.Logger:
	"""建立可選擇輸出到檔案與終端機的 logger。"""

	logger = logging.getLogger(module_name)
	logger.setLevel(level)
	if logger.handlers:
		return logger

	formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

	if console:
		stream_handler = logging.StreamHandler()
		stream_handler.setFormatter(formatter)
		logger.addHandler(stream_handler)

	if log_path:
		try:
			log_path.parent.mkdir(parents=True, exist_ok=True)
			# 在 Windows 上，使用 delay=True 可以避免文件鎖定問題
			file_handler = logging.FileHandler(log_path, encoding="utf-8", delay=True)
			file_handler.setFormatter(formatter)
			logger.addHandler(file_handler)
		except (OSError, PermissionError) as exc:
			# 如果文件日誌設置失敗，至少確保控制台日誌可用
			if console:
				logger.warning("Failed to setup file logging for %s: %s", log_path, exc)
			else:
				# 如果 console=False 且文件日誌失敗，回退到控制台輸出
				stream_handler = logging.StreamHandler()
				stream_handler.setFormatter(formatter)
				logger.addHandler(stream_handler)
				logger.warning("File logging failed, falling back to console: %s", exc)

	return logger


# ---------------------------------------------------------------------------
# File I/O helpers


def ensure_dir(path: Path) -> Path:
	"""確保指定資料夾存在，若不存在就建立。"""

	path.mkdir(parents=True, exist_ok=True)
	return path


def read_text(path: Path) -> Optional[str]:
	"""讀取文字檔，若不存在則回傳 None。"""

	try:
		return path.read_text(encoding="utf-8")
	except FileNotFoundError:
		return None


def write_text(path: Path, content: str) -> bool:
	"""寫入文字檔並自動補上換行，寫入失敗回傳 False。"""

	try:
		ensure_dir(path.parent)
		if not content.endswith("\n"):
			content += "\n"
		path.write_text(content, encoding="utf-8")
		return True
	except OSError:
		return False


def read_json(path: Path) -> Optional[Dict[str, object]]:
	"""載入 JSON 檔，解析失敗回傳 None。"""

	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except (FileNotFoundError, json.JSONDecodeError):
		return None


def write_json(path: Path, data: Dict[str, object]) -> bool:
	"""輸出為 JSON 檔並確保資料夾存在。"""

	try:
		ensure_dir(path.parent)
		path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
		return True
	except OSError:
		return False


def write_text_or_raise(path: Path, content: str) -> None:
	"""寫入文字檔，失敗時直接拋出異常。"""

	if not write_text(path, content):
		raise OSError(f"Failed to write {path}")


def write_json_or_raise(path: Path, data: Dict[str, object]) -> None:
	"""寫入 JSON 檔，失敗時直接拋出異常。"""

	if not write_json(path, data):
		raise OSError(f"Failed to write {path}")


# ---------------------------------------------------------------------------
# Story directory helpers


def find_latest_story_root(output_dir: Path) -> Optional[Path]:
	"""在 output 目錄中找到最後更新的故事資料夾（搜尋三層階層）。"""

	if not output_dir.exists():
		return None

	candidates: List[Path] = []
	for category_dir in output_dir.iterdir():
		if not category_dir.is_dir():
			continue
		for age_dir in category_dir.iterdir():
			if not age_dir.is_dir():
				continue
			for story_dir in age_dir.iterdir():
				if not story_dir.is_dir():
					continue
				if (story_dir / "resource").exists() or (story_dir / "resources").exists():
					candidates.append(story_dir)
	if not candidates:
		return None
	return max(candidates, key=lambda p: p.stat().st_mtime)


def resolve_story_root(story_root: Optional[Path], output_root: Path = Path("output")) -> Path:
	"""決定 CLI 應該使用的故事資料夾，若未指定則找最新的。"""

	if story_root is not None:
		if story_root.exists():
			return story_root
		raise FileNotFoundError(f"Story root not found: {story_root}")

	latest = find_latest_story_root(output_root)
	if latest is None:
		raise FileNotFoundError(f"No stories found under {output_root}")
	return latest


def ensure_story_subdirs(story_root: Path) -> Dict[str, Path]:
	"""建立故事資料夾底下的標準子目錄並回傳路徑表。"""

	subdirs = {
		"resource": story_root / "resource",
		"image": story_root / "image",
		"image_main": story_root / "image" / "main",
		"image_original": story_root / "image" / "original",
		"image_nobg": story_root / "image" / "nobg",
		"logs": story_root / "logs",
	}
	for path in subdirs.values():
		ensure_dir(path)
	return subdirs


def ensure_story_languages(story_root: Path, languages: Sequence[str]) -> Dict[str, Dict[str, Path]]:
	"""確保語言資料夾存在並建立 TTS 子目錄。"""

	layout: Dict[str, Dict[str, Path]] = {}
	for language in languages:
		lang_dir = ensure_dir(story_root / language)
		tts_dir = ensure_dir(lang_dir / "tts")
		layout[language] = {"root": lang_dir, "tts": tts_dir}
	return layout


def create_story_root(output_dir: Path, relative_path: str, languages: Optional[Sequence[str]] = None) -> Path:
	"""建立故事根目錄並預先準備所需子資料夾。"""

	story_root = output_dir / relative_path
	ensure_dir(story_root)
	ensure_story_subdirs(story_root)
	if languages:
		ensure_story_languages(story_root, languages)
	return story_root


def relocate_story_root(current_root: Path, output_dir: Path, new_relative_path: str) -> Path:
	"""將臨時故事資料夾移動到正式路徑。"""

	target = output_dir / new_relative_path
	if current_root.resolve() == target.resolve():
		return target
	ensure_dir(target.parent)
	if target.exists():
		raise FileExistsError(f"Target story directory already exists: {target}")

	def _ignore_runtime_locked_dirs(_src: str, names: List[str]) -> List[str]:
		# Windows 上 logs 目錄中的檔案有時會因 logger/file handle 或防毒掃描暫時鎖定。
		# 發生這種情況時，允許先搬主要故事內容，再由新流程在目標路徑重建 logs。
		return [name for name in names if name.lower() == "logs"]

	try:
		shutil.move(str(current_root), str(target))
	except (PermissionError, OSError):
		shutil.copytree(
			current_root,
			target,
			ignore=_ignore_runtime_locked_dirs,
			dirs_exist_ok=False,
		)
		try:
			shutil.rmtree(current_root, ignore_errors=True)
		except Exception:
			pass
	return target


@dataclass
class BranchInfo:
	"""儲存分支的結構資訊。"""
	id: str
	parent_id: Optional[str]
	divergence_point: int
	convergence_point: Optional[int] = None


@dataclass
class PageInfo:
	number: int
	path: Path

	@property
	def content(self) -> str:
		return read_text(self.path) or ""


@dataclass
class StoryPathManager:
	"""集中管理故事語系與資源檔案路徑。"""

	story_root: Path
	language: str
	page_template: str = "page_{}.txt"
	current_branch: str = "option_1"
	pages: Dict[int, PageInfo] = field(init=False, default_factory=dict)

	def __post_init__(self) -> None:
		self.refresh(self.story_root, self.language)

	def set_branch(self, branch_id: str) -> None:
		"""切換當前分支並更新路徑。"""
		self.current_branch = branch_id
		self.refresh(self.story_root, self.language)

	def refresh(self, story_root: Path, language: Optional[str] = None) -> None:
		if language:
			self.language = language
		self.story_root = story_root
		self.language_root = ensure_dir(self.story_root / self.language)
		
		# 決定資源與日誌的根目錄
		# 所有分支（含 root）統一放在 language_root / branches / branch_id
		self.active_root = ensure_dir(self.language_root / "branches" / self.current_branch)

		self.resource_root = ensure_dir(self.active_root / "resource")
		# 日誌保持在 story_root/logs 統一管理，或者也分開？
		# 為了避免混亂，日誌分開比較好，但主控台日誌可能需要聚合。
		# 暫時保持日誌在各自的 active_root 下，或者統一在最外層？
		# 原本是 story_root/logs。
		# 為了除錯方便，如果是支線，我們在支線目錄下也建 logs
		self.logs_root = ensure_dir(self.active_root / "logs")

		self.paths = {
			"language_root": self.language_root,
			"active_root": self.active_root,
			"outline": self.active_root / "outline.txt",
			"title": self.active_root / "title.txt",
			"story": self.active_root / "draft_story.txt",
			"full_story": self.active_root / "full_story.txt",
			"narration_full": self.active_root / "narration.txt",
			"dialogues_full": self.active_root / "dialogue.txt",
			"resource": self.resource_root,
			"story_meta": self.resource_root / "story_meta.json",
			"kg_profile": self.resource_root / "kg_profile.json",
			"guidelines": self.resource_root / "kg_guidelines.txt",
			"cover": self.resource_root / "book_cover_prompt.txt",
			"scenes_full": self.resource_root / "scenes.txt",
			"poses_full": self.resource_root / "character_poses.txt",
			"logs": self.logs_root,
		}

		self.pages = self._scan_pages()

	def _scan_pages(self) -> Dict[int, PageInfo]:
		"""掃描當前 active_root 下的頁面檔案。"""
		pages: Dict[int, PageInfo] = {}
		if not self.active_root.exists():
			return pages
		
		pattern = self.page_template.replace("{}", "*")
		for path in self.active_root.glob(pattern):
			if not path.is_file():
				continue
			if self.page_template == "page_{}.txt":
				m = re.match(r"page_(\d+)\.txt", path.name)
				if m:
					num = int(m.group(1))
					pages[num] = PageInfo(number=num, path=path)
			else:
				digits = re.findall(r"\d+", path.name)
				if digits:
					num = int(digits[0])
					pages[num] = PageInfo(number=num, path=path)
		return pages

	def relocate(self, new_root: Path) -> None:
		self.refresh(new_root)

	def page_file(self, idx: int) -> Path:
		return self.active_root / self.page_template.format(idx)

	def derivation_path(self, step: str, idx: int) -> Path:
		target_dir = self.active_root if step in {"narration", "dialogue"} else self.resource_root

		suffix_map = {
			"narration": "_narration",
			"dialogue": "_dialogue",
			"scene": "_prompt",
			"pose": "_poses",
		}
		return target_dir / f"page_{idx}{suffix_map[step]}.txt"

	def aggregate_path(self, step: str) -> Path:
		mapping = {
			"narration": self.paths["narration_full"],
			"dialogue": self.paths["dialogues_full"],
			"scene": self.paths["scenes_full"],
			"pose": self.paths["poses_full"],
		}
		return mapping[step]


# ---------------------------------------------------------------------------
# Seed helpers


def load_or_create_seed(resources_dir: Path, filename: str = "seed.txt") -> int:
	"""讀取或產生共用 seed，確保文本/影像一致性。"""

	ensure_dir(resources_dir)
	seed_path = resources_dir / filename
	if seed_path.exists():
		try:
			return int(seed_path.read_text(encoding="utf-8").strip())
		except ValueError:
			pass
	seed = random.randint(1, 10**9)
	seed_path.write_text(str(seed), encoding="utf-8")
	return seed


# ---------------------------------------------------------------------------
# Prompt helpers


def list_character_prompt_files(resources_dir: Path) -> List[Path]:
	"""列出角色 prompt 檔 (character_*.txt) 並排序。"""

	if not resources_dir.exists():
		return []
	files = [p for p in resources_dir.glob("character_*.txt") if p.is_file()]
	return sorted(files)


def list_page_prompt_files(resources_dir: Path) -> List[Path]:
	"""列出 page_X_prompt.txt 檔案並依頁碼排序。"""

	if not resources_dir.exists():
		return []
	files = []
	for path in resources_dir.glob("page_*_prompt.txt"):
		if not path.is_file():
			continue
		files.append(path)
	files.sort(key=_page_sort_key)
	return files


def load_prompt(path: Path) -> str:
	"""載入 prompt 文字並去除首尾空白。"""

	content = read_text(path)
	return content.strip() if content else ""


def _page_sort_key(path: Path) -> int:
	"""依檔名取出頁碼，若失敗則回傳 0。"""

	match = re.search(r"page_(\d+)_prompt", path.name)
	return int(match.group(1)) if match else 0


def page_number_from_prompt(path: Path) -> int:
	"""從 page_X_prompt 檔名中取得頁碼供排序或種子使用。"""

	return _page_sort_key(path)


# ---------------------------------------------------------------------------
# GPU cleanup


class ResourceManager:
	"""統一的 GPU/CPU 資源管理器，整合清理與裝置設定。"""
	
	_logger = logging.getLogger("utils.ResourceManager")
	
	@staticmethod
	def cleanup_torch(aggressive: bool = False) -> None:
		"""釋放 CUDA 快取與 Python 記憶體。
		
		Args:
			aggressive: True 時執行更多輪 GC 與深度清理
		"""
		try:
			import torch
			import gc
		except ImportError:
			return
		
		gc_rounds = 5 if aggressive else 3
		ResourceManager._logger.debug(f"Starting {gc_rounds}-pass GC...")
		
		for _ in range(gc_rounds):
			gc.collect()
		
		if not torch.cuda.is_available():
			return
		
		ResourceManager._logger.debug("Clearing CUDA cache...")
		torch.cuda.empty_cache()
		torch.cuda.ipc_collect()
		
		try:
			torch.cuda.reset_peak_memory_stats()
			if aggressive:
				torch.cuda.reset_accumulated_memory_stats()
		except Exception:
			pass
		
		try:
			torch.cuda.synchronize()
		except Exception:
			pass
		
		ResourceManager._logger.debug("CUDA cleanup complete")
	
	@staticmethod
	def cleanup_model(model: Any, aggressive: bool = False) -> None:
		"""清理模型實例並釋放相關資源。
		
		Args:
			model: 要清理的模型物件（會被 del）
			aggressive: 是否執行激進清理（用於大型模型切換）
		"""
		if model is not None:
			del model
		
		ResourceManager.cleanup_torch(aggressive=aggressive)
	
	@staticmethod
	def setup_torch_generator(device: str, seed: int) -> Any:
		"""統一建立 torch.Generator 並處理裝置邏輯。
		
		Args:
			device: 裝置字串 (如 'cuda:0', 'cuda', 'cpu')
			seed: 隨機種子
			
		Returns:
			已設定 seed 的 torch.Generator
		"""
		try:
			import torch
		except ImportError:
			raise RuntimeError("torch is required for setup_torch_generator")
		
		if device.startswith("cuda"):
			generator_device = device if ":" in device else "cuda:0"
		else:
			generator_device = "cpu"
		
		return torch.Generator(device=generator_device).manual_seed(seed)


# 向後相容：保留舊函式名稱
def cleanup_torch() -> None:
	"""釋放 CUDA 快取，避免 GPU 記憶體殘留。（向後相容包裝）"""
	ResourceManager.cleanup_torch(aggressive=False)


def force_cleanup_models() -> None:
	"""更激進的模型清理，用於大型模型切換之間。（向後相容包裝）"""
	ResourceManager.cleanup_torch(aggressive=True)


# ---------------------------------------------------------------------------
# 通用組態載入/覆寫


def _load_yaml(path: Path) -> Dict[str, Any]:
	"""內部工具：嘗試載入 YAML 並確保結果為字典。"""

	try:
		import yaml  # type: ignore
	except ImportError as exc:  # pragma: no cover - optional dependency
		raise RuntimeError("需要安裝 PyYAML 才能讀取 YAML 組態，請執行 pip install pyyaml") from exc
	data = yaml.safe_load(path.read_text(encoding="utf-8"))  # type: ignore[arg-type]
	if not isinstance(data, dict):
		raise ValueError(f"YAML 組態必須是物件結構：{path}")
	return data


def load_structured_config(path: Path) -> Dict[str, Any]:
	"""讀取 JSON/YAML 組態檔案並回傳字典。"""

	suffix = path.suffix.lower()
	if suffix == ".json":
		data = read_json(path) or {}
		if not isinstance(data, dict):
			raise ValueError(f"JSON 組態必須是物件結構：{path}")
		return data
	if suffix in {".yaml", ".yml"}:
		return _load_yaml(path)
	raise ValueError(f"不支援的組態副檔名：{path.suffix}")


def _flatten_overrides(data: Dict[str, Any], args: argparse.Namespace) -> Dict[str, Any]:
	"""攤平成適用於 argparse Namespace 的鍵值。"""

	flat: Dict[str, Any] = {}
	for key, value in data.items():
		if isinstance(value, dict):
			for sub_key, sub_value in value.items():
				compound = f"{key}_{sub_key}"
				if hasattr(args, compound):
					flat[compound] = sub_value
				elif hasattr(args, sub_key):
					flat[sub_key] = sub_value
		else:
			flat[key] = value
	return flat


def apply_cli_overrides(
	args: argparse.Namespace,
	config_path: Optional[Path],
	allowed_keys: Optional[Sequence[str]] = None,
) -> argparse.Namespace:
	"""將外部組態覆寫到 argparse Namespace，支援巢狀鍵值。"""

	if not config_path:
		return args
	data = load_structured_config(config_path)
	flat = _flatten_overrides(data, args)
	allowed = set(allowed_keys) if allowed_keys else None
	for key, value in flat.items():
		if allowed and key not in allowed:
			continue
		if not hasattr(args, key):
			continue
		current = getattr(args, key)
		if isinstance(current, Path):
			setattr(args, key, Path(value))
		else:
			setattr(args, key, value)
	return args
