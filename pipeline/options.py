"""Chief orchestration 的設定與 CLI 定義。"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence, cast

try:
    import torch
except Exception:  # pragma: no cover - optional dependency for parser-only tests
    torch = None

IMAGE_DEFAULT_STEPS = 4
IMAGE_DEFAULT_GUIDANCE = 0.0
IMAGE_DEFAULT_SKIP_REFINER = True
IMAGE_DEFAULT_NEGATIVE_PROMPT = (
    "text, letters, words, watermark, signature, logo, frame, border, blurry, cropped, "
    "bad anatomy, bad hands, missing fingers, extra fingers, extra limbs, duplicated features, "
    "deformed, distorted face"
)
IMAGE_DEFAULT_COVER_SUFFIX = (
    "children's picture-book cover illustration, readable thumbnail, clear focal subject, no text lettering"
)
IMAGE_DEFAULT_CHARACTER_SUFFIX = (
    "children's picture-book character sheet, full body, clean silhouette, readable face, light plain background"
)
IMAGE_DEFAULT_SCENE_SUFFIX = (
    "children's picture-book scene illustration, layered depth, readable faces, coherent lighting, no text"
)

CATEGORY_CHOICES: Sequence[str] = ("adventure", "educational", "fun", "cultural")
AGE_CHOICES: Sequence[str] = ("2-3", "4-5", "6-8")  # "9-10" 暫時停用
STYLE_KEYWORDS: Sequence[str] = (
    "cinematic",
    "ultra detailed",
    "hyperrealistic",
    "dslr",
    "studio light",
    "watercolor",
    "oil painting",
    "anime",
    "concept art",
)
PUNCTUATION_PATTERN = re.compile(r"[\,\.\!\?\;\:\-]")


@dataclass
class ChiefOptions:
    """整合主控流程所有需要的 CLI 參數與設定。"""

    mode: str
    count: int
    main_category: Optional[str]
    age_group: Optional[str]
    seed: Optional[int]
    resume: Optional[str]
    rebuild_interval: int
    model_plan: str

    story_language: str
    languages: List[str]
    story_input_mode: str
    story_theme: Optional[str]
    story_subcategory: Optional[str]
    story_user_prompt: str
    story_user_materials: str
    story_model: Path
    story_device: str
    story_dtype: str
    story_quantization: Optional[str]
    story_pages_expected: int
    story_max_chars: int
    story_max_sentences: int
    story_max_tokens: int
    story_min_tokens: int
    story_temperature: float
    story_top_p: float
    story_top_k: int
    story_repetition_penalty: float
    story_no_repeat_ngram: int
    story_model_name: str
    story_prompt_set: str
    story_cover_source: str
    story_output_root: Path
    story_outline_candidates: int
    story_title_candidates: int
    story_key_page_candidates: int

    photo_enabled: bool
    translation_enabled: bool
    voice_enabled: bool
    verify_enabled: bool
    low_vram: bool

    sdxl_base: Path
    sdxl_refiner: Path
    photo_device: str
    photo_dtype: str
    photo_quantization: str
    photo_output_mode: str
    photo_asset_granularity: str
    photo_bg_removal_policy: str
    photo_reuse_strategy: str
    photo_width: int
    photo_height: int
    photo_steps: int
    photo_guidance: float
    photo_refiner_steps: Optional[int]
    photo_skip_refiner: bool
    photo_negative_prompt: str
    photo_cover_suffix: str
    photo_character_suffix: str
    photo_scene_suffix: str
    photo_seed: Optional[int]
    photo_no_remove_bg: bool
    require_nobg: bool

    translation_model: Path
    translation_device: str
    translation_dtype: str
    translation_source_lang: str
    translation_beam_size: int
    translation_length_penalty: float
    strict_translation: bool

    voice_language: str
    voice_device: str
    speaker_wav: Optional[Path]
    speaker_dir: Optional[Path]
    voice_page_start: Optional[int]
    voice_page_end: Optional[int]
    voice_volume_gain: float
    voice_no_concat: bool
    voice_drop_raw: bool
    strict_voice: bool
    pre_eval_policy: str
    pre_eval_profile: str
    pre_eval_threshold: float
    max_book_retries: int
    status_json_path: Optional[Path]


def _default_chief_options() -> ChiefOptions:
    return ChiefOptions(
        mode="single",
        count=1,
        main_category=None,
        age_group=None,
        resume=None,
        seed=None,
        model_plan="auto",
        story_language="en",
        languages=["zh"],
        story_input_mode="preset",
        story_theme=None,
        story_subcategory=None,
        story_user_prompt="",
        story_user_materials="",
        story_model=Path("models/Qwen2.5-14B-Instruct-GPTQ-Int4"),
        story_device="auto",
        story_dtype="float16",
        story_quantization="gptq",
        low_vram=True,
        story_pages_expected=0,
        story_max_chars=1500,
        story_max_sentences=30,
        story_max_tokens=512,
        story_min_tokens=32,
        story_temperature=0.85,
        story_top_p=0.95,
        story_top_k=50,
        story_repetition_penalty=1.1,
        story_no_repeat_ngram=0,
        story_model_name="qwen2.5-14b-instruct-gptq-int4",
        story_prompt_set="general_v1",
        story_cover_source="outline",
        story_output_root=Path("output"),
        story_outline_candidates=1,
        story_title_candidates=1,
        story_key_page_candidates=1,
        photo_enabled=True,
        translation_enabled=True,
        voice_enabled=True,
        verify_enabled=True,
        require_nobg=False,
        strict_translation=True,
        translation_model=Path("models/nllb-200-3.3B"),
        translation_device="auto",
        translation_dtype="float16",
        translation_source_lang="eng_Latn",
        translation_beam_size=1,
        translation_length_penalty=1.0,
        voice_language="en",
        voice_device="auto",
        speaker_wav=None,
        speaker_dir=None,
        sdxl_base=Path("models/FLUX.1-schnell"),
        sdxl_refiner=Path("models/__disabled_refiner__"),
        photo_device="auto",
        photo_dtype="bfloat16",
        photo_quantization="fp8",
        photo_output_mode="dual",
        photo_asset_granularity="page_bundle",
        photo_bg_removal_policy="characters_props",
        photo_reuse_strategy="page_bundle_first",
        photo_width=1024,
        photo_height=768,
        photo_steps=IMAGE_DEFAULT_STEPS,
        photo_guidance=IMAGE_DEFAULT_GUIDANCE,
        photo_refiner_steps=None,
        photo_skip_refiner=IMAGE_DEFAULT_SKIP_REFINER,
        photo_negative_prompt=IMAGE_DEFAULT_NEGATIVE_PROMPT,
        photo_cover_suffix=IMAGE_DEFAULT_COVER_SUFFIX,
        photo_character_suffix=IMAGE_DEFAULT_CHARACTER_SUFFIX,
        photo_scene_suffix=IMAGE_DEFAULT_SCENE_SUFFIX,
        photo_seed=None,
        photo_no_remove_bg=False,
        rebuild_interval=3,
        voice_page_start=None,
        voice_page_end=None,
        voice_volume_gain=1.0,
        voice_no_concat=False,
        voice_drop_raw=False,
        strict_voice=True,
        pre_eval_policy="stop",
        pre_eval_profile="balanced",
        pre_eval_threshold=65.0,
        max_book_retries=1,
        status_json_path=None,
    )


DEFAULT_CHIEF_OPTIONS = _default_chief_options()


def parse_dtype(name: str) -> torch.dtype:
    """將設定字串轉換為對應的 torch dtype。"""

    if torch is None:
        return cast(Any, name)
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }.get(name, torch.float16)


def build_arg_parser() -> argparse.ArgumentParser:
    """建立 chief / pipeline 共用的 CLI parser。"""

    parser = argparse.ArgumentParser(description="Children's story production controller")
    parser.add_argument("--count", type=int, default=1, help="要生成的故事本數，預設 1")
    parser.add_argument("--seed", type=int, default=None, help="固定隨機種子，便於重現結果")
    parser.add_argument(
        "--resume",
        type=str,
        default=None,
        help="Resume from a previous run directory",
    )
    parser.add_argument(
        "--model-plan",
        type=str,
        default="auto",
        choices=["auto", "quality", "balanced", "portable", "cpu", "off"],
        help="Hardware-aware runtime model plan selection",
    )
    parser.add_argument(
        "--age",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=CATEGORY_CHOICES,
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--subcategory",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--story-input-mode",
        type=str,
        default="preset",
        choices=["preset", "custom"],
    )
    parser.add_argument("--pages", type=int, default=0, help="指定預期頁數，0 表示使用知識圖譜的動態設定 (預設 0)")
    parser.add_argument(
        "--story-prompt",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--story-materials",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--story-device",
        type=str,
        default=None,
    )
    parser.add_argument(
        "--story-dtype",
        type=str,
        default=None,
        choices=["float16", "bfloat16", "float32"],
    )
    parser.add_argument(
        "--story-quantization",
        type=str,
        default=None,
        choices=["4bit", "8bit", "gptq", "none"],
    )
    parser.add_argument(
        "--low-vram",
        dest="low_vram",
        action="store_true",
    )
    parser.add_argument(
        "--no-low-vram",
        dest="low_vram",
        action="store_false",
    )
    parser.set_defaults(low_vram=None)
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
    )
    parser.add_argument(
        "--outline-candidates",
        type=int,
        default=None,
        help="Number of outline candidates to generate before reranking",
    )
    parser.add_argument(
        "--title-candidates",
        type=int,
        default=None,
        help="Number of title candidates to generate before reranking",
    )
    parser.add_argument(
        "--key-page-candidates",
        type=int,
        default=None,
        help="Number of candidates to generate for high-value story pages before reranking",
    )
    parser.add_argument(
        "--pre-eval-policy",
        type=str,
        default=str(DEFAULT_CHIEF_OPTIONS.pre_eval_policy),
        choices=["warn", "stop"],
        help="Pre-evaluation gate policy: warn (continue) or stop (hard-stop)",
    )
    parser.add_argument(
        "--pre-eval-profile",
        type=str,
        default=str(DEFAULT_CHIEF_OPTIONS.pre_eval_profile),
        choices=["fast", "balanced", "strict"],
        help="Efficiency/quality profile for stage 1.5 pre-evaluation",
    )
    parser.add_argument(
        "--pre-eval-threshold",
        type=float,
        default=float(DEFAULT_CHIEF_OPTIONS.pre_eval_threshold),
        help="Fail-fast threshold used by stage 1.5 pre-evaluation",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--photo",
        dest="photo_enabled",
        action="store_true",
    )
    parser.add_argument(
        "--no-photo",
        dest="photo_enabled",
        action="store_false",
    )
    parser.set_defaults(photo_enabled=None)
    parser.add_argument(
        "--translation",
        dest="translation_enabled",
        action="store_true",
    )
    parser.add_argument(
        "--no-translation",
        dest="translation_enabled",
        action="store_false",
    )
    parser.set_defaults(translation_enabled=None)
    parser.add_argument(
        "--voice",
        dest="voice_enabled",
        action="store_true",
    )
    parser.add_argument(
        "--no-voice",
        dest="voice_enabled",
        action="store_false",
    )
    parser.set_defaults(voice_enabled=None)
    parser.add_argument(
        "--verify",
        dest="verify_enabled",
        action="store_true",
    )
    parser.add_argument(
        "--no-verify",
        dest="verify_enabled",
        action="store_false",
    )
    parser.set_defaults(verify_enabled=None)

    parser.add_argument(
        "--strict-translation",
        dest="strict_translation",
        action="store_true",
    )
    parser.add_argument(
        "--no-strict-translation",
        dest="strict_translation",
        action="store_false",
    )
    parser.set_defaults(strict_translation=None)
    parser.add_argument(
        "--strict-voice",
        dest="strict_voice",
        action="store_true",
    )
    parser.add_argument(
        "--no-strict-voice",
        dest="strict_voice",
        action="store_false",
    )
    parser.set_defaults(strict_voice=None)
    parser.add_argument(
        "--speaker-wav",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--speaker-dir",
        type=Path,
        default=None,
    )

    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Start dashboard"
    )
    parser.add_argument(
        "--dashboard-host",
        type=str,
        default="127.0.0.1",
        help="Dashboard host"
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8765,
        help="Dashboard port"
    )
    parser.add_argument(
        "--dashboard-no-open",
        action="store_true",
        help="Do not open dashboard"
    )
    return parser
