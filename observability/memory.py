"""
記憶體層觀測工具。
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Dict, Optional

try:
	import torch
except Exception:  # pragma: no cover - torch 可能不存在
	torch = None  # type: ignore

from .utils import torch_allocator_fragmentation, torch_memory_snapshot


class MemoryRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session

	def snapshot(self, label: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
		try:
			snapshot = torch_memory_snapshot()
		except (MemoryError, RuntimeError, Exception):
			# 如果記憶體快照失敗，返回空快照但不影響主程式
			snapshot = {}
		payload = {
			"label": label,
			"metadata": metadata or {},
			"snapshot": snapshot,
			"timestamp": self.session.now(),
		}
		try:
			self.session.emit("memory.snapshot", payload)
		except Exception:
			# 如果 emit 失敗，跳過但不影響主程式
			pass
		return snapshot

	def record_allocation(
		self,
		ptr: int,
		size: int,
		module: str,
		owner: str,
		lifetime_sec: Optional[float] = None,
	) -> None:
		self.session.emit(
			"memory.alloc",
			{
				"ptr": ptr,
				"size": size,
				"module": module,
				"owner": owner,
				"lifetime_sec": lifetime_sec,
				"timestamp": self.session.now(),
			},
		)

	def record_free(self, ptr: int, size: int, module: str) -> None:
		self.session.emit(
			"memory.free",
			{
				"ptr": ptr,
				"size": size,
				"module": module,
				"timestamp": self.session.now(),
			},
		)

	def fragmentation(self, label: Optional[str] = None) -> Dict[str, Any]:
		try:
			stats = torch_allocator_fragmentation()
		except Exception:
			stats = {}
		try:
			self.session.emit(
				"memory.fragmentation",
				{
					"label": label,
					"stats": stats,
					"timestamp": self.session.now(),
				},
			)
		except Exception:
			pass
		return stats

	def record_pool_event(self, pool_name: str, stats: Dict[str, Any]) -> None:
		self.session.emit(
			"memory.pool",
			{
				"pool": pool_name,
				"stats": stats,
				"timestamp": self.session.now(),
			},
		)

	def capture_allocator_snapshot(
		self,
		trace_id: str,
		stage: str,
		metadata: Optional[Dict[str, Any]] = None,
	) -> None:
		if not self.session.config.capture_torch_allocator:
			return
		if not self.session.should_sample("memory"):
			return
		if torch is None or not torch.cuda.is_available():
			return
		try:
			# memory_snapshot() 在記憶體壓力大時可能很慢，加入超時保護
			raw_snapshot = torch.cuda.memory_snapshot()  # type: ignore[attr-defined]
		except (MemoryError, RuntimeError, Exception):  # pragma: no cover - API 可能不存在或 OOM
			# 如果記憶體快照失敗，跳過但不影響主程式
			return
		try:
			summary = self._summarize_snapshot(raw_snapshot)
			payload = {
				"trace_id": trace_id,
				"stage": stage,
				"metadata": metadata or {},
				"summary": summary,
			}
			self.session.emit("memory.alloc_trace", payload)
		except (MemoryError, RuntimeError, Exception):
			# 如果處理快照失敗，跳過但不影響主程式
			pass

	def _summarize_snapshot(self, snapshot: Any) -> Dict[str, Any]:
		if not isinstance(snapshot, list):
			return {"raw": snapshot}
		segment_counts = Counter()
		block_histogram: Counter[int] = Counter()
		active_bytes = 0
		for item in snapshot:
			segment_type = item.get("segment_type")
			segment_counts[segment_type] += 1
			blocks = item.get("blocks") or []
			for block in blocks:
				size = block.get("size", 0)
				block_histogram[size] += 1
				if block.get("state") == "active_allocated":
					active_bytes += size
		top_blocks = [
			{"size": size, "count": count}
			for size, count in block_histogram.most_common(20)
		]
		return {
			"segments": segment_counts,
			"active_bytes": active_bytes,
			"block_histogram": top_blocks,
		}


class NullMemoryRecorder(MemoryRecorder):
	def __init__(self) -> None:
		pass

	def snapshot(self, label: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:  # pragma: no cover
		return {}

	def record_allocation(
		self,
		ptr: int,
		size: int,
		module: str,
		owner: str,
		lifetime_sec: Optional[float] = None,
	) -> None:  # pragma: no cover
		return

	def record_free(self, ptr: int, size: int, module: str) -> None:  # pragma: no cover
		return

	def fragmentation(self, label: Optional[str] = None) -> Dict[str, Any]:  # pragma: no cover
		return {}

	def record_pool_event(self, pool_name: str, stats: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def capture_allocator_snapshot(
		self,
		trace_id: str,
		stage: str,
		metadata: Optional[Dict[str, Any]] = None,
	) -> None:  # pragma: no cover
		return


