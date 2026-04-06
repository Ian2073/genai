"""
Infra 層紀錄：CPU / RAM / 磁碟 / 能耗監測。
"""
from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, Dict, Optional

from .utils import (
	collect_hardware_snapshot,
	gpu_power_snapshot,
	system_resource_snapshot,
)

if TYPE_CHECKING:
	from .session import Session


class InfraRecorder:
	def __init__(self, session: "Session") -> None:
		self.session = session
		self._thread: Optional[threading.Thread] = None
		self._stop_event = threading.Event()
		self._energy_joules = 0.0

	def record_hardware_snapshot(self) -> None:
		snapshot = collect_hardware_snapshot()
		self.session.emit("infra.hardware", snapshot)

	def start_polling(self) -> None:
		# Deprecated: Polling is now handled by MonitorManager (GpuMonitor/CpuMonitor)
		pass

	def stop(self) -> None:
		pass


class NullInfraRecorder(InfraRecorder):
	def __init__(self, *args, **kwargs) -> None:  # type: ignore[override]
		pass

	def record_hardware_snapshot(self) -> None:  # pragma: no cover
		return

	def start_polling(self) -> None:  # pragma: no cover
		return

	def stop(self) -> None:  # pragma: no cover
		return

