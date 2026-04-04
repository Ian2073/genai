"""Story pipeline 共用的純工具函式與步驟參數規則。"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from backends.llm import BaseLLM, GenerationParams
from prompts.prompt_utils import ChatPrompt, load_step_prompts, strip_hidden_thoughts
from utils import load_structured_config

DEFAULT_STEP_OVERRIDES: Dict[str, Dict[str, Any]] = {
    "outline": {
        "max_tokens": 1024,
        "min_tokens": 60,
        "temperature": 0.2,
        "top_p": 0.9,
        "top_k": 40,
        "no_repeat_ngram_size": 3,
        "repetition_penalty": 1.1,
    },
    "title": {
        "max_tokens": 80,
        "min_tokens": 5,
        "temperature": 0.5,
        "top_p": 0.9,
        "top_k": 40,
        "repetition_penalty": 1.1,
    },
    "story_plan": {
        "max_tokens": 300,
        "min_tokens": 50,
        "temperature": 0.4,
        "top_p": 0.9,
        "top_k": 40,
        "repetition_penalty": 1.1,
    },
    "story_write": {
        "max_tokens": 1536,
        "min_tokens": 100,
        "temperature": 0.6,
        "top_p": 0.9,
        "top_k": 40,
        "no_repeat_ngram_size": None,
        "repetition_penalty": 1.05,
    },
    "narration": {
        "max_tokens": 700,
        "min_tokens": 80,
        "temperature": 0.55,
        "top_p": 0.9,
        "top_k": 40,
        "no_repeat_ngram_size": None,
        "repetition_penalty": 1.05,
    },
    "dialogue": {
        "max_tokens": 600,
        "min_tokens": 30,
        "temperature": 0.6,
        "top_p": 0.9,
        "top_k": 40,
        "no_repeat_ngram_size": None,
        "repetition_penalty": 1.05,
    },
    "scene": {
        "max_tokens": 150,
        "min_tokens": 10,
        "temperature": 0.7,
        "top_p": 0.9,
        "top_k": 40,
        "repetition_penalty": 1.05,
    },
    "pose": {
        "max_tokens": 120,
        "min_tokens": 8,
        "temperature": 0.65,
        "top_p": 0.9,
        "top_k": 40,
        "repetition_penalty": 1.05,
    },
    "cover": {
        "max_tokens": 180,
        "min_tokens": 12,
        "temperature": 0.75,
        "top_p": 0.92,
        "top_k": 50,
        "repetition_penalty": 1.03,
    },
}

KNOWN_STEPS = {
    "outline",
    "title",
    "story_plan",
    "story_write",
    "narration",
    "dialogue",
    "scene",
    "pose",
    "cover",
}


def _merge_generation_params(base: GenerationParams, overrides: Dict[str, Any]) -> GenerationParams:
    """以 base 為預設，套用覆寫後產生新的 GenerationParams。"""

    def _pick_int(key: str, fallback: int) -> int:
        value = overrides.get(key)
        return fallback if value is None else int(value)

    def _pick_float(key: str, fallback: float) -> float:
        value = overrides.get(key)
        return fallback if value is None else float(value)

    return GenerationParams(
        max_tokens=_pick_int("max_tokens", base.max_tokens),
        min_tokens=_pick_int("min_tokens", base.min_tokens),
        temperature=_pick_float("temperature", base.temperature),
        top_p=_pick_float("top_p", base.top_p),
        top_k=_pick_int("top_k", base.top_k),
        repetition_penalty=_pick_float("repetition_penalty", base.repetition_penalty),
        no_repeat_ngram_size=overrides.get("no_repeat_ngram_size", base.no_repeat_ngram_size),
    )


def load_step_generation_overrides(config_path: Path, base: GenerationParams) -> Dict[str, GenerationParams]:
    """由 JSON/YAML 讀取步驟化超參數設定。"""

    data = load_structured_config(config_path)
    if not isinstance(data, dict):
        raise ValueError(f"Step config must be a mapping, got {type(data)}")
    step_params: Dict[str, GenerationParams] = {}
    for step, overrides in data.items():
        if not isinstance(overrides, dict):
            continue
        if KNOWN_STEPS and step not in KNOWN_STEPS:
            continue
        step_params[step] = _merge_generation_params(base, overrides)
    return step_params


def _apply_default_step_generations(
    base: GenerationParams,
    user_defined: Dict[str, GenerationParams],
) -> Dict[str, GenerationParams]:
    """套用內建步驟參數。"""

    if not DEFAULT_STEP_OVERRIDES:
        return user_defined
    result = dict(user_defined)
    for step, overrides in DEFAULT_STEP_OVERRIDES.items():
        if step in result:
            continue
        result[step] = _merge_generation_params(base, overrides)
    return result


def estimate_clip_tokens(text: str) -> int:
    """估算 CLIP tokenizer 的 token 數量。"""

    if not text:
        return 0

    try:
        from transformers import CLIPTokenizer

        tokenizer = CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")
        tokens = tokenizer(text, return_length=True)
        return tokens["length"][0]
    except Exception:
        words = len(text.split())
        punctuation_count = text.count(",") + text.count(".") + text.count("!") + text.count("?")
        return int(words * 1.4) + punctuation_count


def validate_image_prompt_length(prompt: str, suffix: str, max_tokens: int = 77, step_name: str = "") -> bool:
    """驗證圖像提示詞是否在 CLIP 77 tokens 限制內。"""

    full_prompt = f"{prompt}, {suffix}" if suffix else prompt
    estimated_tokens = estimate_clip_tokens(full_prompt)
    if estimated_tokens > max_tokens:
        logging.warning(
            "[Step %s] Image prompt exceeds CLIP limit: %d tokens (max %d). Prompt: %s... (truncated)",
            step_name,
            estimated_tokens,
            max_tokens,
            prompt[:100],
        )
        return False
    return True


def run_qwen_step(
    llm: BaseLLM,
    template_path: Union[str, Path],
    params: GenerationParams,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """通用單步驟執行器：讀模板、組 messages、呼叫 LLM。"""

    system_prompt, user_prompt = load_step_prompts(template_path, context=context, **kwargs)
    chat_prompt = ChatPrompt(system_prompt=system_prompt, user_prompt=user_prompt)
    raw = llm.generate(chat_prompt, params)
    return strip_hidden_thoughts(raw)


def split_sentences(text: str) -> List[str]:
    """將段落依終止標點拆成句子清單。"""

    cleaned = text.strip()
    if not cleaned:
        return []
    parts = re.split(r"(?<=[。！？!?\.])\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def paginate_text(text: str, max_chars: int, max_sentences: int) -> List[str]:
    """根據字數與句數限制分頁。"""

    sentences = split_sentences(text)
    if not sentences:
        return [text.strip()] if text.strip() else []

    pages: List[str] = []
    buffer: List[str] = []
    char_count = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        next_chars = char_count + len(sentence)
        if buffer and (next_chars > max_chars or len(buffer) >= max_sentences):
            pages.append(" ".join(buffer).strip())
            buffer = []
            char_count = 0
        buffer.append(sentence)
        char_count += len(sentence)

    if buffer:
        pages.append(" ".join(buffer).strip())
    return pages


def estimate_tokens(text: str) -> int:
    """粗略估計 token 數。"""

    if not text:
        return 0
    return max(1, len(re.findall(r"\S+", text)))


def format_list(items: Optional[Sequence[str]]) -> str:
    """將字串清單排成多行條列。"""

    if not items:
        return ""
    return "\n".join(f"- {item}" for item in items if item)
