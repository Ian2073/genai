"""
Reliability / Fault 觀測工具。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class ReliabilityRecorder:
	def __init__(self, session: "ObservabilitySession") -> None:
		self.session = session

	def record_stage_outcome(
		self,
		trace_id: str,
		stage: str,
		status: str,
		duration_sec: Optional[float] = None,
		error_type: Optional[str] = None,
		details: Optional[str] = None,
		degradation: Optional[Dict[str, Any]] = None,
	) -> None:
		payload = {
			"trace_id": trace_id,
			"stage": stage,
			"status": status,
			"duration_sec": duration_sec,
			"error_type": error_type,
			"details": details,
			"degradation": degradation or {},
		}
		self.session.emit("reliability.stage", payload)

	def record_retry(
		self,
		trace_id: str,
		stage: str,
		attempt: int,
		success: bool,
		delay_sec: Optional[float] = None,
	) -> None:
		self.session.emit(
			"reliability.retry",
			{
				"trace_id": trace_id,
				"stage": stage,
				"attempt": attempt,
				"success": success,
				"delay_sec": delay_sec,
			},
		)

	def record_numeric_anomaly(
		self,
		trace_id: str,
		stage: str,
		indicator: str,
		value: Any,
		threshold: Optional[Any] = None,
	) -> None:
		self.session.emit(
			"reliability.numeric",
			{
				"trace_id": trace_id,
				"stage": stage,
				"indicator": indicator,
				"value": value,
				"threshold": threshold,
			},
		)


class NullReliabilityRecorder(ReliabilityRecorder):
	def __init__(self, *args, **kwargs) -> None:  # type: ignore[override]
		pass

	def record_stage_outcome(
		self,
		trace_id: str,
		stage: str,
		status: str,
		duration_sec: Optional[float] = None,
		error_type: Optional[str] = None,
		details: Optional[str] = None,
		degradation: Optional[Dict[str, Any]] = None,
	) -> None:  # pragma: no cover
		return

	def record_retry(
		self,
		trace_id: str,
		stage: str,
		attempt: int,
		success: bool,
		delay_sec: Optional[float] = None,
	) -> None:  # pragma: no cover
		return

	def record_numeric_anomaly(
		self,
		trace_id: str,
		stage: str,
		indicator: str,
		value: Any,
		threshold: Optional[Any] = None,
	) -> None:  # pragma: no cover
		return

