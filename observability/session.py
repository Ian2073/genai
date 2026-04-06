"""
觀測 Session，統一管理各層 recorder 與輸出。
"""
from __future__ import annotations

import threading
import uuid
import random
from pathlib import Path
from typing import Any, Dict, Optional

from .config import Config
from .exporters import JsonlExporter, Exporter, NoOpExporter
from .infra import InfraRecorder, NullInfraRecorder
from .kernel import KernelRecorder, NullKernelRecorder
from .memory import MemoryRecorder, NullMemoryRecorder
from .monitors import MonitorManager, MonitorConfig
from .model_specific import ModelRecorder, NullModelRecorder
from .pipeline import NullPipelineRecorder, PipelineRecorder
from .reliability import NullReliabilityRecorder, ReliabilityRecorder
from .strategy import NullStrategyRecorder, StrategyRecorder
from .utils import build_env_metadata, monotonic_time, utc_now_iso
from .workload import NullWorkloadRecorder, WorkloadRecorder

_GLOBAL_SESSION: Optional["Session"] = None


class Session:
	@staticmethod
	def disabled() -> "Session":
		config = Config(
			enable_pipeline=False,
			enable_kernel=False,
			enable_memory=False,
			enable_strategy=False,
			enable_model=False,
			enable_workload=False,
			enable_infra=False,
			enable_reliability=False,
			enable_gpu_monitor=False,
			enable_cpu_monitor=False,
			capture_env=False,
			capture_torch_allocator=False,
			persist_output=False,
		)
		return Session(
			config,
			run_metadata={"disabled": True},
			exporter=NoOpExporter(),
		)

	def __init__(
		self,
		config: Config,
		run_metadata: Optional[Dict[str, Any]] = None,
		exporter: Optional[Exporter] = None,
	) -> None:
		self.config = config

		self.run_metadata = run_metadata or {}
		self.run_id = self.run_metadata.get("run_id") or f"{config.run_name}-{uuid.uuid4().hex[:8]}"
		self.start_ts = utc_now_iso()
		self._start_monotonic = monotonic_time()
		self._persist_output = getattr(config, "persist_output", True)

		if self._persist_output:
			base_output = Path(config.output_dir)
			run_dir = base_output / self.run_id if config.nest_run_dir else base_output
			run_dir.mkdir(parents=True, exist_ok=True)
			self.run_dir = run_dir
			self.output_path: Optional[Path] = self.run_dir / f"{self.run_id}.jsonl"
			default_exporter = JsonlExporter(self.output_path)
		else:
			self.run_dir = Path()
			self.output_path = None
			default_exporter = NoOpExporter()

		self._exporter = exporter or default_exporter
		self.pipeline = PipelineRecorder(self) if config.enable_pipeline else NullPipelineRecorder()
		self.kernel = KernelRecorder(self) if config.enable_kernel else NullKernelRecorder()
		self.memory = MemoryRecorder(self) if config.enable_memory else NullMemoryRecorder()
		self.strategy = StrategyRecorder(self) if config.enable_strategy else NullStrategyRecorder()
		self.model = ModelRecorder(self) if config.enable_model else NullModelRecorder()
		self.workload = WorkloadRecorder(self) if config.enable_workload else NullWorkloadRecorder()
		self.infra = InfraRecorder(self) if config.enable_infra else NullInfraRecorder()
		self.reliability = (
			ReliabilityRecorder(self) if config.enable_reliability else NullReliabilityRecorder()
		)
		self._monitors: Optional[MonitorManager] = None
		self._trace_counter = 0
		self._emit_session_start()
		if config.enable_infra:
			self.infra.record_hardware_snapshot()
			# self.infra.start_polling() is deprecated/no-op now
		self._start_monitors()

	def now(self) -> str:
		return utc_now_iso()

	def emit(self, record_type: str, payload: Dict[str, Any]) -> None:
		enriched = {
			"run_id": self.run_id,
			"record_type": record_type,
			"ts": self.now(),
			"payload": payload,
			"tags": self.config.tags,
		}
		if self.config.capture_env:
			enriched.setdefault("env", build_env_metadata())
		if self.run_metadata:
			enriched.setdefault("run_metadata", self.run_metadata)
		self._exporter.emit(record_type, enriched)

	def close(self) -> None:
		if getattr(self, '_closed', False):
			return
		self._closed = True
		try:
			if self._monitors:
				self._monitors.stop()
		except Exception:
			pass
		try:
			if self.config.enable_infra:
				self.infra.stop()
		except Exception:
			pass
		try:
			self.workload.flush_session_summary()
		except Exception:
			pass
		try:
			duration = monotonic_time() - self._start_monotonic
			self.emit(
				"session.stop",
				{
					"run_id": self.run_id,
					"duration_sec": round(duration, 3),
				},
			)
		except Exception:
			pass
		try:
			self._exporter.close()
		except Exception:
			pass

	def _emit_session_start(self) -> None:
		payload = {
			"run_id": self.run_id,
			"metadata": self.run_metadata,
			"config": {
				"run_name": self.config.run_name,
				"tags": self.config.tags,
				"enable_pipeline": self.config.enable_pipeline,
				"enable_kernel": self.config.enable_kernel,
				"enable_memory": self.config.enable_memory,
				"enable_strategy": self.config.enable_strategy,
				"enable_model": self.config.enable_model,
				"enable_workload": self.config.enable_workload,
				"enable_infra": self.config.enable_infra,
				"enable_reliability": self.config.enable_reliability,
			},
			"started_at": self.start_ts,
		}
		if self.config.capture_env:
			payload["env"] = build_env_metadata()
		self.emit("session.start", payload)

	def new_trace_id(self) -> str:
		self._trace_counter += 1
		return f"{self.config.request_trace_prefix}-{self._trace_counter:04d}-{uuid.uuid4().hex[:8]}"

	def _start_monitors(self) -> None:
		if not (self.config.enable_gpu_monitor or self.config.enable_cpu_monitor):
			return
		monitor_config = MonitorConfig(
			gpu_interval_sec=self.config.gpu_monitor_interval_sec,
			cpu_interval_sec=self.config.cpu_monitor_interval_sec,
			enable_gpu=self.config.enable_gpu_monitor,
			enable_cpu=self.config.enable_cpu_monitor,
		)
		self._monitors = MonitorManager(self, monitor_config)
		self._monitors.start()

	def should_sample(self, channel: str) -> bool:
		rate = self.config.sampling_rates.get(channel, 1.0)
		if rate >= 1.0:
			return True
		if rate <= 0.0:
			return False
		return random.random() < rate


def init_global_session(
	config: Config,
	run_metadata: Optional[Dict[str, Any]] = None,
) -> Session:
	global _GLOBAL_SESSION
	# 關閉舊的 session（避免 thread/file handle 洩漏）
	if _GLOBAL_SESSION is not None:
		try:
			_GLOBAL_SESSION.close()
		except Exception:
			pass
	session = Session(config, run_metadata=run_metadata)
	_GLOBAL_SESSION = session
	return session


def get_global_session() -> Optional[Session]:
	return _GLOBAL_SESSION


