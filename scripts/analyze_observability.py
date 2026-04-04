from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


MB = 1024 * 1024


def _safe_float(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return None


def _percentile(values: List[float], pct: float) -> Optional[float]:
    if not values:
        return None
    if pct <= 0:
        return min(values)
    if pct >= 100:
        return max(values)
    ordered = sorted(values)
    k = (len(ordered) - 1) * (pct / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _iso_to_dt(text: Any) -> Optional[datetime]:
    if not isinstance(text, str):
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                yield obj


@dataclass
class RunAccumulator:
    run_id: str
    jsonl_path: Path
    total_records: int = 0
    record_counts: Counter = field(default_factory=Counter)

    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    stop_duration_sec: Optional[float] = None

    gpu_util: List[float] = field(default_factory=list)
    gpu_power_w: List[float] = field(default_factory=list)
    gpu_energy_j: List[float] = field(default_factory=list)
    idle_events: int = 0
    idle_duration_sec: float = 0.0

    torch_allocated: List[int] = field(default_factory=list)
    torch_reserved: List[int] = field(default_factory=list)
    nvml_mem_used: List[int] = field(default_factory=list)

    frag_samples: List[float] = field(default_factory=list)

    stage_durations: Dict[str, float] = field(default_factory=lambda: defaultdict(float))
    stage_errors: Counter = field(default_factory=Counter)

    reliability_status: Counter = field(default_factory=Counter)
    reliability_stage_errors: Counter = field(default_factory=Counter)

    workload_requests: int = 0
    workload_latency_avg: Optional[float] = None
    workload_latency_p95: Optional[float] = None

    def ingest(self, record: Dict[str, Any]) -> None:
        self.total_records += 1
        record_type = record.get("record_type") or record.get("type") or "unknown"
        if not isinstance(record_type, str):
            record_type = "unknown"
        self.record_counts[record_type] += 1

        ts = _iso_to_dt(record.get("ts"))
        if ts is not None:
            if self.started_at is None or ts < self.started_at:
                self.started_at = ts
            if self.stopped_at is None or ts > self.stopped_at:
                self.stopped_at = ts

        payload = record.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if record_type == "session.start":
            started = _iso_to_dt(payload.get("started_at"))
            if started is not None:
                self.started_at = started

        elif record_type == "session.stop":
            duration = _safe_float(payload.get("duration_sec"))
            if duration is not None:
                self.stop_duration_sec = duration

        elif record_type == "gpu.monitor":
            stats = payload.get("stats")
            if not isinstance(stats, dict):
                stats = {}
            nvml = stats.get("nvml") if isinstance(stats.get("nvml"), dict) else {}
            torch_stats = stats.get("torch") if isinstance(stats.get("torch"), dict) else {}

            util = _safe_float(nvml.get("gpu_util"))
            if util is not None:
                self.gpu_util.append(util)

            power = _safe_float(nvml.get("power_w"))
            if power is not None:
                self.gpu_power_w.append(power)

            energy = _safe_float(nvml.get("energy_joules_total"))
            if energy is not None:
                self.gpu_energy_j.append(energy)

            used = _safe_int(nvml.get("mem_used"))
            if used is not None:
                self.nvml_mem_used.append(used)

            allocated = _safe_int(torch_stats.get("allocated"))
            if allocated is not None:
                self.torch_allocated.append(allocated)

            reserved = _safe_int(torch_stats.get("reserved"))
            if reserved is not None:
                self.torch_reserved.append(reserved)

            idle_event = stats.get("idle_event")
            if isinstance(idle_event, dict):
                idle_duration = _safe_float(idle_event.get("duration_sec"))
                if idle_duration is not None:
                    self.idle_duration_sec += idle_duration
                    self.idle_events += 1

        elif record_type == "memory.fragmentation":
            stats = payload.get("stats")
            if isinstance(stats, dict):
                frag = _safe_float(stats.get("fragmentation"))
                if frag is not None:
                    self.frag_samples.append(frag)

        elif record_type == "pipeline.segment":
            metrics = payload.get("metrics")
            if not isinstance(metrics, dict):
                metrics = {}
            stage = metrics.get("stage")
            if not isinstance(stage, str):
                stage = "unknown"
            duration = _safe_float(metrics.get("duration_sec"))
            if duration is not None:
                self.stage_durations[stage] += duration
            status = metrics.get("status")
            if isinstance(status, str) and status.lower() != "success":
                self.stage_errors[stage] += 1

        elif record_type == "reliability.stage":
            status = payload.get("status")
            stage = payload.get("stage")
            if isinstance(status, str):
                self.reliability_status[status] += 1
                if status != "success" and isinstance(stage, str):
                    self.reliability_stage_errors[stage] += 1

        elif record_type == "workload.session":
            req = _safe_int(payload.get("requests"))
            if req is not None:
                self.workload_requests = req
            lat_avg = _safe_float(payload.get("latency_avg"))
            if lat_avg is not None:
                self.workload_latency_avg = lat_avg
            lat_p95 = _safe_float(payload.get("latency_p95"))
            if lat_p95 is not None:
                self.workload_latency_p95 = lat_p95


@dataclass
class RunSummary:
    run_id: str
    jsonl_path: str
    output_root: str
    duration_sec: Optional[float]
    total_records: int
    record_counts: Dict[str, int]
    gpu: Dict[str, Any]
    memory: Dict[str, Any]
    pipeline: Dict[str, Any]
    reliability: Dict[str, Any]
    workload: Dict[str, Any]
    goals: Dict[str, Any]
    recommendations: List[str]


class ObservabilityAnalyzer:
    def analyze(self, jsonl_path: Path, output_root: Optional[Path] = None) -> RunSummary:
        records = list(_iter_jsonl(jsonl_path))
        if not records:
            raise ValueError(f"No readable records in: {jsonl_path}")

        run_id = self._resolve_run_id(records, jsonl_path)
        acc = RunAccumulator(run_id=run_id, jsonl_path=jsonl_path)

        for record in records:
            acc.ingest(record)

        duration_sec = acc.stop_duration_sec
        if duration_sec is None and acc.started_at and acc.stopped_at:
            duration_sec = max(0.0, (acc.stopped_at - acc.started_at).total_seconds())

        avg_gpu_util = statistics.mean(acc.gpu_util) if acc.gpu_util else None
        p95_gpu_util = _percentile(acc.gpu_util, 95)
        max_gpu_util = max(acc.gpu_util) if acc.gpu_util else None
        active_ratio = None
        if acc.gpu_util:
            active_samples = sum(1 for u in acc.gpu_util if u >= 50.0)
            active_ratio = active_samples / len(acc.gpu_util)

        avg_power = statistics.mean(acc.gpu_power_w) if acc.gpu_power_w else None
        peak_power = max(acc.gpu_power_w) if acc.gpu_power_w else None
        total_energy = max(acc.gpu_energy_j) if acc.gpu_energy_j else None

        peak_allocated = max(acc.torch_allocated) if acc.torch_allocated else None
        peak_reserved = max(acc.torch_reserved) if acc.torch_reserved else None
        peak_nvml_used = max(acc.nvml_mem_used) if acc.nvml_mem_used else None
        avg_frag = statistics.mean(acc.frag_samples) if acc.frag_samples else None

        stage_total = sum(acc.stage_durations.values()) if acc.stage_durations else 0.0
        top_stages = sorted(acc.stage_durations.items(), key=lambda x: x[1], reverse=True)[:5]

        gpu_goal_met = avg_gpu_util is not None and avg_gpu_util >= 80.0
        idle_ratio = None
        if duration_sec and duration_sec > 0:
            idle_ratio = acc.idle_duration_sec / duration_sec

        goals = {
            "gpu_utilization_target_pct": 80,
            "gpu_utilization_avg_pct": round(avg_gpu_util, 3) if avg_gpu_util is not None else None,
            "gpu_utilization_target_met": gpu_goal_met,
            "idle_ratio": round(idle_ratio, 4) if idle_ratio is not None else None,
        }

        recommendations = self._build_recommendations(
            avg_gpu_util=avg_gpu_util,
            idle_ratio=idle_ratio,
            avg_frag=avg_frag,
            peak_reserved=peak_reserved,
            peak_allocated=peak_allocated,
            top_stages=top_stages,
            stage_total=stage_total,
        )

        if output_root is None:
            if jsonl_path.parent.name.lower() == "observability":
                output_root = jsonl_path.parent.parent / "analysis"
            else:
                output_root = jsonl_path.parent / "analysis"
        output_root.mkdir(parents=True, exist_ok=True)

        summary = RunSummary(
            run_id=run_id,
            jsonl_path=str(jsonl_path),
            output_root=str(output_root),
            duration_sec=round(duration_sec, 6) if duration_sec is not None else None,
            total_records=acc.total_records,
            record_counts=dict(acc.record_counts),
            gpu={
                "samples": len(acc.gpu_util),
                "avg_util_pct": round(avg_gpu_util, 3) if avg_gpu_util is not None else None,
                "p95_util_pct": round(p95_gpu_util, 3) if p95_gpu_util is not None else None,
                "max_util_pct": round(max_gpu_util, 3) if max_gpu_util is not None else None,
                "active_ratio_util_ge_50": round(active_ratio, 4) if active_ratio is not None else None,
                "avg_power_w": round(avg_power, 3) if avg_power is not None else None,
                "peak_power_w": round(peak_power, 3) if peak_power is not None else None,
                "total_energy_j": round(total_energy, 3) if total_energy is not None else None,
                "idle_events": acc.idle_events,
                "idle_duration_sec": round(acc.idle_duration_sec, 4),
            },
            memory={
                "peak_torch_allocated_mb": round(peak_allocated / MB, 3) if peak_allocated is not None else None,
                "peak_torch_reserved_mb": round(peak_reserved / MB, 3) if peak_reserved is not None else None,
                "peak_nvml_used_mb": round(peak_nvml_used / MB, 3) if peak_nvml_used is not None else None,
                "avg_fragmentation": round(avg_frag, 4) if avg_frag is not None else None,
            },
            pipeline={
                "total_segment_duration_sec": round(stage_total, 6),
                "stage_durations_sec": {k: round(v, 6) for k, v in sorted(acc.stage_durations.items())},
                "top_stages": [{"stage": s, "duration_sec": round(d, 6)} for s, d in top_stages],
                "stage_errors": dict(acc.stage_errors),
            },
            reliability={
                "status_counts": dict(acc.reliability_status),
                "stage_errors": dict(acc.reliability_stage_errors),
            },
            workload={
                "requests": acc.workload_requests,
                "latency_avg_sec": round(acc.workload_latency_avg, 6) if acc.workload_latency_avg is not None else None,
                "latency_p95_sec": round(acc.workload_latency_p95, 6) if acc.workload_latency_p95 is not None else None,
            },
            goals=goals,
            recommendations=recommendations,
        )

        self._write_summary(output_root, summary)
        self._write_markdown(output_root, summary)
        return summary

    def _resolve_run_id(self, records: List[Dict[str, Any]], jsonl_path: Path) -> str:
        for record in records:
            run_id = record.get("run_id")
            if isinstance(run_id, str) and run_id:
                return run_id
        return jsonl_path.stem

    def _build_recommendations(
        self,
        *,
        avg_gpu_util: Optional[float],
        idle_ratio: Optional[float],
        avg_frag: Optional[float],
        peak_reserved: Optional[int],
        peak_allocated: Optional[int],
        top_stages: List[Tuple[str, float]],
        stage_total: float,
    ) -> List[str]:
        recs: List[str] = []

        if avg_gpu_util is not None and avg_gpu_util < 80:
            recs.append(
                "GPU average utilization is below target (<80%). Prioritize SCHED overlap across LLM/Image/TTS windows."
            )
        if idle_ratio is not None and idle_ratio > 0.2:
            recs.append(
                "Idle ratio is high (>20%). Introduce shorter stage chunks and prefetch/overlap next modality."
            )
        if avg_frag is not None and avg_frag > 0.35:
            recs.append(
                "Allocator fragmentation is high (>0.35). Strengthen POOL reuse and reduce frequent alloc/free bursts."
            )

        if peak_reserved and peak_allocated and peak_allocated > 0:
            reserve_ratio = peak_reserved / peak_allocated
            if reserve_ratio > 1.5:
                recs.append(
                    "Reserved/allocated memory ratio is high (>1.5). Consider periodic compaction and buffer pool sizing."
                )

        if stage_total > 0 and top_stages:
            lead_stage, lead_dur = top_stages[0]
            share = lead_dur / stage_total
            if share > 0.45:
                recs.append(
                    f"Stage '{lead_stage}' dominates runtime ({share:.1%}). Focus kernel graph capture/fusion in this stage first."
                )

        if not recs:
            recs.append("No major anomaly detected. Continue collecting runs and compare against baseline-0/baseline-1.")

        return recs

    def _write_summary(self, output_root: Path, summary: RunSummary) -> None:
        target = output_root / "observability_summary.json"
        payload = {
            "run_id": summary.run_id,
            "jsonl_path": summary.jsonl_path,
            "duration_sec": summary.duration_sec,
            "total_records": summary.total_records,
            "record_counts": summary.record_counts,
            "gpu": summary.gpu,
            "memory": summary.memory,
            "pipeline": summary.pipeline,
            "reliability": summary.reliability,
            "workload": summary.workload,
            "goals": summary.goals,
            "recommendations": summary.recommendations,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_markdown(self, output_root: Path, summary: RunSummary) -> None:
        target = output_root / "observability_summary.md"
        lines = [
            f"# Observability Summary: {summary.run_id}",
            "",
            f"- Source: `{summary.jsonl_path}`",
            f"- Duration (sec): `{summary.duration_sec}`",
            f"- Total records: `{summary.total_records}`",
            "",
            "## GPU",
            f"- Avg util (%): `{summary.gpu.get('avg_util_pct')}`",
            f"- P95 util (%): `{summary.gpu.get('p95_util_pct')}`",
            f"- Max util (%): `{summary.gpu.get('max_util_pct')}`",
            f"- Idle events: `{summary.gpu.get('idle_events')}`",
            f"- Idle duration (sec): `{summary.gpu.get('idle_duration_sec')}`",
            f"- Total energy (J): `{summary.gpu.get('total_energy_j')}`",
            "",
            "## Memory",
            f"- Peak torch allocated (MB): `{summary.memory.get('peak_torch_allocated_mb')}`",
            f"- Peak torch reserved (MB): `{summary.memory.get('peak_torch_reserved_mb')}`",
            f"- Peak NVML used (MB): `{summary.memory.get('peak_nvml_used_mb')}`",
            f"- Avg fragmentation: `{summary.memory.get('avg_fragmentation')}`",
            "",
            "## Pipeline",
            "| Stage | Duration (sec) |",
            "|---|---:|",
        ]
        for stage_item in summary.pipeline.get("top_stages", []):
            stage = stage_item.get("stage")
            duration = stage_item.get("duration_sec")
            lines.append(f"| {stage} | {duration} |")

        lines.extend([
            "",
            "## Goals",
            f"- GPU util target met: `{summary.goals.get('gpu_utilization_target_met')}`",
            f"- GPU util avg (%): `{summary.goals.get('gpu_utilization_avg_pct')}`",
            f"- Idle ratio: `{summary.goals.get('idle_ratio')}`",
            "",
            "## Recommendations",
        ])

        for rec in summary.recommendations:
            lines.append(f"- {rec}")

        target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _discover_jsonl_files(target: Path) -> List[Path]:
    if target.is_file() and target.suffix.lower() == ".jsonl":
        return [target]
    if not target.is_dir():
        return []

    direct = sorted(target.glob("*.jsonl"))
    if direct:
        return direct

    nested = sorted(target.glob("**/*.jsonl"))
    return nested


def _write_overview(output_dir: Path, summaries: List[RunSummary]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_target = output_dir / "observability_overview.json"
    md_target = output_dir / "observability_overview.md"

    payload = {
        "runs": [
            {
                "run_id": s.run_id,
                "jsonl_path": s.jsonl_path,
                "duration_sec": s.duration_sec,
                "avg_gpu_util_pct": s.gpu.get("avg_util_pct"),
                "p95_gpu_util_pct": s.gpu.get("p95_util_pct"),
                "peak_vram_mb": s.memory.get("peak_nvml_used_mb"),
                "gpu_target_met": s.goals.get("gpu_utilization_target_met"),
            }
            for s in summaries
        ],
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    json_target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Observability Overview",
        "",
        "| Run | Duration (sec) | Avg GPU Util % | P95 GPU Util % | Peak VRAM MB | Target Met |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for summary in summaries:
        lines.append(
            "| {run} | {dur} | {avg} | {p95} | {vram} | {ok} |".format(
                run=summary.run_id,
                dur=summary.duration_sec,
                avg=summary.gpu.get("avg_util_pct"),
                p95=summary.gpu.get("p95_util_pct"),
                vram=summary.memory.get("peak_nvml_used_mb"),
                ok=summary.goals.get("gpu_utilization_target_met"),
            )
        )

    md_target.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze observability JSONL outputs.")
    parser.add_argument(
        "target",
        nargs="?",
        default="runs",
        help="JSONL file, run directory, or root runs directory (default: runs)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory for overview files.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    target = Path(args.target)
    jsonl_files = _discover_jsonl_files(target)
    if not jsonl_files:
        raise SystemExit(f"No JSONL file found under: {target}")

    analyzer = ObservabilityAnalyzer()
    summaries: List[RunSummary] = []

    for jsonl_path in jsonl_files:
        summary = analyzer.analyze(jsonl_path)
        summaries.append(summary)
        print(
            f"[analyzed] {summary.run_id} avg_gpu={summary.gpu.get('avg_util_pct')}% "
            f"peak_vram={summary.memory.get('peak_nvml_used_mb')}MB"
        )

    if len(summaries) > 1:
        if args.output_dir:
            overview_dir = Path(args.output_dir)
        else:
            if target.is_dir() and target.name.lower() == "observability":
                overview_dir = target.parent / "analysis"
            else:
                overview_dir = target / "analysis" if target.is_dir() else target.parent / "analysis"
        _write_overview(overview_dir, summaries)
        print(f"[overview] {overview_dir}")


if __name__ == "__main__":
    main()
