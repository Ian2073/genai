"""
Observability 組態資料類別。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Sequence


@dataclass
class Config:
	"""控制觀測層級與輸出位置的設定。"""

	run_name: str = "default"
	output_dir: Path = Path("runs") / "observability"
	nest_run_dir: bool = True
	persist_output: bool = True
	enable_pipeline: bool = True
	enable_kernel: bool = True
	enable_memory: bool = True
	enable_strategy: bool = True
	enable_model: bool = True
	enable_workload: bool = True
	enable_infra: bool = True
	enable_reliability: bool = True
	enable_gpu_monitor: bool = True
	enable_cpu_monitor: bool = True
	# 優化後的監控間隔：從 0.5/1.0 秒提高到 2.0/3.0 秒
	# 這個頻率既能提供足夠的監測數據，又不會對系統造成負擔
	gpu_monitor_interval_sec: float = 2.0
	cpu_monitor_interval_sec: float = 3.0
	kernel_profile_event_limit: int = 200
	capture_env: bool = True
	capture_torch_allocator: bool = False
	enable_nvtx_markers: bool = False
	request_trace_prefix: str = "trace"
	auto_report_formats: Sequence[str] = ("parquet", "sqlite", "excel")
	tags: Dict[str, str] = field(default_factory=dict)
	sampling_rates: Dict[str, float] = field(
		default_factory=lambda: {
			"kernel": 0.25,
			"memory": 1.0,
			"workload": 1.0,
			"infra": 1.0,
		}
	)


