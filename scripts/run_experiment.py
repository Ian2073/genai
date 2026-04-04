import argparse
import hashlib
import json
import logging
import sys
import time
import re
import warnings
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Dict, Any, List, Optional

import torch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

warnings.filterwarnings(
    "ignore",
    message=r".*_is_quantized_training_enabled.*deprecated.*",
    category=FutureWarning,
)

from utils import (
    ProjectPaths,
    get_story_kg,
    build_story_profile,
    _format_label,
)
from story import (
    StoryInput,
    format_list,
    PipelineOptions,
    StoryPipeline,
    _apply_default_step_generations,
)
from backends.llm import BaseLLM, GenerationParams, LLMConfig, build_llm
from prompts.prompt_utils import ChatPrompt, _load_chat_sections, render_prompt


def setup_experiment_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("experiment")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    
    if not logger.handlers:
        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
        logger.addHandler(console)
        
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
        logger.addHandler(file_handler)
        
    return logger


def _build_compatible_pipeline_options(**candidate_kwargs) -> PipelineOptions:
    """建立與當前 `PipelineOptions` 定義相容的參數，忽略未知欄位。"""
    valid_fields = {f.name for f in fields(PipelineOptions)}
    filtered = {k: v for k, v in candidate_kwargs.items() if k in valid_fields}
    return PipelineOptions(**filtered)


def _reset_generation_seed(llm: BaseLLM, seed: int) -> None:
    """在每個 group 執行前重置隨機狀態，避免執行順序干擾公平性。"""
    import random

    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(llm, "set_seed"):
        llm.set_seed(seed)


def _count_words(text: str) -> int:
    """以空白切詞估算字數，供跨組公平比較使用。"""
    if not text:
        return 0
    return len(re.findall(r"\S+", text))


def _truncate_to_words(text: str, target_words: int) -> str:
    """將文本截斷到指定字數，避免長度差異干擾一致性比較。"""
    if target_words <= 0:
        return ""
    words = re.findall(r"\S+", text or "")
    if len(words) <= target_words:
        return text
    clipped_words = words[:target_words]
    return " ".join(clipped_words)


def _build_prompt_audit(prompts_payload: Dict[str, Any]) -> Dict[str, Any]:
    """建立 prompt 稽核摘要（字數、雜湊、關鍵標記）。"""
    prompt_texts: List[str] = []
    prompt_files: List[str] = []
    for key, value in prompts_payload.items():
        if isinstance(value, dict):
            system_prompt = str(value.get("system_prompt", ""))
            user_prompt = str(value.get("user_prompt", ""))
            raw_text = str(value.get("raw_text", ""))
            merged = "\n".join([system_prompt, user_prompt, raw_text]).strip()
            if merged:
                prompt_texts.append(merged)
                prompt_files.append(str(key))
    merged_prompt_text = "\n\n".join(prompt_texts)
    markers = [
        "CHARACTER REFERENCE CARD",
        "Knowledge Graph",
        "branch_slots",
        "pronouns consistently",
    ]
    marker_hits: Dict[str, int] = {}
    for marker in markers:
        marker_hits[marker] = merged_prompt_text.count(marker)
    return {
        "prompt_files": prompt_files,
        "prompt_count": len(prompt_texts),
        "prompt_words": _count_words(merged_prompt_text),
        "prompt_sha256": hashlib.sha256(merged_prompt_text.encode("utf-8")).hexdigest() if merged_prompt_text else "",
        "marker_hits": marker_hits,
    }


def _prepare_fair_evaluation_views(case_dir: Path, logger: logging.Logger) -> Dict[str, Any]:
    """為同一 case 的三組建立等長評估文本 `story_for_eval.txt`。"""
    groups = ["G0", "G1", "G2"]
    stories: Dict[str, str] = {}
    word_counts: Dict[str, int] = {}
    for group in groups:
        story_path = case_dir / group / "story.txt"
        if not story_path.exists():
            raise FileNotFoundError(f"Missing story for fairness prep: {story_path}")
        story_text = story_path.read_text(encoding="utf-8")
        stories[group] = story_text
        word_counts[group] = _count_words(story_text)

    common_eval_words = min(word_counts.values()) if word_counts else 0
    for group in groups:
        eval_text = _truncate_to_words(stories[group], common_eval_words)
        eval_path = case_dir / group / "story_for_eval.txt"
        eval_path.write_text(eval_text, encoding="utf-8")

    max_words = max(word_counts.values()) if word_counts else 0
    min_words = common_eval_words
    ratio = (max_words / max(1, min_words)) if min_words else 0.0
    fairness = {
        "word_counts_story_txt": word_counts,
        "common_eval_words": common_eval_words,
        "max_to_min_word_ratio": round(ratio, 4),
        "story_for_eval_note": "All groups truncated to the same word count for fair consistency comparison.",
    }
    logger.info(
        "[Fairness] word counts=%s, common_eval_words=%s, max/min ratio=%.3f",
        word_counts,
        common_eval_words,
        ratio,
    )
    return fairness


def _build_g2_consistency_step_generations(base: GenerationParams) -> Dict[str, GenerationParams]:
    """Build a lower-variance step map for G2 to improve consistency metrics robustness."""
    step_map = _apply_default_step_generations(base, {})

    def _override(step: str, **kwargs: Any) -> None:
        current = step_map.get(step, base)
        step_map[step] = replace(current, **kwargs)

    # Ambiguity-control profile: reduce referential drift without intentionally shrinking output length.
    _override(
        "outline",
        temperature=0.16,
        top_p=0.84,
        top_k=24,
        repetition_penalty=max(step_map["outline"].repetition_penalty, 1.12),
    )
    _override(
        "story_plan",
        max_tokens=min(max(step_map["story_plan"].max_tokens, 320), 520),
        min_tokens=max(step_map["story_plan"].min_tokens, 80),
        temperature=0.24,
        top_p=0.84,
        top_k=24,
        repetition_penalty=max(step_map["story_plan"].repetition_penalty, 1.14),
    )
    _override(
        "story_write",
        max_tokens=min(max(step_map["story_write"].max_tokens, 460), 820),
        min_tokens=max(step_map["story_write"].min_tokens, 110),
        temperature=0.30,
        top_p=0.82,
        top_k=24,
        repetition_penalty=max(step_map["story_write"].repetition_penalty, 1.18),
        no_repeat_ngram_size=4,
    )
    return step_map


# --- BASELINE G0/G1 PIPELINE CLASSES ---

@dataclass
class BaselinePipelineOptions:
    pages_expected: int
    generation: GenerationParams
    model_name: str
    seed: int = 42
    no_kg: bool = False

class BaselineStoryPipeline:
    def __init__(
        self,
        inputs: StoryInput,
        output_dir: Path,
        llm: BaseLLM,
        options: BaselinePipelineOptions,
        logger: logging.Logger,
    ):
        self.inputs = inputs
        self.output_dir = output_dir
        self.llm = llm
        self.options = options
        self.logger = logger
        self.profile = inputs.kg_profile
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.primary_characters = self._determine_primary_characters() if not options.no_kg else []
        characters_csv = self._build_characters_csv_with_attributes() if not options.no_kg else ""
        
        self.base_context = {
            "language": inputs.language,
            "age_group": inputs.age_group,
            "category": inputs.category,
            "subcategory": inputs.subcategory,
            "theme": inputs.theme,
            "kg_characters": format_list((inputs.kg_payload or {}).get("characters")) if not options.no_kg else "",
            "kg_scenes": format_list((inputs.kg_payload or {}).get("scenes")) if not options.no_kg else "",
            "kg_moral": (inputs.kg_payload or {}).get("moral", "") if not options.no_kg else "",
            "kg_guidelines": self.profile.prompt_guidelines if (self.profile and not options.no_kg) else "",
            "character1": self.primary_characters[0] if self.primary_characters else "Protagonist",
            "characters_csv": characters_csv,
            "pages_expected": self.options.pages_expected
        }
        
        self.prompts_used = {}
        
    def _determine_primary_characters(self) -> List[str]:
        if not self.profile or not self.profile.kg_payload:
            return []
        chars = self.profile.kg_payload.get("characters", [])
        return [c.split(":")[0].strip() for c in chars if ":" in c][:3]
        
    def _build_characters_csv_with_attributes(self) -> str:
        if not self.profile or not self.profile.kg_payload:
            return ""
        chars = self.profile.kg_payload.get("characters", [])
        return "\n".join([f"- {c}" for c in chars])

    def _run_llm(self, prompt_file: str, context: Dict[str, Any], params: GenerationParams, step_name: str) -> str:
        prompt_path = Path("prompts") / prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Missing baseline prompt template: {prompt_path}")
            
        system_tmpl, user_tmpl = _load_chat_sections(str(prompt_path))
        
        system_prompt = render_prompt(system_tmpl, context)
        user_prompt = render_prompt(user_tmpl, context)
        
        self.prompts_used[step_name] = {
            "template_file": prompt_file,
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
        
        prompt = ChatPrompt(system_prompt=system_prompt, user_prompt=user_prompt)
        text, _ = self.llm.generate(prompt, params)
        return text

    def run(self) -> None:
        group_label = "G0_noKG_freeform" if self.options.no_kg else "G1_KG_freeform"
        self.logger.info(f"=== Running Baseline Pipeline: {group_label} ===")
        
        # 1. Generate Outline (Aligned to generation params)
        outline_params = GenerationParams(
            max_tokens=800,
            min_tokens=50,
            temperature=self.options.generation.temperature,
            top_p=self.options.generation.top_p,
            top_k=self.options.generation.top_k,
            repetition_penalty=self.options.generation.repetition_penalty,
            no_repeat_ngram_size=None
        )
        
        outline_template = "baseline_outline_nokg.txt" if self.options.no_kg else "baseline_outline.txt"
        outline_text = self._run_llm(outline_template, self.base_context, outline_params, "outline")
        
        outline_path = self.output_dir / "outline.txt"
        outline_path.write_text(outline_text, encoding="utf-8")
        
        self.base_context["story_outline"] = outline_text
        
        # 2. Generate Full Story in one shot
        story_params = self.options.generation
        story_template = "baseline_story_nokg.txt" if self.options.no_kg else "baseline_story.txt"
        story_text = self._run_llm(story_template, self.base_context, story_params, "story")
        
        story_path = self.output_dir / "story.txt"
        story_path.write_text(story_text, encoding="utf-8")
        
        # 3. Output Prompts JSON
        prompts_path = self.output_dir / "prompts.json"
        with open(prompts_path, "w", encoding="utf-8") as f:
            json.dump(self.prompts_used, f, indent=2, ensure_ascii=False)
        
        # 4. Output Meta JSON
        meta = {
            "group_id": "G0" if self.options.no_kg else "G1",
            "kg_mode": "none" if self.options.no_kg else "kg",
            "pipeline": "freeform",
            "refinement": False,
            "outline_prompt_file": outline_template,
            "story_prompt_file": story_template,
            "generation_params": {
                "max_tokens": story_params.max_tokens,
                "temperature": story_params.temperature,
                "top_p": story_params.top_p,
                "top_k": story_params.top_k,
                "repetition_penalty": story_params.repetition_penalty
            }
        }
        
        meta_path = self.output_dir / "meta.json"
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2, ensure_ascii=False)


# --- MAIN ORCHESTRATOR ---

def main():
    parser = argparse.ArgumentParser(
        description="一鍵執行三組一致性實驗（只需指定案例數量）"
    )
    parser.add_argument(
        "-n",
        "--num",
        "--num_cases",
        dest="num_cases",
        type=int,
        default=1,
        help="要生成的 case 數量",
    )
    args = parser.parse_args()

    # 極簡模式：其餘參數全部固定在程式內建預設，避免每次手動帶 CLI。
    args.age = None
    args.category = None
    args.subcategory = None
    args.theme = None
    args.language = "en"
    args.model = "models/Qwen2.5-14B-Instruct-GPTQ-Int4"
    args.device = "auto"
    args.dtype = "float16"
    args.quantization = "gptq"
    args.pages = 8
    args.max_tokens = 2500
    args.temperature = 0.7
    args.top_p = 0.9
    args.top_k = 40
    args.repetition_penalty = 1.1
    args.seed = 42
    paths = ProjectPaths.discover()
    log_path = paths.logs_dir / f"experiment_run_{int(time.time())}.log"
    logger = setup_experiment_logger(log_path)
    
    # Load LLM Once Globally
    llm_config = LLMConfig(
        model_dir=args.model,
        device_map=args.device,
        dtype=args.dtype,
        seed=args.seed,
        quantization=args.quantization,
        use_sdpa=True
    )
    
    logger.info(f"Loading Global LLM from {args.model} ...")
    llm = build_llm(llm_config)
    
    try:
        # 使用更大的 seed 空間，並混入 run entropy，避免重跑時 case_id 重複
        import random as _seed_rng
        seed_min = 0
        seed_max = 9_999_999_999
        seed_space_size = seed_max - seed_min + 1
        if args.num_cases > seed_space_size:
            raise ValueError(f"num_cases={args.num_cases} exceeds seed space size={seed_space_size}")

        run_entropy = time.time_ns() & 0xFFFFFFFF
        _seed_rng.seed(f"{args.seed}:{args.num_cases}:{run_entropy}")
        experiment_seeds = sorted(_seed_rng.sample(range(seed_min, seed_max + 1), args.num_cases))
        logger.info(
            "Experiment seeds (%s cases, entropy=%s): %s",
            args.num_cases,
            run_entropy,
            experiment_seeds,
        )

        used_case_ids = set()
        
        success_cases = 0
        failed_cases = 0
        for i, current_seed in enumerate(experiment_seeds):
            logger.info(f"========== STARTING CASE {i+1}/{args.num_cases} (Seed: {current_seed}) ==========")
            
            try:
                _reset_generation_seed(llm, current_seed)
            
                # 1. Prepare Experiment Directories & Case ID
                kg = get_story_kg()
                
                profile = build_story_profile(
                    language=args.language,
                    age=args.age,
                    category=args.category,
                    subcategory=args.subcategory,
                    theme=args.theme,
                )
                
                theme_safe = profile.theme_label if profile.theme_label else "none"
                theme_hash = hashlib.md5(theme_safe.encode('utf-8')).hexdigest()[:6]
                safe_category = str(profile.category_label).replace(' ', '_')
                
                # 若遇到既有資料夾或同批次重複 case_id，則重抽 seed 直到唯一。
                while True:
                    case_id = f"{profile.language}_{profile.age_label}_{safe_category}_{theme_hash}_v{kg.KG_SCHEMA_VERSION}_{current_seed}"
                    # 直接輸出到 output/experiments/case_xxx，不再增加額外層級。
                    case_dir = paths.output_dir / "experiments" / f"case_{case_id}"
                    if case_id not in used_case_ids and not case_dir.exists():
                        used_case_ids.add(case_id)
                        break

                    old_seed = current_seed
                    current_seed = _seed_rng.randint(seed_min, seed_max)
                    logger.warning(
                        "Case ID collision detected for seed %s (dir: %s). Regenerated seed -> %s",
                        old_seed,
                        case_dir,
                        current_seed,
                    )
                
                case_dir.mkdir(parents=True, exist_ok=True)
                
                from utils import BranchLayout, PaceQuota
                if not profile.layout:
                    profile.layout = BranchLayout(
                        trunk_pages=range(1, args.pages+1),
                        decision_page=0,
                        branch_pages=range(0,0),
                        ending_pages=range(args.pages, args.pages+1),
                        total_pages=args.pages,
                        branch_count=0,
                        layout_id="linear_baseline",
                        description="Baseline Layout",
                        pacing="balanced",
                        pace_quota=PaceQuota(2,0,2,args.pages)
                    )
                        
                story_input = StoryInput(
                    language=profile.language,
                    age_group=profile.age_label,
                    category=profile.category_label,
                    subcategory=profile.subcategory_label,
                    theme=profile.theme_label,
                    kg_payload=profile.kg_payload,
                    kg_profile=profile
                )
                
                # 2. Write Shared Config
                shared_config = {
                    "case_id": case_id,
                    "language": args.language,
                    "age": args.age,
                    "category": args.category,
                    "theme": theme_safe,
                    "kg_version": kg.KG_SCHEMA_VERSION,
                    "pages_expected": args.pages,
                    "seed": current_seed,
                    "model_name": Path(args.model).name,
                    "generation_params": {
                        "max_tokens": args.max_tokens,
                        "temperature": args.temperature,
                        "top_p": args.top_p,
                        "top_k": args.top_k,
                        "repetition_penalty": args.repetition_penalty
                    },
                    "fairness_protocol": {
                        "same_model_for_all_groups": True,
                        "same_base_generation_params_for_all_groups": True,
                        "g2_structured_step_overrides_enabled": True,
                        "same_seed_for_all_groups": True,
                        "evaluation_uses_word_normalized_rates": True,
                        "evaluation_uses_equal_length_story_for_eval": True,
                        "g2_low_variance_profile": "v3_ambiguity_control_no_length_squeeze",
                    },
                }
                with open(case_dir / "config.json", "w", encoding="utf-8") as f:
                    json.dump(shared_config, f, indent=2, ensure_ascii=False)
                    
                base_generation = GenerationParams(
                    max_tokens=args.max_tokens,
                    min_tokens=100,
                    temperature=args.temperature,
                    top_p=args.top_p,
                    top_k=int(args.top_k),
                    repetition_penalty=args.repetition_penalty,
                    no_repeat_ngram_size=None
                )
                
                # ==========================================
                # GROUP 0: No KG, Free-form
                # ==========================================
                _reset_generation_seed(llm, current_seed)
                g0_dir = case_dir / "G0"
                g0_options = BaselinePipelineOptions(
                    pages_expected=args.pages,
                    generation=base_generation,
                    model_name=shared_config["model_name"],
                    seed=current_seed,
                    no_kg=True
                )
                g0_pipeline = BaselineStoryPipeline(story_input, g0_dir, llm, g0_options, logger)
                g0_pipeline.run()
                del g0_pipeline
                import gc
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
    
                # ==========================================
                # GROUP 1: KG, Free-form
                # ==========================================
                _reset_generation_seed(llm, current_seed)
                g1_dir = case_dir / "G1"
                g1_options = BaselinePipelineOptions(
                    pages_expected=args.pages,
                    generation=base_generation,
                    model_name=shared_config["model_name"],
                    seed=current_seed,
                    no_kg=False
                )
                g1_pipeline = BaselineStoryPipeline(story_input, g1_dir, llm, g1_options, logger)
                g1_pipeline.run()
                del g1_pipeline
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
    
                # ==========================================
                # GROUP 2: KG, Structured (Original Pipeline)
                # ==========================================
                _reset_generation_seed(llm, current_seed)
                g2_dir = case_dir / "G2"
                g2_dir.mkdir(parents=True, exist_ok=True)
                
                logger.info("=== Running Controlled Pipeline: G2 ===")
                
                from pipeline import generate_story_id, create_story_root
                from utils import build_story_relative_path
                
                sandbox_story_id = f"sandbox_G2_{current_seed}_{int(time.time())}"
                sandbox_rel = build_story_relative_path(profile, sandbox_story_id)
                sandbox_root = create_story_root(paths.output_dir, sandbox_rel, languages=[args.language])
                
                # Disable branching for the academic experiment to speed up G2 and ensure 
                # a direct apples-to-apples comparison with G0/G1 (which are linear).
                if profile.layout:
                    profile.layout.branch_count = 0
                    profile.layout.total_pages = args.pages
                    profile.layout.decision_page = args.pages
                    profile.layout.trunk_pages = range(1, args.pages + 1)
                    profile.layout.branch_pages = range(0, 0)
                    profile.layout.ending_pages = range(0, 0)
                    profile.layout.branch_slots = []
                
                step_generations = _build_g2_consistency_step_generations(base_generation)
                pipeline_options = _build_compatible_pipeline_options(
                    pages_expected=args.pages,
                    # Keep page length natural; control ambiguity via prompt + decoding, not hard length squeeze.
                    max_page_chars=1350,
                    max_page_sentences=9,
                    generation=base_generation,
                    model_name=shared_config["model_name"],
                    prompt_set="default",
                    cover_source="outline",
                    kg_enabled=True,
                    kg_version=profile.kg_version,
                    seed=current_seed,
                    step_generations=step_generations,
                    aggressive_memory_cleanup=False,
                    disable_category_temperature_adaptation=True,
                    use_summary_context=True,
                    enable_structured_constraints=True,
                    enable_entity_memory=True,
                    hybrid_quality_speed_mode=True,
                    hybrid_risk_threshold=0.9,
                )
                
                pipeline = StoryPipeline(
                    inputs=story_input,
                    story_id=sandbox_story_id,
                    relative_path=sandbox_rel,
                    output_root=paths.output_dir,
                    story_root=sandbox_root,
                    llm=llm,
                    options=pipeline_options,
                    logger=logger
                )
                
                # Monkey patch assets
                pipeline._generate_assets = lambda *args, **kwargs: None
                
                pipeline.run()
            
                # G2 Post-Processing: Find the actual branch folder dynamically
                import shutil
                # The sandbox_root may have been relocated by StoryPipeline based on the generated title
                actual_story_root = pipeline.story_root
                # Compatible with both legacy layout (.../story/<lang>/...) and current layout (.../<lang>/...)
                lang_dir_candidates = [
                    actual_story_root / "story" / args.language,
                    actual_story_root / args.language,
                ]
                lang_dir = next((p for p in lang_dir_candidates if p.exists()), lang_dir_candidates[0])

                story_path: Optional[Path] = None
                sandbox_outline: Optional[Path] = None
                raw_g2_text: Optional[str] = None
                branch_name = "option_1"

                search_roots: List[Path] = []
                if lang_dir.exists():
                    branches_root = lang_dir / "branches"
                    if branches_root.exists() and branches_root.is_dir():
                        canonical = branches_root / "option_1"
                        if canonical.exists() and canonical.is_dir():
                            search_roots.append(canonical)
                        for d in sorted(branches_root.iterdir(), key=lambda p: p.name):
                            if d.is_dir() and d not in search_roots:
                                search_roots.append(d)

                    # Legacy layouts that place branch folders directly under lang_dir
                    for d in sorted(lang_dir.iterdir(), key=lambda p: p.name):
                        if not d.is_dir():
                            continue
                        if d.name in {"branches", "resource", "logs", "tts", "voice", "image"}:
                            continue
                        if d not in search_roots:
                            search_roots.append(d)

                    # Final fallback: files may live directly in language root
                    if lang_dir not in search_roots:
                        search_roots.append(lang_dir)

                def _page_sort_key(path: Path) -> int:
                    m = re.match(r"page_(\d+)\.txt$", path.name)
                    return int(m.group(1)) if m else 10**9

                for root in search_roots:
                    candidate_outline = root / "outline.txt"
                    if not candidate_outline.exists():
                        continue

                    # Prefer explicit compiled story files
                    for candidate_name in ("story.txt", "full_story.txt", "draft_story.txt"):
                        candidate_story = root / candidate_name
                        if candidate_story.exists():
                            story_path = candidate_story
                            sandbox_outline = candidate_outline
                            if root.parent.name == "branches":
                                branch_name = root.name
                            elif root == lang_dir:
                                branch_name = "option_1"
                            else:
                                branch_name = root.name
                            break

                    if story_path is not None:
                        break

                    # Fallback: stitch page_*.txt if compiled story file is unavailable
                    page_files = sorted(root.glob("page_*.txt"), key=_page_sort_key)
                    if page_files:
                        raw_pages: List[str] = []
                        for i, page_file in enumerate(page_files, start=1):
                            text = page_file.read_text(encoding="utf-8", errors="replace").strip()
                            raw_pages.append(f"Page {i}: {text}")
                        raw_g2_text = "\n\n".join(raw_pages)
                        sandbox_outline = candidate_outline
                        if root.parent.name == "branches":
                            branch_name = root.name
                        elif root == lang_dir:
                            branch_name = "option_1"
                        else:
                            branch_name = root.name
                        break

                dev_dir = actual_story_root / "_dev" / branch_name
                
                if not sandbox_outline or not sandbox_outline.exists():
                    raise FileNotFoundError(f"G2 generated no outline.txt in any branch of {lang_dir}")
                if raw_g2_text is None and (not story_path or not story_path.exists()):
                    raise FileNotFoundError(f"G2 generated no story.txt in any branch of {lang_dir}")
                    
                shutil.copy2(sandbox_outline, g2_dir / "outline.txt")
                # 剝離 Page N: 前綴但保留段落分隔
                if raw_g2_text is None and story_path is not None:
                    raw_g2_text = story_path.read_text(encoding="utf-8", errors="replace")
                # Strip "Page N: " prefixes while keeping paragraph separators
                cleaned_g2 = re.sub(r"^Page \d+:\s*", "", raw_g2_text, flags=re.MULTILINE)
                (g2_dir / "story.txt").write_text(cleaned_g2.strip(), encoding="utf-8")
                    
                g2_meta = {
                    "group_id": "G2",
                    "kg_mode": "kg",
                    "pipeline": "structured",
                    "refinement": True, 
                    "outline_prompt_file": "A2_series_outline.txt", 
                    "story_prompt_file": "A3_series_page.txt", 
                    "generation_params": {
                        "max_tokens": base_generation.max_tokens,
                        "temperature": base_generation.temperature,
                        "top_p": base_generation.top_p,
                        "top_k": base_generation.top_k,
                        "repetition_penalty": base_generation.repetition_penalty
                    }
                }
                with open(g2_dir / "meta.json", "w", encoding="utf-8") as f:
                    json.dump(g2_meta, f, indent=2, ensure_ascii=False)
                    
                # Extract critical G2 prompts
                g2_prompts = {}
                sandbox_prompt_dir = dev_dir / "prompts"
                if sandbox_prompt_dir.exists():
                    for pfile in sandbox_prompt_dir.glob("*.txt"):
                        key_name = pfile.stem
                        if any(t in key_name for t in ["outline", "page_", "refine"]):
                            content = pfile.read_text(encoding="utf-8")
                            g2_prompts[pfile.name] = {"raw_text": content}
                            
                if not g2_prompts:
                    g2_prompts["note"] = "Found no prompts in sandbox _dev/prompts directory."
                    
                with open(g2_dir / "prompts.json", "w", encoding="utf-8") as f:
                    json.dump(g2_prompts, f, indent=2, ensure_ascii=False)

                # Build fairness manifest (length control + prompt audit)
                prompt_audit: Dict[str, Any] = {}
                for group_name in ("G0", "G1", "G2"):
                    prompt_path = case_dir / group_name / "prompts.json"
                    if prompt_path.exists():
                        payload = json.loads(prompt_path.read_text(encoding="utf-8"))
                        prompt_audit[group_name] = _build_prompt_audit(payload)
                    else:
                        prompt_audit[group_name] = {"note": "prompts.json missing"}

                length_fairness = _prepare_fair_evaluation_views(case_dir, logger)
                fairness_manifest = {
                    "case_id": case_id,
                    "groups": ["G0", "G1", "G2"],
                    "model_name": shared_config["model_name"],
                    "generation_params": shared_config["generation_params"],
                    "length_fairness": length_fairness,
                    "prompt_audit": prompt_audit,
                }
                with open(case_dir / "fairness_manifest.json", "w", encoding="utf-8") as f:
                    json.dump(fairness_manifest, f, indent=2, ensure_ascii=False)
                    
                # Clean up sandbox
                try:
                    import stat
                    def remove_readonly(func, path, excinfo):
                        Path(path).chmod(stat.S_IWRITE)
                        func(path)
                    shutil.rmtree(sandbox_root, onerror=remove_readonly)
                except Exception as e:
                    logger.warning(f"Failed to cleanup sandbox {sandbox_root}: {e}")

                success_cases += 1
                    
            except Exception as e:
                logger.error(f"CRITICAL ERROR in Case {i+1} (Seed {current_seed}): {e}", exc_info=True)
                logger.error("Skipping to next case to maintain batch execution.")
                failed_cases += 1
                continue

        if failed_cases == 0:
            logger.info("=== All Cases Completed Successfully (%s/%s) ===", success_cases, args.num_cases)
        else:
            logger.warning(
                "=== Cases Completed With Failures: success=%s, failed=%s, total=%s ===",
                success_cases,
                failed_cases,
                args.num_cases,
            )

    finally:
        del llm
        torch.cuda.empty_cache()

if __name__ == "__main__":
    main()
