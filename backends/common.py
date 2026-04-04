"""跨 backend 共用的執行裝置與 dtype 輔助函式。"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import torch


def resolve_torch_runtime(
    requested_device: Optional[str],
    requested_dtype: torch.dtype,
    *,
    module_name: str,
    auto_cuda_device: str = "cuda",
    cpu_fallback: bool = True,
    cpu_dtype: torch.dtype = torch.float32,
) -> Tuple[str, torch.dtype]:
    """統一處理 backend 的 device/dtype 選擇邏輯。"""

    device = (requested_device or "auto").strip().lower()
    if device == "auto":
        device = auto_cuda_device if torch.cuda.is_available() else "cpu"

    if device.startswith("cuda") and not torch.cuda.is_available():
        if not cpu_fallback:
            raise RuntimeError(f"{module_name} requested CUDA but no CUDA device is available.")
        logging.warning("%s requested CUDA but no CUDA device is available. Falling back to CPU.", module_name)
        device = "cpu"

    dtype = requested_dtype
    if device == "cpu" and dtype in (torch.float16, torch.bfloat16):
        logging.info("%s in CPU mode: switching dtype to float32 for compatibility.", module_name)
        dtype = cpu_dtype

    return device, dtype
