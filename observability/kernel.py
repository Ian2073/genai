"""
Kernel 層觀測工具與 PyTorch profiler 介面。
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Optional

try:
	import torch
	from torch.profiler import ProfilerActivity, profile
except Exception:  # pragma: no cover - torch/torch.profiler 可能不存在
	torch = None  # type: ignore
	ProfilerActivity = None  # type: ignore
	profile = None  # type: ignore


@contextmanager
def nvtx_range(msg: str, color: str = "blue"):
	"""
	Context manager for NVTX ranges.
	
	Args:
		msg: The message to display in Nsight Systems.
		color: Optional color (not directly supported by simple range_push, 
			   but kept for API compatibility if we upgrade to pynvml later).
	"""
	if torch and torch.cuda.is_available():
		torch.cuda.nvtx.range_push(msg)
	try:
		yield
	finally:
		if torch and torch.cuda.is_available():
			torch.cuda.nvtx.range_pop()


def mark_event(msg: str):
	"""Mark an instantaneous event."""
	if torch and torch.cuda.is_available():
		torch.cuda.nvtx.mark(msg)


class KernelRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session

	def record_launch(self, kernel_name: str, config: Dict[str, Any], metrics: Dict[str, Any]) -> None:
		self.session.emit(
			"kernel.launch",
			{
				"name": kernel_name,
				"config": config,
				"metrics": metrics,
				"timestamp": self.session.now(),
			},
		)

	def record_timeline(
		self,
		kernel_name: str,
		start_us: float,
		end_us: float,
		stream_id: Optional[int],
		overlap: Optional[float] = None,
		metadata: Optional[Dict[str, Any]] = None,
	) -> None:
		self.session.emit(
			"kernel.timeline",
			{
				"name": kernel_name,
				"start_us": start_us,
				"end_us": end_us,
				"duration_us": round(end_us - start_us, 3),
				"stream_id": stream_id,
				"overlap": overlap,
				"metadata": metadata or {},
			},
		)

	def record_graph_event(
		self,
		event_type: str,
		metadata: Optional[Dict[str, Any]] = None,
	) -> None:
		self.session.emit(
			"kernel.graph",
			{
				"event": event_type,
				"metadata": metadata or {},
				"timestamp": self.session.now(),
			},
		)

	def record_hotspot(self, module: str, stats: Dict[str, Any]) -> None:
		self.session.emit(
			"kernel.hotspot",
			{
				"module": module,
				"stats": stats,
				"timestamp": self.session.now(),
			},
		)

	@contextmanager
	def profile(
		self,
		trace_id: str,
		stage: str,
		metadata: Optional[Dict[str, Any]] = None,
	):
		if torch is None or profile is None or ProfilerActivity is None:
			yield
			return
		if not self.session.should_sample("kernel"):
			yield
			return
		
		# 長時間運行的任務（TTS、翻譯等）跳過 PyTorch profiler
		# — profiler 在 19 分鐘 XTTS 推理期間持續錄製 CUDA events，
		#   exit 時序列化耗費 20+ 分鐘，完全抵消了 profiling 的價值。
		long_running_stages = {"translation", "translation_llm", "voice", "voice_xtts", "tts", "story", "photo"}
		if stage in long_running_stages:
			yield
			return
		
		if torch.cuda.is_available():
			activities = [ProfilerActivity.CUDA]
		else:
			activities = [ProfilerActivity.CPU]

		prof = None
		try:
			prof = profile(
				activities=activities,
				record_shapes=False,
				with_stack=False,
				with_modules=False,
				with_flops=False,
				profile_memory=False,
			)
			prof.__enter__()
		except Exception as e:
			try:
				self.session.emit("kernel.error", {"trace_id": trace_id, "stage": stage, "error": str(e), "timestamp": self.session.now()})
			except Exception:
				pass
			prof = None

		try:
			yield
		finally:
			if prof is not None:
				try:
					prof.__exit__(None, None, None)
				except Exception as e:
					try:
						self.session.emit("kernel.error", {"trace_id": trace_id, "stage": stage, "error": f"Exit error: {e}", "timestamp": self.session.now()})
					except Exception:
						pass
					prof = None

			# 安全地處理 profiler 結果（僅短任務會走到這裡）
			if prof is not None:
				try:
					event_limit = self.session.config.kernel_profile_event_limit
					self._emit_profiler_events_safe(prof, trace_id, stage, metadata or {}, event_limit)
				except (MemoryError, RuntimeError, Exception) as e:
					try:
						self.session.emit(
							"kernel.error",
							{
								"trace_id": trace_id,
								"stage": stage,
								"error": f"Failed to emit profiler events: {e}",
								"timestamp": self.session.now(),
							},
						)
					except Exception:
						pass

	def _emit_profiler_events_safe(
		self,
		prof: "torch.profiler.profile",
		trace_id: str,
		stage: str,
		metadata: Dict[str, Any],
		event_limit: int,
	) -> None:
		"""安全地發送 profiler 事件，限制數量以避免 OOM。
		
		注意：不主動呼叫 gc.collect() 或 empty_cache()，
		因為它們在 CUDA 忙碌時可能各自卡住數秒。
		"""
		try:
			averages = list(prof.key_averages())[:event_limit]
		except (MemoryError, RuntimeError, Exception):
			return
		
		for item in averages:
			try:
				self.record_launch(
					item.key,
					{"trace_id": trace_id, "stage": stage},
					{
						"cpu_time_total_us": getattr(item, "cpu_time_total", None),
						"cuda_time_total_us": getattr(item, "cuda_time_total", None),
						"calls": getattr(item, "count", None),
					},
				)
			except Exception:
				break
		
		del averages

class NullKernelRecorder(KernelRecorder):
	def __init__(self) -> None:
		pass

	def record_launch(self, kernel_name: str, config: Dict[str, Any], metrics: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def record_timeline(
		self,
		kernel_name: str,
		start_us: float,
		end_us: float,
		stream_id: Optional[int],
		overlap: Optional[float] = None,
		metadata: Optional[Dict[str, Any]] = None,
	) -> None:  # pragma: no cover
		return

	def record_graph_event(self, event_type: str, metadata: Optional[Dict[str, Any]] = None) -> None:  # pragma: no cover
		return

	def record_hotspot(self, module: str, stats: Dict[str, Any]) -> None:  # pragma: no cover
		return

	@contextmanager
	def profile(self, *args, **kwargs):  # type: ignore[override]
		yield


