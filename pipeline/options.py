"""Chief orchestration 的設定與 CLI 定義。"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

import torch

from image import Config as ImageConfig

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
    rebuild_interval: int

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

    photo_enabled: bool
    translation_enabled: bool
    voice_enabled: bool
    verify_enabled: bool
    low_vram: bool

    sdxl_base: Path
    sdxl_refiner: Path
    photo_device: str
    photo_dtype: str
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
    max_book_retries: int
    status_json_path: Optional[Path]


def _default_chief_options() -> ChiefOptions:
    return ChiefOptions(
        mode="single",
        count=1,
        main_category=None,
        age_group=None,
        story_language="en",
        languages=[],
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
        story_prompt_set="qwen_v1",
        story_cover_source="outline",
        story_output_root=Path("output"),
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
        sdxl_base=Path("models/stable-diffusion-xl-base-1.0"),
        sdxl_refiner=Path("models/stable-diffusion-xl-refiner-1.0"),
        photo_device="auto",
        photo_dtype="float16",
        photo_width=1024,
        photo_height=768,
        photo_steps=40,
        photo_guidance=7.0,
        photo_refiner_steps=None,
        photo_skip_refiner=False,
        photo_negative_prompt="",
        photo_cover_suffix=ImageConfig.cover_prompt_suffix,
        photo_character_suffix=ImageConfig.character_prompt_suffix,
        photo_scene_suffix=ImageConfig.scene_prompt_suffix,
        photo_seed=None,
        photo_no_remove_bg=False,
        seed=None,
        rebuild_interval=3,
        voice_page_start=None,
        voice_page_end=None,
        voice_volume_gain=1.0,
        voice_no_concat=False,
        voice_drop_raw=False,
        strict_voice=True,
        max_book_retries=1,
        status_json_path=None,
    )


DEFAULT_CHIEF_OPTIONS = _default_chief_options()


def parse_dtype(name: str) -> torch.dtype:
    """將設定字串轉換為對應的 torch dtype。"""

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
        "--age",
        type=str,
        default=None,
        help="指定年齡組（輸入 2-3, 4-5, 6-8，或單一數字例如 6），未指定則隨機選擇 (9-10 暫時停用)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=CATEGORY_CHOICES,
        help="指定主類別（adventure, educational, fun, cultural），未指定則隨機選擇",
    )
    parser.add_argument(
        "--theme",
        type=str,
        default=None,
        help="指定主題提示（可輸入 KG 已有主題標籤或自由文字，未指定則由 KG 自動選擇）",
    )
    parser.add_argument(
        "--subcategory",
        type=str,
        default=None,
        help="指定子類別提示（可輸入 KG 子類別標籤，未指定則由 KG 自動選擇）",
    )
    parser.add_argument(
        "--story-input-mode",
        type=str,
        default="preset",
        choices=["preset", "custom"],
        help="故事輸入模式：preset 直接使用系統預設，custom 會啟用使用者自由輸入的結構化轉換",
    )
    parser.add_argument("--pages", type=int, default=0, help="指定預期頁數，0 表示使用知識圖譜的動態設定 (預設 0)")
    parser.add_argument(
        "--story-prompt",
        type=str,
        default=None,
        help="額外的自由敘事指令，會經過正規化後注入提示詞模板",
    )
    parser.add_argument(
        "--story-materials",
        type=str,
        default=None,
        help="補充素材（可用換行分點），會轉為結構化素材提示注入模板",
    )
    parser.add_argument(
        "--story-device",
        type=str,
        default=None,
        help="LLM 模型使用的設備（例如 cuda:0, cuda, cpu），未指定則使用預設值 auto",
    )
    parser.add_argument(
        "--story-dtype",
        type=str,
        default=None,
        choices=["float16", "bfloat16", "float32"],
        help="LLM 模型的資料類型（float16, bfloat16, float32），未指定則使用預設值 float16",
    )
    parser.add_argument(
        "--story-quantization",
        type=str,
        default=None,
        choices=["4bit", "8bit", "gptq", "none"],
        help="LLM 量化模式 (4bit, 8bit, gptq, none)，預設使用模型相容的建議值",
    )
    parser.add_argument(
        "--low-vram",
        action="store_true",
        default=None,
        help="啟用低顯存模式 (Aggressive Cleanup / Model Offloading)",
    )
    parser.add_argument(
        "--no-low-vram",
        action="store_false",
        dest="low_vram",
        help="禁用低顯存模式 (適用於大顯存 GPU，如 24GB+ 或 16GB+ 且模型較小)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="單本故事失敗時的自動整本重跑次數 (不含首次執行)",
    )
    parser.add_argument(
        "--status-file",
        type=Path,
        default=None,
        help="輸出即時狀態 JSON 檔案路徑（供儀表板讀取）",
    )

    parser.add_argument(
        "--photo",
        action="store_true",
        dest="photo_enabled",
        default=None,
        help="啟用圖像生成階段",
    )
    parser.add_argument(
        "--no-photo",
        action="store_false",
        dest="photo_enabled",
        help="停用圖像生成階段",
    )
    parser.add_argument(
        "--translation",
        action="store_true",
        dest="translation_enabled",
        default=None,
        help="啟用翻譯階段",
    )
    parser.add_argument(
        "--no-translation",
        action="store_false",
        dest="translation_enabled",
        help="停用翻譯階段",
    )
    parser.add_argument(
        "--voice",
        action="store_true",
        dest="voice_enabled",
        default=None,
        help="啟用語音合成階段",
    )
    parser.add_argument(
        "--no-voice",
        action="store_false",
        dest="voice_enabled",
        help="停用語音合成階段",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        dest="verify_enabled",
        default=None,
        help="啟用完整性驗證階段",
    )
    parser.add_argument(
        "--no-verify",
        action="store_false",
        dest="verify_enabled",
        help="停用完整性驗證階段",
    )

    parser.add_argument(
        "--strict-translation",
        action="store_true",
        dest="strict_translation",
        default=None,
        help="翻譯失敗視為整本失敗",
    )
    parser.add_argument(
        "--no-strict-translation",
        action="store_false",
        dest="strict_translation",
        help="翻譯失敗僅記為警告",
    )
    parser.add_argument(
        "--strict-voice",
        action="store_true",
        dest="strict_voice",
        default=None,
        help="語音失敗視為整本失敗",
    )
    parser.add_argument(
        "--no-strict-voice",
        action="store_false",
        dest="strict_voice",
        help="語音失敗僅記為警告",
    )
    parser.add_argument(
        "--speaker-wav",
        type=Path,
        default=None,
        help="指定語音克隆的說話人參考音檔（WAV）",
    )
    parser.add_argument(
        "--speaker-dir",
        type=Path,
        default=None,
        help="指定語音克隆的說話人樣本資料夾",
    )

    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="啟動本地儀表板（可視化操作與監看）",
    )
    parser.add_argument(
        "--dashboard-host",
        type=str,
        default="127.0.0.1",
        help="儀表板綁定主機",
    )
    parser.add_argument(
        "--dashboard-port",
        type=int,
        default=8765,
        help="儀表板連接埠",
    )
    parser.add_argument(
        "--dashboard-no-open",
        action="store_true",
        help="啟動儀表板時不自動開啟瀏覽器",
    )
    return parser
