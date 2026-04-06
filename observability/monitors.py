"""
背景監測執行緒：負責 GPU / CPU / 系統資源的週期性採樣。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
	import psutil  # type: ignore
except Exception:  # pragma: no cover
	psutil = None  # type: ignore

try:
	import pynvml  # type: ignore
except Exception:  # pragma: no cover
	pynvml = None  # type: ignore

try:
	import torch
except Exception:  # pragma: no cover
	torch = None  # type: ignore


@dataclass
class MonitorConfig:
	gpu_interval_sec: float = 0.5
	cpu_interval_sec: float = 1.0
	enable_gpu: bool = True
	enable_cpu: bool = True
	enable_nvml_power: bool = True


class _BaseMonitor:
	def __init__(self, name: str, interval: float) -> None:
		self.name = name
		self.interval = interval
		self._stop = threading.Event()
		self._thread: Optional[threading.Thread] = None
		self._error_count = 0
		self._max_errors = 5

	def start(self) -> None:
		if self._thread and self._thread.is_alive():
			return
		self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
		self._thread.start()

	def stop(self, timeout: float = 1.5) -> None:
		self._stop.set()
		if self._thread and self._thread.is_alive():
			self._thread.join(timeout=timeout)

	def _run(self) -> None:
		while not self._stop.wait(self.interval):
			try:
				self.sample()
				self._error_count = 0  # 成功則重置錯誤計數
			except (Exception, MemoryError, OSError):
				self._error_count += 1
				if self._error_count > self._max_errors:
					# 連續失敗超過上限，永久停止監控以保護主程式
					break
				continue

	def sample(self) -> None:  # pragma: no cover - interface
		raise NotImplementedError


class GpuMonitor(_BaseMonitor):
	def __init__(self, session: "ObservabilitySession", config: MonitorConfig) -> None:
		super().__init__("gpu-monitor", config.gpu_interval_sec)
		self.session = session
		self.config = config
		self._nvml_initialized = False
		self._device_index = 0
		self._idle_start: Optional[float] = None
		self._idle_events: int = 0
		self._energy_joules: float = 0.0
		if pynvml is not None:
			try:
				pynvml.nvmlInit()
				self._nvml_initialized = True
			except Exception:
				self._nvml_initialized = False

	def _nvml_snapshot(self) -> Dict[str, Any]:
		if not self._nvml_initialized:
			return {}
		try:
			handle = pynvml.nvmlDeviceGetHandleByIndex(self._device_index)
			util = pynvml.nvmlDeviceGetUtilizationRates(handle)
			mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
			power = None
			if self.config.enable_nvml_power:
				try:
					power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
					# Accumulate energy: Power (W) * Time (s) = Energy (J)
					# Note: This is an approximation based on the sampling interval
					self._energy_joules += power * self.config.gpu_interval_sec
				except Exception:
					power = None
			return {
				"gpu_util": util.gpu,
				"mem_util": util.memory,
				"mem_total": mem.total,
				"mem_used": mem.used,
				"mem_free": mem.free,
				"power_w": power,
				"energy_joules_total": round(self._energy_joules, 3) if power is not None else None,
			}
		except Exception:
			return {}

	def _torch_snapshot(self) -> Dict[str, Any]:
		if torch is None or not torch.cuda.is_available():
			return {}
		try:
			device = torch.cuda.current_device()
		except Exception:
			device = 0
		stats: Dict[str, Any] = {}
		try:
			stats = {
				"allocated": torch.cuda.memory_allocated(device),
				"reserved": torch.cuda.memory_reserved(device),
				"max_allocated": torch.cuda.max_memory_allocated(device),
				"max_reserved": torch.cuda.max_memory_reserved(device),
			}
		except Exception:
			pass
		return stats

	def sample(self) -> None:
		now = time.time()
		try:
			nvml_data = self._nvml_snapshot()
			torch_data = self._torch_snapshot()
		except (Exception, MemoryError, OSError):
			# 捕獲錯誤，讓 _BaseMonitor 處理
			raise
			
		payload = {
			"nvml": nvml_data,
			"torch": torch_data,
		}
		gpu_util = payload["nvml"].get("gpu_util") if payload["nvml"] else None
		if gpu_util is not None:
			if gpu_util < 5:
				if self._idle_start is None:
					self._idle_start = now
			else:
				if self._idle_start is not None:
					idle_duration = now - self._idle_start
					self._idle_start = None
					self._idle_events += 1
					payload["idle_event"] = {
						"duration_sec": round(idle_duration, 4),
						"count": self._idle_events,
					}
		self.session.emit(
			"gpu.monitor",
			{
				"stats": payload,
				"timestamp": self.session.now(),
			},
		)


class CpuMonitor(_BaseMonitor):
	def __init__(self, session: "ObservabilitySession", config: MonitorConfig) -> None:
		super().__init__("cpu-monitor", config.cpu_interval_sec)
		self.session = session
		self.config = config

	def sample(self) -> None:
		if psutil is None:
			return
		try:
			process = psutil.Process()
			with process.oneshot():
				cpu_percent = process.cpu_percent(interval=None)
				# 使用 memory_info() 替代 memory_full_info()
				# memory_full_info() 在 Windows 上會觸發高開銷的 USS 計算
				# 在記憶體吃緊時會導致 MemoryError 並卡死整個程式
				mem = process.memory_info()
				num_threads = process.num_threads()
			system = psutil.virtual_memory()
			cpu_times = psutil.cpu_times_percent(interval=None)
			
			# Add Disk and Network I/O
			io = psutil.disk_io_counters(perdisk=False)
			net = psutil.net_io_counters(pernic=False)
			
			payload = {
				"process": {
					"cpu_percent": cpu_percent,
					"rss": getattr(mem, "rss", None),
					"vms": getattr(mem, "vms", None),
					"shared": getattr(mem, "shared", None),
					"num_threads": num_threads,
				},
				"system": {
					"cpu_user": getattr(cpu_times, "user", None),
					"cpu_system": getattr(cpu_times, "system", None),
					"cpu_idle": getattr(cpu_times, "idle", None),
					"ram_total": system.total,
					"ram_available": system.available,
					"ram_used": system.used,
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
			self.session.emit(
				"cpu.monitor",
				{
					"stats": payload,
					"timestamp": self.session.now(),
				},
			)
		except (Exception, MemoryError, OSError):
			# 捕獲所有可能的錯誤，讓 _BaseMonitor 的錯誤計數機制處理
			raise


class MonitorManager:
	def __init__(self, session: "Session", config: MonitorConfig) -> None:
		self.session = session
		self.config = config
		self.gpu_monitor: Optional[GpuMonitor] = (
			GpuMonitor(session, config) if config.enable_gpu else None
		)
		self.cpu_monitor: Optional[CpuMonitor] = (
			CpuMonitor(session, config) if config.enable_cpu else None
		)

	def start(self) -> None:
		if self.gpu_monitor:
			self.gpu_monitor.start()
		if self.cpu_monitor:
			self.cpu_monitor.start()

	def stop(self) -> None:
		if self.gpu_monitor:
			self.gpu_monitor.stop()
		if self.cpu_monitor:
			self.cpu_monitor.stop()


