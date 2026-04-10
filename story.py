"""故事文本產生主程式。

此模組串起 README.md 描述的十步驟流程：載入提示模板、呼叫假輸出或
transformers LLM、寫入所有中介檔案，並將最終 `story_meta.json` 與 KG 描述
集中保存於 `resource/` 目錄內。
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import time
import torch #勿動此行
import platform
import difflib
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, Iterator, Set

LOGGER_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

if platform.system().lower().startswith("win") or platform.system().lower().startswith("darwin"):
	logging.getLogger("torch.distributed.elastic").setLevel(logging.ERROR)

from utils import (
	StoryPathManager,
	StoryProfile,
	BranchInfo, # [NEW]
	build_story_relative_path,
	get_story_kg,  # Import KG instance getter
	cleanup_torch,
	relocate_story_root,
	setup_logging,
	write_json_or_raise,
	write_text_or_raise,
)
from prompts.prompt_utils import (
	EXTRACTION_TAGS,
	PAGE_TEMPLATE,
	PROMPT_FILES,
	STEP_TAGS,
	THINK_BLOCK_PATTERN,
	ChatPrompt,
	_load_chat_sections,
	_strip_page_prefix,
	load_step_prompts,
	load_template,
	render_prompt,
	strip_hidden_thoughts,
)
from backends.llm import BaseLLM, GenerationParams
from story_core.story_entry import cli, generate_story_id, main
from story_core.story_branching import (
	compile_full_story,
	copy_branch_pages,
	copy_branch_state,
	create_branch as register_branch,
	current_branch_value_focus,
	get_page_owner,
	read_page_content,
	switch_branch as activate_branch,
)
from story_core.story_state_io import (
	extract_state_snapshot,
	read_page_structure,
	structure_path,
	write_page_structure,
	write_state_snapshot,
)
from story_core.story_outputs import (
	build_cover_context,
	build_story_meta,
	collect_branch_pages,
	load_full_story_text,
	persist_story_meta,
	select_canonical_branch,
)
from story_core.story_page_flow import (
	append_system_announcement,
	build_structural_fallback_state,
	finalize_story_pages,
	format_decision_options,
	preload_existing_pages,
	resolve_page_range,
)
from story_core.story_helpers import (
	_apply_default_step_generations,
	estimate_clip_tokens,
	estimate_tokens,
	format_list,
	paginate_text,
	run_qwen_step,
	split_sentences,
	validate_image_prompt_length,
)
from story_core.story_text_normalize import (
	build_character_alias_map,
	coref_ambiguity_score,
	count_character_mentions,
	enforce_dynamic_consistency,
	enforce_name_consistency,
	sanitize_text,
)
from story_core.story_types import PipelineOptions, StoryInput


class GenerationAbortedError(Exception):
	"""Raised when a specific step fails all retries and validation, aborting the generation."""
	pass


class StoryPipeline:
	"""
	故事生成管線 (Pipeline)。
	封裝了從初始化、大綱規劃、章節撰寫到最終產出 metadata 的完整十步驟流程。
	對外主要提供 `run()` 方法作為執行入口。
	"""
	def __init__(
		self,
		inputs: StoryInput,
		story_id: str,
		relative_path: str,
		output_root: Path,
		story_root: Path,
		llm: BaseLLM,
		options: PipelineOptions,
		logger: logging.Logger,
		kernel_recorder: Any = None,
	) -> None:
		"""以 KG Profile/LLM/路徑設定初始化所需狀態。"""
		if inputs.kg_profile is None:
			raise ValueError("StoryInput must include kg_profile")
		self.inputs = inputs
		self.story_id = story_id
		self.output_root = output_root
		self.story_root = story_root
		self.llm = llm
		self.options = options
		self.logger = logger
		self.kernel_recorder = kernel_recorder
		self.profile: StoryProfile = inputs.kg_profile
		self.kg = get_story_kg()  # Initialize KG instance for accessing configuration
		self.system_config = self._load_system_config()
		self.step_history: List[Dict[str, Any]] = []
		self.age_policy = dict(self.profile.raw_config.get("age_config", {}) or {})
		self.dialogue_rules = self.age_policy.get("dialogue_rules") or "Each character delivers one concise sentence that is easy to read aloud."
		self.narration_rules = self.age_policy.get("narration_rules") or "Rewrite the page as natural spoken narration with casual phrasing."
		self.image_style_lock = self._image_style_lock()
		# Avoid using prompt_guidelines as fallback for age_wording, as it now contains the full KG summary
		age_wording = self.age_policy.get("language_guidelines") or "Use warm, simple sentences for children."
		self.base_context = {
			"language": inputs.language,
			"age_group": inputs.age_group,
			"category": inputs.category,
			"subcategory": inputs.subcategory,
			"theme": inputs.theme,
			"kg_characters": format_list(
				(inputs.kg_payload or {}).get("characters")
			),
			"kg_scenes": format_list((inputs.kg_payload or {}).get("scenes")),
			"kg_moral": (inputs.kg_payload or {}).get("moral", ""),
			"kg_guidelines": "",
		}
		self.primary_characters = self._determine_primary_characters()
		glossary_text = "Strict Rule: Use exactly these character names. Do not merge or abbreviate them: " + ", ".join(self.primary_characters)
		
		self.base_context.update(
			{
				"character1": self.primary_characters[0],
				"character2": self.primary_characters[1],
				"character3": self.primary_characters[2],
				"primary_characters": self.primary_characters,
				"characters_csv": ", ".join(self.primary_characters),
				"glossary": glossary_text,
				"story_variations": self._format_story_variations(),
				"min_page": self.profile.layout.total_pages if self.profile.layout else self.options.pages_expected,
				"pages_expected": self.profile.layout.total_pages if self.profile.layout else self.options.pages_expected,
				"main_category": inputs.category,
				"sub_category": inputs.subcategory,
				"language_instruction": "Write everything in English only.",
				"age_wording_rules": age_wording,
				"dialogue_rules": self.dialogue_rules,
				"narration_rules": self.narration_rules,
				"image_style_lock": self.image_style_lock,
			}
		)
		self.story_input_mode = str(getattr(self.inputs, "input_mode", "preset") or "preset").strip().lower()
		if self.story_input_mode not in {"preset", "custom"}:
			self.story_input_mode = "preset"
		self.user_story_prompt = (self.inputs.user_prompt or "").strip()
		self.user_story_materials = (self.inputs.user_materials or "").strip()
		self.user_story_intent = self._build_user_story_intent()
		self.effective_guidelines = self._compose_effective_guidelines()
		self.base_context["kg_guidelines"] = self.effective_guidelines
		self.base_context["story_input_mode"] = self.story_input_mode
		self.base_context["user_story_prompt"] = self.user_story_prompt
		self.base_context["user_story_materials"] = self.user_story_materials
		self.base_context["user_story_materials_structured"] = format_list(
			self.user_story_intent.get("must_include", [])
		)
		self.root_branch_id = "option_1"
		self.file_manager = StoryPathManager(self.story_root, self.inputs.language)
		self.language_dir = self.file_manager.language_root
		self.paths = self.file_manager.paths
		self.story_title: Optional[str] = None
		self.relative_path = relative_path
		self._major_step_total = 8
		self._major_step_index = 0

		# [Multi-Branch Support]
		self.branches: Dict[str, BranchInfo] = {
			self.root_branch_id: BranchInfo(id=self.root_branch_id, parent_id=None, divergence_point=1)
		}
		self.current_branch_id: str = self.root_branch_id
		# 初始將 file_manager 設定為 root branch
		self.file_manager.set_branch(self.root_branch_id)

	def _load_system_config(self) -> Dict[str, Any]:
		"""從外部設定檔載入系統閾值，若失敗則傳回預設值"""
		config_path = Path("system_config.json")
		if config_path.exists():
			try:
				return json.loads(config_path.read_text(encoding="utf-8"))
			except Exception as exc:
				self.logger.warning("Failed to load system_config.json: %s", exc)
		return {"max_retries_per_step": 2, "validation": {"clip_tokens": {}}}

	def _split_hint_text(self, text: str, *, max_items: int = 12) -> List[str]:
		"""將使用者輸入切成簡潔條目。"""
		if not text:
			return []
		parts = re.split(r"[\n,;；、]+", text)
		cleaned: List[str] = []
		seen: Set[str] = set()
		for part in parts:
			item = re.sub(r"\s+", " ", part.strip())
			if not item:
				continue
			key = item.casefold()
			if key in seen:
				continue
			seen.add(key)
			cleaned.append(item)
			if len(cleaned) >= max_items:
				break
		return cleaned

	def _extract_json_object(self, text: str) -> Optional[Dict[str, Any]]:
		"""從模型輸出中盡可能擷取 JSON 物件。"""
		if not text:
			return None
		candidates: List[str] = []
		blob = strip_hidden_thoughts(text).strip()
		fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", blob, re.IGNORECASE | re.DOTALL)
		if fenced:
			candidates.append(fenced.group(1).strip())
		start = blob.find("{")
		end = blob.rfind("}")
		if start >= 0 and end > start:
			candidates.append(blob[start:end + 1].strip())
		for candidate in candidates:
			try:
				obj = json.loads(candidate)
			except Exception:
				continue
			if isinstance(obj, dict):
				return obj
		return None

	def _normalize_list_field(self, value: Any, *, max_items: int = 8) -> List[str]:
		"""標準化模型抽出的 list 欄位。"""
		if isinstance(value, str):
			return self._split_hint_text(value, max_items=max_items)
		if not isinstance(value, list):
			return []
		items: List[str] = []
		seen: Set[str] = set()
		for element in value:
			item = re.sub(r"\s+", " ", str(element or "").strip())
			if not item:
				continue
			key = item.casefold()
			if key in seen:
				continue
			seen.add(key)
			items.append(item)
			if len(items) >= max_items:
				break
		return items

	def _outline_page_count(self, outline_text: str) -> int:
		return len(re.findall(r"\bPage\s+\d+\b", outline_text or "", flags=re.IGNORECASE))

	def _looks_like_text_glitch(self, text: str) -> bool:
		if not text:
			return True
		bad_markers = ("�", "?", "?", "??")
		return any(marker in text for marker in bad_markers)

	def _critique_outline_candidate(self, outline_text: str) -> Dict[str, Any]:
		outline_text = (outline_text or "").strip()
		if not outline_text:
			return {"pass": False, "score": 0.0, "issues": ["outline_empty"]}

		critique_prompt = ChatPrompt(
			system_prompt=(
				"You review children's story outlines. "
				"Return compact JSON only with keys: pass, score, issues."
			),
			user_prompt=(
				f"Expected pages: {self._total_pages()}\n"
				f"Primary characters: {', '.join(self.primary_characters)}\n"
				"Check for page coverage, character consistency, readability, and obvious glitches.\n"
				"Outline:\n"
				f"{outline_text}\n"
			),
		)
		params = replace(self._generation_for("outline"), max_tokens=120, min_tokens=12, temperature=0.1, top_p=0.8)
		try:
			raw_text, _tokens = self.llm.generate(critique_prompt, params)
			payload = self._extract_json_object(strip_hidden_thoughts(raw_text))
			if isinstance(payload, dict):
				try:
					score_value = max(0.0, min(100.0, float(payload.get("score", 0.0))))
				except (TypeError, ValueError):
					score_value = 0.0
				issues = payload.get("issues")
				if not isinstance(issues, list):
					issues = []
				return {
					"pass": bool(payload.get("pass")) or score_value >= 70.0,
					"score": score_value,
					"issues": [str(item) for item in issues[:6]],
				}
		except Exception as exc:
			self.logger.warning("Outline critique fallback engaged: %s", exc)
		return {"pass": True, "score": 70.0, "issues": []}

	def _score_outline_candidate(self, outline_text: str) -> Dict[str, Any]:
		expected_pages = max(1, self._total_pages())
		page_count = self._outline_page_count(outline_text)
		score = 55.0
		issues: List[str] = []

		if page_count:
			score += max(0.0, 20.0 - abs(page_count - expected_pages) * 5.0)
		else:
			score -= 15.0
			issues.append("missing_page_markers")

		char_hits = 0
		lowered_outline = (outline_text or "").casefold()
		for name in self.primary_characters:
			if name and name.casefold() in lowered_outline:
				char_hits += 1
		score += min(12.0, char_hits * 6.0)
		if char_hits == 0:
			issues.append("missing_primary_character")

		if self.profile and self.profile.layout and self.profile.layout.branch_count > 0:
			if "turning point" in lowered_outline:
				score += 6.0
			else:
				issues.append("missing_turning_point_signal")

		if self._looks_like_text_glitch(outline_text):
			score -= 25.0
			issues.append("encoding_or_token_glitch")

		critique = self._critique_outline_candidate(outline_text)
		score = max(0.0, min(100.0, score * 0.65 + float(critique.get("score", 0.0)) * 0.35))
		if not critique.get("pass", True):
			score = max(0.0, score - 10.0)
		issues.extend(str(item) for item in critique.get("issues", []) if str(item))

		return {
			"score": round(score, 2),
			"page_count": page_count,
			"issues": issues[:8],
			"critique": critique,
		}

	def _score_title_candidate(self, raw_title: str) -> Dict[str, Any]:
		title = self._extract_title_candidate(raw_title) or self._clean_title_candidate(raw_title)
		score = 60.0
		issues: List[str] = []
		word_count = len(title.split())

		if not self._is_plausible_title(title):
			score -= 30.0
			issues.append("implausible_title")
		if word_count < 2:
			score -= 10.0
			issues.append("too_short")
		elif word_count > 8:
			score -= min(20.0, float((word_count - 8) * 3))
			issues.append("too_long")
		else:
			score += 10.0

		if re.search(r"\bpage\b", title, flags=re.IGNORECASE):
			score -= 25.0
			issues.append("contains_page_marker")
		if self._looks_like_text_glitch(title):
			score -= 25.0
			issues.append("encoding_or_token_glitch")

		return {
			"score": round(max(0.0, min(100.0, score)), 2),
			"title": title,
			"issues": issues[:6],
		}

	def _rank_step_candidates(
		self,
		step: str,
		extra_context: Dict[str, Any],
		output_path: Path,
		*,
		candidate_count: int,
		generation: Optional[GenerationParams] = None,
		banned_phrases: Optional[List[str]] = None,
	) -> str:
		candidate_count = max(1, int(candidate_count or 1))
		if candidate_count <= 1 or output_path.exists():
			return self._run_single_step(
				step,
				extra_context,
				output_path,
				generation=generation,
				banned_phrases=banned_phrases,
			)

		candidates: List[Dict[str, Any]] = []
		for idx in range(candidate_count):
			candidate_path = output_path.with_name(f"{output_path.stem}__candidate_{idx + 1}{output_path.suffix}")
			candidate_text = self._run_single_step(
				step,
				extra_context,
				candidate_path,
				generation=generation,
				banned_phrases=banned_phrases,
			)
			if step == "outline":
				scorecard = self._score_outline_candidate(candidate_text)
			elif step == "title":
				scorecard = self._score_title_candidate(candidate_text)
			else:
				scorecard = {"score": 0.0, "issues": []}
			candidates.append({"path": candidate_path, "text": candidate_text, "scorecard": scorecard})
			self.logger.info(
				"[Step %s] candidate %d/%d score=%.2f issues=%s",
				step,
				idx + 1,
				candidate_count,
				float(scorecard.get("score", 0.0)),
				scorecard.get("issues", []),
			)

		selected = max(candidates, key=lambda item: float(item["scorecard"].get("score", 0.0)))
		write_text_or_raise(output_path, str(selected["text"]))
		self.step_history.append(
			{
				"step": f"{step}_selection",
				"candidate_count": candidate_count,
				"selected_candidate": output_path.name,
				"selected_source": Path(str(selected["path"])).name,
				"selected_score": float(selected["scorecard"].get("score", 0.0)),
				"issues": list(selected["scorecard"].get("issues", [])),
			}
		)
		return str(selected["text"])

	def _rule_based_story_intent(self) -> Dict[str, List[str]]:
		"""先做 deterministic 規則式抽取，確保任何情況都有結果。"""
		must_include = self._split_hint_text(self.user_story_materials, max_items=10)
		style_hints: List[str] = []
		tone_hints: List[str] = []
		avoid: List[str] = []

		for line in self._split_hint_text(self.user_story_prompt, max_items=16):
			lowered = line.casefold()
			if any(token in lowered for token in ["不要", "避免", "avoid", "do not", "don't", "no "]):
				avoid.append(line)
			elif any(token in lowered for token in ["風格", "style", "畫面", "cinematic", "watercolor", "anime", "tone"]):
				style_hints.append(line)
			elif any(token in lowered for token in ["情緒", "情感", "親切", "溫暖", "父母", "gentle", "warm", "emotion"]):
				tone_hints.append(line)
			else:
				must_include.append(line)

		return {
			"must_include": self._normalize_list_field(must_include, max_items=10),
			"style_hints": self._normalize_list_field(style_hints, max_items=8),
			"tone_hints": self._normalize_list_field(tone_hints, max_items=8),
			"avoid": self._normalize_list_field(avoid, max_items=8),
		}

	def _model_extract_story_intent(self) -> Dict[str, List[str]]:
		"""用 LLM 將自由輸入轉成結構化欄位，失敗時回退。"""
		if self.story_input_mode != "custom":
			return {}
		if not (self.user_story_prompt or self.user_story_materials):
			return {}
		try:
			system_prompt = (
				"You are a strict extraction engine. "
				"Convert user story preferences into compact JSON with keys: "
				"must_include, style_hints, tone_hints, avoid. "
				"Return JSON object only."
			)
			user_prompt = (
				"Story user prompt:\n"
				+ (self.user_story_prompt or "")
				+ "\n\nStory materials:\n"
				+ (self.user_story_materials or "")
			)
			chat_prompt = ChatPrompt(system_prompt=system_prompt, user_prompt=user_prompt)
			params = GenerationParams(
				max_tokens=220,
				min_tokens=24,
				temperature=0.15,
				top_p=0.9,
				top_k=40,
				repetition_penalty=1.05,
				no_repeat_ngram_size=None,
			)
			raw, _ = self.llm.generate(chat_prompt, params, prefill="{")
			parsed = self._extract_json_object("{" + (raw or ""))
			if not parsed:
				return {}
			return {
				"must_include": self._normalize_list_field(parsed.get("must_include"), max_items=10),
				"style_hints": self._normalize_list_field(parsed.get("style_hints"), max_items=8),
				"tone_hints": self._normalize_list_field(parsed.get("tone_hints"), max_items=8),
				"avoid": self._normalize_list_field(parsed.get("avoid"), max_items=8),
			}
		except Exception as exc:
			self.logger.warning("Story intent model extraction failed, fallback to rules: %s", exc)
			return {}

	def _build_user_story_intent(self) -> Dict[str, Any]:
		"""彙整規則式與模型式結果，輸出穩定結構。"""
		if self.story_input_mode != "custom":
			return {
				"raw_prompt": "",
				"raw_materials": "",
				"must_include": [],
				"style_hints": [],
				"tone_hints": [],
				"avoid": [],
			}
		rule_intent = self._rule_based_story_intent()
		model_intent = self._model_extract_story_intent()
		merged: Dict[str, List[str]] = {}
		for key in ("must_include", "style_hints", "tone_hints", "avoid"):
			combo = (rule_intent.get(key) or []) + (model_intent.get(key) or [])
			merged[key] = self._normalize_list_field(combo, max_items=10 if key == "must_include" else 8)
		return {
			"raw_prompt": self.user_story_prompt,
			"raw_materials": self.user_story_materials,
			**merged,
		}

	def _compose_effective_guidelines(self) -> str:
		"""將 KG 指南與使用者額外需求合併成最終提示規格。"""
		base = (self.profile.prompt_guidelines or "").strip()
		if self.story_input_mode != "custom":
			return base
		intent = self.user_story_intent or {}
		if not (self.user_story_prompt or self.user_story_materials):
			return base

		blocks: List[str] = []
		if intent.get("must_include"):
			blocks.append("Must Include Elements: " + "; ".join(intent["must_include"]))
		if intent.get("style_hints"):
			blocks.append("Style Hints: " + "; ".join(intent["style_hints"]))
		if intent.get("tone_hints"):
			blocks.append("Tone Hints: " + "; ".join(intent["tone_hints"]))
		if intent.get("avoid"):
			blocks.append("Avoid: " + "; ".join(intent["avoid"]))

		if not blocks:
			return base

		user_block = (
			"USER EXTRA INTENT (Normalized):\n"
			"- Treat these as preferences under KG safety and age appropriateness.\n"
			+ "\n".join(f"- {line}" for line in blocks)
		)
		if base:
			return base + "\n\n" + user_block
		return user_block

	def create_branch(self, new_branch_id: str, divergence_point: int, parent_id: Optional[str] = None) -> None:
		"""建立一個新分支並註冊。
		
		創建一個從父分支分離出來的新故事分支，
		用於支援互動式故事的不同選擇路徑。
		
		Args:
			new_branch_id: 新分支的唯一 ID (例如 "option_2")。
			divergence_point: 此分支開始偏離父分支的頁碼。
			parent_id: 父分支 ID，若為 None 則預設為 Root Branch。
		"""
		register_branch(
			self.branches,
			new_branch_id=new_branch_id,
			divergence_point=divergence_point,
			root_branch_id=self.root_branch_id,
			logger=self.logger,
			parent_id=parent_id,
		)

	def switch_branch(self, branch_id: str) -> None:
		"""切換當前工作的目標分支，並更新檔案管理器狀態。
		
		Args:
			branch_id: 要切換到的分支 ID。
			
		Raises:
			ValueError: 分支 ID 不存在。
		"""
		self.current_branch_id, self.paths = activate_branch(
			self.branches,
			branch_id=branch_id,
			file_manager=self.file_manager,
			logger=self.logger,
		)

	def _get_page_owner(self, page_idx: int, branch_id: Optional[str] = None) -> str:
		"""遞迴判斷某頁面歸屬於哪個分支（處理繼承邏輯）。
		
		根據分支的分離點 (divergence_point) 決定頁面所有權，
		如果頁面於分離點之前，則向上遞迴查找父分支。
		
		Args:
			page_idx: 頁面索引。
			branch_id: 分支 ID，未指定則使用當前分支。
			
		Returns:
			擁有該頁面的分支 ID。
			
		Raises:
			ValueError: 找不到擁有者。
		"""
		return get_page_owner(
			self.branches,
			page_idx=page_idx,
			current_branch_id=self.current_branch_id,
			branch_id=branch_id,
		)

	def _read_page_content(self, idx: int) -> Optional[str]:
		"""讀取指定頁面的內容，自動處理分支繼承關係 (若當前分支無此頁，則向上查找)。
		
		Args:
			idx: 頁面索引。
			
		Returns:
			頁面內容文本，找不到則返回 None。
		"""
		return read_page_content(
			self.branches,
			idx=idx,
			current_branch_id=self.current_branch_id,
			file_manager=self.file_manager,
			logger=self.logger,
		)

	def _reset_log_file_handler(self, log_path: Optional[Path]) -> None:
		"""重新綁定檔案 handler，先關閉既有 file handler。"""
		for handler in list(self.logger.handlers):
			if isinstance(handler, logging.FileHandler):
				try:
					handler.flush()
				except Exception:
					pass
				handler.close()
				self.logger.removeHandler(handler)
		if log_path:
			file_handler = logging.FileHandler(log_path, encoding="utf-8")
			file_handler.setFormatter(logging.Formatter(LOGGER_FORMAT))
			self.logger.addHandler(file_handler)

	def _log_major_step(self, name: str) -> None:
		self._major_step_index += 1
		self.logger.info(
			"[Progress] Step %s/%s → %s",
			self._major_step_index,
			self._major_step_total,
			name,
		)

	def _generation_for(self, step: str) -> GenerationParams:
		"""取得指定步驟應用的生成參數。"""
		params = self.options.step_generations.get(step, self.options.generation)

		# 實驗模式：關閉類別驅動的溫度漂移，避免跨案例方差放大。
		if self.options.disable_category_temperature_adaptation:
			return params

		# 針對不同故事類型進行微調
		if self.profile and self.profile.category_id:
			category = self.profile.category_id.lower()
			
			# Adventure: 需要更多創意與動態感
			if category == "adventure":
				if step in {"story", "narration"}:
					# 稍微提高溫度以增加情節變化
					params = replace(params, temperature=max(params.temperature, 0.75))
			
			# Educational: 需要準確與清晰，稍微降低隨機性
			elif category == "educational":
				if step in {"story", "narration"}:
					# 降低溫度以確保邏輯清晰
					params = replace(params, temperature=min(params.temperature, 0.6))
			
			# Fun: 需要幽默與誇張
			elif category == "fun":
				if step in {"story", "dialogue"}:
					# 提高溫度以增加幽默感
					params = replace(params, temperature=max(params.temperature, 0.8))

			# Cultural: 重視氛圍與傳統描述，溫度適中
			elif category == "cultural":
				if step in {"story", "narration"}:
					# 設定為 0.65，兼顧敘事創意與內容穩定性
					params = replace(params, temperature=0.65)

		return params

	def _extract_title(self, raw_title: str) -> str:
		"""由模型產生的標題文本擷取實際書名。"""
		title = self._extract_title_candidate(raw_title)
		if title:
			return title

		# 如果無法解析出書名，回傳安全預設值
		self.logger.warning("Failed to extract title from: %s", raw_title[:100])
		return "My Adventure Story"

	def _clean_title_candidate(self, candidate: str) -> str:
		"""清理標題候選字串，避免 JSON/Markdown 殘片污染。"""
		cleaned = (candidate or "").strip()
		cleaned = re.sub(r"^<title>\s*", "", cleaned, flags=re.IGNORECASE)
		cleaned = cleaned.strip().strip("`").strip()
		if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
			cleaned = cleaned[1:-1].strip()
		cleaned = cleaned.rstrip(",").strip()
		cleaned = re.sub(r"\s+", " ", cleaned).strip()
		return cleaned

	def _is_plausible_title(self, title: str) -> bool:
		"""用輕量規則判斷標題是否可用。"""
		if not title:
			return False
		if len(title) < 2 or len(title) > 120:
			return False
		if not re.search(r"[A-Za-z]", title):
			return False
		if title.startswith(("{", "}", "[", "]", "```")):
			return False
		return True

	def _extract_title_candidate(self, raw_title: str) -> Optional[str]:
		"""從模型回應中盡可能抽取可用標題（支援 JSON 與純文字回應）。"""
		if not raw_title:
			return None

		text = raw_title.strip()
		fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
		json_candidate = fence_match.group(1).strip() if fence_match else text

		for maybe_json in (json_candidate, text):
			try:
				data = json.loads(maybe_json)
			except Exception:
				continue

			if isinstance(data, dict):
				title_value = data.get("title")
				if isinstance(title_value, str):
					cleaned = self._clean_title_candidate(title_value)
					if self._is_plausible_title(cleaned):
						return cleaned
			elif isinstance(data, str):
				cleaned = self._clean_title_candidate(data)
				if self._is_plausible_title(cleaned):
					return cleaned

		for pattern in [
			r'"title"\s*:\s*"([^"]+)"',
			r"'title'\s*:\s*'([^']+)'",
			r'"title"\s*:\s*\'([^\']+)\'',
			r"'title'\s*:\s*\"([^\"]+)\"",
		]:
			match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
			if match:
				cleaned = self._clean_title_candidate(match.group(1))
				if self._is_plausible_title(cleaned):
					return cleaned

		for line in [ln.strip() for ln in text.splitlines() if ln.strip()]:
			if line.startswith("```"):
				continue
			line = re.sub(r"^\s*title\s*[:\-]\s*", "", line, flags=re.IGNORECASE)
			cleaned = self._clean_title_candidate(line)
			if self._is_plausible_title(cleaned):
				return cleaned

		return None

	def _finalize_story_root(self, raw_title: str) -> str:
		"""根據書名重新定位故事路徑，並回傳乾淨標題。"""
		title = self._extract_title(raw_title)
		relative = build_story_relative_path(self.profile, title)
		if relative != self.relative_path:
			current_log_path = self.paths["logs"] / "generation.log"
			self._reset_log_file_handler(None)
			try:
				new_root = relocate_story_root(self.story_root, self.output_root, relative)
			except FileExistsError:
				self.logger.warning("Target story path exists, keeping temporary folder: %s", relative)
				self._reset_log_file_handler(current_log_path)
			except (PermissionError, OSError) as exc:
				self.logger.warning("Failed to relocate story folder (%s), keeping temporary path", exc)
				self._reset_log_file_handler(current_log_path)
			else:
				self.story_root = new_root
				self.relative_path = relative
				self.file_manager.relocate(new_root)
				self.language_dir = self.file_manager.language_root
				self.paths = self.file_manager.paths
				new_log_path = self.paths["logs"] / "generation.log"
				self._reset_log_file_handler(new_log_path)
		self.story_title = title
		return title

	def _persist_profile(self) -> None:
		"""將 KG profile 與提示準則寫入 story_root。"""
		profile_path = self.paths["kg_profile"]
		write_json_or_raise(profile_path, self.profile.to_dict())
		guidelines = (self.effective_guidelines or "").strip()
		if guidelines:
			guideline_path = self.paths["guidelines"]
			write_text_or_raise(guideline_path, guidelines)
		self._persist_character_prompt_files()
		write_json_or_raise(self.paths["resource"] / "character_bible.json", self._build_character_bible())
		write_json_or_raise(self.paths["resource"] / "world_style_lock.json", self._build_world_style_lock())

	def _persist_character_prompt_files(self) -> None:
		"""Persist per-character prompt files for the image stage."""
		resource_root = self.paths["resource"]
		for name, prompt_text in self._build_character_prompt_texts().items():
			safe_name = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "character"
			write_text_or_raise(resource_root / f"character_{safe_name}.txt", prompt_text)

	def _build_character_prompt_texts(self) -> Dict[str, str]:
		payload = (self.inputs.kg_payload or {}).get("characters") or []
		result: Dict[str, str] = {}
		seen: Set[str] = set()
		category = (self.inputs.category or self.profile.category_label or "storybook").strip()
		theme = (self.inputs.theme or self.profile.theme_label or "").strip()
		for item in payload:
			label = ""
			role = ""
			appearance = ""
			description = ""
			outfit = ""
			if isinstance(item, str):
				label = re.sub(r"\s+", " ", item).strip()
			elif isinstance(item, dict):
				label = str(item.get("label") or item.get("name") or "").strip()
				role = str(item.get("role") or item.get("type") or "").strip()
				appearance = str(item.get("appearance") or "").strip()
				description = str(item.get("description") or "").strip()
				outfit = str(item.get("outfit") or "").strip()
			if not label:
				continue
			key = label.casefold()
			if key in seen:
				continue
			seen.add(key)
			bits = [label]
			for extra in (role, appearance, description, outfit):
				extra = re.sub(r"\s+", " ", extra).strip(" ,")
				if extra and extra.casefold() not in {part.casefold() for part in bits}:
					bits.append(extra)
			if category:
				bits.append(f"{category} picture-book character")
			if theme:
				bits.append(f"theme cue: {theme}")
			bits.append("consistent outfit colors, readable face, clear silhouette, expressive hands")
			result[label] = ", ".join(bits[:6])

		if result:
			return result

		return {
			name: f"{name}, storybook character, consistent outfit colors, readable face, clear silhouette, expressive hands"
			for name in self.primary_characters
		}

	def _story_character_records(self) -> List[Dict[str, Any]]:
		payload = (self.inputs.kg_payload or {}).get("characters") or []
		result: List[Dict[str, Any]] = []
		seen: Set[str] = set()
		for item in payload:
			record: Dict[str, Any] = {
				"name": "",
				"role": "",
				"appearance": "",
				"description": "",
				"outfit": "",
				"props": [],
			}
			if isinstance(item, str):
				record["name"] = re.sub(r"\([^)]*\)", "", re.sub(r"\s+", " ", item)).strip(" ,")
			elif isinstance(item, dict):
				record["name"] = re.sub(r"\([^)]*\)", "", str(item.get("label") or item.get("name") or "")).strip(" ,")
				record["role"] = str(item.get("role") or item.get("type") or "").strip()
				record["appearance"] = str(item.get("appearance") or "").strip()
				record["description"] = str(item.get("description") or "").strip()
				record["outfit"] = str(item.get("outfit") or "").strip()
				raw_props = item.get("props") or []
				if isinstance(raw_props, str):
					record["props"] = [re.sub(r"\s+", " ", raw_props).strip(" ,")]
				elif isinstance(raw_props, list):
					record["props"] = [
						re.sub(r"\s+", " ", str(prop or "")).strip(" ,")
						for prop in raw_props
						if str(prop or "").strip()
					]
			name = str(record.get("name") or "").strip()
			if not name:
				continue
			key = name.casefold()
			if key in seen:
				continue
			seen.add(key)
			result.append(record)
		if result:
			return result
		return [{"name": name, "role": "", "appearance": "", "description": "", "outfit": "", "props": []} for name in self.primary_characters]

	def _story_scene_anchors(self) -> List[str]:
		scenes = []
		payload = (self.inputs.kg_payload or {}).get("scenes") or []
		for item in payload:
			text = re.sub(r"\s+", " ", str(item or "")).strip(" ,.")
			if text and text not in scenes:
				scenes.append(text)
		return scenes[:6]

	def _extract_color_locks(self, *chunks: str) -> List[str]:
		color_vocab = (
			"red", "orange", "yellow", "green", "blue", "purple", "pink", "brown",
			"black", "white", "gray", "grey", "gold", "silver", "teal", "navy",
		)
		text = " ".join(re.sub(r"\s+", " ", str(chunk or "")).casefold() for chunk in chunks)
		return [color for color in color_vocab if re.search(rf"\b{re.escape(color)}\b", text)]

	def _build_character_bible(self) -> Dict[str, Any]:
		characters: List[Dict[str, Any]] = []
		for record in self._story_character_records():
			name = str(record.get("name") or "").strip()
			appearance = str(record.get("appearance") or "").strip()
			description = str(record.get("description") or "").strip()
			outfit = str(record.get("outfit") or "").strip()
			role = str(record.get("role") or "").strip()
			props = list(record.get("props") or [])
			color_lock = self._extract_color_locks(appearance, description, outfit)
			forbidden_drift: List[str] = []
			if appearance:
				forbidden_drift.append(f"different appearance from {name}'s canon")
			if outfit:
				forbidden_drift.append(f"different outfit from {name}'s canon")
			if color_lock:
				forbidden_drift.append(f"wrong outfit colors for {name}")
			characters.append(
				{
					"name": name,
					"age_look": "young child" if name in self.primary_characters[:2] else "supporting story character",
					"height_ratio": "child-sized" if name in self.primary_characters[:2] else "adult-sized",
					"hair": appearance or description,
					"face_shape": "readable round-friendly storybook face",
					"outfit_core": outfit or description,
					"color_lock": color_lock,
					"silhouette": outfit or appearance or "clean readable silhouette",
					"props": props,
					"expression_style": description or "clear child-readable expression",
					"role": role,
					"forbidden_drift": forbidden_drift,
				}
			)
		return {
			"version": "1.0",
			"story_title": self.story_title,
			"characters": characters,
			"readability_goal": "Stable, child-readable characters that stay recognizable across pages.",
		}

	def _build_world_style_lock(self) -> Dict[str, Any]:
		visual_frame = self.profile.layout.visual_frame.to_dict() if self.profile and self.profile.layout and self.profile.layout.visual_frame else {}
		depth_layers = dict(visual_frame.get("depth_layers") or {})
		return {
			"version": "1.0",
			"world_id": re.sub(r"[^a-z0-9]+", "_", f"{self.profile.category_label}_{self.profile.theme_label}".casefold()).strip("_") or "storybook_world",
			"style_lock": self.image_style_lock,
			"render_principle": "Stable, readable picture-book storytelling frames instead of showcase art.",
			"camera_language": {
				"far": "full environment view with one clear story beat",
				"mid": "group action focus with readable gesture hierarchy",
				"close": "emotion and hand detail focus with simple composition",
			},
			"lighting_language": {
				"bright": "clear, welcoming, easy for children to read at a glance",
				"dim": "gentle magical mood while keeping the action readable",
			},
			"space_rules": {
				"foreground": depth_layers.get("foreground") or "nearest interactive prop or gesture cue",
				"midground": depth_layers.get("midground") or "main character action zone",
				"background": depth_layers.get("background") or "setting anchor that keeps the world recognizable",
			},
			"story_goal": "Each image should communicate the current page's story state in one glance.",
			"scene_anchors": self._story_scene_anchors(),
			"forbidden_styles": [
				"photorealism",
				"3d render",
				"comic panel",
				"cinematic lens flare",
				"text overlay",
			],
		}

	def _page_file(self, idx: int) -> Path:
		"""依頁碼回傳單頁文字檔路徑。"""
		return self.file_manager.page_file(idx)

	def _derivation_path(self, step: str, idx: int) -> Path:
		"""給定步驟/頁碼，取得對應推導檔路徑。"""
		return self.file_manager.derivation_path(step, idx)

	def _aggregate_path(self, step: str) -> Path:
		"""回傳合併紀錄檔案路徑（narration/dialogue/scene/pose）。"""
		return self.file_manager.aggregate_path(step)

	def _format_aggregate_line(self, step: str, idx: int, text: str) -> str:
		"""產生合併檔案中每頁的描述格式。"""
		label = "Page" if step in {"narration", "dialogue", "scene", "pose"} else step
		return f"{label} {idx}: {text.strip()}"
	
	def _validate_derivation_pages(self, step: str, outputs: List[str], expected_count: int) -> None:
		"""驗證衍生步驟生成的頁數是否與預期一致。"""
		actual_count = len(outputs)
		if actual_count != expected_count:
			# [FIX] Only raise error if difference is significant (more than 2 pages)
			# Allow minor mismatches due to inheritance/copying issues
			diff = abs(actual_count - expected_count)
			if diff > 2:
				self.logger.error(
					"⚠️ [Step %s] 頁數不一致：預期 %s 頁，實際生成 %s 頁！",
					step, expected_count, actual_count
				)
				raise ValueError(
					f"[Step {step}] Page count mismatch: expected {expected_count}, got {actual_count}"
				)
			else:
				self.logger.warning(
					"⚠️ [Step %s] 頁數略有差異：預期 %s 頁，實際生成 %s 頁（允許範圍內）",
					step, expected_count, actual_count
				)
		self.logger.info("✓ [Step %s] 完成：%s 頁", step, actual_count)

	def run(self) -> Dict[str, Any]:
		"""
		執行整體故事生成流程並回傳 story_meta 結構。
		包含多分支 (Multi-Branch) 的執行邏輯：
		1. 生成大綱 (Outline) 與標題 (Title)
		2. 生成主線內容 (Trunk) - 通常是第 1 頁到決策點
		3. 根據 Profile 設定生成各個支線 (Branches)
		4. 迭代所有分支生成衍生內容 (Narration, Dialogue, Scene, Pose)
		5. 產生 Meta 與 Cover (基於主線或 Canonical Branch)
		"""
		self.start_time = time.perf_counter()
		self.logger.info("Starting pipeline for %s", self.story_id)
		# Recompute major step total based on branch count
		branch_count = self.profile.layout.branch_count if self.profile and self.profile.layout else 0
		branch_total = max(branch_count, 1)
		# outline + title + story + (narration/dialogue/scene/pose per branch) + cover + meta
		self._major_step_total = 3 + (branch_total * 4) + 2
		self._major_step_index = 0
		self._log_major_step("outline")
		outline_candidate_count = max(1, int(getattr(self.options, "outline_candidates", 1) or 1))
		outline = self._rank_step_candidates(
			"outline",
			{"kg_enabled": self.options.kg_enabled},
			self.paths["outline"],
			candidate_count=outline_candidate_count,
		)
		self.logger.info(
			"Stage 0.5 outline selection completed with %d candidate(s)",
			outline_candidate_count,
		)
		self.logger.info("Outline selection is now handled by candidate scoring and rerank.")

		# Extract dynamic turning point from outline
		detected_turning_point = self._extract_turning_point_from_outline(outline)
		self.base_context["detected_turning_point"] = detected_turning_point
		self.base_context["outline"] = outline
		
		# Update layout.decision_page to use detected turning point
		if self.profile and self.profile.layout and detected_turning_point > 0:
			if self.profile.layout.branch_count > 0:
				# Validate range
				layout_config = self.kg.get_layout_config(self.profile.age_value) if self.kg else {}
				turning_point_range = layout_config.get("turning_point_range", [detected_turning_point, detected_turning_point])
				if turning_point_range[0] <= detected_turning_point <= turning_point_range[1]:
					self.logger.info(f"Updating layout decision_page from {self.profile.layout.decision_page} to {detected_turning_point}")
					# Update the layout object
					self.profile.layout.decision_page = detected_turning_point
					# Recalculate trunk_pages and branch_pages
					self.profile.layout.trunk_pages = range(1, detected_turning_point + 1)
					self.profile.layout.branch_pages = range(detected_turning_point + 1, self.profile.layout.total_pages + 1)
				else:
					self.logger.warning(f"Detected turning point {detected_turning_point} outside valid range {turning_point_range}, keeping default")
		
		self.logger.info("Outline generated with turning point at Page %d", detected_turning_point)
		
		self._log_major_step("title")
		title_candidate_count = max(1, int(getattr(self.options, "title_candidates", 1) or 1))
		raw_title = self._rank_step_candidates(
			"title",
			{
				"outline": outline, 
				"story_outline": outline,
				"age": self.inputs.age_group or self.profile.age_label, # Provide age explicit for title prompt
				"theme": self.profile.theme_label,
				"main_category": self.profile.category_label,
				"sub_category": self.profile.subcategory_label,
				"character1": self.primary_characters[0] if self.primary_characters else "Character",
				"character2": self.primary_characters[1] if len(self.primary_characters) > 1 else "",
				"character3": self.primary_characters[2] if len(self.primary_characters) > 2 else "",
			},
			self.paths["title"],
			candidate_count=title_candidate_count,
		)
		title = self._finalize_story_root(raw_title)
		self.base_context["story_title"] = title
		self.base_context["branch_context"] = "" # Default for Trunk
		self._log_major_step("story")

		# --- Rigid 3-Stage Orchestration (Trunk -> Branch Loop -> Ending) ---
		layout = self.profile.layout
		if not layout:
			raise ValueError("CRITICAL: BranchLayout missing in profile. Cannot proceed.")

		# [FIX] Initialize main_pages safely so it is available for meta building later.
		# But "main_pages" is a legacy concept. We should compile from canonical (option_1) for story_meta?
		# Or story_meta should just point to option_1?
		# Let's keep main_pages as option_1's content for legacy compatibility if needed.
		main_pages = [] 
		
		self.logger.info(f"Layout Rigid Plan: Trunk={layout.trunk_pages}, Decision={layout.decision_page}, Branches={layout.branch_count}")
		
		# --- Stage 1: Trunk Generation (Canonical: option_1) ---
		# We generate the shared trunk IN option_1 directly.
		self.logger.info(">>> Stage 1: Generating Trunk & Decision Page (Canonical: option_1)...")
		
		canonical_bid = "option_1"
		# Explicitly create option_1 (NO "main" parent, it is the root)
		if canonical_bid not in self.branches:
			# Parent ID empty means Root
			self.create_branch(canonical_bid, 0, parent_id=None) 
		self.switch_branch(canonical_bid)
		
		decision_page_num = layout.decision_page
		# If Linear (decision=0), target is total_pages
		trunk_target = decision_page_num if layout.branch_count > 0 else layout.total_pages
		
		# Generate Trunk
		trunk_out, trunk_text = self._generate_story_pages(
			outline, 
			title, 
			start_page_override=1,
			end_page_limit=trunk_target
		)
		if trunk_out:
			main_pages.extend(trunk_out) # Capture canonical pages
			
		# Parse Decision (if branching)
		# [Refactor] No more parsing decision page text. 
		# We use the strict archetypes from layout.branch_slots.
		# But for the "Decision Page" itself, we still generated it freely?
		# ideally, we should have injected the PRE-SELECTED options into the prompt for the decision page too.
		# (Future Improvement: Inject options into decision page generation prompt)
		
		# For now, we trust the profile has the slots.
		branch_slots = layout.branch_slots
		if layout.branch_count > 0 and len(branch_slots) < layout.branch_count:
			raise ValueError("Branch slots missing or insufficient. KG must provide complete branch slots.")
			
		self.logger.info(f"Using Strict Branch Slots: {[s['label'] for s in branch_slots]}")
		
		generated_branches_ids = []
		
		# [Branch Span Control] Allow configurable short branches with converging ending
		age_value = self.profile.age_value if self.profile else 0
		layout_config = self.kg.get_layout_config(age_value) if self.kg else {}
		branch_span = layout_config.get("branch_span_pages")
		ending_span = layout_config.get("ending_span_pages")
		converge_ending = bool(layout_config.get("converge_ending", False))
		branch_end_page = layout.total_pages
		ending_start = None
		ending_end = None
		if layout.branch_count > 0 and converge_ending and branch_span:
			# Log to verify values are being set
			self.logger.info(f"[Convergence] branch_span={branch_span}, ending_span={ending_span}, converge_ending={converge_ending}")
			branch_end_page = min(decision_page_num + int(branch_span), layout.total_pages)
			ending_start = branch_end_page + 1
			if ending_start <= layout.total_pages:
				if ending_span:
					ending_end = min(ending_start + int(ending_span) - 1, layout.total_pages)
				else:
					ending_end = layout.total_pages
				self.logger.info(f"[Convergence] branch_end_page={branch_end_page}, ending_start={ending_start}, ending_end={ending_end}")
			else:
				ending_start = None
				ending_end = None
				converge_ending = False  # Disable if no room for ending pages
		elif layout.branch_count > 0 and not branch_span:
			self.logger.warning(f"[Convergence] branch_span_pages not configured for age {age_value}, convergence disabled")
			converge_ending = False
		
		# Convergence anchor (prefer the last actionable event; fallback to final event)
		outline_events = self._extract_outline_events(outline)
		if len(outline_events) >= 2:
			convergence_anchor = outline_events[-2]
		else:
			convergence_anchor = outline_events[-1] if outline_events else "a gentle resolution"
		self.logger.info(f"[Convergence] Anchor Event: '{convergence_anchor}'")
		self.base_context["converge_ending"] = converge_ending
		self.base_context["branch_end_page"] = branch_end_page
		self.base_context["convergence_anchor"] = convergence_anchor
		self.base_context["ending_start"] = ending_start
		self.base_context["ending_end"] = ending_end
		
		# --- Stage 2: Branch Generation Loop (option_1..N) ---
		# Loop includes Option 1 (which continues from Trunk) and Option 2+ (which fork)
		if layout.branch_count <= 0:
			# 線性故事 (Linear Story)：無需重新生成頁面，僅完成 Metadata。
			bid = canonical_bid
			generated_branches_ids.append(bid)
			opt_label = "Linear Path"
			opt_desc = "Follow the story."
			branch_dir = self.file_manager.language_root / "branches" / bid
			if not branch_dir.exists():
				branch_dir.mkdir(parents=True, exist_ok=True)
			meta_payload = {
				"layout_id": layout.layout_id,
				"branch_id": bid,
				"option_text": opt_label,
				"option_desc": opt_desc,
				"meaning_tag": opt_label,
				"branch_trait": opt_label,
				"branch_trait_desc": opt_desc,
				"decision_page": decision_page_num,
				"total_pages": layout.total_pages
			}
			write_json_or_raise(branch_dir / "metadata.json", meta_payload)
			self._compile_full_story(branch_dir, layout.total_pages)
		else:
			loop_range = range(1, layout.branch_count + 1)
		
		if layout.branch_count > 0:
			for i in loop_range:
				bid = f"option_{i}"
				generated_branches_ids.append(bid)
				
				# 設定當前分支 (Setup Branch)
				if i == 1:
					# Option 1 已經存在且包含 Trunk
					# 確保切換過去
					self.switch_branch(bid)
				else:
					# Option 2+: 建立並 Fork
					# 從 Canonical (Option 1) 複製 Trunk (1..Decision)
					if bid not in self.branches:
						self.create_branch(bid, decision_page_num, parent_id=canonical_bid)
					self.switch_branch(bid)
					
					# 物理複製檔案 (Physical Copy) - 確保每個分支目錄是獨立完整的，便於後續驗證與處理
					self._copy_branch_state(canonical_bid, bid, decision_page_num)

				# 準備分支特定的 Prompt Context (Strict Authority)
				opt_label = "Linear Path"
				opt_desc = "Follow the story."
				slot: Dict[str, Any] = {}
				
				# 嚴格映射: i=1 -> index 0
				if i <= len(branch_slots):
					slot = branch_slots[i-1]
					opt_label = slot.get('label', f"Option {i}")
					opt_desc = slot.get('desc', "A unique path")
				else:
					opt_label = f"Option {i}"
					opt_desc = "A generic path"
					
				# 注入嚴格的分支意圖 Context (The "State-Driven" Core)
				sensory_guide = slot.get('sensory_guide', '')
				emotional_arc = slot.get('emotional_arc', '')
				resolution_model = slot.get('resolution_model', '')
				
				self.base_context["branch_context"] = (
					f"Branch intent: '{opt_label}' - {opt_desc}.\n"
					f"ARCHETYPE GUIDES (Strictly Follow):\n"
					f"- Sensory Focus: {sensory_guide}\n"
					f"- Emotional Arc: {emotional_arc}\n"
					f"- Resolution Style: {resolution_model}\n"
					f"STRICTLY follow this archetype. Do NOT drift into other branches.\n"
					f"Focus on the consequences of this path without naming the trait explicitly."
				)
				# 供 strict context 和 state snapshots 使用的 Branch trait
				self.base_context["branch_type"] = opt_label
				self.base_context["branch_desc"] = opt_desc
				# 同時注入 'smart_context' 供 derivatives 使用
				self.base_context["smart_context"] = (
					f"Branch intent: {opt_label} ({opt_desc}). "
					f"Sensory: {sensory_guide}. Emotion: {emotional_arc}."
				)
				
				# 生成剩餘頁面 (Decision+1 .. Branch End)
				branch_start = decision_page_num + 1
				
				if branch_start <= branch_end_page:
					self.logger.info(f"    Generating {bid} Content ({branch_start}-{branch_end_page})...")
					# 啟用 "Ending Mode" 
					self.base_context["is_ending"] = True 
					
					branch_out, _ = self._generate_story_pages(
						outline, 
						title, 
						start_page_override=branch_start, 
						end_page_limit=branch_end_page
					)
					self.base_context.pop("is_ending", None)
					
					# For Option 1, append to main_pages collector
					if i == 1 and branch_out:
						main_pages.extend(branch_out)
				
				# Generate converging ending per branch (same event, different phrasing)
				if converge_ending and ending_start and ending_end and ending_start <= ending_end:
					self.logger.info(f"    Generating converging ending ({ending_start}-{ending_end}) in {bid}...")
					self.base_context["is_ending"] = True
					self.base_context["is_converging_ending"] = True
					ending_out, _ = self._generate_story_pages(
						outline,
						title,
						start_page_override=ending_start,
						end_page_limit=ending_end
					)
					self.base_context.pop("is_converging_ending", None)
					self.base_context.pop("is_ending", None)
					if i == 1 and ending_out:
						main_pages.extend(ending_out)

				# --- Finalize Check: Metadata Only (No in-text Trait markers) ---
				# Write Metadata (Strictly in this branch's folder)
				branch_dir = self.file_manager.language_root / "branches" / bid
				# Ensure dir exists (it should if pages were written)
				if not branch_dir.exists():
					branch_dir.mkdir(parents=True, exist_ok=True)
					
				meta_payload = {
					"layout_id": layout.layout_id,
					"branch_id": bid,
					"option_text": opt_label, # Use our strict label
					"option_desc": opt_desc,  # Save description too
					"meaning_tag": opt_label,
					"branch_trait": opt_label,
					"branch_trait_desc": opt_desc,
					"decision_page": decision_page_num,
					"total_pages": layout.total_pages
				}
				write_json_or_raise(branch_dir / "metadata.json", meta_payload)

				# Also Ensure full_story.txt is compiled here
				self._compile_full_story(branch_dir, layout.total_pages)

		# --- Asset Generation ---
		# --- Asset Generation ---
		self._generate_assets(generated_branches_ids, outline, title)

		self._log_major_step("meta")
		meta_out = self._build_meta(outline, title, generated_branches_ids)
		return meta_out

	# --- Helper Methods for Strict Branching ---

	def _current_branch_value_focus(self) -> str:
		"""Resolve a neutral value-focus identifier for the current branch."""
		return current_branch_value_focus(
			profile=self.profile,
			current_branch_id=self.current_branch_id,
			fallback=self.base_context.get("branch_type", ""),
		)

	def _build_page_structure(self, idx: int) -> Dict[str, Any]:
		"""Builds explicit structural metadata for the page from KG configuration."""
		age_value = self.profile.age_value if self.profile else 5
		
		# Get layout configuration from KG
		layout_config = self.kg.get_layout_config(age_value) if self.kg else {}
		interaction_rules = self.kg.get_interaction_rules(age_value) if self.kg else {}
		
		# Single turning point design
		page_function = "NARRATIVE"
		branch_trigger = False
		allowed_actions: List[str] = []
		interaction_intent = "advance the narrative"
		is_branch_start = False
		
		# Use detected turning point from outline, fallback to config
		turning_point = self.base_context.get("detected_turning_point") or layout_config.get("turning_point_page", 0)
		total_pages = layout_config.get("total_pages", 8)
		has_interaction = interaction_rules.get("has_interaction", False)
		
		# Validate turning point is within acceptable range
		turning_point_range = layout_config.get("turning_point_range", [turning_point, turning_point])
		if turning_point < turning_point_range[0] or turning_point > turning_point_range[1]:
			self.logger.warning(f"Turning point {turning_point} outside valid range {turning_point_range}, using config default")
			turning_point = layout_config.get("turning_point_page", 4)
		
		if has_interaction and turning_point > 0:
			if idx == turning_point:
				# Turning point page
				page_function = "INTERACTION"
				branch_trigger = True
				allowed_actions = ["move_object", "gesture", "touch"]
				interaction_intent = "present turning point where character action matters"
			elif idx == (turning_point + 1):
				# First page after turning point
				is_branch_start = True
				interaction_intent = "reveal immediate consequence of action"
		
		# Optional: Mark final page as reflection
		if idx == total_pages:
			page_function = "REFLECTION"
			interaction_intent = "provide gentle closure and reflection"

		# Legacy layout support for decision_slots and value_focus
		layout = self.profile.layout if self.profile else None
		decision_slots: List[Dict[str, str]] = []
		if layout and layout.branch_slots:
			for i, slot in enumerate(layout.branch_slots, start=1):
				decision_slots.append({
					"id": f"option_{i}",
					"label": slot.get("label", f"Option {i}"),
					"desc": slot.get("desc", ""),
					"type": slot.get("type", ""),
				})
		
		value_focus = ""
		if layout and layout.branch_count > 0 and layout.decision_page > 0 and idx > layout.decision_page:
			value_focus = self._current_branch_value_focus()
		
		branch_logic = "action_result" if branch_trigger or page_function == "DIVERGENCE" else ""
		
		return {
			"page_num": idx,
			"page_function": page_function,
			"allowed_actions": allowed_actions,
			"interaction_intent": interaction_intent,
			"branch_trigger": branch_trigger,
			"branch_logic": branch_logic,
			"value_focus": value_focus,
			"state_delta": {
				"character_attitude": "",
				"world_condition": "",
			},
			"system_assumptions": self.kg.SYSTEM_CORE_ASSUMPTIONS if self.kg else "",
			"branch_id": self.current_branch_id,
			"branch_trait": self.base_context.get("branch_type", ""),
			"branch_trait_desc": self.base_context.get("branch_desc", ""),
			"decision_page": turning_point,
			"total_pages": self._total_pages(),
			"is_branch_start": is_branch_start,
			"decision_options": decision_slots,
		}

	def _is_key_story_page(self, idx: int, page_structure: Dict[str, Any]) -> bool:
		total_pages = self._total_pages()
		if idx <= 1:
			return True
		if idx >= total_pages:
			return True
		if idx == max(1, total_pages - 1):
			return True
		if page_structure.get("branch_trigger"):
			return True
		if bool(page_structure.get("is_branch_start")):
			return True
		if str(page_structure.get("page_function") or "").upper() == "REFLECTION":
			return True
		return False

	def _score_story_page_candidate(
		self,
		text: str,
		*,
		idx: int,
		page_structure: Dict[str, Any],
		history: Optional[List[str]] = None,
	) -> Dict[str, Any]:
		score = 62.0
		issues: List[str] = []
		word_count = len(re.findall(r"[A-Za-z']+|[\u4e00-\u9fff]", text or ""))
		min_words, max_words = self._target_word_bounds(idx)
		risk = self._assess_generation_quality_risks("story_write", text)
		signals = dict(risk.get("signals") or {})

		if min_words <= word_count <= max_words:
			score += 16.0
		elif word_count < min_words:
			score -= min(22.0, (min_words - word_count) * 0.45)
			issues.append("too_short")
		else:
			score -= min(18.0, (word_count - max_words) * 0.25)
			issues.append("too_long")

		if signals.get("glitch"):
			score -= 25.0
			issues.append("text_glitch")
		if float(signals.get("duplicate_sentence_ratio", 0.0) or 0.0) >= 0.18:
			score -= min(20.0, float(signals.get("duplicate_sentence_ratio", 0.0)) * 70.0)
			issues.append("sentence_repetition")
		if bool(signals.get("repeated_phrase")):
			score -= 12.0
			issues.append("phrase_repetition")
		if int(signals.get("coref_ambiguity_score", 0) or 0) >= 2:
			score -= 10.0
			issues.append("coref_ambiguity")
		if float(signals.get("avg_sentence_words", 0.0) or 0.0) >= 24.0:
			score -= 8.0
			issues.append("dense_sentence")

		if history and self._check_repetition(text, history, threshold=0.74):
			score -= 18.0
			issues.append("too_similar_to_recent_page")

		if page_structure.get("branch_trigger"):
			if "Option 1" in text or "Option 2" in text:
				score -= 25.0
				issues.append("explicit_option_list")
			else:
				score += 4.0

		if idx == 1:
			lowered_text = (text or "").casefold()
			name_hits = sum(1 for name in self.primary_characters[:2] if name and name.casefold() in lowered_text)
			if name_hits == 0:
				score -= 8.0
				issues.append("missing_primary_character")
			else:
				score += min(6.0, name_hits * 3.0)

		if idx >= self._total_pages() - 1 and text and text.rstrip()[-1] not in ".!?。！？\"'”":
			score -= 5.0
			issues.append("weak_closure")

		return {
			"score": round(max(0.0, min(100.0, score)), 2),
			"issues": issues[:8],
			"signals": signals,
			"word_count": word_count,
		}

	def _structure_path(self, idx: int) -> Path:
		return structure_path(self.paths["story"], idx)

	def _write_page_structure(self, idx: int, structure: Dict[str, Any]) -> None:
		"""Persist page structure so downstream modules don't parse text."""
		write_page_structure(self.paths["story"], idx, structure)

	def _read_page_structure(self, idx: int) -> Optional[Dict[str, Any]]:
		"""Read structural metadata for a page if available."""
		return read_page_structure(self.paths["story"], idx)

	def _read_state_snapshot(self, idx: int) -> Dict[str, Any]:
		state_path = self.paths["story"].parent / f"page_{idx}_state.json"
		if not state_path.exists():
			return {}
		try:
			payload = json.loads(state_path.read_text(encoding="utf-8"))
		except Exception:
			return {}
		return payload if isinstance(payload, dict) else {}

	def _infer_scene_stage(self, idx: int, page_structure: Dict[str, Any]) -> str:
		page_function = str(page_structure.get("page_function") or "").upper()
		if page_structure.get("branch_trigger") or page_function == "INTERACTION":
			return "action"
		if bool(page_structure.get("is_branch_start")):
			return "action"
		total_pages = int(page_structure.get("total_pages") or self._total_pages() or 1)
		if page_function == "REFLECTION" or idx >= total_pages:
			return "result"
		decision_page = int(page_structure.get("decision_page") or 0)
		if idx <= 2:
			return "setup"
		if decision_page and idx < decision_page:
			return "setup"
		if decision_page and idx > decision_page:
			return "result" if idx >= max(1, total_pages - 1) else "action"
		return "result" if idx >= max(1, total_pages - 1) else "action"

	def _infer_scene_shot(self, idx: int, page_structure: Dict[str, Any], scene_stage: str) -> str:
		page_function = str(page_structure.get("page_function") or "").upper()
		total_pages = int(page_structure.get("total_pages") or self._total_pages() or 1)
		if idx == 1:
			return "far"
		if page_function == "REFLECTION" or idx >= total_pages:
			return "close"
		if page_structure.get("branch_trigger") or bool(page_structure.get("is_branch_start")):
			return "mid"
		if scene_stage == "setup" and idx <= 2:
			return "far"
		if idx >= max(2, total_pages - 1):
			return "mid"
		return "mid"

	def _infer_scene_lighting(self, *chunks: Any) -> str:
		text = " ".join(re.sub(r"\s+", " ", str(chunk or "")).strip() for chunk in chunks if chunk).casefold()
		dim_markers = (
			"night", "moon", "star", "dark", "dim", "shadow", "shadows", "lantern",
			"cave", "storm", "rain", "mist", "fog", "dusk", "evening", "midnight",
		)
		bright_markers = (
			"day", "daylight", "morning", "sun", "sunny", "sunlight", "bright",
			"golden", "warm light", "blue sky", "garden", "backyard", "picnic",
		)
		if any(marker in text for marker in dim_markers):
			return "dim"
		if any(marker in text for marker in bright_markers):
			return "bright"
		return "bright"

	def _page_required_characters(self, page_text: str) -> List[str]:
		lowered = f" {(page_text or '').casefold()} "
		required = []
		for record in self._story_character_records():
			name = str(record.get("name") or "").strip()
			if name and f" {name.casefold()} " in lowered and name not in required:
				required.append(name)
		if required:
			return required
		if self.primary_characters:
			return [self.primary_characters[0]]
		return []

	def _infer_scene_focus_subject(self, required_characters: Sequence[str], page_text: str) -> str:
		if len(required_characters) >= 2:
			return "pair"
		if len(required_characters) == 1:
			return "character"
		object_markers = ("lantern", "key", "map", "book", "box", "bridge", "door", "locket", "boat")
		lowered = f" {(page_text or '').casefold()} "
		if any(marker in lowered for marker in object_markers):
			return "object"
		return "environment"

	def _infer_scene_motion_level(self, scene_stage: str, page_text: str) -> str:
		lowered = f" {(page_text or '').casefold()} "
		active_markers = (
			" run", " running", " jump", " jumping", " reach", " reaching", " chase",
			" climb", " climbing", " pull", " pulling", " push", " pushing",
			" guide", " guiding", " follow", " following", " lead", " leading",
			" open", " opening", " race", " racing", " dash", " dashing",
		)
		if any(marker in lowered for marker in active_markers):
			return "active"
		if scene_stage == "action":
			return "active"
		if scene_stage == "result":
			return "still"
		return "light"

	def _infer_scene_emotion_density(self, state_snapshot: Dict[str, Any], page_text: str) -> str:
		text = " ".join(
			[
				str(state_snapshot.get("character_emotion") or ""),
				str(state_snapshot.get("world_constraint") or ""),
				str(state_snapshot.get("world_condition") or ""),
				str(page_text or ""),
			]
		).casefold()
		if any(marker in text for marker in ("wonder", "curious", "magic", "sparkle", "twinkle", "glow")):
			return "wonder"
		if any(marker in text for marker in ("worried", "nervous", "cautious", "afraid", "tense", "careful")):
			return "tense"
		if any(marker in text for marker in ("happy", "warm", "relief", "hug", "smile", "gentle", "cozy")):
			return "warm"
		return "calm"

	def _infer_scene_composition_balance(self, scene_shot: str, scene_stage: str, required_characters: Sequence[str]) -> str:
		if scene_shot == "close" or scene_stage == "result":
			return "centered"
		if len(required_characters) >= 2 or scene_stage == "action":
			return "layered"
		return "centered"

	def _infer_world_anchor(self, page_text: str, state_snapshot: Dict[str, Any]) -> str:
		anchors = self._story_scene_anchors()
		page_words = set(re.findall(r"[A-Za-z']+", str(page_text or "").casefold()))
		best_anchor = ""
		best_score = 0
		for anchor in anchors:
			anchor_words = {word for word in re.findall(r"[A-Za-z']+", anchor.casefold()) if len(word) > 2}
			score = len(page_words & anchor_words)
			if score > best_score:
				best_anchor = anchor
				best_score = score
		if best_anchor:
			return best_anchor
		world_condition = re.sub(r"\s+", " ", str(state_snapshot.get("world_condition") or "")).strip(" ,.")
		if world_condition:
			return world_condition
		return anchors[0] if anchors else f"{self.profile.category_label} story setting"

	def _build_visual_prompt_context(
		self,
		idx: int,
		page_text: str,
		page_structure: Dict[str, Any],
		state_snapshot: Optional[Dict[str, Any]] = None,
	) -> Dict[str, Any]:
		state = state_snapshot or {}
		scene_stage = self._infer_scene_stage(idx, page_structure)
		scene_shot = self._infer_scene_shot(idx, page_structure, scene_stage)
		scene_lighting = self._infer_scene_lighting(
			page_text,
			state.get("world_condition"),
			state.get("world_constraint"),
			self.inputs.theme,
			self.inputs.category,
		)
		required_characters = self._page_required_characters(page_text)
		scene_focus_subject = self._infer_scene_focus_subject(required_characters, page_text)
		scene_motion_level = self._infer_scene_motion_level(scene_stage, page_text)
		scene_emotion_density = self._infer_scene_emotion_density(state, page_text)
		scene_composition_balance = self._infer_scene_composition_balance(scene_shot, scene_stage, required_characters)
		world_anchor = self._infer_world_anchor(page_text, state)
		stage_boundary = {
			"setup": "keep one clear introductory beat with uncluttered staging",
			"action": "keep one decisive beat with readable motion and focus",
			"result": "keep one resolved beat with calm readable aftermath",
		}.get(scene_stage, "keep one clear beat with uncluttered staging")
		viewpoint = "eye-level picture-book framing" if scene_shot != "close" else "close picture-book framing focused on faces and hands"
		return {
			"scene_stage": scene_stage,
			"scene_shot": scene_shot,
			"scene_lighting": scene_lighting,
			"scene_focus_subject": scene_focus_subject,
			"scene_motion_level": scene_motion_level,
			"scene_emotion_density": scene_emotion_density,
			"scene_composition_balance": scene_composition_balance,
			"world_anchor": world_anchor,
			"visual_viewpoint": viewpoint,
			"visual_stage_boundary": stage_boundary,
			"visual_foreground": "lead prop, hands, path edge, or texture cue that introduces the scene",
			"visual_midground": "main characters and the central action or pose",
			"visual_background": "setting, light source, and depth cues that support the mood",
			"story_readability_goal": "one clear child-readable story moment, not a showcase illustration",
			"state_snapshot": json.dumps(state, ensure_ascii=False) if state else "{}",
			"character_goal": str(state.get("character_goal") or ""),
			"character_emotion": str(state.get("character_emotion") or ""),
			"world_constraint": str(state.get("world_constraint") or ""),
			"world_condition": str(state.get("world_condition") or ""),
		}

	def _primary_character_for_page(self, page_text: str) -> str:
		lowered = f" {(page_text or '').casefold()} "
		for name in self.primary_characters:
			if name and f" {name.casefold()} " in lowered:
				return name
		return self.primary_characters[0] if self.primary_characters else "Friend"

	def _derive_scene_core(self, scene_text: str, page_text: str) -> str:
		candidate = re.sub(r"\s+", " ", str(scene_text or "").strip()).strip(" .")
		if candidate:
			first_clause = candidate.split(",")[0].strip()
			if len(first_clause.split()) >= 5:
				return first_clause
			return candidate
		page_line = re.sub(r"\s+", " ", str(page_text or "").strip()).strip(" .")
		return " ".join(page_line.split()[:18]).strip()

	def _extract_scene_layer_phrase(self, scene_text: str, layer: str) -> str:
		patterns = (
			rf"([^,.]+?)\s+(?:in the|at the)\s+{layer}\b",
			rf"{layer}\s*:\s*([^,.]+)",
			rf"([^,.]+?)\s+{layer}\b",
		)
		for pattern in patterns:
			match = re.search(pattern, str(scene_text or ""), flags=re.IGNORECASE)
			if match:
				return re.sub(r"\s+", " ", match.group(1)).strip(" ,.")
		return ""

	def _canonical_asset_id(self, value: str, fallback: str = "asset") -> str:
		token = re.sub(r"[^a-z0-9]+", "_", str(value or "").casefold()).strip("_")
		return token or fallback

	def _infer_pose_id(self, pose_text: str, page_text: str, stage: str) -> str:
		text = f" {pose_text} {page_text} ".casefold()
		mapping = (
			("hold", (" hold", " holding", " carry", " carrying", " hug", " hugging")),
			("reach", (" reach", " reaching", " point", " pointing", " touch", " touching", " open", " opening", " pull", " pulling", " push", " pushing")),
			("walk", (" walk", " walking", " step", " stepping", " run", " running", " cross", " crossing", " follow", " following", " guide", " guiding", " lead", " leading", " climb", " climbing")),
			("surprised", (" surprise", " surprised", " startled", " gasp", " amazed", " shock")),
			("joyful", (" joyful", " joy", " smile", " smiling", " laugh", " laughing", " cheer", " cheering", " dance", " dancing", " celebrate")),
			("sad", (" sad", " crying", " cry", " tear", " tears", " worried", " worry", " lonely")),
		)
		for pose_id, markers in mapping:
			if any(marker in text for marker in markers):
				return pose_id
		return "neutral" if stage == "setup" else "walk" if stage == "action" else "joyful"

	def _infer_facing(self, pose_text: str, page_text: str, index: int, total: int) -> str:
		text = f" {pose_text} {page_text} ".casefold()
		if any(marker in text for marker in (" facing left", " looking left", " turns left", " turned left")):
			return "left_3q"
		if any(marker in text for marker in (" facing right", " looking right", " turns right", " turned right")):
			return "right_3q"
		if total <= 1:
			return "front"
		return "left_3q" if index == 0 else "right_3q" if index == total - 1 else "front"

	def _character_slot(self, index: int, total: int, focus_subject: str) -> str:
		if total <= 1:
			return "center" if focus_subject in {"character", "pair"} else "center_left"
		if total == 2:
			return "left" if index == 0 else "right"
		return ("left", "center", "right")[min(index, 2)]

	def _character_scale_hint(self, shot: str) -> str:
		return {
			"far": "small",
			"mid": "medium",
			"close": "large",
		}.get(str(shot or "").strip().lower(), "medium")

	def _collect_prop_candidates(
		self,
		page_text: str,
		page_plan: Dict[str, Any],
		required_characters: Sequence[str],
	) -> List[str]:
		combined = " ".join(
			[
				str(page_text or ""),
				str(page_plan.get("scene_core") or ""),
				str(page_plan.get("scene_layout") or ""),
				" ".join(str(value or "") for value in (page_plan.get("continuity_keys") or {}).values()),
			]
		).casefold()
		props: List[str] = []
		for record in self._story_character_records():
			name = str(record.get("name") or "").strip()
			if name not in required_characters:
				continue
			for raw_prop in record.get("props") or []:
				label = re.sub(r"\s+", " ", str(raw_prop or "")).strip(" ,.")
				if label and label.casefold() not in {item.casefold() for item in props}:
					props.append(label)
		vocabulary = (
			"lantern",
			"key",
			"map",
			"locket",
			"book",
			"letter",
			"stone",
			"gem",
			"backpack",
			"umbrella",
			"flower",
			"ticket",
			"toy",
			"boat",
			"rope",
			"star",
		)
		for term in vocabulary:
			if re.search(rf"\b{re.escape(term)}s?\b", combined) and term not in {item.casefold() for item in props}:
				props.append(term)
		return props[:4]

	def _collect_midground_objects(
		self,
		page_plan: Dict[str, Any],
		page_text: str,
		world_anchor: str,
	) -> List[Dict[str, Any]]:
		phrases: List[str] = []
		for key in ("midground_subjects", "background_subjects"):
			for item in page_plan.get(key) or []:
				text = re.sub(r"\s+", " ", str(item or "")).strip(" ,.")
				if text:
					phrases.append(text)
		if world_anchor:
			phrases.append(world_anchor)
		text = f" {page_text} {' '.join(phrases)} ".casefold()
		keywords = (
			"bridge",
			"tree",
			"door",
			"window",
			"bed",
			"table",
			"river",
			"boat",
			"tower",
			"path",
			"gate",
			"garden",
			"house",
			"hill",
			"arch",
			"stone",
			"forest",
		)
		objects: List[Dict[str, Any]] = []
		for keyword in keywords:
			if not re.search(rf"\b{re.escape(keyword)}s?\b", text):
				continue
			canonical_id = self._canonical_asset_id(keyword, "scene_object")
			if any(item["canonical_id"] == canonical_id for item in objects):
				continue
			objects.append(
				{
					"canonical_id": canonical_id,
					"label": keyword,
					"prompt": f"{keyword} as a readable storybook midground object, isolated and reusable for Unity scene assembly",
					"layer": "midground_objects",
					"slot": "center",
					"remove_bg": True,
				}
			)
		if not objects and world_anchor:
			objects.append(
				{
					"canonical_id": self._canonical_asset_id(world_anchor, "world_anchor"),
					"label": world_anchor,
					"prompt": f"{world_anchor}, readable storybook stage object for the main middle layer, isolated and reusable",
					"layer": "midground_objects",
					"slot": "center",
					"remove_bg": True,
				}
			)
		return objects[:3]

	def _build_page_asset_plan(
		self,
		idx: int,
		page_text: str,
		page_plan: Dict[str, Any],
		page_structure: Dict[str, Any],
		state_snapshot: Dict[str, Any],
	) -> Dict[str, Any]:
		world_anchor = re.sub(r"\s+", " ", str(page_plan.get("world_anchor") or page_plan.get("location") or "")).strip(" ,.")
		shot = str(page_plan.get("shot") or "mid").strip()
		lighting = str(page_plan.get("lighting") or "bright").strip()
		stage = str(page_plan.get("stage") or "action").strip()
		required_characters = list(page_plan.get("required_characters") or [])
		focus_subject = str(page_plan.get("focus_subject") or "character").strip()
		pose_reference = str(page_plan.get("pose_reference") or "").strip()
		scene_core = str(page_plan.get("scene_core") or page_plan.get("scene_goal") or page_text).strip()
		atmosphere = str(page_plan.get("atmosphere") or page_plan.get("emotion_density") or "calm").strip()
		characters: List[Dict[str, Any]] = []
		for index, name in enumerate(required_characters):
			characters.append(
				{
					"character_id": self._canonical_asset_id(name, "character"),
					"label": name,
					"pose_id": self._infer_pose_id(pose_reference, page_text, stage),
					"facing": self._infer_facing(pose_reference, page_text, index, len(required_characters)),
					"layer": "characters",
					"slot": self._character_slot(index, len(required_characters), focus_subject),
					"scale_hint": self._character_scale_hint(shot),
					"remove_bg": True,
				}
			)
		props: List[Dict[str, Any]] = []
		for prop_label in self._collect_prop_candidates(page_text, page_plan, required_characters):
			canonical_id = self._canonical_asset_id(prop_label, "prop")
			props.append(
				{
					"canonical_id": canonical_id,
					"label": prop_label,
					"prompt": f"{prop_label}, isolated children's storybook prop sprite, readable shape, reusable across pages",
					"interactive": False,
					"layer": "props",
					"slot": "center",
					"remove_bg": True,
				}
			)
		interactive_labels: List[str] = []
		if bool(page_structure.get("branch_trigger")) or str(page_structure.get("page_function") or "").upper() == "INTERACTION":
			if props:
				interactive_labels.append(str(props[0].get("label") or ""))
			else:
				interactive_labels.append(world_anchor or scene_core)
		interactives: List[Dict[str, Any]] = []
		for label in interactive_labels[:2]:
			canonical_id = self._canonical_asset_id(label, "interactive")
			interactives.append(
				{
					"canonical_id": canonical_id,
					"label": label,
					"prompt": f"{label}, isolated interactive storybook object sprite with a clear outline for highlighting",
					"interactive": True,
					"layer": "props",
					"slot": "center",
					"remove_bg": True,
				}
			)
		backdrop_prompt = ", ".join(
			part
			for part in [
				f"{world_anchor} backdrop" if world_anchor else "storybook backdrop",
				f"{lighting} {page_plan.get('time_of_day') or 'day'} lighting",
				f"{atmosphere} mood",
				"children's storybook environment plate",
				"no characters",
				"no hand-held props",
				"leave open stage space for Unity character placement",
			]
			if part
		)
		foreground_overlay_prompt = ", ".join(
			part
			for part in [
				str((page_plan.get("foreground_subjects") or ["soft foreground decor"])[0]).strip(),
				"foreground overlay only",
				"transparent-friendly isolated decorative layer",
				"no characters",
			]
			if part
		)
		return {
			"page_number": idx,
			"branch_id": self.current_branch_id,
			"world_anchor": world_anchor,
			"shot": shot,
			"lighting": lighting,
			"stage": stage,
			"story_readability_goal": str(page_plan.get("story_readability_goal") or "").strip(),
			"backdrop_prompt": backdrop_prompt,
			"foreground_overlay_prompt": foreground_overlay_prompt,
			"midground_objects": self._collect_midground_objects(page_plan, page_text, world_anchor),
			"characters": characters,
			"props": props,
			"interactives": interactives,
			"assembly_order": [
				"backdrop",
				"midground_objects",
				"characters",
				"props",
				"foreground_overlay",
			],
			"scene_core": scene_core,
			"continuity_keys": dict(page_plan.get("continuity_keys") or {}),
			"focus_subject": focus_subject,
			"motion_level": str(page_plan.get("motion_level") or "light").strip(),
			"emotion_density": str(page_plan.get("emotion_density") or "calm").strip(),
		}

	def _build_page_visual_plan(
		self,
		idx: int,
		page_text: str,
		scene_text: str,
		pose_text: str,
		page_structure: Dict[str, Any],
		state_snapshot: Dict[str, Any],
	) -> Dict[str, Any]:
		visual_context = self._build_visual_prompt_context(idx, page_text, page_structure, state_snapshot)
		required_characters = self._page_required_characters(page_text)
		world_anchor = str(visual_context.get("world_anchor") or "").strip()
		scene_core = self._derive_scene_core(scene_text, page_text)
		foreground_phrase = self._extract_scene_layer_phrase(scene_text, "foreground") or "nearest prop or leading gesture"
		midground_phrase = self._extract_scene_layer_phrase(scene_text, "midground") or scene_core
		background_phrase = self._extract_scene_layer_phrase(scene_text, "background") or world_anchor
		time_of_day = "night" if str(visual_context.get("scene_lighting") or "") == "dim" else "day"
		emotion_density = str(visual_context.get("scene_emotion_density") or "calm")
		world_constraint = str(state_snapshot.get("world_constraint") or "").strip()
		atmosphere = emotion_density
		if emotion_density == "wonder" and world_constraint:
			atmosphere = "wonder with caution"
		continuity_keys: Dict[str, str] = {}
		for record in self._story_character_records():
			name = str(record.get("name") or "").strip()
			if name not in required_characters:
				continue
			safe_name = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")
			outfit = re.sub(r"\s+", " ", str(record.get("outfit") or "")).strip(" ,")
			colors = ", ".join(self._extract_color_locks(record.get("appearance", ""), record.get("description", ""), outfit))
			props = ", ".join(str(prop or "").strip() for prop in (record.get("props") or []) if str(prop or "").strip())
			if outfit:
				continuity_keys[f"{safe_name}_outfit"] = outfit
			if colors:
				continuity_keys[f"{safe_name}_colors"] = colors
			if props:
				continuity_keys[f"{safe_name}_props"] = props
		forbidden_elements = ["text", "watermark", "logo", "photorealism", "3d render"]
		if time_of_day == "night":
			forbidden_elements.append("daylight")
		if len(required_characters) <= 2:
			forbidden_elements.append("extra characters")
		return {
			"page_id": idx,
			"page_number": idx,
			"branch_id": self.current_branch_id,
			"scene_goal": str(state_snapshot.get("character_goal") or scene_core).strip(),
			"scene_core": scene_core,
			"scene_layout": f"foreground: {foreground_phrase}; midground: {midground_phrase}; background: {background_phrase}",
			"shot": visual_context.get("scene_shot", "mid"),
			"lighting": visual_context.get("scene_lighting", "bright"),
			"stage": visual_context.get("scene_stage", "action"),
			"focus_subject": visual_context.get("scene_focus_subject", "character"),
			"motion_level": visual_context.get("scene_motion_level", "light"),
			"emotion_density": emotion_density,
			"composition_balance": visual_context.get("scene_composition_balance", "centered"),
			"location": world_anchor,
			"world_anchor": world_anchor,
			"time_of_day": time_of_day,
			"event_scene": str(state_snapshot.get("character_goal") or scene_core).strip(),
			"atmosphere": atmosphere,
			"foreground_subjects": [foreground_phrase],
			"midground_subjects": [midground_phrase],
			"background_subjects": [background_phrase],
			"required_characters": required_characters,
			"forbidden_elements": forbidden_elements,
			"continuity_keys": continuity_keys,
			"emotion_vector": [emotion_density] if atmosphere == emotion_density else [emotion_density, "caution"],
			"pose_reference": re.sub(r"\s+", " ", str(pose_text or "")).strip(" ,"),
			"story_readability_goal": visual_context.get("story_readability_goal", ""),
		}

	def _persist_branch_visual_plans(self, pages: Sequence[str], scenes: Sequence[str], poses: Sequence[str]) -> None:
		resource_root = self.paths["resource"]
		plans: List[Dict[str, Any]] = []
		asset_plans: List[Dict[str, Any]] = []
		for idx, page_text in enumerate(pages, start=1):
			page_structure = self._read_page_structure(idx) or {}
			state_snapshot = self._read_state_snapshot(idx)
			scene_text = scenes[idx - 1] if idx - 1 < len(scenes) else ""
			pose_text = poses[idx - 1] if idx - 1 < len(poses) else ""
			plan = self._build_page_visual_plan(idx, page_text, scene_text, pose_text, page_structure, state_snapshot)
			plans.append(plan)
			write_json_or_raise(resource_root / f"page_{idx}_visual_plan.json", plan)
			asset_plan = self._build_page_asset_plan(idx, page_text, plan, page_structure, state_snapshot)
			asset_plans.append(asset_plan)
			write_json_or_raise(resource_root / f"page_{idx}_asset_plan.json", asset_plan)
		write_json_or_raise(resource_root / "visual_plans.json", {"pages": plans, "branch_id": self.current_branch_id})
		write_json_or_raise(resource_root / "asset_plans.json", {"pages": asset_plans, "branch_id": self.current_branch_id})

	def _compile_full_story(self, branch_dir: Path, total_pages: int) -> None:
		"""Compiles Page 1..Total into full_story.txt in the branch dir."""
		compile_full_story(branch_dir, total_pages=total_pages, logger=self.logger)

	def _copy_branch_state(self, src_bid: str, dst_bid: str, decision_page: int) -> None:
		"""物理複製主線 (Trunk) 頁面 (1..decision_page) 從來源分支到目標分支。"""
		copy_branch_state(
			self.file_manager,
			logger=self.logger,
			src_bid=src_bid,
			dst_bid=dst_bid,
			decision_page=decision_page,
		)

	def _copy_branch_pages(self, src_bid: str, dst_bid: str, start_page: int, end_page: int) -> None:
		"""Copy a range of pages (and related metadata) from src to dst branch."""
		copy_branch_pages(
			self.file_manager,
			logger=self.logger,
			src_bid=src_bid,
			dst_bid=dst_bid,
			start_page=start_page,
			end_page=end_page,
		)

	def _extract_state_snapshot(self, plan_text: str) -> Optional[Dict[str, Any]]:
		"""Extracts <state_json>...</state_json> block from plan text."""
		return extract_state_snapshot(plan_text, logger=self.logger)

	def _write_state_snapshot(self, idx: int, snapshot: Dict[str, Any]) -> None:
		"""Persist state snapshot per page in the current branch folder."""
		write_state_snapshot(self.paths["story"], idx, snapshot)

	# --- End Helper Methods ---

	def _generate_assets(self, generated_branches_ids: List[str], outline: str, title: str) -> None:
		"""
		為所有分支生成衍生資產 (Narration, Dialogue, Scene, Pose)。
		這是多分支架構下最耗時的步驟，因為需要對每個分支都跑一次完整的資產生成流程。
		"""
		# Initialize meta collectors (prevent UnboundLocalError)
		all_meta_pages = []
		all_meta_narration = []
		all_meta_dialogues = []
		all_meta_scenes = []
		all_meta_poses = []
		
		canonical_bid = select_canonical_branch(generated_branches_ids, self.root_branch_id)
		limit = self._total_pages()

		for bid in generated_branches_ids:
			self.logger.info(f"Generating assets for branch: {bid}")
			self.switch_branch(bid)
			
			branch_pages = collect_branch_pages(
				self.file_manager.language_root,
				bid,
				limit,
				logger=self.logger,
			)
			
			if not branch_pages:
				self.logger.error(f"No pages found for branch {bid} to generate assets.")
				continue
			
			self.logger.info(f"Found {len(branch_pages)} pages for branch {bid} (expected {limit})")

			# Run derivations
			self._log_major_step(f"narration ({bid})")
			narration = self._run_page_derivation(branch_pages, "narration")
			
			self._log_major_step(f"dialogue ({bid})")
			dialogues = self._run_page_derivation(branch_pages, "dialogue")
			
			self._log_major_step(f"scene ({bid})")
			scenes = self._run_page_derivation(branch_pages, "scene")
			
			self._log_major_step(f"pose ({bid})")
			poses = self._run_page_derivation(branch_pages, "pose")
			self._persist_branch_visual_plans(branch_pages, scenes, poses)
			
			# Validate (Log only, don't crash main pipeline for a branch error)
			try:
				self._validate_derivation_pages("narration", narration, self._total_pages())
			except Exception as e:
				self.logger.warning(f"Branch {bid} validation error: {e}")

			# Keep Canonical branch data for story_meta
			if bid == canonical_bid:
				all_meta_pages = branch_pages
				all_meta_narration = narration
				all_meta_dialogues = dialogues
				all_meta_scenes = scenes
				all_meta_poses = poses

		# Ensure we are on a valid branch for cover generation context
		self.switch_branch(canonical_bid) 
		story_text = load_full_story_text(self.file_manager.language_root, canonical_bid)

		cover_source = outline if self.options.cover_source == "outline" else story_text
		self._log_major_step("cover")
		cover_context = build_cover_context(
			cover_source=cover_source,
			outline=outline,
			title=title,
			age=self.inputs.age_group or self.profile.age_label,
			character_descriptions=self._build_image_character_descriptions(),
			cover_guidelines=self.effective_guidelines or "",
			category=self.inputs.category or "",
			theme=self.inputs.theme or "",
			visual_style=self.image_style_lock,
			cover_source_label=self.options.cover_source,
		)
		cover_prompt = self._run_single_step(
			"cover",
			cover_context,
			self.paths["cover"],
		)

		self._persist_profile()
		meta = self._build_meta(
			outline,
			title,
			generated_branches_ids#(Fixed signature mismatch if exists)
		)
		# Add branching info to meta
		meta["branches"] = generated_branches_ids
		
		meta_path = self.paths["story_meta"]
		write_text_or_raise(meta_path, json.dumps(meta, ensure_ascii=False, indent=2))
		self.logger.info("Finished pipeline in %.2fs", meta["timestamps"]["generation_time_sec"])
		return meta

	def _sanitize_text(self, text: str) -> str:
		"""清理文本中的非英文字元與格式問題。"""
		return sanitize_text(text, self.primary_characters, logger=self.logger)

	def _enforce_dynamic_consistency(self, text: str) -> str:
		"""使用模糊匹配動態修復角色名稱錯誤。"""
		return enforce_dynamic_consistency(text, self.primary_characters, logger=self.logger)

	def _refine_text_with_llm(self, text: str, extra_context: Optional[Dict[str, Any]] = None, bad_words_ids: Optional[List[List[int]]] = None) -> str:
		"""使用 LLM 進行智能文本校正（修復名稱、間距、標點）。"""
		if not text or len(text) < 5:
			return text
			
		# 先進行基本的清理，並保存清理後的版本作為回退
		# 這確保即使 LLM refinement 失敗，我們至少有一個清理過的版本
		cleaned_text = self._sanitize_text(text)
		text = cleaned_text  # 使用清理後的版本作為基礎
			
		# 準備校正提示詞
		template_path = "prompts/Z1_text_refinement.txt"
		
		# 合併上下文
		context = {
			**self.base_context,
			**(extra_context or {}),
			"text": text
		}
		
		# 確保 smart_context 存在，如果沒有則提供預設值
		if "smart_context" not in context:
			context["smart_context"] = "No previous context available."
		
		try:
			system_prompt, user_prompt = load_step_prompts(template_path, context=context)
			chat_prompt = ChatPrompt(system_prompt=system_prompt, user_prompt=user_prompt)
			
			# 使用較低的溫度進行校正，確保穩定性
			params = GenerationParams(
				max_tokens=min(len(text) + 100, 300), # 減少最大 token 數以加速
				min_tokens=10,
				temperature=0.3,  # 降低到 0.3 確保格式穩定
				top_p=0.95,
				top_k=40,
				repetition_penalty=1.15,
				no_repeat_ngram_size=None
			)
			
			self.logger.info("Running LLM refinement on text (%d chars)...", len(text))
			# 使用 prefill 強制以 <refined> 開頭
			refined_text, _ = self.llm.generate(chat_prompt, params, prefill="<refined>", bad_words_ids=bad_words_ids)
			
			# [FIX] Robust tag handling
			# Ensure we have the opening tag exactly once
			refined_text = refined_text.strip()
			if not refined_text.startswith("<refined>"):
				refined_text = "<refined>" + refined_text
			
			# Strip thoughts (careful not to kill the <refined> tag if inside thought?? No, strip_hidden_thoughts usually safe)
			# But to be safe, extract content FIRST then strip thoughts from content
			
			tag_match = re.search(r"<refined>(.*?)(?:</refined>|$)", refined_text, re.DOTALL | re.IGNORECASE)
			if tag_match:
				inner_content = tag_match.group(1).strip()
				# Now strip thoughts from the content
				inner_content = strip_hidden_thoughts(inner_content).strip()
				inner_content = _strip_page_prefix(inner_content)
				
				if inner_content:
					refined_text = inner_content
				else:
					# Content became empty (maybe it was all thought?)
					self.logger.warning("Refinement content empty after stripping thoughts. Reverting.")
					return cleaned_text
			else:
				# Should be impossible if we forced prepend, unless regex failed on weird chars
				self.logger.warning("Refinement missing <refined> tag logic failed. Reverting.")
				return cleaned_text

			# Skip "Reverting to cleaned original" check since we handled it
			# Just do final sanity checks
			
			# 二次清理校正後的文本
			refined_text = self._sanitize_text(refined_text)

			# 如果校正後變空，則回退到原始文本
			if not refined_text:
				self.logger.warning("Refinement returned empty result, keeping cleaned original.")
				return cleaned_text  # 返回已清理的版本
			
			# 放寬長度檢查：如果內容是重複的，Refinement 可能會大幅縮短它，這是好事
			# 只有當長度極短 (< 20%) 時才懷疑是錯誤
			if len(refined_text) < len(text) * 0.2:
				self.logger.warning("Refinement result too short (%d vs %d), keeping cleaned original.", len(refined_text), len(text))
				return cleaned_text  # 返回已清理的版本
				
			if refined_text != text:
				self.logger.info("Refinement applied. Diff: %d chars", len(refined_text) - len(text))
				return refined_text
				
		except Exception as e:
			self.logger.error("LLM refinement failed: %s", e)
			# 返回已清理的版本，而不是完全未處理的原始文本
			return cleaned_text
		
		return text

	def _build_character_alias_map(self) -> Dict[str, str]:
		"""建立 alias -> canonical 的角色映射。"""
		return build_character_alias_map(self.primary_characters)

	def _count_character_mentions(self, text: str, alias_map: Dict[str, str]) -> int:
		"""估算句內被提及的不同角色數。"""
		return count_character_mentions(text, alias_map)

	def _coref_ambiguity_score(self, text: str) -> int:
		"""以輕量規則估算文本中的代名詞歧義風險分數。"""
		return coref_ambiguity_score(text, self.primary_characters)
	
	def _repair_coref_ambiguity_with_llm(
		self,
		text: str,
		extra_context: Optional[Dict[str, Any]] = None,
		bad_words_ids: Optional[List[List[int]]] = None,
	) -> str:
		"""僅在偵測到歧義風險時，執行一次局部語意保留式代名詞消歧修復。"""
		if not text or len(text) < 40:
			return text

		before_score = self._coref_ambiguity_score(text)
		if before_score <= 0:
			return text

		template_path = "prompts/Z2_coref_disambiguation.txt"
		context = {**self.base_context, **(extra_context or {}), "text": text}
		if not context.get("characters_csv") and self.primary_characters:
			context["characters_csv"] = ", ".join(self.primary_characters)

		try:
			system_prompt, user_prompt = load_step_prompts(template_path, context=context)
			chat_prompt = ChatPrompt(system_prompt=system_prompt, user_prompt=user_prompt)

			params = GenerationParams(
				max_tokens=min(max(len(text) + 120, 180), 520),
				min_tokens=max(24, min(120, len(text) // 4)),
				temperature=0.2,
				top_p=0.9,
				top_k=40,
				repetition_penalty=1.1,
				no_repeat_ngram_size=None,
			)

			raw_fixed, _ = self.llm.generate(
				chat_prompt,
				params,
				prefill="<fixed>",
				bad_words_ids=bad_words_ids,
			)
			fixed_text = raw_fixed.strip()
			if not fixed_text.startswith("<fixed>"):
				fixed_text = "<fixed>" + fixed_text

			match = re.search(r"<fixed>(.*?)(?:</fixed>|$)", fixed_text, re.DOTALL | re.IGNORECASE)
			if not match:
				return text

			candidate = strip_hidden_thoughts(match.group(1)).strip()
			candidate = _strip_page_prefix(candidate)
			candidate = self._sanitize_text(candidate)
			if not candidate:
				return text

			if len(candidate) < len(text) * 0.65 or len(candidate) > len(text) * 1.35:
				self.logger.info(
					"Skip coref repair due to large length drift (%d -> %d).",
					len(text),
					len(candidate),
				)
				return text

			after_score = self._coref_ambiguity_score(candidate)
			if after_score <= before_score:
				self.logger.info(
					"Applied coref disambiguation repair (ambiguity score %d -> %d).",
					before_score,
					after_score,
				)
				return candidate

			self.logger.info(
				"Skip coref repair (ambiguity score %d -> %d not improved).",
				before_score,
				after_score,
			)
			return text
		except Exception as exc:
			self.logger.warning("Coref disambiguation pass failed: %s", exc)
			return text

	def _assess_generation_quality_risks(self, step: str, text: str) -> Dict[str, Any]:
		if step not in {"story", "story_write"} or not text:
			return {
				"needs_coref_repair": False,
				"needs_refinement": False,
				"signals": {},
			}

		sentences = [chunk.strip() for chunk in re.split(r"(?<=[.!?。！？])\s*", text) if chunk.strip()]
		normalized_sentences = [re.sub(r"\s+", " ", sentence).strip().lower() for sentence in sentences]
		sentence_count = len(normalized_sentences)
		duplicate_sentence_ratio = 0.0
		if sentence_count > 0:
			counts = Counter(normalized_sentences)
			duplicate_sentence_ratio = sum(count - 1 for count in counts.values() if count > 1) / max(1, sentence_count)

		word_lengths = [len(token) for token in re.findall(r"[A-Za-z']+|[\u4e00-\u9fff]", text)]
		avg_word_length = (sum(word_lengths) / len(word_lengths)) if word_lengths else 0.0
		avg_sentence_words = (
			sum(len(re.findall(r"[A-Za-z']+|[\u4e00-\u9fff]", sentence)) for sentence in sentences) / max(1, sentence_count)
		)
		repeated_phrase = bool(re.search(r"\b([A-Za-z']+)(?:\s+\1){2,}\b", text, flags=re.IGNORECASE))
		glitch = self._looks_like_text_glitch(text)
		coref_score = self._coref_ambiguity_score(text)

		signals = {
			"duplicate_sentence_ratio": round(duplicate_sentence_ratio, 4),
			"avg_sentence_words": round(avg_sentence_words, 2),
			"avg_word_length": round(avg_word_length, 2),
			"coref_ambiguity_score": coref_score,
			"repeated_phrase": repeated_phrase,
			"glitch": glitch,
		}
		return {
			"needs_coref_repair": coref_score >= 2,
			"needs_refinement": glitch or repeated_phrase or duplicate_sentence_ratio >= 0.22 or avg_sentence_words >= 24.0,
			"signals": signals,
		}

	def _apply_targeted_quality_repair(
		self,
		step: str,
		text: str,
		extra_context: Optional[Dict[str, Any]] = None,
		bad_words_ids: Optional[List[List[int]]] = None,
	) -> str:
		risk = self._assess_generation_quality_risks(step, text)
		if not risk.get("needs_coref_repair") and not risk.get("needs_refinement"):
			return text

		self.logger.info("[Step %s] Targeted repair triggered with signals=%s", step, risk.get("signals", {}))
		candidate = text
		if risk.get("needs_coref_repair"):
			candidate = self._repair_coref_ambiguity_with_llm(
				candidate,
				extra_context=extra_context,
				bad_words_ids=bad_words_ids,
			)
		if risk.get("needs_refinement"):
			candidate = self._refine_text_with_llm(
				candidate,
				extra_context=extra_context,
				bad_words_ids=bad_words_ids,
			)

		candidate = self._sanitize_text(candidate)
		if step in {"story", "story_write", "narration", "dialogue", "scene"}:
			candidate = self._enforce_dynamic_consistency(candidate)
		is_valid, _error_msg = self._validate_step_output(step, candidate, extra_context=extra_context)
		if not is_valid:
			self.logger.warning("[Step %s] Targeted repair produced invalid output; keeping original.", step)
			return text
		return candidate or text

	def _run_page_derivation(
		self,
		pages: Sequence[str],
		step: str,
	) -> List[str]:
		"""對每頁執行衍生步驟（旁白/對話/scene/pose）。"""
		outputs: List[str] = []
		aggregate_lines: List[str] = []
		for idx, page_text in enumerate(pages, start=1):
			page_structure = self._read_page_structure(idx) or {}
			state_snapshot = self._read_state_snapshot(idx)
			visual_prompt_context = self._build_visual_prompt_context(idx, page_text, page_structure, state_snapshot)
			context = {
				"page_text": page_text,
				"page_content": page_text,  # 同時提供兩種變數名以兼容模板
				"page_number": idx,
				"page_count": len(pages),
				"total_pages": len(pages),  # 同時提供兩種變數名以兼容模板
				"page_id": PAGE_TEMPLATE.format(idx),
				"page_structure": json.dumps(page_structure, ensure_ascii=False),
				"page_function": page_structure.get("page_function", "NARRATIVE"),
				"branch_id": page_structure.get("branch_id", ""),
				"branch_trait": page_structure.get("branch_trait", ""),
				"character_name": self._primary_character_for_page(page_text),
				**visual_prompt_context,
			}
			# 為 narration 步驟添加額外的變數
			if step == "narration":
				min_words, max_words = self._target_word_bounds()
				context.update({
					"min_words": min_words,
					"max_words": max_words,
					"narration_guidelines": self.effective_guidelines or "",
				})
			
			# [Phase 4] Inject Visual Style for Scene/Pose
			if step in ["scene", "pose"]:
				context["image_style_lock"] = self.image_style_lock
			file_path = self._derivation_path(step, idx)
			text = self._run_single_step(step, context, file_path)
			outputs.append(text)
			aggregate_lines.append(self._format_aggregate_line(step, idx, text))
		if aggregate_lines:
			write_text_or_raise(self._aggregate_path(step), "\n\n".join(aggregate_lines))
		return outputs

	def _compute_bad_words_ids(self, allowed_names: List[str], banned_phrases: Optional[List[str]] = None) -> Optional[List[List[int]]]:
		"""根據允許的角色名稱與禁止的短語，計算需要禁止的 token ID 列表。
		
		智能策略：
		1. 自動生成所有可能的錯誤變體（黏連、大小寫、性別、後綴）
		2. 使用 tokenizer 將這些變體轉換為禁止的 token IDs
		3. 在生成時物理阻止這些錯誤，從源頭防止問題
		"""
		if not hasattr(self.llm, "tokenizer"):
			return None
			
		tokenizer = self.llm.tokenizer
		bad_words = set()  # 使用 set 自動去重
		
		# 1. 針對每個允許的名字，智能生成所有可能的錯誤變體
		if allowed_names:
			for name in allowed_names:
				parts = name.split()
				
				# 策略 A: 空格移除變體（GrandpaTom）
				merged = name.replace(" ", "")
				if merged != name:
					bad_words.add(merged)
					# 也禁止首字母小寫版本
					bad_words.add(merged[0].lower() + merged[1:] if merged else merged)
				
				# 策略 B: 大小寫變體
				if len(parts) >= 2:
					# 全大寫變體（GRANDPA TOM）
					bad_words.add(name.upper())
					# 第二個詞全大寫（Grandpa TOM）
					bad_words.add(f"{parts[0]} {parts[1].upper()}")
					# 第一個詞全大寫（GRANDPA Tom）
					bad_words.add(f"{parts[0].upper()} {parts[1]}")
				
				# 策略 C: 針對 "Grandpa" 的性別/稱謂變體
				if parts and parts[0].lower() == "grandpa":
					second_part = parts[1] if len(parts) > 1 else ""
					# 性別錯誤
					bad_words.add(f"Grandma {second_part}".strip())
					bad_words.add(f"Grandmother {second_part}".strip())
					# 稱謂變體
					bad_words.add(f"Grandpop {second_part}".strip())
					bad_words.add(f"Grandpad {second_part}".strip())
					bad_words.add(f"Gramps {second_part}".strip())
					bad_words.add(f"Granddad {second_part}".strip())
					# 黏連變體
					if second_part:
						bad_words.add(f"Grandpa{second_part}")
						bad_words.add(f"Grandma{second_part}")
				
				# 策略 D: 複數/所有格錯誤（只針對最後一個詞）
				if parts:
					last_part = parts[-1]
					# Emma -> Emmas, Alex -> Alexs
					bad_words.add(last_part + "s")
					# 但如果原本就是複數（如 Alex），禁止錯誤的所有格
					if last_part.endswith("x"):
						bad_words.add(last_part + "les")  # Axles
				
				# 策略 E: 常見拼寫錯誤（基於 Levenshtein distance = 1）
				# 例如：Tom -> Ton, Tam, Toom
				# 這裡我們只處理最常見的
				for part in parts:
					if len(part) >= 3:
						# 重複最後一個字母
						bad_words.add(part + part[-1])
						# 交換最後兩個字母（如果適用）
						if len(part) >= 2:
							swapped = part[:-2] + part[-1] + part[-2]
							bad_words.add(swapped)

		# 2. 加入額外禁止的短語
		if banned_phrases:
			bad_words.update(banned_phrases)
		
		# 3. 將字串轉換為 token IDs
		bad_words_ids = []
		for word in bad_words:
			if not word:  # 跳過空字串
				continue
			try:
				# 注意：add_special_tokens=False 很重要，否則會加入 BOS token
				ids = tokenizer.encode(word, add_special_tokens=False)
				if ids:
					bad_words_ids.append(ids)
			except Exception as e:
				self.logger.debug(f"Failed to encode bad word '{word}': {e}")
				continue
				
		if bad_words_ids:
			# 計算統計信息
			unique_phrases = len(set(tuple(ids) for ids in bad_words_ids))
			# Log only summary to avoid spamming
			self.logger.info(f"🚫 Generated {unique_phrases} forbidden token patterns from {len(allowed_names)} names (blocking {len(bad_words_ids)} total variants)")
			# Log a sample for debugging
			sample_words = list(bad_words)[:8]
			if len(bad_words) > 8:
				sample_words.append(f"... +{len(bad_words)-8} more")
			self.logger.debug(f"Sample forbidden words: {sample_words}")
			
		return bad_words_ids if bad_words_ids else None

	def _count_prompt_markers(self, text: str, markers: Sequence[str]) -> int:
		lowered = (text or "").casefold()
		count = 0
		for marker in markers:
			if marker and marker.casefold() in lowered:
				count += 1
		return count

	def _scene_has_clear_spatial_staging(self, text: str, scene_stage: str, scene_shot: str) -> bool:
		lowered = f" {(text or '').casefold()} "
		depth_markers = (
			" foreground", " midground", " background",
			" in front of ", " behind ", " beyond ",
		)
		relation_markers = (
			" beside ", " near ", " under ", " beneath ", " above ", " below ",
			" around ", " through ", " across ", " along ", " between ",
			" inside ", " outside ", " against ", " around the ", " by the ",
			" left of ", " right of ", " at the doorway ", " on the path ",
		)
		depth_count = sum(1 for marker in depth_markers if marker in lowered)
		relation_count = sum(1 for marker in relation_markers if marker in lowered)
		if depth_count >= 2:
			return True
		if depth_count >= 1 and relation_count >= 1:
			return True
		if scene_shot in {"close", "mid"} and (depth_count + relation_count) >= 1:
			return True
		if scene_stage in {"setup", "result"} and (depth_count + relation_count) >= 1:
			return True
		return False

	def _has_prompt_action(self, text: str) -> bool:
		action_markers = (
			" stand", " stands", " standing",
			" sit", " sits", " sitting",
			" walk", " walks", " walking",
			" run", " runs", " running",
			" hold", " holds", " holding",
			" reach", " reaches", " reaching",
			" look", " looks", " looking",
			" smile", " smiles", " smiling",
			" hug", " hugs", " hugging",
			" peek", " peeks", " peeking",
			" point", " points", " pointing",
			" kneel", " kneels", " kneeling",
			" glow", " glows", " glowing",
			" float", " floats", " floating",
			" open", " opens", " opening",
			" listen", " listens", " listening",
			" lean", " leans", " leaning",
			" share", " shares", " sharing",
			" hand", " hands", " handing",
			" give", " gives", " giving",
			" offer", " offers", " offering",
			" laugh", " laughs", " laughing",
			" play", " plays", " playing",
			" gather", " gathers", " gathering",
			" dance", " dances", " dancing",
			" jump", " jumps", " jumping",
			" climb", " climbs", " climbing",
			" turn", " turns", " turning",
			" sway", " sways", " swaying",
			" spread", " spreads", " spreading",
			" rise", " rises", " rising",
			" shine", " shines", " shining",
			" carry", " carries", " carrying",
			" swing", " swings", " swinging",
			" pull", " pulls", " pulling",
			" push", " pushes", " pushing",
			" wave", " waves", " waving",
			" watch", " watches", " watching",
			" move", " moves", " moving",
			" guide", " guides", " guiding", " guided",
			" lead", " leads", " leading", " led",
			" follow", " follows", " following", " followed",
			" drift", " drifts", " drifting", " drifted",
			" glide", " glides", " gliding", " glided",
			" form", " forms", " forming", " formed",
			" swirl", " swirls", " swirling", " swirled",
			" shimmer", " shimmers", " shimmering", " shimmered",
			" twinkle", " twinkles", " twinkling", " twinkled",
			" trail", " trails", " trailing", " trailed",
			" arc", " arcs", " arcing", " arced",
			" circle", " circles", " circling", " circled",
			" sparkle", " sparkles", " sparkling", " sparkled",
		)
		lowered = f" {(text or '').casefold()} "
		return any(marker in lowered for marker in action_markers)

	def _has_prompt_pose_or_state(self, text: str) -> bool:
		pose_markers = (
			" seated", " sitting", " standing", " kneeling", " crouching", " leaning",
			" waiting", " watching", " listening", " resting", " sleeping", " smiling",
			" frowning", " face lit", " arms open", " hands on", " hands lifted",
			" glowing", " sunlit", " moonlit", " gathered", " together", " still",
		)
		lowered = f" {(text or '').casefold()} "
		return any(marker in lowered for marker in pose_markers)

	def _current_image_family(self) -> str:
		token = str(getattr(self.options, "sdxl_base", "") or "").strip().lower()
		if not token:
			return "unknown"
		if "flux.1-schnell" in token or "flux-1-schnell" in token or "schnell" in token:
			return "flux_schnell"
		if "flux" in token:
			return "flux"
		if ("stable-diffusion-3.5" in token and "turbo" in token) or ("sd3" in token and "turbo" in token):
			return "sd3_turbo"
		if "stable-diffusion-3.5" in token or "sd3" in token:
			return "sd3"
		return "sdxl"

	def _image_prompt_budget(self, step: str) -> Tuple[int, int, int]:
		clip_cfg = self.system_config.get("validation", {}).get("clip_tokens", {})
		family = self._current_image_family()
		if family == "flux_schnell":
			if step == "scene":
				return (18, 72, 96)
			if step == "pose":
				return (10, 36, 60)
			if step == "cover":
				return (20, 72, 96)
		if family in {"flux", "sd3_turbo", "sd3"}:
			if step == "scene":
				return (20, 92, 124)
			if step == "pose":
				return (10, 40, 68)
			if step == "cover":
				return (22, 92, 124)
		if step == "scene":
			return (
				int(clip_cfg.get("scene_min", 20)),
				int(clip_cfg.get("scene_max", 56)),
				int(clip_cfg.get("scene_total_max", 78)),
			)
		if step == "pose":
			return (
				int(clip_cfg.get("pose_min", 10)),
				int(clip_cfg.get("pose_max", 30)),
				int(clip_cfg.get("pose_total_max", 54)),
			)
		if step == "cover":
			return (
				int(clip_cfg.get("cover_min", 22)),
				int(clip_cfg.get("cover_max", 56)),
				int(clip_cfg.get("cover_total_max", 78)),
			)
		default_max = int(clip_cfg.get("default_total_max", 80))
		return (0, default_max, default_max)

	def _trim_prompt_segment(self, segment: str, max_words: int) -> str:
		cleaned = re.sub(r"\s+", " ", str(segment or "").strip()).strip(", ")
		if not cleaned or max_words <= 0:
			return ""
		words = cleaned.split()
		if len(words) <= max_words:
			return cleaned

		removable_tokens = {
			"the", "a", "an", "very", "really", "gently", "softly", "quietly", "calmly",
			"brightly", "warmly", "soft", "gentle", "cozy", "little", "small",
		}
		filtered = [word for word in words if re.sub(r"[^a-z]+", "", word.casefold()) not in removable_tokens]
		if len(filtered) >= max_words:
			words = filtered
		return " ".join(words[:max_words]).strip(", ")

	def _compress_image_prompt_to_budget(
		self,
		step: str,
		text: str,
		extra_context: Optional[Dict[str, Any]] = None,
	) -> str:
		cleaned = re.sub(r"\s+", " ", str(text or "").strip())
		if not cleaned or step not in {"scene", "cover", "pose"}:
			return cleaned

		suffix_map = {
			"scene": "children's picture-book scene illustration, layered depth, readable faces, coherent lighting, no text",
			"pose": "children's picture-book character sheet, full body, clean silhouette, readable face, light plain background",
			"cover": "children's picture-book cover illustration, readable thumbnail, clear focal subject, no text lettering",
		}
		clip_cfg = self.system_config.get("validation", {}).get("clip_tokens", {})
		_, prompt_max, total_max = self._image_prompt_budget(step)

		def _fits_budget(value: str) -> bool:
			prompt_tokens = estimate_clip_tokens(value)
			total_tokens = prompt_tokens + estimate_clip_tokens(suffix_map.get(step, "")) + 1
			return prompt_tokens <= prompt_max and total_tokens <= total_max

		if _fits_budget(cleaned):
			return cleaned

		original = cleaned
		replacements = (
			(r"\bin the foreground\b", "foreground"),
			(r"\bin the midground\b", "midground"),
			(r"\bin the background\b", "background"),
			(r"\bat the foreground\b", "foreground"),
			(r"\bat the midground\b", "midground"),
			(r"\bat the background\b", "background"),
			(r"\bwith a\b", "with"),
			(r"\bwith an\b", "with"),
			(r"\bthere is\b", ""),
			(r"\bthere are\b", ""),
			(r"\bcan be seen\b", "shows"),
			(r"\bthat is\b", "that"),
			(r"\bsoft morning\b", "morning"),
			(r"\bwarm golden\b", "golden"),
		)
		for pattern, replacement in replacements:
			cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
		cleaned = re.sub(r"\s+,", ",", cleaned)
		cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
		if _fits_budget(cleaned):
			if cleaned != original:
				self.logger.info("[Step %s] Compressed image prompt to fit the estimated prompt budget.", step)
			return cleaned

		segments = [segment.strip() for segment in cleaned.split(",") if segment.strip()]
		if step == "scene" and segments:
			limits = [11, 6, 6, 6]
			trimmed_segments = [
				self._trim_prompt_segment(segment, limits[min(index, len(limits) - 1)])
				for index, segment in enumerate(segments[:4])
			]
			cleaned = ", ".join([segment for segment in trimmed_segments if segment])
		elif step == "cover" and segments:
			limits = [12, 7, 6]
			trimmed_segments = [
				self._trim_prompt_segment(segment, limits[min(index, len(limits) - 1)])
				for index, segment in enumerate(segments[:3])
			]
			cleaned = ", ".join([segment for segment in trimmed_segments if segment])
		elif step == "pose" and segments:
			cleaned = ", ".join(self._trim_prompt_segment(segment, 3) for segment in segments[:6] if segment)

		cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
		if _fits_budget(cleaned):
			if cleaned != original:
				self.logger.info("[Step %s] Compressed image prompt to fit the estimated prompt budget.", step)
			return cleaned

		words = cleaned.split()
		hard_limit = max(8, prompt_max - 4)
		if len(words) > hard_limit:
			cleaned = " ".join(words[:hard_limit]).strip(" ,")
		cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,")
		if cleaned != original:
			self.logger.info(
				"[Step %s] Applied aggressive prompt compression (%d -> %d chars).",
				step,
				len(original),
				len(cleaned),
			)
		return cleaned

	def _validate_image_prompt_quality(
		self,
		step: str,
		text: str,
		extra_context: Optional[Dict[str, Any]] = None,
	) -> Optional[str]:
		cleaned = re.sub(r"\s+", " ", (text or "").strip())
		if not cleaned:
			return "Output is empty."

		word_count = len(cleaned.split())
		comma_segments = [segment.strip() for segment in cleaned.split(",") if segment.strip()]
		spatial_markers = (
			"foreground",
			"midground",
			"background",
			"behind",
			"beside",
			"near",
			"under",
			"inside",
			"outside",
			"beneath",
			"beyond",
			"across",
		)

		if step == "scene":
			scene_stage = str((extra_context or {}).get("scene_stage") or "").strip().casefold()
			scene_shot = str((extra_context or {}).get("scene_shot") or "").strip().casefold()
			has_action = self._has_prompt_action(cleaned)
			has_pose = self._has_prompt_pose_or_state(cleaned)
			if word_count < 14:
				return "Constraint violation: Scene prompt is too terse. Use a fuller illustration sentence with clear staging."
			if not has_action and not has_pose:
				return "Constraint violation: Scene prompt needs a visible action or pose, not just objects."
			if scene_stage not in {"setup", "result"} and not has_action:
				return "Constraint violation: Scene prompt needs clearer visible action for this page."
			if not self._scene_has_clear_spatial_staging(cleaned, scene_stage, scene_shot):
				return "Constraint violation: Scene prompt needs clearer spatial staging across the scene."
			if len(comma_segments) >= 3 and all(len(segment.split()) <= 4 for segment in comma_segments[:3]):
				return "Constraint violation: Scene prompt reads like a bare placeholder list. Rewrite it as a natural illustration sentence."
			return None

		if step == "cover":
			if word_count < 14:
				return "Constraint violation: Cover prompt is too terse. Add a stronger focal scene, action, and setting."
			if not (self._has_prompt_action(cleaned) or self._has_prompt_pose_or_state(cleaned)):
				return "Constraint violation: Cover prompt needs a clear action or pose for the main subject."
			if len(comma_segments) >= 3 and all(len(segment.split()) <= 4 for segment in comma_segments[:3]):
				return "Constraint violation: Cover prompt is too telegraphic. Use one flowing sentence instead of stacked fragments."
			return None

		if step == "pose":
			if any(punct in cleaned for punct in ".!?"):
				return "Constraint violation: Pose prompt should be comma-separated phrases, not a sentence."
			if len(comma_segments) < 4:
				return "Constraint violation: Pose prompt needs more pose detail. Include stance, hands, face, gaze, and mood."
			if len(comma_segments) > 8:
				return "Constraint violation: Pose prompt has too many fragments. Keep it concise and focused."
			if any(len(segment.split()) > 4 for segment in comma_segments):
				return "Constraint violation: Pose prompt phrases are too long. Use compact illustrator-style fragments."
			lowered = cleaned.casefold()
			if any(name and name.casefold() in lowered for name in self.primary_characters):
				return "Constraint violation: Pose prompt must not contain character names."
			return None

		return None

	def _validate_step_output(
		self,
		step: str,
		text: str,
		extra_context: Optional[Dict[str, Any]] = None,
	) -> Tuple[bool, Optional[str]]:
		"""驗證步驟輸出是否符合硬性約束（CLIP tokens, 完整性等）。"""
		# 對於圖像相關步驟，驗證提示詞長度
		if step in {"scene", "pose", "cover"}:
			quality_error = self._validate_image_prompt_quality(step, text, extra_context=extra_context)
			if quality_error:
				return False, quality_error
			# 獲取對應的 suffix
			suffix_map = {
				"scene": "children's picture-book scene illustration, layered depth, readable faces, coherent lighting, no text",
				"pose": "children's picture-book character sheet, full body, clean silhouette, readable face, light plain background",
				"cover": "children's picture-book cover illustration, readable thumbnail, clear focal subject, no text lettering",
			}
			suffix = suffix_map.get(step, "")
			
			# 驗證主提示詞的 token 數量
			prompt_tokens = estimate_clip_tokens(text)
			suffix_tokens = estimate_clip_tokens(suffix)
			total_tokens = prompt_tokens + suffix_tokens + 1  # +1 for comma
			
			# 根據步驟檢查是否符合要求 (從 config 動態讀取)
			min_tokens, max_prompt_tokens, max_total = self._image_prompt_budget(step)
			expected_range = (min_tokens, max_prompt_tokens)
			
			if prompt_tokens < expected_range[0]:
				self.logger.error(
					"[Step %s] Prompt token estimate (%d) is TOO SHORT (minimum %d). "
					"REJECTING output to ensure image quality.",
					step, prompt_tokens, expected_range[0]
				)
				return False, f"Constraint violation: Prompt is too short ({prompt_tokens} < {expected_range[0]} estimated tokens). Please provide more detailed visual descriptions."
				
			if prompt_tokens > expected_range[1]:
				self.logger.warning(
					"[Step %s] Prompt token estimate (%d) exceeds the target (%d) but is under the max total budget. "
					"Continuing anyway.",
					step, prompt_tokens, expected_range[1]
				)
			
			if total_tokens > max_total:
				self.logger.error(
					"[Step %s] Total prompt exceeds budget: %d estimated tokens (max %d). "
					"Main prompt: %d tokens, Suffix: %d tokens. "
					"This will cause truncation and poor image quality. "
					"Prompt: %s...",
					step, total_tokens, max_total, prompt_tokens, suffix_tokens, text[:80]
				)
				return False, f"Constraint violation: Prompt is too long ({total_tokens} > {max_total} estimated tokens). Shorten it to under {expected_range[1]} tokens."
			else:
				self.logger.debug(
					"[Step %s] Prompt token count: %d (main) + %d (suffix) = %d total (max %d) ✓",
					step, prompt_tokens, suffix_tokens, total_tokens, max_total
				)
				return True, None

		# 對於 JSON 輸出步驟（如 title），確保格式正確
		if step == "title":
			parsed_title = self._extract_title_candidate(text)
			if not parsed_title:
				return False, "Constraint violation: Unable to parse a valid title from model output."
			return True, None

		# 針對故事文本檢查完整性 (Story Text Integrity Check)
		if step in {"story", "story_write", "narration"}:
			# 檢查是否以標點符號結尾
			text = text.strip()
			if not text:
				return False, "Output is empty."
				
			# 允許的結尾標點
			valid_endings = ('.', '!', '?', '"', '”', '…')
			if not text.endswith(valid_endings):
				self.logger.warning("[Step %s] Text likely truncated (no punctuation at end): ...%s", step, text[-20:])
				return False, "Constraint violation: The text seems truncated or incomplete. Ensure it ends with proper punctuation."
				
		return True, None

	def _build_step_retry_instruction(
		self,
		step: str,
		extra_context: Optional[Dict[str, Any]],
		error_msg: str,
	) -> str:
		context = extra_context or {}
		if step == "scene":
			if "too long" in (error_msg or "").casefold():
				return (
					f"Retry guidance: rewrite as one tighter natural sentence for Shot={context.get('scene_shot', '')}, "
					f"Lighting={context.get('scene_lighting', '')}, Stage={context.get('scene_stage', '')}. "
					"Keep only the main subject, one visible action or pose, three depth cues, and one concrete anchor. "
					"Cut extra modifiers so the sentence stays compact."
				)
			if "action or pose" in (error_msg or "").casefold():
				return (
					f"Retry guidance: rewrite as one natural sentence for Shot={context.get('scene_shot', '')}, "
					f"Lighting={context.get('scene_lighting', '')}, Stage={context.get('scene_stage', '')}. "
					"Use a concrete visible verb such as walking, guiding, following, reaching, floating, or leaning, "
					"or describe a readable pose. Include at least one clear depth cue and 1-2 concrete visual anchors."
				)
			return (
				f"Retry guidance: rewrite as one natural sentence for Shot={context.get('scene_shot', '')}, "
				f"Lighting={context.get('scene_lighting', '')}, Stage={context.get('scene_stage', '')}. "
				"Use exact character names when needed, show a visible action or a readable pose, "
				"include at least one clear depth cue or spatial relation, and add 1-2 concrete visual anchors. "
				"Do not return a keyword list or a static object inventory."
			)
		if step == "cover":
			return (
				"Retry guidance: choose one iconic focal moment, keep the subject group readable at thumbnail size, "
				"show a clear action or pose, mention one memorable prop or light cue, and avoid listing multiple events."
			)
		if step == "pose":
			return (
				"Retry guidance: return only 4-7 short comma-separated phrases covering stance, hands, face, gaze, and energy. "
				"No full sentences and no character names."
			)
		return f"Retry guidance: {error_msg}"

	def _run_single_step(
		self,
		step: str,
		extra_context: Dict[str, Any],
		output_path: Path,
		generation: Optional[GenerationParams] = None,
		banned_phrases: Optional[List[str]] = None, # 允許傳遞動態禁止詞
	) -> str:
		"""渲染提示並呼叫 LLM 取得輸出後寫入檔案。"""
		
		# [Phase 5: Checkpoint / Resume]
		if output_path.exists():
			try:
				content = output_path.read_text(encoding="utf-8", errors="replace")
				# 確保檔案不為空，若為空則重跑
				if content and len(content.strip()) > 0:
					self.logger.info("[Step %s] Resuming from existing file: %s", step, output_path.name)
					self.step_history.append({
						"step": step,
						"duration_sec": 0,
						"generated_tokens": 0,
						"output_chars": len(content),
						"retries": 0,
						"cached": True,
						"page_number": extra_context.get("page_number") if extra_context else None
					})
					return content
			except Exception as exc:
				self.logger.warning("Failed to read existing file %s: %s. Regenerating...", output_path.name, exc)
				
		template_path = PROMPT_FILES.get(step)
		if template_path is None:
			raise KeyError(f"Unknown step '{step}'")
		context = {**self.base_context, **extra_context}
		system_prompt, user_prompt = load_step_prompts(template_path, context=context)
		
		# 決定此步驟的預填內容 (Prefill)
		prefill_tag = STEP_TAGS.get(step, "")
		
		params = generation or self._generation_for(step)
		
		# Retry Loop
		max_retries = self.system_config.get("max_retries_per_step", 2)
		current_try = 0
		last_error = ""
		
		# 初始 prompt
		current_user_prompt = user_prompt
		
		while current_try <= max_retries:
			chat_prompt = ChatPrompt(system_prompt=system_prompt, user_prompt=current_user_prompt)
			total_chars = len(system_prompt) + len(current_user_prompt) + len(prefill_tag)
			
			self.logger.info(
				"[Step %s] Try %d/%d system=%s chars, user=%s chars, prefill='%s', total=%s, max_tokens=%s, temp=%.2f",
				step,
				current_try + 1,
				max_retries + 1,
				len(system_prompt),
				len(current_user_prompt),
				prefill_tag,
				total_chars,
				params.max_tokens,
				params.temperature,
			)
			
			step_start = time.perf_counter()
			
			# Profiling logic
			profile_meta = {
				"step": step,
				"page_number": extra_context.get("page_number", 0) if extra_context else 0,
				"model_name": self.options.model_name,
				"try": current_try
			}
			
			def _do_generate():
				"""執行 LLM 生成並返回結果。"""
				generated_text, tokens = self.llm.generate(chat_prompt, params, prefill=prefill_tag)
				return prefill_tag + generated_text, tokens

			if self.kernel_recorder:
				with self.kernel_recorder.profile(self.story_id, f"story_step_{step}", metadata=profile_meta):
					raw_text, actual_tokens = _do_generate()
			else:
				raw_text, actual_tokens = _do_generate()
			
			text = strip_hidden_thoughts(raw_text)
			
			# Cleanup
			text = _strip_page_prefix(text)
			text = self._sanitize_text(text)
			
			# Apply dynamic consistency (name and pronoun alias resolution)
			if step in {"story", "story_write", "narration", "dialogue", "scene"}:
				text = self._enforce_dynamic_consistency(text)

			if step in {"scene", "pose", "cover"}:
				text = self._compress_image_prompt_to_budget(step, text, extra_context=extra_context)
			
			# Validation
			is_valid, error_msg = self._validate_step_output(step, text, extra_context=extra_context)
			
			if is_valid:
				if step in {"story", "story_write"}:
					original_text = text
					repaired_text = self._apply_targeted_quality_repair(
						step,
						text,
						extra_context=extra_context,
					)
					if repaired_text != text:
						text = repaired_text
						is_valid, error_msg = self._validate_step_output(step, text, extra_context=extra_context)
						if not is_valid:
							self.logger.warning("[Step %s] Repaired output failed validation; restoring original draft.", step)
							text = original_text
							is_valid = True

				if step == "title":
					parsed_title = self._extract_title_candidate(text)
					if parsed_title:
						text = json.dumps({"title": parsed_title}, ensure_ascii=False, indent=2)

				# Success
				step_elapsed = time.perf_counter() - step_start
				self.logger.info(
					"[Step %s] completed in %.2fs, generated %s tokens",
					step, step_elapsed, actual_tokens
				)
				
				write_text_or_raise(output_path, text)
				step_record = {
					"step": step,
					"duration_sec": round(step_elapsed, 6),
					"generated_tokens": actual_tokens,
					"output_chars": len(text),
					"prompt_chars": total_chars,
					"page_number": extra_context.get("page_number") if extra_context else None,
					"temperature": params.temperature,
					"max_tokens": params.max_tokens,
					"min_tokens": params.min_tokens,
					"retries": current_try
				}
				self.step_history.append(step_record)
				return text
			
			# Failure handling
			current_try += 1
			last_error = error_msg
			self.logger.warning("[Step %s] Validation failed (Try %d): %s", step, current_try, error_msg)
			rejected_preview = " ".join((text or "").split())
			if rejected_preview:
				if len(rejected_preview) > 220:
					rejected_preview = f"{rejected_preview[:220]}..."
				self.logger.warning("[Step %s] Rejected output preview: %s", step, rejected_preview)
			
			if current_try <= max_retries:
				# Append error instruction to prompt for next try
				retry_guidance = self._build_step_retry_instruction(step, extra_context, error_msg or "")
				current_user_prompt = (
					f"{user_prompt}\n\nprevious_output: {text}\n\nSYSTEM_FEEDBACK: {error_msg}\n"
					f"{retry_guidance}\nPlease retry and fix the issue."
				)
		
		# If all retries failed, raise error instead of saving garbage
		self.logger.error("[Step %s] Failed all %d retries. Aborting generation. Error: %s", step, max_retries, last_error)
		raise GenerationAbortedError(f"Step {step} failed after {max_retries} retries: {last_error}")



	def _determine_primary_characters(self) -> List[str]:
		payload = (self.inputs.kg_payload or {}).get("characters") or []
		names: List[str] = []
		for item in payload:
			if isinstance(item, str):
				name = item.split("(")[0].strip()
				if name:
					names.append(name)
			elif isinstance(item, dict):
				label = item.get("label") or ""
				if label:
					names.append(str(label).strip())
			if len(names) >= 3:
				break
		
		# 使用 fallback 補足至 3 人，並確保不重複
		fallback = ["Emma", "Grandpa Tom", "Alex"]
		for fb_name in fallback:
			if len(names) >= 3:
				break
			# 簡單的去重檢查 (case-insensitive)
			if not any(fb_name.lower() == n.lower() for n in names):
				names.append(fb_name)
				
		# 如果還是不足 3 人 (極端情況)，補 generic 名稱
		while len(names) < 3:
			names.append(f"Friend {len(names)+1}")
			
		return names[:3]

	def _format_story_variations(self) -> str:
		selected = (self.inputs.kg_payload or {}).get("selected_variations") or {}
		if not isinstance(selected, dict):
			return ""
		parts = []
		for key, value in selected.items():
			if isinstance(value, dict):
				label = value.get("label") or value.get("description")
				if label:
					parts.append(f"{key.title()}: {label}")
			elif value:
				parts.append(f"{key.title()}: {value}")
		return " | ".join(parts)
	
	def _format_character_descriptions(self) -> str:
		"""格式化角色描述供封面提示使用。"""
		characters = self.primary_characters
		if not characters:
			return ""
		# 簡單格式：列出角色名稱
		return ", ".join(characters)

	def _build_image_character_descriptions(self) -> str:
		"""Build concise character descriptors for cover and illustration prompts."""
		payload = (self.inputs.kg_payload or {}).get("characters") or []
		descriptors: List[str] = []
		seen: Set[str] = set()
		for item in payload:
			label = ""
			role = ""
			description = ""
			if isinstance(item, str):
				label = re.sub(r"\s+", " ", item).strip()
			elif isinstance(item, dict):
				label = str(item.get("label") or item.get("name") or "").strip()
				role = str(item.get("role") or item.get("type") or "").strip()
				description = str(item.get("description") or item.get("appearance") or "").strip()
			if not label:
				continue
			parts = [label]
			extra_bits = [bit for bit in [role, description] if bit]
			if extra_bits:
				parts.append(f"({'; '.join(extra_bits[:2])})")
			entry = " ".join(parts).strip()
			key = entry.casefold()
			if key in seen:
				continue
			seen.add(key)
			descriptors.append(entry)
			if len(descriptors) >= 4:
				break
		if descriptors:
			return ", ".join(descriptors)
		return ", ".join(self.primary_characters)

	def _target_word_bounds(self, page_num: Optional[int] = None) -> Tuple[int, int]:
		"""Return word bounds based on page type and age group from KG."""
		age_value = self.profile.age_value if self.profile else 5
		
		# Get word ranges from KG
		if self.kg:
			word_ranges = self.kg.get_word_ranges(age_value)
			layout_config = self.kg.get_layout_config(age_value)
			
			# Age 2-3: lightweight throughout
			if age_value <= 3:
				return word_ranges.get("narrative", (50, 80))
			
			# Age 4-5 and 6-7: differentiate by page type
			if page_num and layout_config:
				# Use detected turning point if available
				turning_point = self.base_context.get("detected_turning_point") or layout_config.get("turning_point_page", 4)
				if turning_point > 0 and page_num == turning_point:
					# Turning point page
					return word_ranges.get("turning_point", (120, 160))
				elif turning_point > 0 and page_num > turning_point:
					# Post-branch pages
					return word_ranges.get("post_branch", (100, 140))
			
			# Default: lightweight narrative
			return word_ranges.get("narrative", (60, 100))
		
		# Fallback if no KG
		if age_value <= 3:
			return (50, 80)
		return (60, 100)

	def _total_pages(self) -> int:
		"""Single source of truth for total pages."""
		if self.profile and self.profile.layout:
			return self.profile.layout.total_pages
		return max(1, int(self.options.pages_expected or 1))

	def _image_style_lock(self) -> str:
		visual = (self.age_policy.get("visual_style") or "").strip()
		age_label = (self.inputs.age_group or self.profile.age_label or "").strip()
		category = (self.inputs.category or self.profile.category_label or "storybook").strip().lower()
		age_anchor = {
			"2-3": "simple shapes, large readable faces, minimal clutter",
			"4-5": "warm gouache watercolor texture, cozy palette, clear expressions",
			"6-8": "richer environmental detail, luminous atmosphere, readable action",
		}.get(age_label, "warm storybook rendering, readable faces, gentle painterly texture")
		category_anchor = {
			"adventure": "sense of discovery, luminous paths, clear focal landmarks",
			"educational": "grounded props, warm domestic or outdoor realism, gentle clarity",
			"fun": "playful poses, brighter accents, energetic but readable staging",
			"cultural": "grounded setting detail, respectful motifs, warm ceremonial color cues",
		}.get(category, "clear picture-book staging and cohesive palettes")
		style_parts: List[str] = []
		if visual:
			style_parts.append(visual)
		style_parts.extend(
			[
				"warm storybook gouache illustration",
				age_anchor,
				category_anchor,
				"clean silhouettes, readable faces and hands, layered foreground midground background, child-safe mood",
			]
		)
		seen: Set[str] = set()
		deduped: List[str] = []
		for part in style_parts:
			text = re.sub(r"\s+", " ", part).strip(" ,.")
			if not text:
				continue
			key = text.casefold()
			if key in seen:
				continue
			seen.add(key)
			deduped.append(text)
		result = ", ".join(deduped)
		if len(result) > 220:
			result = result[:217].rstrip(",;:.") + "..."
		return result
		"""構建圖像風格鎖定描述，確保簡潔且無重複。"""
		visual = (self.age_policy.get("visual_style") or "").strip()
		# prompt_guidelines now contains text-based rules and KG summary, not suitable for image style.
		# So we ignore it here to avoid polluting the image prompt.
		
		# 如果已有 visual_style，直接使用（它已經包含了年齡組特定的風格描述）
		# 否則使用簡潔的默認描述
		if visual:
			style_parts = [visual]
		else:
			category = (self.inputs.category or "storybook").strip()
			style_parts = [f"Consistent {category} picture-book style with soft lighting and cohesive palettes."]
		
		result = " ".join(style_parts).strip()
		# 限制總長度在 150 字符以內
		if len(result) > 150:
			result = result[:147] + "..."
		return result

	def _extract_turning_point_from_outline(self, outline: str) -> int:
		"""Extract turning point page number from outline [TURNING_POINT] marker."""
		for line in outline.splitlines():
			line = line.strip()
			if "[TURNING_POINT]" in line:
				match = re.match(r"^(\d+)\.", line)
				if match:
					page_num = int(match.group(1))
					self.logger.info(f"Detected turning point from outline: Page {page_num}")
					return page_num
		
		# Fallback: use layout config default
		layout_config = self.kg.get_layout_config(self.profile.age_value if self.profile else 5) if self.kg else {}
		default = layout_config.get("turning_point_page", 4)
		self.logger.info(f"No turning point marker found in outline, using default: Page {default}")
		return default
	
	def _extract_outline_events(self, outline: str) -> List[str]:
		"""從大綱抽取每頁事件。

		優先支援標準格式：
		1. ...\n2. ...\n（由 A2 outline prompt 要求）

		若模型輸出不符合格式（例如整段摘要），則使用句子切分作為備援，
		避免後續 pages 全部退化成同一個 theme。
		"""
		events: List[str] = []
		for line in outline.splitlines():
			line = line.strip()
			if not line:
				continue
			# Clean markdown bolding like **1. Event**
			line = line.replace("**", "").replace("__", "")
			match = re.match(r"^\d+\.\s*(.+)", line)
			if match:
				events.append(match.group(1).strip())

		# [FIX] Handle case where _sanitize_text squashed newlines into spaces
		# e.g. "1. Event A. 2. Event B."
		if len(events) == 1 and "2." in events[0]:
			raw_text = outline.replace("**", "").replace("__", "")
			# Regex to find "N. Content" patterns
			# We look for a digit, a dot, a space, content, and then either another digit-dot-space or end of string
			matches = re.findall(r"(\d+)\.\s+(.*?)(?=\s+\d+\.\s+|$)", raw_text)
			if len(matches) > 1:
				# Sort by the number to ensure order
				matches.sort(key=lambda x: int(x[0]))
				events = [m[1].strip() for m in matches]
				return events

		if events:
			return events

		# Fallback: treat outline as a paragraph summary.
		sentences = [_strip_page_prefix(s) for s in split_sentences(outline) if s.strip()]
		if not sentences:
			return []
		pages_expected = self._total_pages()
		if len(sentences) >= pages_expected:
			return sentences[:pages_expected]
		return sentences + [sentences[-1]] * (pages_expected - len(sentences))

	def _enforce_name_consistency(self, text: str) -> str:
		"""以確定性規則修正常見的人名黏連/變體（作為 LLM refinement 的保底）。"""
		return enforce_name_consistency(text, self.primary_characters)

	def _build_story_context(self, events: Sequence[str], idx: int, previous_pages: Optional[List[str]] = None) -> str:
		"""構建精簡的故事上下文，包含事件提示與目前為止的完整故事內容。"""
		parts: List[str] = []
		
		# [Multi-Branch Update] 使用 _read_page_content 獲取跨分支的歷史內容
		# 獲取前幾頁內容作為上下文 (最多回溯 3 頁)
		history_lines = []
		start_lookback = max(1, idx - 3)
		for i in range(start_lookback, idx):
			# 優先嘗試讀取已生成的檔案
			content = self._read_page_content(i)
			if content:
				# 簡單清理：移除可能的 Page X 標頭
				text = _strip_page_prefix(content)
				history_lines.append(f"Page {i}: {text}")
			elif previous_pages and (i - 1 < len(previous_pages)):
				# Fallback to provided previous_pages list if file read failed (e.g. in-memory only)
				# 注意：previous_pages index 0 是 Page 1
				try:
					text = _strip_page_prefix(previous_pages[i-1])
					history_lines.append(f"Page {i}: {text}")
				except IndexError:
					pass

		if history_lines:
			parts.append("Previous Context:")
			parts.extend(history_lines)
		
		# 添加事件上下文
		# 確保即使大綱事件少於頁數也不會崩潰
		safe_idx = min(idx - 1, len(events) - 1)
		
		if idx > 1:
			prev_idx = min(idx - 2, len(events) - 1)
			if prev_idx >= 0:
				parts.append(f"Previous event: {events[prev_idx]}")
		
		parts.append(f"CURRENT GOAL (Page {idx}): {events[safe_idx]}")
		
		if idx < len(events):
			parts.append(f"Upcoming event: {events[idx]}")
		
		return "\n".join(parts) if parts else "Continue the adventure in English."

	def _check_repetition(self, new_text: str, history: List[str], threshold: float = 0.70) -> bool:
		"""檢查新生成的文本是否與之前的頁面過於相似 (Anti-Looping)。"""
		if not history or not new_text or len(new_text) < 50:
			return False
			
		# 只檢查最近 2 頁，避免誤殺 (例如回呼開頭)
		recent_history = history[-2:]
		
		for i, prev_text in enumerate(recent_history):
			# 計算相似度
			ratio = difflib.SequenceMatcher(None, new_text, prev_text).ratio()
			if ratio > threshold:
				self.logger.warning(f"⚠️ Loop detected! Similarity {ratio:.2f} with previous page {len(history)-len(recent_history)+i+1}. Text: {new_text[:30]}...")
				return True
		return False


	def _generate_story_pages(
		self, 
		outline: str, 
		title: str, 
		start_page_override: Optional[int] = None,
		end_page_limit: Optional[int] = None
	) -> Tuple[List[str], str]:
		"""
		生成故事頁面內容的核心迴圈。
		Args:
			start_page_override: 若設定，則強制從此頁碼開始生成 (例如分支的分歧點+1)。
			end_page_limit: 若設定，則在此頁碼結束生成 (包含此頁)。
		"""
		# Determine strict start/end range
		current_branch = self.file_manager.current_branch
		branch_info = self.branches.get(current_branch)
		
		start_page, end_page = resolve_page_range(
			existing_page_numbers=list(self.file_manager.pages.keys()),
			total_pages=self._total_pages(),
			start_page_override=start_page_override,
			end_page_limit=end_page_limit,
		)
			
		if start_page > end_page:
			self.logger.info(f"Skipping generation: start {start_page} > end {end_page}")
			# Return existing content for these pages if available
			all_texts = []
			for p in range(1, end_page + 1):
				if p in self.file_manager.pages:
					all_texts.append(self.file_manager.pages[p].content)
			return all_texts, "\n".join(all_texts)

		self.logger.info(
			"Generating pages %d to %d for branch '%s'",
			start_page, end_page, current_branch
		)
		
		events = self._extract_outline_events(outline)
		if not events:
			events = [self.inputs.theme or "the adventure"] * self._total_pages()
		pages = preload_existing_pages(
			start_page=start_page,
			read_page_content=self._read_page_content,
			sanitize_text=self._sanitize_text,
		)
		
		for idx in range(start_page, end_page + 1):
			event = events[min(idx - 1, len(events) - 1)]
			page_structure = self._build_page_structure(idx)
			min_words, max_words = self._target_word_bounds(idx)
			self._write_page_structure(idx, page_structure)
			decision_options_text = format_decision_options(page_structure)
			
			# --- 4. Branch & Interaction Context Injection ---
			# Use the rigid Interaction Plan from Profile
			
			smart_ctx = self._build_story_context(events, idx, pages if pages else None)
			plan_smart_ctx = smart_ctx
			write_smart_ctx = smart_ctx

			# Inject branch intent context for planning only
			branch_type = self.base_context.get("branch_type")
			branch_desc = self.base_context.get("branch_desc")
			if branch_type and branch_desc:
				plan_smart_ctx += (
					f"\n\n[SYSTEM: BRANCH INTENT]\n"
					f"Intent: {branch_type}\n"
					f"Directive: {branch_desc}\n"
					f"Reflect this intent through actions and consequences. Do NOT name the trait explicitly."
				)
			
			# STRICT FORMATTING DIRECTIVE
			strict_total = self._total_pages()
			
			smart_ctx += (
				f"\n\n[SYSTEM: STRICT FORMAT]\n"
				f"Do NOT include page headers like 'Page {idx}:'.\n"
				f"This is Page {idx} of {strict_total}.\n"
				f"Write only this single page. Do NOT combine pages."
			)

			# Inject Interaction Slot directives
			if self.profile.interaction_plan and (idx - 1) < len(self.profile.interaction_plan):
				slot = self.profile.interaction_plan[idx - 1]
				
				if slot.kind == "decision":
					plan_smart_ctx += (
						f"\n\n[SYSTEM: INTERACTION PAGE (BRANCH TRIGGER)]\n{slot.directive}\n"
						f"Embed possible actions naturally in the story flow. Do NOT list options or use UI/choice language."
					)
					write_smart_ctx += (
						f"\n\n[SYSTEM: INTERACTION PAGE (BRANCH TRIGGER)]\n{slot.directive}\n"
						f"Embed action affordances in prose only. Do NOT list options, do NOT use labels like 'Option 1', and do NOT break narrative flow."
					)
				elif slot.kind == "action":
					smart_ctx += f"\n\n[SYSTEM: INTERACTION PAGE (Action)]\n{slot.directive}\nEncourage physical movement or help."
				elif slot.kind == "reflection":
					smart_ctx += f"\n\n[SYSTEM: REFLECTION PAGE]\n{slot.directive}"

			# Force immediate divergence after decision
			if self.profile and self.profile.layout and self.profile.layout.branch_count > 0:
				if idx == (self.profile.layout.decision_page + 1):
					plan_smart_ctx += (
						"\n\n[SYSTEM: IMMEDIATE DIVERGENCE]\n"
						"This page MUST show a clear, observable divergence in action and state\n"
						"based on the branch intent. Do NOT just change wording."
					)
				
				# Narrator style injection for narrative pages in branches
				if self.base_context.get("branch_style"):
					# Fallback style injection if not covered by slot directive
					pass
			
			# Ending pages should resolve without structural markers
			# Previous Context Logic
			# (Removed legacy bridge/ending_guidance variables)

			base_context = {
				"outline": outline,
				"title": title,
				"page_num": idx,
				"total_pages": strict_total,
				"current_event": event,
				"min_words": min_words,
				"max_words": max_words,
				"age": self.inputs.age_group or self.profile.age_label,
				"theme": self.profile.theme_label if self.profile else self.inputs.theme,
				"main_category": self.profile.category_label if self.profile else self.inputs.category,
				"kg_guidelines": self.effective_guidelines,
				"detected_turning_point": self.base_context.get("detected_turning_point", 4),
				# [CRITICAL FIX] Initialize system_announcement and system_core_assumptions
				"system_core_assumptions": self.kg.SYSTEM_CORE_ASSUMPTIONS if self.kg else "",
				"system_announcement": "",  # Will be populated conditionally below
				# [CRITICAL FIX 2] Propagate convergence variables from self.base_context to local context
				"converge_ending": self.base_context.get("converge_ending", False),
				"branch_end_page": self.base_context.get("branch_end_page"),
				"convergence_anchor": self.base_context.get("convergence_anchor", "a gentle resolution"),
				"ending_start": self.base_context.get("ending_start"),
				"ending_end": self.base_context.get("ending_end"),
				# "bridge_instruction": bridge_instruction, # [REMOVED] Legacy variable
			}
			base_context.update(self._build_visual_prompt_context(idx, event, page_structure))
			
			# Final page rule: no new plot elements, resolve existing threads
			is_final_page = idx == strict_total or page_structure.get("page_function") == "REFLECTION"
			if is_final_page:
				category_label = (self.profile.category_label if self.profile else self.inputs.category) or ""
				final_rule = (
					"CRITIQUE: Final page only. Do NOT introduce new characters, objects, or plot threads. "
					"Resolve existing events and close gently."
				)
				if category_label.lower() == "educational":
					final_rule += " Reinforce the learning theme through actions/consequences (no explicit moral statements)."
				if base_context.get("system_announcement"):
					base_context["system_announcement"] += "\n\n" + final_rule
				else:
					base_context["system_announcement"] = final_rule
			
			# Convergence handoff: force the last branch-specific page to lead into shared ending
			# Use values already populated in base_context (from self.base_context)
			converge_ending = base_context.get("converge_ending", False)
			branch_end_page = base_context.get("branch_end_page")
			convergence_anchor = base_context.get("convergence_anchor", "a gentle resolution")
			if converge_ending and branch_end_page and idx == branch_end_page:
				branch_end_msg = (
					"CRITIQUE: This is the FINAL branch-specific page. "
					"End this page by clearly leading into the shared resolution. "
					f"Convergence anchor: {convergence_anchor}. "
					"Do NOT introduce new branch-only elements or unresolved threads."
				)
				if base_context.get("system_announcement"):
					base_context["system_announcement"] += "\n\n" + branch_end_msg
				else:
					base_context["system_announcement"] = branch_end_msg
			
			# Converging ending pages: same event, different wording
			# Use values already populated in base_context
			ending_start = base_context.get("ending_start")
			ending_end = base_context.get("ending_end")
			if converge_ending and ending_start and ending_end and ending_start <= idx <= ending_end:
				if idx == ending_start:
					# [SCIENTIFIC ADJUSTMENT]
					# To ensure convergence, we must manage the transition from divergent context
					# to the shared anchor. The prompt must explicitly instruct the planner/writer
					# to resolve the branch-specific thread first.
					critique_msg = (
						"CRITIQUE [CONVERGENCE STEP 1/2]: "
						f"You are writing Page {idx}, the BRIDGE page. "
						"1. OPEN by quickly resolving the specific action from the previous page (1 sentence). "
						f"2. TRANSITION all characters to the shared outcome: '{convergence_anchor}'. "
						"3. The page MUST END with the characters united in this shared state. "
						"Ignore any branch-specific loose ends that cannot be resolved quickly."
					)
					if base_context.get("system_announcement"):
						base_context["system_announcement"] += "\n\n" + critique_msg
					else:
						base_context["system_announcement"] = critique_msg
					self.logger.info(f"[Page {idx}] Convergence directive (Start): {critique_msg[:80]}...")
				else:
					critique_msg = (
						"CRITIQUE [CONVERGENCE STEP 2/2]: "
						"Final Reflection. "
						f"Focus solely on the shared finding: '{convergence_anchor}'. "
						"Do NOT reference branch-specific hazards/items anymore. "
						"Bring the story to a unified close."
					)
					if base_context.get("system_announcement"):
						base_context["system_announcement"] += "\n\n" + critique_msg
					else:
						base_context["system_announcement"] = critique_msg
					self.logger.info(f"[Page {idx}] Convergence directive (End): {critique_msg[:80]}...")
			
			# Stage 1: Plan
			plan_file = self.paths["story"].parent / f"page_{idx}_plan.txt"
			plan_text = ""
			state_snapshot = None
			plan_context = dict(base_context)
			plan_context["smart_context"] = plan_smart_ctx
			plan_context["page_structure"] = json.dumps(page_structure, ensure_ascii=False)
			plan_context["branch_context"] = f"Branch: {self.current_branch_id}" if self.current_branch_id else "Linear Path"
			# [DEBUG LOG] Track if system_announcement is set for this page
			if plan_context.get("system_announcement"):
				self.logger.info(f"[Page {idx}] Plan context includes announcement: {plan_context['system_announcement'][:60]}...")
			max_plan_retries = 2
			for plan_try in range(1, max_plan_retries + 1):
				plan_text = self._run_single_step("story_plan", plan_context, plan_file)
				state_snapshot = self._extract_state_snapshot(plan_text)
				if state_snapshot:
					break
				self.logger.warning(f"[Page {idx}] Missing <state_json> in plan (Try {plan_try}/{max_plan_retries}). Retrying...")
				system_assumptions = self.kg.SYSTEM_CORE_ASSUMPTIONS if self.kg else ""
				retry_msg = "CRITIQUE: You must output BOTH <plan> and <state_json> blocks. Return <state_json> with the required JSON fields."
				append_system_announcement(
					plan_context,
					retry_msg,
					system_assumptions=system_assumptions,
				)

			if not state_snapshot:
				self.logger.error(f"[Page {idx}] Missing <state_json> after retries. Using structural fallback.")
				state_snapshot = build_structural_fallback_state(event, page_structure)
			self._write_state_snapshot(idx, state_snapshot)
			
			# Stage 2: Write
			write_context = {
				**base_context,
				"smart_context": write_smart_ctx,
				"story_plan": plan_text,
				"state_snapshot": json.dumps(state_snapshot, ensure_ascii=False),
				"page_structure": json.dumps(page_structure, ensure_ascii=False),
				"branch_context": f"Branch: {self.current_branch_id}" if self.current_branch_id else "Linear Path",
			}
			write_context.update(self._build_visual_prompt_context(idx, event, page_structure, state_snapshot))
			# [DEBUG LOG] Track if system_announcement reaches write context
			if write_context.get("system_announcement"):
				self.logger.info(f"[Page {idx}] Write context includes announcement: {write_context['system_announcement'][:60]}...")
			
			# Anti-Looping Retry Logic
			max_dedup_retries = 2
			page_text = ""
			key_page_candidate_count = (
				max(1, int(getattr(self.options, "key_page_candidates", 1) or 1))
				if self._is_key_story_page(idx, page_structure)
				else 1
			)
			
			for dedup_try in range(max_dedup_retries):
				if key_page_candidate_count > 1:
					candidate_entries: List[Dict[str, Any]] = []
					for candidate_idx in range(key_page_candidate_count):
						candidate_path = self._page_file(idx).with_name(
							f"{self._page_file(idx).stem}__r{dedup_try + 1}_candidate_{candidate_idx + 1}{self._page_file(idx).suffix}"
						)
						candidate_text = self._run_single_step(
							"story_write",
							write_context,
							candidate_path,
							banned_phrases=["Page", "Page:", "Page-"],
						)
						scorecard = self._score_story_page_candidate(
							candidate_text,
							idx=idx,
							page_structure=page_structure,
							history=pages,
						)
						candidate_entries.append(
							{
								"path": candidate_path,
								"text": candidate_text,
								"scorecard": scorecard,
							}
						)
						self.logger.info(
							"[Page %d] candidate %d/%d score=%.2f issues=%s",
							idx,
							candidate_idx + 1,
							key_page_candidate_count,
							float(scorecard.get("score", 0.0)),
							scorecard.get("issues", []),
						)
					selected = max(candidate_entries, key=lambda item: float(item["scorecard"].get("score", 0.0)))
					page_text = str(selected["text"])
					self.step_history.append(
						{
							"step": "story_write_selection",
							"page_number": idx,
							"candidate_count": key_page_candidate_count,
							"selected_source": Path(str(selected["path"])).name,
							"selected_score": float(selected["scorecard"].get("score", 0.0)),
							"issues": list(selected["scorecard"].get("issues", [])),
						}
					)
				else:
					page_text = self._run_single_step(
						"story_write", 
						write_context, 
						self._page_file(idx),
						banned_phrases=["Page", "Page:", "Page-"]
					)

				# Ensure no explicit option lists appear on interaction/branch-trigger pages
				if page_structure.get("branch_trigger"):
					if "Option 1" in page_text or "Option 2" in page_text:
						self.logger.warning(f"[Page {idx}] Explicit option list detected. Prompting for embedded actions.")
						retry_msg = "CRITIQUE: Do NOT list options or use labels like 'Option 1'. Embed action affordances in prose only."
						append_system_announcement(
							write_context,
							retry_msg,
							system_assumptions=self.kg.SYSTEM_CORE_ASSUMPTIONS if self.kg else "",
						)
						continue

				if not self._check_repetition(page_text, pages):
					break
					
				self.logger.warning(f"[Page {idx}] Repetition detected (Try {dedup_try+1}/{max_dedup_retries}). Retrying...")
				retry_msg = "CRITIQUE: The previous draft was too similar to the last page. WRITE SOMETHING NEW AND DIFFERENT."
				append_system_announcement(write_context, retry_msg)

			# Persist final page text (including any appended decision options)
			write_text_or_raise(self._page_file(idx), page_text)
			pages.append(page_text.strip())
			
			if self.options.aggressive_memory_cleanup and torch.cuda.is_available():
				cleanup_torch()
			
			# [Multi-Branch] Append Convergence Content (Post-Generation)
			# If this branch ends early (at convergence point), we must append the shared ending pages 
			# so that full_story.txt and downstream derivations have the complete story.
			# [Multi-Branch] Convergence Logic REMOVED.
			# Requirement: "Each branch will have its own unique ending state."
			# No appending of shared content.
			pass

		# END of page generation loop - now compile full story
		combined = finalize_story_pages(self.paths["story"], self.paths["full_story"], pages)
		return pages, combined


	def _build_meta(
		self,
		outline: str,
		title: str,
		generated_branches_ids: List[str],
		# Optional args for legacy compatibility or if we want to pass specific stats
		# But with multi-branch, exact page/token counts are complex to aggregate here.
		# We will aggregate what we can.
	) -> Dict[str, Any]:
		"""整理整本書的統計/檔案位置，作為後續模組依據。"""
		meta = build_story_meta(
			story_id=self.story_id,
			story_title=self.story_title,
			relative_path=self.relative_path,
			inputs=self.inputs,
			options=self.options,
			profile=self.profile,
			generated_branches_ids=generated_branches_ids,
			start_time=self.start_time if hasattr(self, "start_time") else 0,
		)
		persist_story_meta(self.file_manager.language_root, meta)
		return meta
if __name__ == "__main__":
	cli()
