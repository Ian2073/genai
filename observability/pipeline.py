"""
Pipeline 層紀錄工具。
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, Optional

from .utils import monotonic_time


@dataclass
class PipelineSpanHandle:
	"""供外部進一步標記 checkpoint 的控制器。"""

	recorder: "PipelineRecorder"
	span_id: str

	def checkpoint(self, name: str, metadata: Optional[Dict[str, Any]] = None) -> None:
		self.recorder.record_checkpoint(self.span_id, name, metadata or {})


class PipelineRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session

	@contextmanager
	def span(
		self,
		name: str,
		category: str,
		metadata: Optional[Dict[str, Any]] = None,
		capture_gpu: bool = False,
		trace_id: Optional[str] = None,
	) -> Iterator[PipelineSpanHandle]:
		start_wall = self.session.now()
		start_perf = monotonic_time()
		span_id = str(uuid.uuid4())
		meta = metadata or {}
		payload = {
			"span_id": span_id,
			"name": name,
			"category": category,
			"metadata": meta,
			"status": "start",
		}
		if trace_id:
			payload["trace_id"] = trace_id
		if capture_gpu:
			payload["gpu_start"] = self._quick_gpu_snapshot()
		self.session.emit("pipeline.span", payload)
		status = "ok"
		try:
			yield PipelineSpanHandle(self, span_id)
		except Exception:
			status = "error"
			raise
		finally:
			duration = monotonic_time() - start_perf
			end_payload = {
				"span_id": span_id,
				"name": name,
				"category": category,
				"metadata": meta,
				"status": status,
				"duration_sec": round(duration, 6),
				"finished_at": self.session.now(),
			}
			if trace_id:
				end_payload["trace_id"] = trace_id
			if capture_gpu:
				end_payload["gpu_end"] = self._quick_gpu_snapshot()
			self.session.emit("pipeline.span", end_payload)

	def _quick_gpu_snapshot(self) -> Dict[str, Any]:
		"""O(1) GPU 記憶體快照 — 不走 emit，不呼叫 memory_stats。"""
		try:
			import torch as _torch
			if _torch.cuda.is_available():
				d = _torch.cuda.current_device()
				return {
					"allocated": _torch.cuda.memory_allocated(d),
					"reserved": _torch.cuda.memory_reserved(d),
				}
		except Exception:
			pass
		return {}

	def record_checkpoint(self, span_id: str, name: str, metadata: Dict[str, Any]) -> None:
		self.session.emit(
			"pipeline.checkpoint",
			{
				"span_id": span_id,
				"name": name,
				"metadata": metadata,
				"timestamp": self.session.now(),
			},
		)

	def record_switch(
		self,
		source: str,
		target: str,
		metadata: Optional[Dict[str, Any]] = None,
	) -> None:
		self.session.emit(
			"pipeline.switch",
			{
				"source": source,
				"target": target,
				"metadata": metadata or {},
				"timestamp": self.session.now(),
			},
		)

	def record_pipeline_state(self, state: Dict[str, Any]) -> None:
		self.session.emit(
			"pipeline.state",
			{
				"state": state,
				"timestamp": self.session.now(),
			},
		)

	def record_segment(
		self,
		trace_id: str,
		stage: str,
		metrics: Dict[str, Any],
	) -> None:
		payload = {
			"trace_id": trace_id,
			"stage": stage,
			"metrics": metrics,
			"timestamp": self.session.now(),
		}
		self.session.emit("pipeline.segment", payload)


class NullPipelineRecorder(PipelineRecorder):
	"""關閉時的空實作。"""

	def __init__(self) -> None:
		pass

	@contextmanager
	def span(self, *args, trace_id: Optional[str] = None, **kwargs):  # type: ignore[override]
		yield PipelineSpanHandle(self, span_id="noop")

	def record_checkpoint(self, span_id: str, name: str, metadata: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def record_switch(self, source: str, target: str, metadata: Optional[Dict[str, Any]] = None) -> None:  # pragma: no cover
		return

	def record_pipeline_state(self, state: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def record_segment(self, trace_id: str, stage: str, metrics: Dict[str, Any]) -> None:  # pragma: no cover
		return


