"""
Workload 層紀錄：請求 meta、複雜度、session 統計。
"""
from __future__ import annotations

import statistics
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
	from .session import Session


def _percentile(values: List[float], pct: float) -> Optional[float]:
	if not values:
		return None
	if pct <= 0:
		return min(values)
	if pct >= 100:
		return max(values)
	values_sorted = sorted(values)
	k = (len(values_sorted) - 1) * (pct / 100.0)
	f = int(k)
	c = min(f + 1, len(values_sorted) - 1)
	if f == c:
		return values_sorted[f]
	return values_sorted[f] + (values_sorted[c] - values_sorted[f]) * (k - f)


class WorkloadRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session
		self._lock = Lock()
		self._latencies: List[float] = []
		self._token_totals: List[int] = []
		self._requests = 0

	def register_request(self, trace_id: str, meta: Dict[str, Any]) -> None:
		self.session.emit(
			"workload.meta",
			{
				"trace_id": trace_id,
				"meta": meta,
			},
		)

	def record_concurrency(self, trace_id: str, level: int) -> None:
		self.session.emit(
			"workload.concurrency",
			{
				"trace_id": trace_id,
				"level": level,
			},
		)

	def record_input_complexity(self, trace_id: str, complexity: Dict[str, Any]) -> None:
		self.session.emit(
			"workload.complexity",
			{
				"trace_id": trace_id,
				"metrics": complexity,
			},
		)

	def finalize_request(self, trace_id: str, summary: Dict[str, Any]) -> None:
		duration = summary.get("duration_sec")
		token_total = summary.get("token_total")
		with self._lock:
			self._requests += 1
			if isinstance(duration, (int, float)):
				self._latencies.append(float(duration))
			if isinstance(token_total, (int, float)):
				self._token_totals.append(int(token_total))
		self.session.emit(
			"workload.result",
			{
				"trace_id": trace_id,
				"summary": summary,
			},
		)

	def flush_session_summary(self) -> None:
		with self._lock:
			if not self._requests:
				return
			latencies = list(self._latencies)
			tokens = list(self._token_totals)
		summary = {
			"requests": self._requests,
			"latency_avg": statistics.mean(latencies) if latencies else None,
			"latency_p95": _percentile(latencies, 95) if latencies else None,
			"latency_p99": _percentile(latencies, 99) if latencies else None,
			"token_avg": statistics.mean(tokens) if tokens else None,
		}
		self.session.emit("workload.session", summary)


class NullWorkloadRecorder(WorkloadRecorder):
	def __init__(self, *args, **kwargs) -> None:  # type: ignore[override]
		pass

	def register_request(self, trace_id: str, meta: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def record_concurrency(self, trace_id: str, level: int) -> None:  # pragma: no cover
		return

	def record_input_complexity(self, trace_id: str, complexity: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def finalize_request(self, trace_id: str, summary: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def flush_session_summary(self) -> None:  # pragma: no cover
		return

