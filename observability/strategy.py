"""
策略層觀測工具。
"""
from __future__ import annotations

from typing import Any, Dict


class StrategyRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session

	def record_state(self, state: Dict[str, Any]) -> None:
		self.session.emit(
			"strategy.state",
			{
				"state": state,
				"timestamp": self.session.now(),
			},
		)

	def record_action(self, action: Dict[str, Any]) -> None:
		self.session.emit(
			"strategy.action",
			{
				"action": action,
				"timestamp": self.session.now(),
			},
		)

	def record_reward(self, metrics: Dict[str, Any]) -> None:
		self.session.emit(
			"strategy.reward",
			{
				"metrics": metrics,
				"timestamp": self.session.now(),
			},
		)


class NullStrategyRecorder(StrategyRecorder):
	def __init__(self) -> None:
		pass

	def record_state(self, state: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def record_action(self, action: Dict[str, Any]) -> None:  # pragma: no cover
		return

	def record_reward(self, metrics: Dict[str, Any]) -> None:  # pragma: no cover
		return


