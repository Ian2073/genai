"""
執行期相容層的統一入口。
"""

from __future__ import annotations

import logging
import os
import sys
import types
from typing import Any

from runtime.compat_transformers import apply_all_patches, patch_gpt2_generate_method
from runtime.exllamav2_shim import setup_exllamav2_shim

logger = logging.getLogger(__name__)


def _patch_subprocess_for_utf8() -> None:
    import subprocess
    import functools

    original_popen_init = subprocess.Popen.__init__

    @functools.wraps(original_popen_init)
    def patched_popen_init(self, *args, **kwargs):
        # 如果使用者要求文字輸出，我們確保 errors = "replace"
        if kwargs.get("text") or kwargs.get("universal_newlines") or kwargs.get("encoding"):
            kwargs.setdefault("errors", "replace")
        original_popen_init(self, *args, **kwargs)

    if not getattr(subprocess.Popen, "_utf8_patched", False):
        subprocess.Popen.__init__ = patched_popen_init # type: ignore
        subprocess.Popen._utf8_patched = True # type: ignore
        logger.debug("subprocess.Popen patched to default errors='replace' for text mode.")

_patch_subprocess_for_utf8()

def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _install_tts_monotonic_align_fallback() -> None:
    """Install a Python fallback for TTS monotonic alignment when C-extension build fails.

    Coqui-TTS may try to compile `TTS.tts.utils.monotonic_align.core` at import time.
    On some Windows setups this compile step fails even when TTS is installed. This
    fallback injects a compatible pure-Python module so TTS can continue to load.
    """

    force_fallback = _bool_env("GENAI_TTS_FORCE_PY_MONOTONIC_ALIGN", default=(os.name == "nt"))
    if not force_fallback and os.name == "nt":
        # Windows is the most common environment for pyximport/MSVC failures.
        # Keep fallback enabled by default unless explicitly disabled.
        force_fallback = True

    if not force_fallback:
        return

    module_name = "TTS.tts.utils.monotonic_align.core"
    if module_name in sys.modules:
        return

    fallback_module = types.ModuleType(module_name)

    def _maximum_path_each(path, value, t_x: int, t_y: int, max_neg_val: float) -> None:
        if t_x <= 0 or t_y <= 0:
            return

        index = t_x - 1
        for y in range(t_y):
            x_start = max(0, t_x + y - t_y)
            x_end = min(t_x, y + 1)
            for x in range(x_start, x_end):
                v_cur = max_neg_val if x == y else float(value[x, y - 1])
                if x == 0:
                    v_prev = 0.0 if y == 0 else max_neg_val
                else:
                    v_prev = float(value[x - 1, y - 1])
                best_prev = v_cur if v_cur >= v_prev else v_prev
                value[x, y] = best_prev + float(value[x, y])

        for y in range(t_y - 1, -1, -1):
            path[index, y] = 1
            if index != 0 and (index == y or float(value[index, y - 1]) < float(value[index - 1, y - 1])):
                index -= 1

    def maximum_path_c(paths, values, t_xs, t_ys, max_neg_val: float = -1e9) -> None:
        batch = int(getattr(values, "shape", [0])[0])
        for i in range(batch):
            _maximum_path_each(paths[i], values[i], int(t_xs[i]), int(t_ys[i]), float(max_neg_val))

    fallback_module.maximum_path_c = maximum_path_c
    sys.modules[module_name] = fallback_module
    logger.info("Installed Python fallback module for %s", module_name)


def prepare_tts_runtime() -> None:
    """在載入 XTTS 前，套用 TTS 所需的相容修補。"""
    _install_tts_monotonic_align_fallback()
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
    處理 evaluator 所需的模型權重載入相容問題。
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
