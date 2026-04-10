"""Story pipeline 的公開型別與預設設定。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Union

from backends.llm import GenerationParams
from utils import StoryProfile


@dataclass
class StoryInput:
    """描述生成故事所需的 Knowledge Graph 屬性與語言條件。"""

    language: str
    age_group: str
    category: str
    subcategory: str
    theme: str
    input_mode: str = "preset"
    user_prompt: str = ""
    user_materials: str = ""
    kg_payload: Optional[Dict[str, Any]] = None
    kg_profile: Optional[StoryProfile] = None


@dataclass
class StoryRunConfig:
    """當 story 模組直接執行時採用的預設設定。"""

    age_group: Optional[str | int] = 5
    category: Optional[str] = "adventure"
    output_root: Union[str, Path] = Path("output")
    story_id: Optional[str] = None
    llm_model_dir: Union[str, Path] = Path("models/Qwen2.5-14B-Instruct-GPTQ-Int4")
    llm_model_name: str = "qwen2.5-14b-instruct-gptq-int4"
    llm_device_map: str = "auto"
    llm_dtype: str = "float16"
    llm_seed: int = 42
    llm_quantization: Optional[str] = "gptq"


DEFAULT_STORY_CONFIG = StoryRunConfig()


@dataclass
class PipelineOptions:
    """封裝故事生成流程的相關設定。"""

    pages_expected: int
    max_page_chars: int
    max_page_sentences: int
    generation: GenerationParams
    model_name: str
    prompt_set: str
    cover_source: str
    kg_enabled: bool
    kg_version: Optional[str]
    step_generations: Dict[str, GenerationParams] = field(default_factory=dict)
    outline_candidates: int = 1
    title_candidates: int = 1
    key_page_candidates: int = 1
    aggressive_memory_cleanup: bool = True
    disable_category_temperature_adaptation: bool = False
