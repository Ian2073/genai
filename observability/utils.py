"""
觀測套件輔助工具。
"""
from __future__ import annotations

import os
import platform
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

try:
	import psutil  # type: ignore
except Exception:  # pragma: no cover
	psutil = None  # type: ignore

try:
	from cpuinfo import get_cpu_info
except Exception:  # pragma: no cover
	get_cpu_info = None  # type: ignore

try:
	import torch
except Exception:  # pragma: no cover - torch 可能不存在
	torch = None  # type: ignore

try:
	import pynvml
except Exception:  # pragma: no cover - pynvml 是選用
	pynvml = None  # type: ignore


def utc_now_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def ensure_dir(path: Path) -> None:
	path.mkdir(parents=True, exist_ok=True)


def build_env_metadata() -> Dict[str, Any]:
	return {
		"hostname": socket.gethostname(),
		"platform": platform.platform(),
		"python_version": platform.python_version(),
		"pid": os.getpid(),
	}


def torch_memory_snapshot(device: Optional[int] = None) -> Dict[str, Any]:
	"""輕量 GPU 記憶體快照 — 僅讀取 4 個 O(1) 指標。
	
	注意：不呼叫 torch.cuda.memory_stats()，因為該函式在 GPU 記憶體
	壓力大時可能卡住數分鐘（回傳 150+ key 的字典，內部需遍歷 allocator）。
	"""
	if torch is None or not torch.cuda.is_available():
		return {}
	try:
		device_index = device if device is not None else torch.cuda.current_device()
		return {
			"allocated": torch.cuda.memory_allocated(device_index),
			"reserved": torch.cuda.memory_reserved(device_index),
			"max_allocated": torch.cuda.max_memory_allocated(device_index),
			"max_reserved": torch.cuda.max_memory_reserved(device_index),
		}
	except Exception:
		return {}


def torch_allocator_fragmentation(device: Optional[int] = None) -> Dict[str, Any]:
	"""計算 GPU allocator 碎片率。
	
	使用 allocated/reserved 的比例估算碎片化程度，
	避免呼叫 memory_stats()（在壓力大時可能卡死）。
	"""
	if torch is None or not torch.cuda.is_available():
		return {}
	try:
		device_index = device if device is not None else torch.cuda.current_device()
		allocated = torch.cuda.memory_allocated(device_index)
		reserved = torch.cuda.memory_reserved(device_index)
		fragmentation = 0.0
		if reserved > 0:
			fragmentation = 1.0 - (allocated / reserved)
		return {
			"total_reserved": reserved,
			"allocated": allocated,
			"fragmentation": round(fragmentation, 4),
		}
	except Exception:
		return {}


def nvml_device_count() -> int:
	if pynvml is None:  # pragma: no cover
		return 0
	try:
		pynvml.nvmlInit()
		return pynvml.nvmlDeviceGetCount()
	except Exception:
		return 0


def nvml_snapshot(device_index: int = 0) -> Dict[str, Any]:
	if pynvml is None:  # pragma: no cover
		return {}
	try:
		handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
		util = pynvml.nvmlDeviceGetUtilizationRates(handle)
		mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
		return {
			"gpu_util": util.gpu,
			"mem_util": util.memory,
			"mem_total": mem.total,
			"mem_used": mem.used,
			"mem_free": mem.free,
		}
	except Exception:
		return {}


def monotonic_time() -> float:
	return time.perf_counter()


def gpu_power_snapshot(device_index: int = 0) -> Dict[str, Any]:
	if pynvml is None:  # pragma: no cover
		return {}
	try:
		handle = pynvml.nvmlDeviceGetHandleByIndex(device_index)
		power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # watts
		temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
		clock = pynvml.nvmlDeviceGetClockInfo(handle, pynvml.NVML_CLOCK_SM)
		return {
			"power_watts": power,
			"temperature_c": temp,
			"sm_clock_mhz": clock,
		}
	except Exception:
		return {}


def system_resource_snapshot() -> Dict[str, Any]:
	if psutil is None:  # pragma: no cover
		return {}
	try:
		process = psutil.Process(os.getpid())
		cpu_percent = process.cpu_percent(interval=None)
		# 使用 memory_info() 替代 memory_full_info()，後者在 Windows 上會觸發高開銷的 USS 計算導致 MemoryError
		mem = process.memory_info()
		
		# 嘗試取得 USS，如果失敗則略過
		rss = getattr(mem, "rss", None)
		vms = getattr(mem, "vms", None)
		
		io = psutil.disk_io_counters(perdisk=False)
		net = psutil.net_io_counters(pernic=False)
		virtual_mem = psutil.virtual_memory()
		
		return {
			"process": {
				"cpu_percent": cpu_percent,
				"rss": rss,
				"vms": vms,
				"shared": getattr(mem, "shared", None),
				"num_threads": process.num_threads(),
			},
			"system": {
				"cpu_percent": psutil.cpu_percent(interval=None),
				"load_avg": os.getloadavg()[0] if hasattr(os, "getloadavg") else None,
				"ram_total": virtual_mem.total,
				"ram_available": virtual_mem.available,
				"ram_used": virtual_mem.used,
			},
			"disk": {
				"read_bytes": getattr(io, "read_bytes", None),
				"write_bytes": getattr(io, "write_bytes", None),
			},
			"network": {
				"bytes_sent": getattr(net, "bytes_sent", None),
				"bytes_recv": getattr(net, "bytes_recv", None),
			},
		}
	except Exception:
		# 如果監控過程出錯（如 AccessDenied, MemoryError），回傳空資料避免影響主程式
		return {}


def collect_hardware_snapshot() -> Dict[str, Any]:
	info: Dict[str, Any] = {
		"platform": platform.platform(),
		"python_version": platform.python_version(),
		"cpu": {},
		"gpu": [],
		"memory": {},
	}
	if get_cpu_info:
		try:
			cpu_data = get_cpu_info()
			info["cpu"] = {
				"brand": cpu_data.get("brand_raw"),
				"arch": cpu_data.get("arch_string_raw"),
				"hz_advertised": cpu_data.get("hz_advertised_friendly"),
				"physical_cores": cpu_data.get("count"),
			}
		except Exception:
			pass
	if psutil:
		info.setdefault("cpu", {}).update(
			{
				"logical_cores": psutil.cpu_count(logical=True),
				"physical_cores": psutil.cpu_count(logical=False),
			}
		)
		vm = psutil.virtual_memory()
		info["memory"] = {
			"total": vm.total,
			"available": vm.available,
		}
	if pynvml:
		try:
			pynvml.nvmlInit()
			count = pynvml.nvmlDeviceGetCount()
			for idx in range(count):
				handle = pynvml.nvmlDeviceGetHandleByIndex(idx)
				mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
				name = pynvml.nvmlDeviceGetName(handle)
				name_str = name.decode("utf-8") if isinstance(name, bytes) else str(name)
				pci = pynvml.nvmlDeviceGetPciInfo(handle)
				bus = getattr(pci, "busId", "")
				if isinstance(bus, bytes):
					bus = bus.decode("utf-8")
				info["gpu"].append(
					{
						"name": name_str,
						"total_mem": mem.total,
						"pci": str(bus),
					}
				)
		except Exception:
			pass
	return info


def generate_trace_id(prefix: str = "trace") -> str:
	return f"{prefix}-{uuid4().hex}"


