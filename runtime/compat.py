"""
執行期相容層的統一入口。
"""

from __future__ import annotations

import logging
from typing import Any

from runtime.compat_transformers import apply_all_patches, patch_gpt2_generate_method
from runtime.exllamav2_shim import setup_exllamav2_shim

logger = logging.getLogger(__name__)


def prepare_tts_runtime() -> None:
    """在載入 XTTS 前，套用 TTS 所需的相容修補。"""
    apply_all_patches()


def patch_tts_instance_after_load(tts_instance: Any) -> None:
    """在 XTTS 實例建立後，補上 decoder generate 相容性。"""
    patch_gpt2_generate_method(tts_instance)


def prepare_gptq_runtime() -> bool:
    """準備 GPTQ 執行環境，並回傳 shim 是否成功啟用。"""
    try:
        enabled = setup_exllamav2_shim()
    except Exception as exc:
        logger.warning("Failed to setup exllamav2 shim: %s", exc)
        return False

    if enabled:
        logger.info("exllamav2 kernel shim activated for GPTQ acceleration")
    else:
        logger.info("exllamav2 kernel shim not enabled; GPTQ will use slower fallback")
    return enabled


def prepare_evaluator_runtime() -> None:
    """
    處理 evaluator 所需的 spaCy-transformers / transformers 相容問題。
    """
    import torch

    original = getattr(torch.nn.Module.load_state_dict, "__wrapped__", torch.nn.Module.load_state_dict)
    if getattr(torch.nn.Module.load_state_dict, "_story_runtime_compat_patch", False):
        return

    def patched_load_state_dict(self, state_dict, strict=True, assign=False):
        if "embeddings.position_ids" in state_dict:
            del state_dict["embeddings.position_ids"]
        if "roberta.embeddings.position_ids" in state_dict:
            del state_dict["roberta.embeddings.position_ids"]
        return original(self, state_dict, strict=False)

    patched_load_state_dict._story_runtime_compat_patch = True  # type: ignore[attr-defined]
    patched_load_state_dict.__wrapped__ = original  # type: ignore[attr-defined]
    torch.nn.Module.load_state_dict = patched_load_state_dict  # type: ignore[assignment]
