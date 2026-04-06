"""
模型層觀測工具。
"""
from __future__ import annotations

from typing import Any, Dict, Optional


class ModelRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session

	def record_llm(
		self,
		stage: str,
		metrics: Dict[str, Any],
		extra: Optional[Dict[str, Any]] = None,
	) -> None:
		self._emit("model.llm", stage, metrics, extra)

	def record_image(
		self,
		stage: str,
		metrics: Dict[str, Any],
		extra: Optional[Dict[str, Any]] = None,
	) -> None:
		self._emit("model.image", stage, metrics, extra)

	def record_tts(
		self,
		stage: str,
		metrics: Dict[str, Any],
		extra: Optional[Dict[str, Any]] = None,
	) -> None:
		self._emit("model.tts", stage, metrics, extra)

	def record_translator(
		self,
		stage: str,
		metrics: Dict[str, Any],
		extra: Optional[Dict[str, Any]] = None,
	) -> None:
		self._emit("model.translation", stage, metrics, extra)

	def _emit(
		self,
		record_type: str,
		stage: str,
		metrics: Dict[str, Any],
		extra: Optional[Dict[str, Any]],
	) -> None:
		self.session.emit(
			record_type,
			{
				"stage": stage,
				"metrics": metrics,
				"extra": extra or {},
				"timestamp": self.session.now(),
			},
		)


class NullModelRecorder(ModelRecorder):
	def __init__(self) -> None:
		pass

	def _emit(
		self,
		record_type: str,
		stage: str,
		metrics: Dict[str, Any],
		extra: Optional[Dict[str, Any]],
	) -> None:  # pragma: no cover
		return


