"""Product-style local dashboard for orchestration control and operations insight."""

from __future__ import annotations

import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import runtime.compat
import subprocess
import sys
import threading
import time
import re
import traceback
import psutil
try:
    import pynvml
except Exception:  # pragma: no cover - optional dependency on CPU-only hosts
    pynvml = None

try:
    _SYSTEM_STATUS_CACHE_TTL_SEC = max(0.2, float(os.environ.get("DASHBOARD_SYSTEM_STATUS_CACHE_SEC", "1.0")))
except (TypeError, ValueError):
    _SYSTEM_STATUS_CACHE_TTL_SEC = 2.0

_SYSTEM_STATUS_LOCK = threading.Lock()
_SYSTEM_STATUS_CACHE: Dict[str, Any] = {"cached_at": 0.0, "value": None}
_NVML_INIT_ATTEMPTED = False
_NVML_SUPPORTED = False
_DASHBOARD_API_VERSION = "2026-04-07.1"
_STALE_RUN_RECOVERY_GRACE_SEC = 45.0


def _dashboard_capabilities() -> Dict[str, Any]:
    return {
        "queue_api": True,
        "alerts_api": True,
        "capacity_api": True,
        "configs_api": True,
        "system_cpu": True,
        "system_processes": True,
        "system_sampled_at": True,
        "system_model_cache": True,
    }


def _clone_system_status(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "api_version": str(payload.get("api_version") or _DASHBOARD_API_VERSION),
        "capabilities": dict(payload.get("capabilities") or {}),
        "cpu": dict(payload.get("cpu") or {}),
        "ram": dict(payload.get("ram") or {}),
        "gpus": [dict(item) for item in (payload.get("gpus") or [])],
        "processes": {
            str(name): dict(details)
            for name, details in (payload.get("processes") or {}).items()
            if isinstance(details, dict)
        },
        "model_cache": [dict(item) for item in (payload.get("model_cache") or [])],
        "model_plan": dict(payload.get("model_plan") or {}),
        "sampled_at": str(payload.get("sampled_at") or ""),
    }


def _snapshot_process(pid: Any, *, label: str = "") -> Optional[Dict[str, Any]]:
    process_id = _safe_int(pid, 0, min_value=0)
    if process_id <= 0:
        return None
    try:
        proc = psutil.Process(process_id)
        mem = proc.memory_info()
        try:
            cpu_percent = round(float(proc.cpu_percent(interval=None)), 1)
        except Exception:
            cpu_percent = 0.0
        try:
            process_name = str(proc.name() or label or f"pid={process_id}")
        except Exception:
            process_name = label or f"pid={process_id}"
        try:
            status = str(proc.status() or "unknown")
        except Exception:
            status = "unknown"
        try:
            threads = int(proc.num_threads() or 0)
        except Exception:
            threads = 0
        try:
            uptime_sec = round(max(0.0, time.time() - float(proc.create_time() or time.time())), 1)
        except Exception:
            uptime_sec = 0.0
        return {
            "pid": process_id,
            "label": label or process_name,
            "name": process_name,
            "status": status,
            "cpu_percent": cpu_percent,
            "rss": int(mem.rss),
            "threads": threads,
            "uptime_sec": uptime_sec,
        }
    except Exception:
        return None


def _build_runtime_process_status() -> Tuple[Dict[str, Dict[str, Any]], List[Dict[str, Any]]]:
    processes: Dict[str, Dict[str, Any]] = {}
    model_cache: List[Dict[str, Any]] = []

    dashboard_snapshot = _snapshot_process(os.getpid(), label="dashboard")
    if dashboard_snapshot:
        processes["dashboard"] = dashboard_snapshot

    handler_cls = globals().get("DashboardHandler")
    runtime = getattr(handler_cls, "runtime", None) if handler_cls is not None else None
    if runtime is None:
        return processes, model_cache

    chief_pid = 0
    with getattr(runtime, "lock", threading.Lock()):
        process = getattr(runtime, "process", None)
        if process is not None and getattr(process, "poll", None) is not None and process.poll() is None:
            chief_pid = _safe_int(getattr(process, "pid", 0), 0, min_value=0)

    chief_snapshot = _snapshot_process(chief_pid, label="chief")
    if chief_snapshot:
        processes["chief"] = chief_snapshot

    now_ts = time.time()
    cache_lock = getattr(runtime, "model_cache_lock", None)
    slots = getattr(runtime, "model_slots", None)
    if cache_lock is None or not isinstance(slots, dict):
        return processes, model_cache

    with cache_lock:
        for kind, slot in slots.items():
            if not isinstance(slot, dict):
                continue
            model_cache.append(
                {
                    "kind": str(kind),
                    "in_use": _safe_int(slot.get("in_use"), 0, min_value=0),
                    "offloaded": bool(slot.get("offloaded")),
                    "idle_sec": round(max(0.0, now_ts - _safe_float(slot.get("last_used_ts"), now_ts)), 1),
                }
            )
    model_cache.sort(key=lambda item: str(item.get("kind") or ""))
    return processes, model_cache


def _build_model_plan_status() -> Dict[str, Any]:
    try:
        hardware = detect_hardware_profile()
        recommended_plan = choose_plan_key("auto", hardware)
        spec = MODEL_PLAN_SPECS.get(recommended_plan)
        return {
            "recommended_plan": recommended_plan,
            "description": getattr(spec, "description", ""),
            "hardware": {
                "accelerator": hardware.accelerator,
                "gpu_count": hardware.gpu_count,
                "gpu_names": list(hardware.gpu_names),
                "gpu_vram_gb": round(float(hardware.gpu_vram_gb), 1),
                "system_ram_gb": round(float(hardware.system_ram_gb), 1),
                "cuda_version": hardware.cuda_version or "",
            },
        }
    except Exception:
        return {
            "recommended_plan": "balanced",
            "description": "",
            "hardware": {
                "accelerator": "unknown",
                "gpu_count": 0,
                "gpu_names": [],
                "gpu_vram_gb": 0.0,
                "system_ram_gb": 0.0,
                "cuda_version": "",
            },
        }


def get_system_status():
    global _NVML_INIT_ATTEMPTED, _NVML_SUPPORTED

    now = time.monotonic()
    with _SYSTEM_STATUS_LOCK:
        cached_value = _SYSTEM_STATUS_CACHE.get("value")
        cached_at = float(_SYSTEM_STATUS_CACHE.get("cached_at") or 0.0)
        if cached_value is not None and (now - cached_at) < _SYSTEM_STATUS_CACHE_TTL_SEC:
            return _clone_system_status(cached_value)

        mem = psutil.virtual_memory()
        gpus: List[Dict[str, Any]] = []

        if not _NVML_INIT_ATTEMPTED:
            _NVML_INIT_ATTEMPTED = True
            if pynvml is not None:
                try:
                    pynvml.nvmlInit()
                    _NVML_SUPPORTED = True
                except Exception:
                    _NVML_SUPPORTED = False

        if _NVML_SUPPORTED and pynvml is not None:
            try:
                for i in range(pynvml.nvmlDeviceGetCount()):
                    handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                    name = pynvml.nvmlDeviceGetName(handle)
                    if isinstance(name, bytes):
                        name = name.decode("utf-8", errors="replace")
                    mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                    util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                    gpus.append(
                        {
                            "id": i,
                            "name": str(name),
                            "vram_total": mem_info.total,
                            "vram_used": mem_info.used,
                            "vram_percent": round((mem_info.used / mem_info.total) * 100, 1)
                            if mem_info.total
                            else 0.0,
                            "gpu_util": util.gpu,
                        }
                    )
            except Exception:
                gpus = []

        processes, model_cache = _build_runtime_process_status()

        payload: Dict[str, Any] = {
            "api_version": _DASHBOARD_API_VERSION,
            "capabilities": _dashboard_capabilities(),
            "cpu": {
                "percent": round(float(psutil.cpu_percent(interval=None)), 1),
                "logical_count": int(psutil.cpu_count(logical=True) or 0),
            },
            "ram": {
                "total": mem.total,
                "used": mem.used,
                "percent": mem.percent,
            },
            "gpus": gpus,
            "processes": processes,
            "model_cache": model_cache,
            "model_plan": _build_model_plan_status(),
            "sampled_at": _utc_now_iso(),
        }
        _SYSTEM_STATUS_CACHE["cached_at"] = now
        _SYSTEM_STATUS_CACHE["value"] = payload
        return _clone_system_status(payload)

import webbrowser
from collections import deque
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Deque, Dict, List, Optional, Sequence, Tuple
 
 
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from utils import (
  list_character_prompt_files,
  list_page_prompt_files,
  load_or_create_seed,
  load_prompt,
  page_number_from_prompt,
)
from runtime.story_files import (
  detect_story_languages,
  find_latest_story_root,
  list_generated_audio_files,
)

from .model_plan import (
    MODEL_PLAN_SPECS,
    choose_plan_key,
    classify_image_model,
    classify_image_provider,
    detect_hardware_profile,
    resolve_image_defaults,
)
from .options import AGE_CHOICES, CATEGORY_CHOICES, DEFAULT_CHIEF_OPTIONS, parse_dtype

_LOG_BUFFER_SIZE = 2000
_RUN_LOG_BUFFER_SIZE = 3000
_HISTORY_LIMIT = 120
_ALERT_LIMIT = 200
_QUEUE_LIMIT = 120
_CONFIG_LIMIT = 120
_CAPACITY_WINDOW = 40
_MODULE_QUEUE_LIMIT = 180
_MODULE_HISTORY_LIMIT = 200
_DEFAULT_GPU_HOURLY_USD = 0.85
_MODEL_REUSE_WINDOW_SEC_DEFAULT = 150
_MODEL_CLEANUP_WINDOW_SEC_DEFAULT = 900
_MODEL_REAPER_INTERVAL_SEC = 10
_LOG_LINE_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})(?:,\d+)?\s+\[(?P<level>[A-Za-z]+)\]\s?(?P<msg>.*)$"
)
_BOOK_RUN_DIR_PATTERN = re.compile(
    r"^.+?_book-(?P<book_index>\d+)_of_(?P<book_total>\d+)_run-(?P<run_seq>\d+)$",
    re.IGNORECASE,
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_int(
    value: Any,
    default: int,
    *,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _safe_text(value: Any, *, default: str = "", max_length: int = 4000) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if max_length > 0 and len(text) > max_length:
        text = text[:max_length]
    return text


def _safe_report_branch_token(value: Any, *, default: str = "canonical") -> str:
    text = _safe_text(value, default=default, max_length=120)
    token = re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")
    return token or default


def _normalize_eval_source(value: Any, *, default: str = "latest") -> str:
    token = _safe_text(value, default=default, max_length=40).lower()
    if token in {"run", "run_id"}:
        return "run"
    if token in {"story", "story_root", "path"}:
        return "story_root"
    return "latest"


def _normalize_pre_eval_policy(value: Any, *, default: str = "stop") -> str:
    token = _safe_text(value, default=default, max_length=16).lower()
    if token in {"stop", "hard_stop", "hard-stop"}:
        return "stop"
    return "warn"


def _normalize_progress_line(line: str) -> str:
    # Some Windows code pages turn unicode bar glyphs into replacement pairs
    # like "�i" in tqdm output. Normalize these pairs to readable ASCII.
    if "�" in line and "%" in line and "|" in line:
        return re.sub(r"�.", "#", line)
    return line


def _build_subprocess_env() -> Dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PYTHONUNBUFFERED", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    # Do not force TQDM_ASCII via env string; a single-char value can break tqdm
    # formatting (nsyms=0) in some call paths.
    return env


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.environ.get(name, "")).strip().lower()
    if not raw:
        return bool(default)
    return raw in {"1", "true", "yes", "on"}


def _process_cmdline_text(cmdline: Any) -> str:
    if isinstance(cmdline, (list, tuple)):
        return " ".join(str(part) for part in cmdline if part is not None)
    return str(cmdline or "")


def _looks_like_dashboard_process(cmdline: Any) -> bool:
    text = _process_cmdline_text(cmdline)
    normalized = " ".join(text.lower().replace('"', " ").split())
    return "--dashboard" in normalized and "-m pipeline" in normalized


def _collect_port_listener_processes(port: int) -> List[psutil.Process]:
    target_port = _safe_int(port, 8765, min_value=1, max_value=65535)
    try:
        conns = psutil.net_connections(kind="tcp")
    except Exception:
        return []

    seen: Dict[int, psutil.Process] = {}
    for conn in conns:
        if conn.status != psutil.CONN_LISTEN:
            continue
        laddr = conn.laddr
        local_port: Optional[int] = None
        if hasattr(laddr, "port"):
            local_port = getattr(laddr, "port")
        elif isinstance(laddr, tuple) and len(laddr) >= 2:
            local_port = _safe_int(laddr[1], default=0, min_value=0, max_value=65535)
        if local_port != target_port:
            continue
        pid = _safe_int(getattr(conn, "pid", 0), default=0, min_value=0)
        if pid <= 0 or pid in seen:
            continue
        try:
            seen[pid] = psutil.Process(pid)
        except Exception:
            continue
    return list(seen.values())


def _terminate_psutil_tree(root: psutil.Process, *, graceful_timeout: float = 6.0, force_timeout: float = 2.5) -> None:
    targets: List[psutil.Process] = []
    try:
        targets = root.children(recursive=True)
    except Exception:
        targets = []
    targets.append(root)

    unique: Dict[int, psutil.Process] = {}
    for proc in targets:
        try:
            unique[proc.pid] = proc
        except Exception:
            continue
    all_targets = list(unique.values())
    if not all_targets:
        return

    for proc in all_targets:
        try:
            proc.terminate()
        except Exception:
            pass

    _, alive = psutil.wait_procs(all_targets, timeout=max(0.5, float(graceful_timeout)))
    if alive:
        for proc in alive:
            try:
                proc.kill()
            except Exception:
                pass
        psutil.wait_procs(alive, timeout=max(0.3, float(force_timeout)))


def _terminate_subprocess_tree(
    process: subprocess.Popen[str],
    *,
    graceful_timeout: float = 8.0,
    force_timeout: float = 3.0,
) -> Optional[int]:
    if process.poll() is not None:
        return process.poll()

    try:
        root = psutil.Process(process.pid)
    except Exception:
        root = None

    if root is not None:
        _terminate_psutil_tree(root, graceful_timeout=graceful_timeout, force_timeout=force_timeout)
    else:
        try:
            process.terminate()
            process.wait(timeout=max(0.5, float(graceful_timeout)))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=max(0.3, float(force_timeout)))

    if process.poll() is None:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=max(0.3, float(force_timeout)))
        except Exception:
            pass
    return process.poll()


def _describe_process(proc: psutil.Process) -> str:
    try:
        exe = proc.exe()
    except Exception:
        exe = ""
    try:
        cmdline = _process_cmdline_text(proc.cmdline())
    except Exception:
        cmdline = ""
    if exe and cmdline:
        return f"{exe} | {cmdline}"
    return exe or cmdline or f"pid={proc.pid}"


def _same_workspace_dashboard_process(proc: psutil.Process) -> bool:
    def _norm_path(value: str) -> str:
        return str(value or "").strip().replace("\\", "/").lower().rstrip("/")

    workspace_root = _norm_path(str(Path(__file__).resolve().parent.parent))
    if not workspace_root:
        return True

    try:
        proc_cwd = _norm_path(proc.cwd())
        if proc_cwd == workspace_root or proc_cwd.startswith(workspace_root + "/"):
            return True
    except Exception:
        pass

    try:
        cmdline_text = _norm_path(_process_cmdline_text(proc.cmdline()))
        if workspace_root in cmdline_text:
            return True
    except Exception:
        pass

    return False


def _ensure_dashboard_port_ready(port: int) -> None:
    reclaim_enabled = _env_flag("DASHBOARD_RECLAIM_PORT", default=True)
    listeners = _collect_port_listener_processes(port)
    if not listeners:
        return
    survivors: List[psutil.Process] = []

    for proc in listeners:
        if proc.pid == os.getpid():
            continue
        is_dashboard = False
        try:
            is_dashboard = _looks_like_dashboard_process(proc.cmdline())
        except Exception:
            is_dashboard = False

        if not is_dashboard:
            raise RuntimeError(
                f"Port {port} is already in use by non-dashboard process: {_describe_process(proc)}"
            )

        if not _same_workspace_dashboard_process(proc):
            raise RuntimeError(
                f"Port {port} is occupied by dashboard from another workspace: {_describe_process(proc)}"
            )

        if not reclaim_enabled:
            raise RuntimeError(
                f"Port {port} occupied by another dashboard (PID {proc.pid}). "
                f"Set DASHBOARD_RECLAIM_PORT=1 to auto-reclaim, or stop it manually."
            )

        print(f"[dashboard] Reclaiming port {port} from PID {proc.pid}...")
        try:
            _terminate_psutil_tree(proc)
        except Exception as exc:
            survivors.append(proc)
            print(f"[dashboard] Failed to terminate PID {proc.pid}: {exc}")

    if survivors:
        raise RuntimeError(f"Unable to reclaim port {port}; stale dashboard process still running")

    # Final guard against race conditions (progressive backoff for Windows).
    for attempt in range(15):
        if not _collect_port_listener_processes(port):
            return
        time.sleep(0.25 + attempt * 0.1)
    raise RuntimeError(f"Port {port} is still occupied after reclaim attempts")


def _popen_kwargs() -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    return kwargs


def _parse_iso_datetime(raw: Any) -> Optional[datetime]:
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _priority_rank(priority: str) -> int:
    mapping = {
        "high": 0,
        "normal": 1,
        "low": 2,
    }
    return mapping.get(priority, 1)


def _normalize_priority(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"high", "normal", "low"}:
            return lowered
    return "normal"


def _job_public_view(job: Dict[str, Any]) -> Dict[str, Any]:
    payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
    return {
        "job_id": job.get("job_id"),
        "run_id": job.get("run_id"),
        "status": job.get("status"),
        "priority": job.get("priority"),
        "enqueued_at": job.get("enqueued_at"),
        "started_at": job.get("started_at"),
        "count": payload.get("count"),
        "category": payload.get("category"),
        "age": payload.get("age"),
        "max_retries": payload.get("max_retries"),
        "pages": payload.get("pages"),
        "seed": payload.get("seed"),
    }


def _default_runner_payload(last_config: Dict[str, Any]) -> Dict[str, Any]:
    count_hint = _safe_int(last_config.get("count"), 0, min_value=0)
    return {
        "state": "idle",
        "total_books": count_hint,
        "completed_books": 0,
        "success_books": 0,
        "failed_books": 0,
        "current_book": None,
        "current_attempt": 1,
        "current_stage": "idle",
        "last_story_root": None,
        "last_error": None,
        "pre_evaluation": None,
        "stage_progress": None,
        "stage_detail": None,
        "updated_at": _utc_now_iso(),
    }


_HTML_TEMPLATE = Path(__file__).parent / "templates" / "dashboard.html"

def get_html() -> bytes:
    if _HTML_TEMPLATE.exists():
        with open(_HTML_TEMPLATE, "r", encoding="utf-8") as f:
            html = f.read()
        try:
            css_mtime = int((Path(__file__).parent / "static" / "css" / "dashboard.css").stat().st_mtime)
        except Exception:
            css_mtime = 0
        try:
            js_mtime = int((Path(__file__).parent / "static" / "js" / "dashboard.js").stat().st_mtime)
        except Exception:
            js_mtime = 0
        html = html.replace('/static/css/dashboard.css', f'/static/css/dashboard.css?v={css_mtime}')
        html = html.replace('/static/js/dashboard.js', f'/static/js/dashboard.js?v={js_mtime}')
        return html.encode("utf-8")
    return b"<html><body>Template not found.</body></html>"



class DashboardRuntime:
    """Manage subprocess lifecycle, queueing, run audit, and dashboard telemetry."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self.runs_dir = self.root_dir / "runs"
        self.records_dir = self.runs_dir / "dashboard_records"
        self.status_file = self.records_dir / "dashboard_status.json"
        self.run_lock_file = self.records_dir / "dashboard_run.lock"
        self.history_file = self.records_dir / "dashboard_history.json"
        self.configs_file = self.records_dir / "dashboard_config_versions.json"
        self.alert_file = self.records_dir / "dashboard_alerts.json"
        self.alert_state_file = self.records_dir / "dashboard_alert_state.json"
        self.module_jobs_file = self.records_dir / "dashboard_jobs.json"
        self.module_events_file = self.records_dir / "dashboard_job_events.json"
        self.module_history_file = self.records_dir / "dashboard_module_history.json"

        self.process: Optional[subprocess.Popen[str]] = None
        self.reader_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        self.last_config: Dict[str, Any] = {}
        self.last_error: Optional[str] = None

        self.current_run_id: Optional[str] = None
        self.current_run_started_at: Optional[float] = None
        self.current_run_started_iso: Optional[str] = None
        self.current_exit_code: Optional[int] = None
        self.current_status_signature: Optional[str] = None
        self.current_lock_token: Optional[str] = None

        self.active_job: Optional[Dict[str, Any]] = None
        self.pending_jobs: List[Dict[str, Any]] = []

        self.log_seq = 0
        self.log_lines: Deque[Dict[str, Any]] = deque(maxlen=_LOG_BUFFER_SIZE)
        self.run_logs: Dict[str, Deque[Dict[str, Any]]] = {}
        self.run_events: Dict[str, List[Dict[str, Any]]] = {}

        self.history: List[Dict[str, Any]] = []
        self.config_versions: List[Dict[str, Any]] = []
        self.alerts: List[Dict[str, Any]] = []
        self.suppressed_live_alert_ids: Dict[str, str] = {}

        self.module_log_seq = 0
        self.module_active_job: Optional[Dict[str, Any]] = None
        self.module_pending_jobs: List[Dict[str, Any]] = []
        self.module_history: List[Dict[str, Any]] = []
        self.module_events: Dict[str, List[Dict[str, Any]]] = {}
        self.module_logs: Dict[str, Deque[Dict[str, Any]]] = {}
        self.module_worker_stop = threading.Event()
        self.module_worker: Optional[threading.Thread] = None
        self.general_lock = threading.Lock()

        self.model_cache_lock = threading.Lock()
        self.model_slots: Dict[str, Dict[str, Any]] = {}
        self.model_reuse_window_sec = _safe_int(
            os.environ.get("DASHBOARD_MODEL_REUSE_SEC"),
            _MODEL_REUSE_WINDOW_SEC_DEFAULT,
            min_value=10,
            max_value=3600,
        )
        self.model_cleanup_window_sec = _safe_int(
            os.environ.get("DASHBOARD_MODEL_CLEANUP_SEC"),
            _MODEL_CLEANUP_WINDOW_SEC_DEFAULT,
            min_value=20,
            max_value=7200,
        )
        if self.model_cleanup_window_sec <= self.model_reuse_window_sec:
            self.model_cleanup_window_sec = self.model_reuse_window_sec + 30
        self.model_low_vram_mode = _safe_bool(
            os.environ.get("DASHBOARD_MODEL_LOW_VRAM"),
            bool(DEFAULT_CHIEF_OPTIONS.low_vram),
        )
        self.model_reaper_stop = threading.Event()
        self.model_reaper: Optional[threading.Thread] = None

        self.records_dir.mkdir(parents=True, exist_ok=True)
        self._migrate_legacy_record_files()
        self._load_history()
        self._load_config_versions()
        self._load_alerts()
        self._load_alert_state()
        self._load_module_history()
        self._load_module_events()
        self._save_module_jobs_snapshot_locked()
        self._start_module_worker()
        self._start_model_reaper()

    def _read_json_list(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                return []
            return [item for item in data if isinstance(item, dict)]
        except Exception:
            return []

    def _write_json_list(self, path: Path, payload: List[Dict[str, Any]]) -> None:
        try:
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)
        except Exception:
            pass

    def _read_json_dict(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write_json_dict(self, path: Path, payload: Dict[str, Any]) -> None:
        try:
            temp = path.with_suffix(path.suffix + ".tmp")
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(path)
        except Exception:
            pass

    def _migrate_legacy_record_files(self) -> None:
        legacy_map = {
            self.runs_dir / "dashboard_status.json": self.status_file,
            self.runs_dir / "dashboard_history.json": self.history_file,
            self.runs_dir / "dashboard_config_versions.json": self.configs_file,
            self.runs_dir / "dashboard_alerts.json": self.alert_file,
            self.runs_dir / "dashboard_jobs.json": self.module_jobs_file,
            self.runs_dir / "dashboard_job_events.json": self.module_events_file,
            self.runs_dir / "dashboard_module_history.json": self.module_history_file,
        }

        for legacy_path, target_path in legacy_map.items():
            if legacy_path == target_path:
                continue
            if not legacy_path.exists() or target_path.exists():
                continue

            try:
                target_path.parent.mkdir(parents=True, exist_ok=True)
                legacy_path.replace(target_path)
            except Exception:
                try:
                    payload = legacy_path.read_bytes()
                    target_path.write_bytes(payload)
                    legacy_path.unlink()
                except Exception:
                    pass

    @staticmethod
    def _pid_alive(pid: Any) -> bool:
        candidate = _safe_int(pid, 0, min_value=0)
        if candidate <= 0:
            return False
        try:
            proc = psutil.Process(candidate)
            return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
        except Exception:
            return False

    @staticmethod
    def _normalize_cmdline_text(value: Any) -> str:
        return str(value or "").strip().replace("\\", "/").lower()

    def _find_external_chief_process(self) -> Optional[Dict[str, Any]]:
        managed_pid = self.process.pid if self.process and self.process.poll() is None else 0
        dashboard_pid = os.getpid()
        chief_hint = self._normalize_cmdline_text(str((self.root_dir / "chief.py").resolve()))
        status_hint = self._normalize_cmdline_text(str(self.status_file.resolve()))

        try:
            iterator = psutil.process_iter(attrs=["pid", "cmdline"])
        except Exception:
            return None

        for proc in iterator:
            try:
                pid = _safe_int(proc.info.get("pid"), 0, min_value=0)
                if pid <= 0 or pid in {dashboard_pid, managed_pid}:
                    continue
                if not self._pid_alive(pid):
                    continue

                cmdline_parts = proc.info.get("cmdline") or []
                if not cmdline_parts:
                    continue
                cmdline_text = self._normalize_cmdline_text(
                    " ".join(str(part) for part in cmdline_parts if part)
                )
                if "chief.py" not in cmdline_text:
                    continue

                same_workspace = (chief_hint and chief_hint in cmdline_text) or (
                    status_hint and status_hint in cmdline_text
                )
                if not same_workspace:
                    continue

                return {
                    "pid": pid,
                    "command": " ".join(str(part) for part in cmdline_parts if part),
                }
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue

        return None

    def _acquire_cross_process_run_lock(self, run_id: str) -> Tuple[bool, str]:
        stale_startup_window_sec = 120.0

        for _ in range(3):
            token = uuid4().hex
            payload = {
                "token": token,
                "run_id": str(run_id or ""),
                "dashboard_pid": os.getpid(),
                "chief_pid": None,
                "created_at": _utc_now_iso(),
                "created_at_ts": time.time(),
            }

            try:
                fd = os.open(str(self.run_lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                existing = self._read_json_dict(self.run_lock_file)
                now_ts = time.time()
                if not existing:
                    try:
                        self.run_lock_file.unlink()
                        continue
                    except Exception:
                        return False, "run lock exists but cannot be inspected"

                existing_run = str(existing.get("run_id") or "")
                existing_chief_pid = _safe_int(existing.get("chief_pid"), 0, min_value=0)
                existing_dashboard_pid = _safe_int(existing.get("dashboard_pid"), 0, min_value=0)
                existing_created_ts = _safe_float(existing.get("created_at_ts"), 0.0)

                if self._pid_alive(existing_chief_pid):
                    return False, f"another run is active (run_id={existing_run}, pid={existing_chief_pid})"

                startup_recent = (now_ts - existing_created_ts) < stale_startup_window_sec
                if self._pid_alive(existing_dashboard_pid) and startup_recent:
                    return False, f"another dashboard is starting a run (run_id={existing_run})"

                try:
                    self.run_lock_file.unlink()
                    continue
                except Exception:
                    return False, f"stale run lock detected but cannot remove (run_id={existing_run})"
            except Exception as exc:
                return False, f"failed to create run lock: {exc}"

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle, ensure_ascii=False, indent=2)
            except Exception as exc:
                try:
                    if self.run_lock_file.exists():
                        self.run_lock_file.unlink()
                except Exception:
                    pass
                return False, f"failed to write run lock: {exc}"

            self.current_lock_token = token
            return True, ""

        return False, "unable to acquire run lock"

    def _update_cross_process_run_lock(self, chief_pid: int) -> None:
        token = self.current_lock_token
        if not token:
            return

        payload = self._read_json_dict(self.run_lock_file)
        if not payload:
            return
        if str(payload.get("token") or "") != str(token):
            return

        payload["chief_pid"] = _safe_int(chief_pid, 0, min_value=0)
        payload["updated_at"] = _utc_now_iso()
        payload["updated_at_ts"] = time.time()
        self._write_json_dict(self.run_lock_file, payload)

    def _release_cross_process_run_lock(self) -> None:
        token = self.current_lock_token
        if not token:
            return
        try:
            payload = self._read_json_dict(self.run_lock_file)
            if payload and str(payload.get("token") or "") != str(token):
                return
            if self.run_lock_file.exists():
                self.run_lock_file.unlink()
        except Exception:
            pass
        finally:
            self.current_lock_token = None

    def _load_history(self) -> None:
        self.history = self._read_json_list(self.history_file)[-_HISTORY_LIMIT:]

    def _save_history(self) -> None:
        self._write_json_list(self.history_file, self.history[-_HISTORY_LIMIT:])

    def _load_config_versions(self) -> None:
        self.config_versions = self._read_json_list(self.configs_file)[-_CONFIG_LIMIT:]

    def _save_config_versions(self) -> None:
        self._write_json_list(self.configs_file, self.config_versions[-_CONFIG_LIMIT:])

    def _load_alerts(self) -> None:
        self.alerts = self._read_json_list(self.alert_file)[-_ALERT_LIMIT:]

    def _save_alerts(self) -> None:
        self._write_json_list(self.alert_file, self.alerts[-_ALERT_LIMIT:])

    def _load_alert_state(self) -> None:
        payload = self._read_json_dict(self.alert_state_file)
        suppressed = payload.get("suppressed_live_alert_ids") if isinstance(payload, dict) else {}
        if isinstance(suppressed, dict):
            self.suppressed_live_alert_ids = {
                str(key): str(value)
                for key, value in suppressed.items()
                if str(key).strip()
            }
        else:
            self.suppressed_live_alert_ids = {}

    def _save_alert_state(self) -> None:
        self._write_json_dict(
            self.alert_state_file,
            {"suppressed_live_alert_ids": dict(self.suppressed_live_alert_ids)},
        )

    def _load_module_history(self) -> None:
        self.module_history = self._read_json_list(self.module_history_file)[-_MODULE_HISTORY_LIMIT:]

    def _save_module_history(self) -> None:
        self._write_json_list(self.module_history_file, self.module_history[-_MODULE_HISTORY_LIMIT:])

    def _load_module_events(self) -> None:
        self.module_events = {}
        rows = self._read_json_list(self.module_events_file)
        for row in rows:
            job_id = str(row.get("job_id") or "")
            events = row.get("events") if isinstance(row.get("events"), list) else []
            if not job_id:
                continue
            self.module_events[job_id] = [item for item in events if isinstance(item, dict)][-800:]

    def _save_module_events(self) -> None:
        rows: List[Dict[str, Any]] = []
        for job_id, events in self.module_events.items():
            rows.append({
                "job_id": job_id,
                "events": events[-800:],
            })
        rows.sort(key=lambda item: str(item.get("job_id") or ""))
        self._write_json_list(self.module_events_file, rows[-_MODULE_HISTORY_LIMIT:])

    @staticmethod
    def _strip_module_runtime(job: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in job.items() if k != "runtime"}

    def _module_job_public_view(self, job: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not isinstance(job, dict):
            return None
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        return {
            "job_id": job.get("job_id"),
            "job_type": job.get("job_type"),
            "status": job.get("status"),
            "priority": job.get("priority"),
            "created_at": job.get("created_at"),
            "started_at": job.get("started_at"),
            "finished_at": job.get("finished_at"),
            "error": job.get("error"),
            "artifacts": job.get("artifacts") if isinstance(job.get("artifacts"), dict) else {},
            "story_root": payload.get("story_root"),
            "cancel_requested": bool(job.get("cancel_requested")),
        }

    def _save_module_jobs_snapshot_locked(self) -> None:
        snapshot = {
            "updated_at": _utc_now_iso(),
            "active_job": self._module_job_public_view(self.module_active_job),
            "pending_jobs": [
                self._module_job_public_view(item)
                for item in self.module_pending_jobs
                if isinstance(item, dict)
            ],
        }
        self._write_json_dict(self.module_jobs_file, snapshot)

    def _start_module_worker(self) -> None:
        if self.module_worker and self.module_worker.is_alive():
            return
        self.module_worker_stop.clear()
        worker = threading.Thread(
            target=self._module_worker_loop,
            name="dashboard-module-worker",
            daemon=True,
        )
        worker.start()
        self.module_worker = worker

    def _start_model_reaper(self) -> None:
        if self.model_reaper and self.model_reaper.is_alive():
            return
        self.model_reaper_stop.clear()
        worker = threading.Thread(
            target=self._model_reaper_loop,
            name="dashboard-model-reaper",
            daemon=True,
        )
        worker.start()
        self.model_reaper = worker

    @staticmethod
    def _cleanup_backend_instance(instance: Any) -> None:
        if instance is None:
            return
        cleanup = getattr(instance, "cleanup", None)
        if callable(cleanup):
            cleanup()

    @staticmethod
    def _offload_backend_instance(kind: str, instance: Any) -> bool:
        if instance is None:
            return False
        method = None
        if kind == "llm":
            method = getattr(instance, "offload", None)
        elif kind in {"image", "voice"}:
            method = getattr(instance, "offload_model", None)
        if callable(method):
            method()
            return True
        return False

    @staticmethod
    def _load_backend_instance(kind: str, instance: Any) -> None:
        if instance is None:
            return
        method = None
        if kind == "llm":
            method = getattr(instance, "load", None)
        elif kind in {"image", "voice"}:
            method = getattr(instance, "load_model", None)
        if callable(method):
            method()

    def _cleanup_cached_models(self, *, force: bool = False) -> None:
        now_ts = time.time()
        with self.model_cache_lock:
            for kind in list(self.model_slots.keys()):
                slot = self.model_slots.get(kind)
                if not isinstance(slot, dict):
                    self.model_slots.pop(kind, None)
                    continue
                if _safe_int(slot.get("in_use"), 0, min_value=0) > 0:
                    continue

                idle_sec = now_ts - _safe_float(slot.get("last_used_ts"), now_ts)
                instance = slot.get("instance")
                offloaded = bool(slot.get("offloaded"))

                if force or idle_sec >= self.model_cleanup_window_sec:
                    try:
                        self._cleanup_backend_instance(instance)
                    except Exception:
                        pass
                    self.model_slots.pop(kind, None)
                    continue

                if idle_sec >= self.model_reuse_window_sec and not offloaded:
                    try:
                        if self._offload_backend_instance(kind, instance):
                            slot["offloaded"] = True
                    except Exception:
                        pass

    def _model_reaper_loop(self) -> None:
        while not self.model_reaper_stop.wait(_MODEL_REAPER_INTERVAL_SEC):
            self._cleanup_cached_models(force=False)

    def _acquire_cached_backend(self, kind: str, key: Tuple[Any, ...], builder: Any) -> Any:
        now_ts = time.time()
        with self.model_cache_lock:
            slot = self.model_slots.get(kind)
            if isinstance(slot, dict):
                slot_key = slot.get("key")
                if slot_key != key:
                    if _safe_int(slot.get("in_use"), 0, min_value=0) > 0:
                        raise RuntimeError(f"Backend '{kind}' is busy with another configuration")
                    try:
                        self._cleanup_backend_instance(slot.get("instance"))
                    except Exception:
                        pass
                    self.model_slots.pop(kind, None)
                    slot = None

            if isinstance(slot, dict):
                instance = slot.get("instance")
                if bool(slot.get("offloaded")):
                    self._load_backend_instance(kind, instance)
                    slot["offloaded"] = False
                slot["in_use"] = _safe_int(slot.get("in_use"), 0, min_value=0) + 1
                slot["last_used_ts"] = now_ts
                return instance

            instance = builder()
            self.model_slots[kind] = {
                "key": key,
                "instance": instance,
                "in_use": 1,
                "offloaded": False,
                "created_ts": now_ts,
                "last_used_ts": now_ts,
            }
            return instance

    def _release_cached_backend(self, kind: str, key: Tuple[Any, ...]) -> None:
        now_ts = time.time()
        with self.model_cache_lock:
            slot = self.model_slots.get(kind)
            if not isinstance(slot, dict) or slot.get("key") != key:
                return
            current_in_use = _safe_int(slot.get("in_use"), 0, min_value=0)
            slot["in_use"] = max(0, current_in_use - 1)
            slot["last_used_ts"] = now_ts
            if slot["in_use"] == 0 and self.model_low_vram_mode and not bool(slot.get("offloaded")):
                try:
                    if self._offload_backend_instance(kind, slot.get("instance")):
                        slot["offloaded"] = True
                except Exception:
                    pass

    def shutdown(self) -> None:
        try:
            self.stop_run()
        except Exception:
            pass
        try:
            self.stop_module_job(None)
        except Exception:
            pass
        self.module_worker_stop.set()
        try:
            if self.module_worker and self.module_worker.is_alive():
                self.module_worker.join(timeout=1.2)
        except Exception:
            pass
        self.model_reaper_stop.set()
        try:
            if self.model_reaper and self.model_reaper.is_alive():
                self.model_reaper.join(timeout=1.2)
        except Exception:
            pass
        self._cleanup_cached_models(force=True)
        self._release_cross_process_run_lock()

    def _append_log_line_locked(self, text: str, *, run_id: Optional[str], level: str = "info") -> None:
        line = text.rstrip("\r\n")
        if not line:
            return
        line = _normalize_progress_line(line)
        rid = run_id or self.current_run_id or "system"
        self.log_seq += 1
        entry = {
            "seq": self.log_seq,
            "ts": _utc_now_iso(),
            "run_id": rid,
            "level": level,
            "text": line,
        }
        self.log_lines.append(entry)
        if rid not in self.run_logs:
            self.run_logs[rid] = deque(maxlen=_RUN_LOG_BUFFER_SIZE)
        self.run_logs[rid].append(entry)

    def _append_log_line(self, text: str, *, run_id: Optional[str], level: str = "info") -> None:
        with self.lock:
            self._append_log_line_locked(text, run_id=run_id, level=level)

    def _record_run_event_locked(self, run_id: str, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        if run_id not in self.run_events:
            self.run_events[run_id] = []
        events = self.run_events[run_id]
        events.append({
            "ts": _utc_now_iso(),
            "event": event,
            "details": details or {},
        })
        if len(events) > 800:
            del events[:-800]

    def _push_alert_locked(
        self,
        *,
        level: str,
        title: str,
        message: str,
        run_id: Optional[str] = None,
        code: Optional[str] = None,
    ) -> Dict[str, Any]:
        alert = {
            "alert_id": f"al-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}",
            "ts": _utc_now_iso(),
            "level": level,
            "title": title,
            "message": message,
            "run_id": run_id,
            "code": code,
            "acknowledged": False,
        }
        self.alerts.append(alert)
        self.alerts = self.alerts[-_ALERT_LIMIT:]
        self._save_alerts()
        return alert

    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        age = payload.get("age")
        category = payload.get("category")
        theme = _safe_text(payload.get("theme"), default="", max_length=80)
        subcategory = _safe_text(payload.get("subcategory"), default="", max_length=80)
        story_input_mode = _safe_text(payload.get("story_input_mode"), default="preset", max_length=16).lower()
        if story_input_mode not in {"preset", "custom"}:
            story_input_mode = "preset"
        speaker_wav = _safe_text(payload.get("speaker_wav"), default="", max_length=512)
        speaker_dir = _safe_text(payload.get("speaker_dir"), default="", max_length=512)
        model_plan = _safe_text(payload.get("model_plan"), default="auto", max_length=16).lower()
        if model_plan not in {"auto", "quality", "balanced", "portable", "cpu", "off"}:
            model_plan = "auto"

        sanitized: Dict[str, Any] = {
            "count": _safe_int(payload.get("count"), 1, min_value=1, max_value=500),
            "max_retries": _safe_int(payload.get("max_retries"), 1, min_value=0, max_value=20),
            "pages": _safe_int(payload.get("pages"), 0, min_value=0, max_value=80),
            "priority": _normalize_priority(payload.get("priority")),
            "seed": None,
            "age": age if isinstance(age, str) and age in AGE_CHOICES else None,
            "category": category if isinstance(category, str) and category in CATEGORY_CHOICES else None,
            "theme": theme or None,
            "subcategory": subcategory or None,
            "story_input_mode": story_input_mode,
            "story_prompt": _safe_text(payload.get("story_prompt"), default="", max_length=4000),
            "story_materials": _safe_text(payload.get("story_materials"), default="", max_length=4000),
            "speaker_wav": speaker_wav or None,
            "speaker_dir": speaker_dir or None,
            "model_plan": model_plan,
            "photo_enabled": _safe_bool(payload.get("photo_enabled"), True),
            "translation_enabled": _safe_bool(payload.get("translation_enabled"), True),
            "voice_enabled": _safe_bool(payload.get("voice_enabled"), True),
            "verify_enabled": _safe_bool(payload.get("verify_enabled"), True),
            "low_vram": _safe_bool(payload.get("low_vram"), True),
            "strict_translation": _safe_bool(
                payload.get("strict_translation"),
                bool(DEFAULT_CHIEF_OPTIONS.strict_translation),
            ),
            "strict_voice": _safe_bool(
                payload.get("strict_voice"),
                bool(DEFAULT_CHIEF_OPTIONS.strict_voice),
            ),
            "pre_eval_policy": _normalize_pre_eval_policy(
                payload.get("pre_eval_policy"),
                default=str(getattr(DEFAULT_CHIEF_OPTIONS, "pre_eval_policy", "stop") or "stop"),
            ),
            "pre_eval_threshold": _safe_float(
                payload.get("pre_eval_threshold"),
                _safe_float(getattr(DEFAULT_CHIEF_OPTIONS, "pre_eval_threshold", 65.0), 65.0),
            ),
        }

        sanitized["pre_eval_threshold"] = max(0.0, min(100.0, float(sanitized["pre_eval_threshold"])))

        if story_input_mode != "custom":
            sanitized["story_prompt"] = ""
            sanitized["story_materials"] = ""

        if payload.get("seed") not in {None, ""}:
            sanitized["seed"] = _safe_int(payload.get("seed"), 0, min_value=0)
        return sanitized

    def _append_module_log_line_locked(self, job_id: str, text: str, *, level: str = "info") -> None:
        line = text.rstrip("\r\n")
        if not line:
            return
        line = _normalize_progress_line(line)
        self.module_log_seq += 1
        entry = {
            "seq": self.module_log_seq,
            "ts": _utc_now_iso(),
            "job_id": job_id,
            "level": level,
            "text": line,
        }
        if job_id not in self.module_logs:
            self.module_logs[job_id] = deque(maxlen=_RUN_LOG_BUFFER_SIZE)
        self.module_logs[job_id].append(entry)

    def _append_module_log_line(self, job_id: str, text: str, *, level: str = "info") -> None:
        with self.lock:
            self._append_module_log_line_locked(job_id, text, level=level)

    def _record_module_event_locked(self, job_id: str, event: str, details: Optional[Dict[str, Any]] = None) -> None:
        if job_id not in self.module_events:
          self.module_events[job_id] = []
        events = self.module_events[job_id]
        events.append({
          "ts": _utc_now_iso(),
          "event": event,
          "details": details or {},
        })
        if len(events) > 800:
          del events[:-800]

    def _start_general_module_job(self, job_type: str, payload_summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        now_ts = time.time()
        summary = payload_summary if isinstance(payload_summary, dict) else {}
        job_id = f"mjob-{uuid4().hex[:10]}"
        job = {
            "job_id": job_id,
            "job_type": job_type,
            "priority": "normal",
            "priority_rank": _priority_rank("normal"),
            "status": "running",
            "payload": summary,
            "created_at": _utc_now_iso(),
            "created_at_ts": now_ts,
            "enqueued_at_ts": now_ts,
            "started_at": _utc_now_iso(),
            "finished_at": None,
            "error": None,
            "artifacts": {},
            "cancel_requested": False,
            "runtime": {},
        }
        with self.lock:
            if self.module_active_job is None:
                self.module_active_job = job
            self._record_module_event_locked(job_id, "started", {
                "job_type": job_type,
                "source": "general",
            })
            self._append_module_log_line_locked(
                job_id,
                f"[module] started type={job_type} source=general",
                level="info",
            )
            self._save_module_events()
            self._save_module_jobs_snapshot_locked()
        return job

    def _finish_general_module_job(
        self,
        job: Dict[str, Any],
        *,
        ok: bool,
        artifacts: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            return

        final_status = "completed" if ok else "failed"
        finished_ts = _utc_now_iso()
        with self.lock:
            job["status"] = final_status
            job["finished_at"] = finished_ts
            job["finished_at_ts"] = time.time()
            job["error"] = None if ok else _safe_text(error, default="general task failed", max_length=4000)
            job["artifacts"] = artifacts if isinstance(artifacts, dict) else {}
            if self.module_active_job and str(self.module_active_job.get("job_id") or "") == job_id:
                self.module_active_job = None

            self._record_module_event_locked(job_id, "finished", {
                "status": final_status,
                "source": "general",
            })
            if ok:
                self._append_module_log_line_locked(job_id, "[module] finished successfully", level="info")
            else:
                self._append_module_log_line_locked(job_id, f"[module] failed: {job['error']}", level="error")

            self.module_history.append(self._strip_module_runtime(dict(job)))
            self.module_history = self.module_history[-_MODULE_HISTORY_LIMIT:]
            self._save_module_history()
            self._save_module_events()
            self._save_module_jobs_snapshot_locked()

    def _sort_module_queue_locked(self) -> None:
        self.module_pending_jobs.sort(
          key=lambda item: (item.get("priority_rank", 1), item.get("enqueued_at_ts", 0.0))
        )

    @staticmethod
    def _parse_lang_list(raw: Any, *, limit: int = 16) -> List[str]:
        values: List[str] = []
        if isinstance(raw, list):
          for item in raw:
            if not isinstance(item, str):
              continue
            values.extend(item.replace("\r", "\n").replace(",", "\n").split("\n"))
        elif isinstance(raw, str):
          values.extend(raw.replace("\r", "\n").replace(",", "\n").split("\n"))

        result: List[str] = []
        seen: set[str] = set()
        for value in values:
          item = value.strip()
          if not item:
            continue
          key = item.casefold()
          if key in seen:
            continue
          seen.add(key)
          result.append(item)
          if len(result) >= limit:
            break
        return result

    def _sanitize_module_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        job_type = _safe_text(payload.get("job_type"), default="", max_length=24).lower()
        if job_type not in {"story", "image", "translation", "voice"}:
          raise ValueError("job_type must be one of: story, image, translation, voice")

        body = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
        priority = _normalize_priority(body.get("priority") if isinstance(body, dict) else None)

        if not isinstance(body, dict):
          body = {}

        if job_type == "story":
          input_mode = _safe_text(body.get("story_input_mode"), default="preset", max_length=16).lower()
          if input_mode not in {"preset", "custom"}:
            input_mode = "preset"
          sanitized_payload: Dict[str, Any] = {
            "count": _safe_int(body.get("count"), 1, min_value=1, max_value=80),
            "max_retries": _safe_int(body.get("max_retries"), 0, min_value=0, max_value=8),
            "pages": _safe_int(body.get("pages"), 0, min_value=0, max_value=80),
            "seed": None,
            "age": body.get("age") if isinstance(body.get("age"), str) and body.get("age") in AGE_CHOICES else None,
            "category": body.get("category") if isinstance(body.get("category"), str) and body.get("category") in CATEGORY_CHOICES else None,
            "theme": _safe_text(body.get("theme"), default="", max_length=80) or None,
            "subcategory": _safe_text(body.get("subcategory"), default="", max_length=80) or None,
            "story_input_mode": input_mode,
            "story_prompt": _safe_text(body.get("story_prompt"), default="", max_length=4000),
            "story_materials": _safe_text(body.get("story_materials"), default="", max_length=4000),
            "low_vram": _safe_bool(body.get("low_vram"), True),
          }
          if input_mode != "custom":
            sanitized_payload["story_prompt"] = ""
            sanitized_payload["story_materials"] = ""
          if body.get("seed") not in {None, ""}:
            sanitized_payload["seed"] = _safe_int(body.get("seed"), 0, min_value=0)

        elif job_type == "image":
          task_ids_raw = body.get("task_ids") if isinstance(body.get("task_ids"), list) else []
          task_ids: List[str] = []
          for item in task_ids_raw:
            text = _safe_text(item, default="", max_length=200)
            if text:
              task_ids.append(text)
            if len(task_ids) >= 800:
              break

          raw_overrides = body.get("overrides") if isinstance(body.get("overrides"), dict) else {}
          sanitized_payload = {
            "story_root": _safe_text(body.get("story_root"), default="", max_length=1200),
            "task_ids": task_ids,
            "overrides": {
              "positive_prompt": _safe_text(raw_overrides.get("positive_prompt"), default="", max_length=12000) or None,
              "negative_prompt": _safe_text(raw_overrides.get("negative_prompt"), default="", max_length=4000) or None,
              "width": None if raw_overrides.get("width") in {None, ""} else _safe_int(raw_overrides.get("width"), int(DEFAULT_CHIEF_OPTIONS.photo_width), min_value=256, max_value=2048),
              "height": None if raw_overrides.get("height") in {None, ""} else _safe_int(raw_overrides.get("height"), int(DEFAULT_CHIEF_OPTIONS.photo_height), min_value=256, max_value=2048),
              "steps": None if raw_overrides.get("steps") in {None, ""} else _safe_int(raw_overrides.get("steps"), int(DEFAULT_CHIEF_OPTIONS.photo_steps), min_value=1, max_value=150),
              "guidance": None if raw_overrides.get("guidance") in {None, ""} else _safe_float(raw_overrides.get("guidance"), float(DEFAULT_CHIEF_OPTIONS.photo_guidance)),
              "seed": None if raw_overrides.get("seed") in {None, ""} else _safe_int(raw_overrides.get("seed"), 0, min_value=0),
              "refiner_steps": None if raw_overrides.get("refiner_steps") in {None, ""} else _safe_int(raw_overrides.get("refiner_steps"), max(1, int(DEFAULT_CHIEF_OPTIONS.photo_steps) // 4), min_value=1, max_value=80),
              "skip_refiner": _safe_bool(raw_overrides.get("skip_refiner"), bool(DEFAULT_CHIEF_OPTIONS.photo_skip_refiner)),
              "low_vram": _safe_bool(raw_overrides.get("low_vram"), True),
            },
          }

        elif job_type == "translation":
          dtype_text = _safe_text(body.get("dtype"), default=str(DEFAULT_CHIEF_OPTIONS.translation_dtype), max_length=16)
          if dtype_text not in {"float16", "bfloat16", "float32"}:
            dtype_text = str(DEFAULT_CHIEF_OPTIONS.translation_dtype)
          sanitized_payload = {
            "story_root": _safe_text(body.get("story_root"), default="", max_length=1200),
            "source_folder": _safe_text(body.get("source_folder"), default=DEFAULT_CHIEF_OPTIONS.story_language, max_length=32),
            "source_lang": _safe_text(body.get("source_lang"), default=DEFAULT_CHIEF_OPTIONS.translation_source_lang, max_length=32),
            "target_langs": self._parse_lang_list(body.get("target_langs"), limit=24),
            "beam_size": _safe_int(body.get("beam_size"), int(DEFAULT_CHIEF_OPTIONS.translation_beam_size), min_value=1, max_value=8),
            "length_penalty": _safe_float(body.get("length_penalty"), float(DEFAULT_CHIEF_OPTIONS.translation_length_penalty)),
            "device": _safe_text(body.get("device"), default=str(DEFAULT_CHIEF_OPTIONS.translation_device), max_length=24),
            "dtype": dtype_text,
          }

        else:
          page_start = None if body.get("page_start") in {None, ""} else _safe_int(body.get("page_start"), 1, min_value=1, max_value=999)
          page_end = None if body.get("page_end") in {None, ""} else _safe_int(body.get("page_end"), 1, min_value=1, max_value=999)
          sanitized_payload = {
            "story_root": _safe_text(body.get("story_root"), default="", max_length=1200),
            "language": _safe_text(body.get("language"), default="", max_length=24),
            "speaker_wav": _safe_text(body.get("speaker_wav"), default="", max_length=1200),
            "speaker_dir": _safe_text(body.get("speaker_dir"), default="", max_length=1200),
            "page_start": page_start,
            "page_end": page_end,
            "gain": _safe_float(body.get("gain"), 1.0),
            "speed": _safe_float(body.get("speed"), 1.0),
            "concat": _safe_bool(body.get("concat"), True),
            "keep_raw": _safe_bool(body.get("keep_raw"), True),
            "device": _safe_text(body.get("device"), default=str(DEFAULT_CHIEF_OPTIONS.voice_device), max_length=24),
          }

        return {
          "job_type": job_type,
          "priority": priority,
          "payload": sanitized_payload,
        }

    def run_module_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
          normalized = self._sanitize_module_request(payload)
        except ValueError as exc:
          return {"ok": False, "error": str(exc)}

        with self.lock:
          if len(self.module_pending_jobs) >= _MODULE_QUEUE_LIMIT:
            return {"ok": False, "error": f"Module queue limit reached ({_MODULE_QUEUE_LIMIT})."}

          now_ts = time.time()
          job = {
            "job_id": f"mjob-{uuid4().hex[:10]}",
            "job_type": normalized["job_type"],
            "priority": normalized["priority"],
            "priority_rank": _priority_rank(normalized["priority"]),
            "status": "queued",
            "payload": normalized["payload"],
            "created_at": _utc_now_iso(),
            "created_at_ts": now_ts,
            "enqueued_at_ts": now_ts,
            "started_at": None,
            "finished_at": None,
            "error": None,
            "artifacts": {},
            "cancel_requested": False,
            "runtime": {},
          }
          self.module_pending_jobs.append(job)
          self._sort_module_queue_locked()
          queue_position = next(
            (idx + 1 for idx, item in enumerate(self.module_pending_jobs) if str(item.get("job_id")) == str(job.get("job_id"))),
            len(self.module_pending_jobs),
          )
          self._record_module_event_locked(str(job["job_id"]), "queued", {
            "job_type": job["job_type"],
            "priority": job["priority"],
          })
          self._append_module_log_line_locked(
            str(job["job_id"]),
            f"[module] queued type={job['job_type']} priority={job['priority']}",
          )
          self._save_module_events()
          self._save_module_jobs_snapshot_locked()

        return {
          "ok": True,
          "job": self._module_job_public_view(job),
          "queue_depth": len(self.module_pending_jobs),
          "queue_position": queue_position,
        }

    def list_module_jobs(self, *, limit: int = 40) -> Dict[str, Any]:
        limit = _safe_int(limit, 40, min_value=1, max_value=400)
        with self.lock:
          active = self._module_job_public_view(self.module_active_job)
          pending = [self._module_job_public_view(item) for item in self.module_pending_jobs]
          history_rows = [
            self._module_job_public_view(item)
            for item in reversed(self.module_history[-limit:])
            if isinstance(item, dict)
          ]
        return {
          "ok": True,
          "active_job": active,
          "pending_jobs": pending,
          "history": history_rows,
          "queue_depth": len(pending),
        }

    def get_module_job_detail(self, job_id: str, *, log_limit: int = 300, event_limit: int = 200) -> Dict[str, Any]:
        if not job_id:
          return {"ok": False, "error": "job_id is required"}

        log_limit = _safe_int(log_limit, 300, min_value=1, max_value=1500)
        event_limit = _safe_int(event_limit, 200, min_value=1, max_value=1200)

        with self.lock:
          selected: Optional[Dict[str, Any]] = None
          if self.module_active_job and str(self.module_active_job.get("job_id")) == str(job_id):
            selected = dict(self.module_active_job)
          if selected is None:
            for item in self.module_pending_jobs:
              if str(item.get("job_id")) == str(job_id):
                selected = dict(item)
                break
          if selected is None:
            for item in self.module_history:
              if str(item.get("job_id")) == str(job_id):
                selected = dict(item)
                break
          if selected is None:
            return {"ok": False, "error": f"module job not found: {job_id}"}

          logs = list(self.module_logs.get(job_id, []))[-log_limit:]
          events = list(self.module_events.get(job_id, []))[-event_limit:]

        return {
          "ok": True,
          "job": self._strip_module_runtime(selected),
          "logs": logs,
          "events": events,
        }

    def stop_module_job(self, job_id: Optional[str]) -> Dict[str, Any]:
        target = str(job_id or "").strip()

        with self.lock:
          if not target and self.module_active_job:
            target = str(self.module_active_job.get("job_id") or "")

          if target:
            for idx, item in enumerate(self.module_pending_jobs):
              if str(item.get("job_id")) != target:
                continue
              removed = self.module_pending_jobs.pop(idx)
              removed["status"] = "stopped"
              removed["finished_at"] = _utc_now_iso()
              removed["error"] = "Canceled before start"
              self.module_history.append(self._strip_module_runtime(dict(removed)))
              self.module_history = self.module_history[-_MODULE_HISTORY_LIMIT:]
              self._record_module_event_locked(target, "canceled", {"where": "queue"})
              self._append_module_log_line_locked(target, "[module] canceled while queued", level="warning")
              self._save_module_history()
              self._save_module_events()
              self._save_module_jobs_snapshot_locked()
              return {"ok": True, "job_id": target, "message": "Canceled queued module job."}

          active = self.module_active_job
          if active and str(active.get("job_id")) == target:
            active["cancel_requested"] = True
            active["status"] = "stopping"
            runtime = active.get("runtime") if isinstance(active.get("runtime"), dict) else {}
            process = runtime.get("process")
            if isinstance(process, subprocess.Popen):
              try:
                if process.poll() is None:
                  process.terminate()
              except Exception:
                pass
            self._record_module_event_locked(target, "cancel_requested", {})
            self._append_module_log_line_locked(target, "[module] cancel requested", level="warning")
            self._save_module_events()
            self._save_module_jobs_snapshot_locked()
            return {"ok": True, "job_id": target, "message": "Cancel requested for running module job."}

        return {"ok": False, "error": f"module job not found: {target or '(none)'}"}

    def _module_cancel_requested(self, job_id: str) -> bool:
        with self.lock:
          return bool(
            self.module_active_job
            and str(self.module_active_job.get("job_id")) == str(job_id)
            and self.module_active_job.get("cancel_requested")
          )

    def _module_worker_loop(self) -> None:
        while not self.module_worker_stop.is_set():
          job: Optional[Dict[str, Any]] = None
          with self.lock:
            can_start = (
              self.module_active_job is None
              and bool(self.module_pending_jobs)
              and not self._is_running()
              and self.active_job is None
            )
            if can_start:
              job = self.module_pending_jobs.pop(0)
              job["status"] = "running"
              job["started_at"] = _utc_now_iso()
              job["started_at_ts"] = time.time()
              job["runtime"] = {}
              self.module_active_job = job
              job_id = str(job.get("job_id") or "")
              self._record_module_event_locked(job_id, "started", {
                "job_type": job.get("job_type"),
              })
              self._append_module_log_line_locked(
                job_id,
                f"[module] started type={job.get('job_type')}",
              )
              self._save_module_events()
              self._save_module_jobs_snapshot_locked()

          if job is None:
            time.sleep(0.35)
            continue

          job_id = str(job.get("job_id") or "")
          artifacts: Dict[str, Any] = {}
          run_error: Optional[str] = None
          final_status = "completed"
          try:
            artifacts = self._execute_module_job(job)
          except Exception as exc:
            run_error = str(exc)
            final_status = "failed"

          if self._module_cancel_requested(job_id) and final_status != "completed":
            final_status = "stopped"

          with self.lock:
            active = self.module_active_job
            if not active or str(active.get("job_id")) != job_id:
              active = job
            active["finished_at"] = _utc_now_iso()
            active["status"] = final_status
            active["error"] = run_error
            active["artifacts"] = artifacts if isinstance(artifacts, dict) else {}
            self._record_module_event_locked(job_id, "finished", {
              "status": final_status,
              "error": run_error,
            })
            if run_error:
              self._append_module_log_line_locked(job_id, f"[module] failed: {run_error}", level="error")
            else:
              self._append_module_log_line_locked(job_id, "[module] finished successfully", level="info")

            self.module_history.append(self._strip_module_runtime(dict(active)))
            self.module_history = self.module_history[-_MODULE_HISTORY_LIMIT:]
            self._save_module_history()
            self._save_module_events()
            self.module_active_job = None
            self._save_module_jobs_snapshot_locked()

    def _execute_module_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        job_type = str(job.get("job_type") or "")
        if job_type == "story":
          return self._execute_story_module_job(job)
        if job_type == "image":
          return self._execute_image_module_job(job)
        if job_type == "translation":
          return self._execute_translation_module_job(job)
        if job_type == "voice":
          return self._execute_voice_module_job(job)
        raise RuntimeError(f"Unsupported module job type: {job_type}")

        def _execute_story_module_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
                self._cleanup_cached_models(force=True)
                payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
                sanitized = self._sanitize_payload(
                        {
                                "count": payload.get("count", 1),
                                "max_retries": payload.get("max_retries", 0),
                                "pages": payload.get("pages", 0),
                                "seed": payload.get("seed"),
                                "age": payload.get("age"),
                                "category": payload.get("category"),
                                "theme": payload.get("theme"),
                                "subcategory": payload.get("subcategory"),
                                "story_input_mode": payload.get("story_input_mode", "preset"),
                                "story_prompt": payload.get("story_prompt", ""),
                                "story_materials": payload.get("story_materials", ""),
                                "low_vram": payload.get("low_vram", True),
                                "photo_enabled": False,
                                "translation_enabled": False,
                                "voice_enabled": False,
                                "verify_enabled": False,
                                "strict_translation": False,
                                "strict_voice": False,
                                "priority": "normal",
                        }
                )

                cmd = self._build_command(sanitized)
                job_id = str(job.get("job_id") or "")
                self._append_module_log_line(job_id, "[story] command: " + " ".join(cmd))

                env = _build_subprocess_env()
                process = subprocess.Popen(
                        cmd,
                        cwd=str(self.root_dir),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        env=env,
                        **_popen_kwargs(),
                )
                with self.lock:
                        if self.module_active_job and str(self.module_active_job.get("job_id")) == job_id:
                                runtime = self.module_active_job.get("runtime") if isinstance(self.module_active_job.get("runtime"), dict) else {}
                                runtime["process"] = process
                                self.module_active_job["runtime"] = runtime

                if process.stdout is not None:
                        for raw in iter(process.stdout.readline, ""):
                                if raw == "":
                                        break
                                self._append_module_log_line(job_id, raw)
                                if self._module_cancel_requested(job_id):
                                        try:
                                                if process.poll() is None:
                                                        process.terminate()
                                        except Exception:
                                                pass
                        try:
                                process.stdout.close()
                        except Exception:
                                pass

                exit_code = process.wait()
                if exit_code != 0:
                        raise RuntimeError(f"Story module exited with code {exit_code}")

                latest_story = find_latest_story_root(self.root_dir / "output")
                return {
                        "exit_code": exit_code,
                        "story_root": str(latest_story) if latest_story else None,
                        "count": sanitized.get("count"),
                }

        def _execute_image_module_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
                payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
                story_root = self._resolve_story_root_path(payload.get("story_root"))
                if story_root is None:
                        raise RuntimeError("Unable to resolve story_root for image module job")

                items = self._collect_image_items_for_story(story_root, limit=900)
                task_ids = set(payload.get("task_ids") or [])
                if task_ids:
                        items = [item for item in items if str(item.get("task_id") or "") in task_ids]
                if not items:
                        raise RuntimeError("No image tasks found for the selected story")

                job_id = str(job.get("job_id") or "")
                raw_overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
                overrides: Dict[str, Any] = {}
                for key, value in raw_overrides.items():
                        if value is None and key not in {"skip_refiner"}:
                                continue
                        overrides[key] = value
                overrides["low_vram"] = _safe_bool(raw_overrides.get("low_vram"), True)

                from backends.image import build_image_backend

                backend_cfg = self._build_image_backend_config(
                        {
                                "width": overrides.get("width"),
                                "height": overrides.get("height"),
                                "steps": overrides.get("steps"),
                                "guidance": overrides.get("guidance"),
                                "negative_prompt": overrides.get("negative_prompt"),
                                "skip_refiner": overrides.get("skip_refiner"),
                                "refiner_steps": overrides.get("refiner_steps"),
                                "low_vram": overrides.get("low_vram", True),
                        }
                )
                backend_key = self._image_backend_key(backend_cfg)
                backend = self._acquire_cached_backend(
                        "image",
                        backend_key,
                        lambda: build_image_backend(backend_cfg),
                )

                results: List[Dict[str, Any]] = []
                ok_count = 0
                try:
                        for index, item in enumerate(items, start=1):
                                if self._module_cancel_requested(job_id):
                                        raise RuntimeError("Image module job canceled")
                                result = self._regenerate_single_image_item(item, overrides, backend=backend)
                                results.append(result)
                                if result.get("ok"):
                                        ok_count += 1
                                self._append_module_log_line(
                                        job_id,
                                        f"[image] {index}/{len(items)} task={item.get('task_id')} ok={bool(result.get('ok'))}",
                                        level="info" if result.get("ok") else "warning",
                                )
                finally:
                        self._release_cached_backend("image", backend_key)

                if ok_count == 0:
                        raise RuntimeError("Image module job failed for all selected items")

                return {
                        "story_root": str(story_root),
                        "total": len(items),
                        "ok": ok_count,
                        "failed": len(items) - ok_count,
                        "results": results[:80],
                }

        def _execute_translation_module_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
                from trans import Config as TransConfig, translate_story

                self._cleanup_cached_models(force=True)
                payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
                story_root = self._resolve_story_root_path(payload.get("story_root"))
                if story_root is None:
                        raise RuntimeError("Unable to resolve story_root for translation module job")

                target_langs = self._parse_lang_list(payload.get("target_langs"), limit=24)
                cfg = TransConfig(
                        model_dir=Path(DEFAULT_CHIEF_OPTIONS.translation_model),
                        device=str(payload.get("device") or DEFAULT_CHIEF_OPTIONS.translation_device),
                        dtype=parse_dtype(str(payload.get("dtype") or DEFAULT_CHIEF_OPTIONS.translation_dtype)),
                        source_lang=str(payload.get("source_lang") or DEFAULT_CHIEF_OPTIONS.translation_source_lang),
                        source_folder=str(payload.get("source_folder") or DEFAULT_CHIEF_OPTIONS.story_language),
                        target_langs=target_langs,
                        sample_dir=self.root_dir / "models" / "XTTS-v2" / "samples",
                        output_dir_name="",
                        beam_size=_safe_int(payload.get("beam_size"), int(DEFAULT_CHIEF_OPTIONS.translation_beam_size), min_value=1, max_value=8),
                        length_penalty=_safe_float(payload.get("length_penalty"), float(DEFAULT_CHIEF_OPTIONS.translation_length_penalty)),
                )

                job_id = str(job.get("job_id") or "")
                self._append_module_log_line(job_id, f"[translation] story={story_root} source={cfg.source_folder} targets={cfg.target_langs or 'auto'}")
                outputs = translate_story(story_root, cfg, console=False)

                languages = sorted(outputs.keys())
                file_count = sum(len(items) for items in outputs.values())
                self._append_module_log_line(job_id, f"[translation] completed languages={languages} files={file_count}")

                return {
                        "story_root": str(story_root),
                        "languages": languages,
                        "file_count": file_count,
                }

        def _execute_voice_module_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
                from voice import Config as VoiceConfig, generate_narration_for_story

                self._cleanup_cached_models(force=True)
                payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
                story_root = self._resolve_story_root_path(payload.get("story_root"))
                if story_root is None:
                        raise RuntimeError("Unable to resolve story_root for voice module job")

                language = _safe_text(payload.get("language"), default="", max_length=24)
                if not language:
                        candidates = detect_story_languages(story_root)
                        language = candidates[0] if candidates else str(DEFAULT_CHIEF_OPTIONS.voice_language)

                speaker_wav_path = self._safe_path_under_root(str(payload.get("speaker_wav") or ""))
                speaker_dir_path = self._safe_path_under_root(str(payload.get("speaker_dir") or ""))
                if speaker_wav_path and not speaker_wav_path.exists():
                        speaker_wav_path = None
                if speaker_dir_path and not speaker_dir_path.exists():
                        speaker_dir_path = None

                cfg = VoiceConfig(
                        model_dir=self.root_dir / "models" / "XTTS-v2",
                        device=str(payload.get("device") or DEFAULT_CHIEF_OPTIONS.voice_device),
                        language=language,
                        speaker_wav=speaker_wav_path,
                        speaker_dir=speaker_dir_path,
                        page_start=payload.get("page_start"),
                        page_end=payload.get("page_end"),
                        gain=_safe_float(payload.get("gain"), 1.0),
                        concat=_safe_bool(payload.get("concat"), True),
                        keep_raw=_safe_bool(payload.get("keep_raw"), True),
                        speed=_safe_float(payload.get("speed"), 1.0),
                )

                job_id = str(job.get("job_id") or "")
                self._append_module_log_line(job_id, f"[voice] story={story_root} language={language}")
                success = generate_narration_for_story(story_root, cfg, console=False)
                if not success:
                        raise RuntimeError("Voice module generation returned failure")

                audio_files = list_generated_audio_files(story_root, language, cfg.audio_dir, cfg.format)
                self._append_module_log_line(job_id, f"[voice] generated {len(audio_files)} audio files")

                return {
                        "story_root": str(story_root),
                        "language": language,
                        "audio_count": len(audio_files),
                        "audio_files": [str(path) for path in audio_files[:80]],
                }

    def save_voice_recording(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        wav_base64 = _safe_text(payload.get("wav_base64"), default="", max_length=40_000_000)
        if not wav_base64:
            return {"ok": False, "error": "wav_base64 is required"}

        try:
            wav_bytes = base64.b64decode(wav_base64, validate=True)
        except Exception:
            return {"ok": False, "error": "Invalid wav_base64 payload"}

        if len(wav_bytes) < 44:
            return {"ok": False, "error": "Audio payload is too small"}
        if wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
            return {"ok": False, "error": "Expected WAV/RIFF audio payload"}

        script_text = _safe_text(payload.get("script_text"), default="", max_length=4000)
        custom_root = self.root_dir / "runs" / "voice_samples"
        default_dir = custom_root / "custom"
        custom_root.mkdir(parents=True, exist_ok=True)
        default_dir.mkdir(parents=True, exist_ok=True)

        selected_dir = self._safe_path_under_root(_safe_text(payload.get("speaker_dir"), default="", max_length=1200))
        if selected_dir is not None:
            try:
                selected_dir.relative_to(custom_root.resolve(strict=False))
            except Exception:
                selected_dir = None
        recordings_dir = selected_dir or default_dir
        recordings_dir.mkdir(parents=True, exist_ok=True)

        file_stem = f"speaker-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:6]}"
        wav_path = recordings_dir / f"{file_stem}.wav"

        try:
            wav_path.write_bytes(wav_bytes)
            if script_text:
                (recordings_dir / f"{file_stem}.txt").write_text(script_text + "\n", encoding="utf-8")
        except Exception as exc:
            return {"ok": False, "error": f"Failed to persist recording: {exc}"}

        self._append_log_line(
            f"[voice] Saved speaker sample: {wav_path}",
            run_id=self.current_run_id,
            level="info",
        )
        return {
            "ok": True,
            "path": self._to_root_relative_path(wav_path),
            "dir": self._to_root_relative_path(recordings_dir),
            "size_bytes": len(wav_bytes),
        }

    def list_voice_preset_samples(self) -> Dict[str, Any]:
        root = self.root_dir / "models" / "XTTS-v2" / "samples"
        samples: List[Dict[str, Any]] = []
        if root.exists() and root.is_dir():
            for item in sorted(root.glob("*.wav"), key=lambda path: path.name.lower()):
                if not item.is_file():
                    continue
                samples.append(
                    {
                        "path": self._to_root_relative_path(item),
                        "name": item.name,
                        "language": self._infer_voice_sample_language(item),
                    }
                )
        auto_defaults: Dict[str, str] = {}
        for language in ("en", "zh", "zh-cn", "ja", "de", "es", "fr", "pt", "tr"):
            resolved = self._best_wav_in_dir(root, language, fallback=False)
            if resolved is not None:
                auto_defaults[language] = self._to_root_relative_path(resolved)
        fallback_wav = self._best_wav_in_dir(root, "en", fallback=True)
        return {
            "ok": True,
            "root": self._to_root_relative_path(root),
            "samples": samples,
            "auto_defaults": auto_defaults,
            "fallback_sample": self._to_root_relative_path(fallback_wav) if fallback_wav is not None else None,
        }

    def list_custom_voice_library(self, selected_dir_hint: str = "") -> Dict[str, Any]:
        root = self.root_dir / "runs" / "voice_samples"
        default_dir = root / "custom"
        root.mkdir(parents=True, exist_ok=True)
        default_dir.mkdir(parents=True, exist_ok=True)

        selected_dir = self._safe_path_under_root(_safe_text(selected_dir_hint, default="", max_length=1200))
        if selected_dir is not None:
            try:
                selected_dir.relative_to(root.resolve(strict=False))
            except Exception:
                selected_dir = None
        selected_dir = selected_dir or default_dir
        selected_dir.mkdir(parents=True, exist_ok=True)

        directory_map: Dict[str, Path] = {str(root.resolve(strict=False)): root, str(default_dir.resolve(strict=False)): default_dir}
        for item in root.rglob("*"):
            if not item.is_dir():
                continue
            try:
                rel = item.relative_to(root)
            except Exception:
                continue
            if len(rel.parts) > 3:
                continue
            directory_map[str(item.resolve(strict=False))] = item

        directories: List[Dict[str, Any]] = []
        for item in sorted(directory_map.values(), key=lambda path: self._to_root_relative_path(path).lower()):
            wav_count = 0
            try:
                wav_count = sum(1 for child in item.glob("*.wav") if child.is_file())
            except Exception:
                wav_count = 0
            rel_path = self._to_root_relative_path(item)
            label = "custom root" if item == root else str(item.relative_to(root)).replace("\\", "/")
            directories.append(
                {
                    "path": rel_path,
                    "label": label,
                    "wav_count": wav_count,
                }
            )

        files: List[Dict[str, Any]] = []
        try:
            wav_items = sorted(selected_dir.glob("*.wav"), key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
        except Exception:
            wav_items = []
        for item in wav_items:
            if not item.is_file():
                continue
            files.append(
                {
                    "path": self._to_root_relative_path(item),
                    "name": item.name,
                }
            )

        return {
            "ok": True,
            "root": self._to_root_relative_path(root),
            "default_dir": self._to_root_relative_path(default_dir),
            "selected_dir": self._to_root_relative_path(selected_dir),
            "directories": directories,
            "files": files,
        }

    @staticmethod
    def _clamp_float(value: float, *, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, float(value)))

    def _resolve_config_path(self, raw_path: Any) -> Path:
        path_text = str(raw_path or "").strip()
        path = Path(path_text) if path_text else self.root_dir
        if not path.is_absolute():
            path = self.root_dir / path
        return path

    def _to_root_relative_path(self, path: Path) -> str:
        try:
            resolved = path.resolve(strict=False)
            root_resolved = self.root_dir.resolve(strict=False)
            return str(resolved.relative_to(root_resolved)).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")

    @staticmethod
    def _normalize_voice_sample_language(value: str) -> str:
        token = re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-")
        if token in {"zh-tw", "zh-hant", "zho-hant", "cmn-hant", "zh-hk"}:
            return "zh-tw"
        if token in {"zh-cn", "zh-hans", "zho-hans", "cmn-hans"}:
            return "zh-cn"
        if token.startswith("en"):
            return "en"
        if token.startswith("zh"):
            return "zh"
        if token.startswith("ja"):
            return "ja"
        if token.startswith("de"):
            return "de"
        if token.startswith("es"):
            return "es"
        if token.startswith("fr"):
            return "fr"
        if token.startswith("pt"):
            return "pt"
        if token.startswith("tr"):
            return "tr"
        return token

    @classmethod
    def _preferred_voice_sample_tokens(cls, language: str) -> List[str]:
        token = cls._normalize_voice_sample_language(language)
        if token in {"", "en"}:
            return ["en", "en-us", "en-gb"]
        if token in {"zh", "zh-tw"}:
            return ["zh-tw", "zh-hant", "zho-hant", "zh", "zh-cn", "zh-hans", "zho-hans"]
        if token == "zh-cn":
            return ["zh-cn", "zh-hans", "zho-hans", "zh", "zh-tw", "zh-hant", "zho-hant"]
        if token == "ja":
            return ["ja", "ja-jp"]
        return [token]

    @staticmethod
    def _voice_sample_rank(path: Path, preferred_tokens: Sequence[str]) -> Optional[int]:
        stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
        for index, token in enumerate(preferred_tokens):
            if not token:
                continue
            if stem == token or stem.startswith(token + "-") or stem.endswith("-" + token) or f"-{token}-" in stem:
                return index
        return None

    def _infer_voice_sample_language(self, path: Path) -> str:
        stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
        for token in ("zh-tw", "zh-cn", "ja", "en", "de", "es", "fr", "pt", "tr", "zh"):
            if stem == token or stem.startswith(token + "-") or stem.endswith("-" + token) or f"-{token}-" in stem:
                return token
        return "default"

    def _best_wav_in_dir(self, directory: Path, language: str, *, fallback: bool = True) -> Optional[Path]:
        if not directory.exists() or not directory.is_dir():
            return None
        candidates: List[Path] = []
        try:
            for item in directory.glob("*.wav"):
                if item.exists() and item.is_file():
                    candidates.append(item)
        except Exception:
            return None
        if not candidates:
            return None
        candidates.sort(key=lambda p: p.name.lower())

        preferred_tokens = self._preferred_voice_sample_tokens(language)
        ranked: List[Tuple[int, str, Path]] = []
        for item in candidates:
            rank = self._voice_sample_rank(item, preferred_tokens)
            if rank is not None:
                ranked.append((rank, item.name.lower(), item))
        if ranked:
            ranked.sort(key=lambda entry: (entry[0], entry[1]))
            return ranked[0][2]

        if not fallback:
            return None

        english_tokens = self._preferred_voice_sample_tokens("en")
        english_ranked: List[Tuple[int, str, Path]] = []
        for item in candidates:
            rank = self._voice_sample_rank(item, english_tokens)
            if rank is not None:
                english_ranked.append((rank, item.name.lower(), item))
        if english_ranked:
            english_ranked.sort(key=lambda entry: (entry[0], entry[1]))
            return english_ranked[0][2]
        return candidates[0]

    def _resolve_general_speaker_wav(self, speaker_hint: str, language: str) -> Optional[Path]:
        hinted = self._safe_path_under_root(speaker_hint)
        if hinted and hinted.exists() and hinted.is_file() and hinted.suffix.lower() == ".wav":
            return hinted
        if hinted and hinted.exists() and hinted.is_dir():
            wav = self._best_wav_in_dir(hinted, language, fallback=True)
            if wav is not None:
                return wav

        language_text = _safe_text(language, default="", max_length=24).lower()
        language_short = language_text.split("-", 1)[0] if language_text else ""

        candidate_dirs: List[Path] = [
            self.root_dir / "models" / "XTTS-v2" / "samples",
            self.root_dir / "runs" / "voice_samples",
        ]
        if language_text:
            candidate_dirs.insert(1, self.root_dir / "models" / "XTTS-v2" / "samples" / language_text)
        if language_short and language_short != language_text:
            candidate_dirs.insert(2, self.root_dir / "models" / "XTTS-v2" / "samples" / language_short)

        for directory in candidate_dirs:
            wav = self._best_wav_in_dir(directory, language, fallback=True)
            if wav is not None:
                return wav
        return None

    def general_text_generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = _safe_text(payload.get("prompt"), default="", max_length=16_000)
        if not prompt:
            return {"ok": False, "error": "prompt is required"}

        tracked_job = self._start_general_module_job(
            "general_text",
            {
                "prompt": prompt[:240],
            },
        )
        tracked_job_id = str(tracked_job.get("job_id") or "")

        system_prompt = _safe_text(
            payload.get("system_prompt"),
            default="You are a helpful assistant.",
            max_length=4000,
        )
        seed = _safe_int(payload.get("seed"), int(DEFAULT_CHIEF_OPTIONS.seed or 42), min_value=0)

        dtype_text = _safe_text(
            payload.get("dtype"),
            default=str(DEFAULT_CHIEF_OPTIONS.story_dtype),
            max_length=16,
        ).lower()
        if dtype_text not in {"float16", "bfloat16", "float32"}:
            dtype_text = str(DEFAULT_CHIEF_OPTIONS.story_dtype)

        quantization = _safe_text(
            payload.get("quantization"),
            default=str(DEFAULT_CHIEF_OPTIONS.story_quantization or ""),
            max_length=16,
        ).lower()
        if quantization == "none":
            quantization = ""
        if quantization not in {"", "4bit", "8bit", "gptq"}:
            quantization = ""

        max_tokens = _safe_int(
            payload.get("max_tokens"),
            int(DEFAULT_CHIEF_OPTIONS.story_max_tokens),
            min_value=16,
            max_value=2048,
        )
        min_tokens = _safe_int(
            payload.get("min_tokens"),
            int(DEFAULT_CHIEF_OPTIONS.story_min_tokens),
            min_value=0,
            max_value=1024,
        )
        if min_tokens >= max_tokens:
            min_tokens = max(0, max_tokens - 1)

        temperature = self._clamp_float(
            _safe_float(payload.get("temperature"), float(DEFAULT_CHIEF_OPTIONS.story_temperature)),
            min_value=0.0,
            max_value=2.0,
        )
        top_p = self._clamp_float(
            _safe_float(payload.get("top_p"), float(DEFAULT_CHIEF_OPTIONS.story_top_p)),
            min_value=0.01,
            max_value=1.0,
        )
        top_k = _safe_int(payload.get("top_k"), int(DEFAULT_CHIEF_OPTIONS.story_top_k), min_value=0, max_value=200)
        repetition_penalty = self._clamp_float(
            _safe_float(payload.get("repetition_penalty"), float(DEFAULT_CHIEF_OPTIONS.story_repetition_penalty)),
            min_value=1.0,
            max_value=2.0,
        )
        no_repeat_ngram = _safe_int(
            payload.get("no_repeat_ngram"),
            int(DEFAULT_CHIEF_OPTIONS.story_no_repeat_ngram),
            min_value=0,
            max_value=8,
        )

        with self.general_lock:
            self._cleanup_cached_models(force=False)
            try:
                from backends.llm import GenerationParams, LLMConfig, build_llm
                from prompts.prompt_utils import ChatPrompt

                config = LLMConfig(
                    model_dir=self._resolve_config_path(DEFAULT_CHIEF_OPTIONS.story_model),
                    device_map=_safe_text(
                        payload.get("device"),
                        default=str(DEFAULT_CHIEF_OPTIONS.story_device),
                        max_length=24,
                    ),
                    dtype=dtype_text,
                    seed=seed,
                    quantization=quantization or None,
                    provider="transformers",
                    model_family=str(DEFAULT_CHIEF_OPTIONS.story_model_name or "") or None,
                )
                params = GenerationParams(
                    max_tokens=max_tokens,
                    min_tokens=min_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    top_k=top_k,
                    repetition_penalty=repetition_penalty,
                    no_repeat_ngram_size=no_repeat_ngram or None,
                )

                backend_key: Tuple[Any, ...] = (
                    "llm",
                    str(config.model_dir),
                    str(config.device_map),
                    str(config.dtype),
                    str(config.quantization or ""),
                    str(config.provider or ""),
                    str(config.model_family or ""),
                )
                llm = self._acquire_cached_backend("llm", backend_key, lambda: build_llm(config))
                try:
                    text, token_count = llm.generate(ChatPrompt(system_prompt=system_prompt, user_prompt=prompt), params)
                    self._append_log_line(
                        f"[general-text] Generated response with {token_count} tokens",
                        run_id=self.current_run_id,
                        level="info",
                    )
                    self._append_module_log_line(
                        tracked_job_id,
                        f"[general-text] generated tokens={int(token_count)}",
                        level="info",
                    )
                    result = {
                        "ok": True,
                        "text": text,
                        "tokens": int(token_count),
                        "model": str(self._resolve_config_path(DEFAULT_CHIEF_OPTIONS.story_model)),
                        "module_job_id": tracked_job_id,
                    }
                    self._finish_general_module_job(
                        tracked_job,
                        ok=True,
                        artifacts={
                            "tokens": int(token_count),
                            "model": str(self._resolve_config_path(DEFAULT_CHIEF_OPTIONS.story_model)),
                        },
                    )
                    return result
                finally:
                    self._release_cached_backend("llm", backend_key)
            except Exception as exc:
                error_text = f"General text generation failed: {exc}"
                self._append_module_log_line(tracked_job_id, f"[general-text] failed: {exc}", level="error")
                self._finish_general_module_job(tracked_job, ok=False, error=error_text)
                return {"ok": False, "error": error_text, "module_job_id": tracked_job_id}

    def general_image_generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        prompt = _safe_text(payload.get("prompt"), default="", max_length=12_000)
        if not prompt:
            return {"ok": False, "error": "prompt is required"}

        tracked_job = self._start_general_module_job(
            "general_image",
            {
                "prompt": prompt[:240],
            },
        )
        tracked_job_id = str(tracked_job.get("job_id") or "")

        seed = _safe_int(
            payload.get("seed"),
            int((time.time() * 1000) % 2_147_483_647),
            min_value=0,
            max_value=2_147_483_647,
        )
        overrides = {
            "provider": _safe_text(payload.get("provider"), default="", max_length=64),
            "model_family": _safe_text(payload.get("model_family"), default="", max_length=64),
            "base_model_dir": _safe_text(payload.get("base_model_dir"), default="", max_length=1200),
            "refiner_model_dir": _safe_text(payload.get("refiner_model_dir"), default="", max_length=1200),
            "width": payload.get("width"),
            "height": payload.get("height"),
            "steps": payload.get("steps"),
            "guidance": payload.get("guidance"),
            "negative_prompt": _safe_text(payload.get("negative_prompt"), default="", max_length=4000),
            "skip_refiner": _safe_bool(payload.get("skip_refiner"), bool(DEFAULT_CHIEF_OPTIONS.photo_skip_refiner)),
            "refiner_steps": payload.get("refiner_steps"),
            "low_vram": _safe_bool(payload.get("low_vram"), True),
        }

        with self.general_lock:
            self._cleanup_cached_models(force=False)
            try:
                from backends.image import build_image_backend

                backend_cfg = self._build_image_backend_config(overrides)
                backend_key = self._image_backend_key(backend_cfg)
                backend = self._acquire_cached_backend("image", backend_key, lambda: build_image_backend(backend_cfg))
                try:
                    image = backend.generate_image(
                        prompt=prompt,
                        seed=seed,
                        width=int(backend_cfg.width),
                        height=int(backend_cfg.height),
                        num_inference_steps=int(backend_cfg.steps),
                        guidance_scale=float(backend_cfg.guidance),
                        negative_prompt=str(backend_cfg.negative_prompt or ""),
                        skip_refiner=bool(backend_cfg.skip_refiner),
                        refiner_steps=backend_cfg.refiner_steps,
                    )
                finally:
                    self._release_cached_backend("image", backend_key)

                output_dir = self.root_dir / "runs" / "general" / "image"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"general-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}.png"
                image.save(output_path)
                image_path = self._to_root_relative_path(output_path)

                self._append_log_line(
                    f"[general-image] Generated image: {image_path}",
                    run_id=self.current_run_id,
                    level="info",
                )
                self._append_module_log_line(
                    tracked_job_id,
                    f"[general-image] generated path={image_path} seed={seed}",
                    level="info",
                )
                result = {
                    "ok": True,
                    "image_path": image_path,
                    "seed": seed,
                    "width": int(backend_cfg.width),
                    "height": int(backend_cfg.height),
                    "steps": int(backend_cfg.steps),
                    "guidance": float(backend_cfg.guidance),
                    "module_job_id": tracked_job_id,
                }
                self._finish_general_module_job(
                    tracked_job,
                    ok=True,
                    artifacts={
                        "image_path": image_path,
                        "seed": seed,
                        "width": int(backend_cfg.width),
                        "height": int(backend_cfg.height),
                    },
                )
                return result
            except Exception as exc:
                error_text = f"General image generation failed: {exc}"
                self._append_module_log_line(tracked_job_id, f"[general-image] failed: {exc}", level="error")
                self._finish_general_module_job(tracked_job, ok=False, error=error_text)
                return {"ok": False, "error": error_text, "module_job_id": tracked_job_id}

    def general_translate_text(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = _safe_text(payload.get("text"), default="", max_length=60_000)
        if not text:
            return {"ok": False, "error": "text is required"}

        tracked_job = self._start_general_module_job(
            "general_translation",
            {
                "text": text[:240],
            },
        )
        tracked_job_id = str(tracked_job.get("job_id") or "")

        target_lang = _safe_text(payload.get("target_lang"), default="zh-TW", max_length=32)
        if not target_lang:
            target_lang = "zh-TW"

        source_lang_raw = _safe_text(
            payload.get("source_lang"),
            default=str(DEFAULT_CHIEF_OPTIONS.translation_source_lang),
            max_length=32,
        )
        source_lang_code = source_lang_raw
        if "_" not in source_lang_code:
            try:
                from backends.translation_common import SAMPLE_LANGUAGE_MAP

                source_lang_code = SAMPLE_LANGUAGE_MAP.get(source_lang_code.lower(), source_lang_code)
            except Exception:
                pass
        if "_" not in source_lang_code:
            source_lang_code = str(DEFAULT_CHIEF_OPTIONS.translation_source_lang)

        dtype_text = _safe_text(
            payload.get("dtype"),
            default=str(DEFAULT_CHIEF_OPTIONS.translation_dtype),
            max_length=16,
        ).lower()
        if dtype_text not in {"float16", "bfloat16", "float32"}:
            dtype_text = str(DEFAULT_CHIEF_OPTIONS.translation_dtype)

        with self.general_lock:
            self._cleanup_cached_models(force=False)
            try:
                from backends.translation import build_translation_backend

                cfg = SimpleNamespace(
                    provider="transformers_nllb",
                    model_dir=self._resolve_config_path(DEFAULT_CHIEF_OPTIONS.translation_model),
                    device=_safe_text(
                        payload.get("device"),
                        default=str(DEFAULT_CHIEF_OPTIONS.translation_device),
                        max_length=24,
                    ),
                    dtype=parse_dtype(dtype_text),
                    source_lang=source_lang_code,
                    quantize=_safe_bool(payload.get("quantize"), True),
                    chunk_size=_safe_int(payload.get("chunk_size"), 1200, min_value=120, max_value=6000),
                    max_input=_safe_int(payload.get("max_input"), 512, min_value=64, max_value=4096),
                    max_output=_safe_int(payload.get("max_output"), 512, min_value=32, max_value=2048),
                    min_output=_safe_int(payload.get("min_output"), 32, min_value=8, max_value=512),
                    batch_size=_safe_int(payload.get("batch_size"), 8, min_value=1, max_value=32),
                    beam_size=_safe_int(
                        payload.get("beam_size"),
                        int(DEFAULT_CHIEF_OPTIONS.translation_beam_size),
                        min_value=1,
                        max_value=8,
                    ),
                    length_penalty=self._clamp_float(
                        _safe_float(
                            payload.get("length_penalty"),
                            float(DEFAULT_CHIEF_OPTIONS.translation_length_penalty),
                        ),
                        min_value=0.1,
                        max_value=3.0,
                    ),
                    no_repeat_ngram_size=_safe_int(payload.get("no_repeat_ngram_size"), 3, min_value=0, max_value=8),
                )
                backend_key: Tuple[Any, ...] = (
                    "translation",
                    str(cfg.provider),
                    str(cfg.model_dir),
                    str(cfg.device),
                    str(cfg.dtype),
                    str(cfg.source_lang),
                    int(cfg.beam_size),
                    float(cfg.length_penalty),
                    int(cfg.no_repeat_ngram_size),
                    bool(cfg.quantize),
                )
                backend = self._acquire_cached_backend("translation", backend_key, lambda: build_translation_backend(cfg))
                try:
                    translated = backend.translate(text, target_lang)
                finally:
                    self._release_cached_backend("translation", backend_key)

                self._append_log_line(
                    f"[general-translation] source={source_lang_code} target={target_lang}",
                    run_id=self.current_run_id,
                    level="info",
                )
                self._append_module_log_line(
                    tracked_job_id,
                    f"[general-translation] source={source_lang_code} target={target_lang}",
                    level="info",
                )
                result = {
                    "ok": True,
                    "translated_text": translated,
                    "source_lang": source_lang_code,
                    "target_lang": target_lang,
                    "module_job_id": tracked_job_id,
                }
                self._finish_general_module_job(
                    tracked_job,
                    ok=True,
                    artifacts={
                        "source_lang": source_lang_code,
                        "target_lang": target_lang,
                        "text_length": len(translated),
                    },
                )
                return result
            except Exception as exc:
                error_text = f"General translation failed: {exc}"
                self._append_module_log_line(tracked_job_id, f"[general-translation] failed: {exc}", level="error")
                self._finish_general_module_job(tracked_job, ok=False, error=error_text)
                return {"ok": False, "error": error_text, "module_job_id": tracked_job_id}

    def general_voice_generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        text = _safe_text(payload.get("text"), default="", max_length=16_000)
        if not text:
            return {"ok": False, "error": "text is required"}

        tracked_job = self._start_general_module_job(
            "general_voice",
            {
                "text": text[:240],
            },
        )
        tracked_job_id = str(tracked_job.get("job_id") or "")

        language = _safe_text(
            payload.get("language"),
            default=str(DEFAULT_CHIEF_OPTIONS.voice_language),
            max_length=24,
        )
        if not language:
            language = str(DEFAULT_CHIEF_OPTIONS.voice_language)

        speaker_hint = _safe_text(payload.get("speaker_wav"), default="", max_length=1200)
        speaker_wav = self._resolve_general_speaker_wav(speaker_hint, language)
        if speaker_wav is None:
            error_text = "No speaker WAV found. Record one first or provide a valid speaker_wav path."
            self._append_module_log_line(tracked_job_id, f"[general-voice] failed: {error_text}", level="error")
            self._finish_general_module_job(tracked_job, ok=False, error=error_text)
            return {
                "ok": False,
                "error": error_text,
                "module_job_id": tracked_job_id,
            }

        speed = self._clamp_float(_safe_float(payload.get("speed"), 1.0), min_value=0.5, max_value=2.0)
        temperature = self._clamp_float(_safe_float(payload.get("temperature"), 0.7), min_value=0.05, max_value=1.5)

        with self.general_lock:
            self._cleanup_cached_models(force=False)
            try:
                from backends.voice import build_voice_backend

                cfg = SimpleNamespace(
                    provider="coqui_xtts",
                    model_family="xtts",
                    model_dir=self.root_dir / "models" / "XTTS-v2",
                    device=_safe_text(
                        payload.get("device"),
                        default=str(DEFAULT_CHIEF_OPTIONS.voice_device),
                        max_length=24,
                    ),
                    speed=speed,
                    temperature=temperature,
                )
                backend_key: Tuple[Any, ...] = (
                    "voice",
                    str(cfg.provider),
                    str(cfg.model_family),
                    str(cfg.model_dir),
                    str(cfg.device),
                    float(cfg.speed),
                    float(cfg.temperature),
                )
                backend = self._acquire_cached_backend("voice", backend_key, lambda: build_voice_backend(cfg))

                try:
                    output_dir = self.root_dir / "runs" / "general" / "voice"
                    output_dir.mkdir(parents=True, exist_ok=True)
                    output_path = output_dir / f"general-tts-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:8]}.wav"
                    backend.synthesize_to_file(
                        text=text,
                        speaker_wav=speaker_wav,
                        language=language,
                        output_path=output_path,
                    )
                finally:
                    self._release_cached_backend("voice", backend_key)

                audio_path = self._to_root_relative_path(output_path)
                speaker_path = self._to_root_relative_path(speaker_wav)
                self._append_log_line(
                    f"[general-voice] Generated audio: {audio_path}",
                    run_id=self.current_run_id,
                    level="info",
                )
                self._append_module_log_line(
                    tracked_job_id,
                    f"[general-voice] generated audio={audio_path} speaker={speaker_path}",
                    level="info",
                )
                result = {
                    "ok": True,
                    "audio_path": audio_path,
                    "speaker_wav": speaker_path,
                    "language": language,
                    "speed": speed,
                    "temperature": temperature,
                    "module_job_id": tracked_job_id,
                }
                self._finish_general_module_job(
                    tracked_job,
                    ok=True,
                    artifacts={
                        "audio_path": audio_path,
                        "speaker_wav": speaker_path,
                        "language": language,
                    },
                )
                return result
            except Exception as exc:
                error_text = f"General voice generation failed: {exc}"
                self._append_module_log_line(tracked_job_id, f"[general-voice] failed: {exc}", level="error")
                self._finish_general_module_job(tracked_job, ok=False, error=error_text)
                return {"ok": False, "error": error_text, "module_job_id": tracked_job_id}

    def _safe_path_under_root(self, raw_path: str) -> Optional[Path]:
        text = _safe_text(raw_path, default="", max_length=1200)
        if not text:
            return None
        candidate = Path(text)
        if not candidate.is_absolute():
            candidate = self.root_dir / candidate
        try:
            resolved = candidate.resolve(strict=False)
            root_resolved = self.root_dir.resolve(strict=False)
        except Exception:
            return None
        try:
            resolved.relative_to(root_resolved)
        except Exception:
            return None
        return resolved

    def _infer_story_root_from_image_path(self, image_path: Path, output_root: Path) -> Optional[Path]:
        try:
            rel = image_path.relative_to(output_root)
        except Exception:
            return None
        if len(rel.parts) < 3:
            return None
        return output_root / rel.parts[0] / rel.parts[1] / rel.parts[2]

    def _discover_story_roots_with_images(self, limit: int = 24) -> List[Path]:
        output_root = self.root_dir / "output"
        if not output_root.exists():
            return []
        image_files = sorted(
            output_root.rglob("image/main/*.png"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        roots: List[Path] = []
        seen: set[str] = set()
        for image_path in image_files:
            story_root = self._infer_story_root_from_image_path(image_path, output_root)
            if story_root is None or not story_root.exists() or not story_root.is_dir():
                continue
            key = str(story_root)
            if key in seen:
                continue
            seen.add(key)
            roots.append(story_root)
            if len(roots) >= limit:
                break
        return roots

    def _resolve_story_root_path(self, story_root_hint: Optional[str]) -> Optional[Path]:
        if story_root_hint:
            direct = self._safe_path_under_root(str(story_root_hint))
            if direct and direct.exists() and direct.is_dir():
                return direct
        candidates = self._discover_story_roots_with_images(limit=1)
        if candidates:
            return candidates[0]
        fallback = find_latest_story_root(self.root_dir / "output")
        if fallback and fallback.exists() and fallback.is_dir():
            return fallback
        return None

    def _normalize_story_root_value(self, raw_value: Any) -> Tuple[Optional[str], Optional[Path]]:
        text = _safe_text(raw_value, default="", max_length=1200)
        if not text:
            return None, None
        path = self._safe_path_under_root(text)
        if path and path.exists() and path.is_dir():
            return self._to_root_relative_path(path), path
        return text, None

    def _resolve_story_root_for_run(self, run_id: str) -> Optional[Path]:
        token = _safe_text(run_id, default="", max_length=120)
        if not token:
            return None

        candidate_texts: List[str] = []
        current_run_id = ""

        with self.lock:
            current_run_id = str(self.current_run_id or "")
            active = self.active_job if isinstance(self.active_job, dict) else None
            if active and str(active.get("run_id") or "") == token:
                payload = active.get("payload") if isinstance(active.get("payload"), dict) else {}
                active_story_root = _safe_text(payload.get("story_root"), default="", max_length=1200)
                if active_story_root:
                    candidate_texts.append(active_story_root)

            for item in reversed(self.history):
                if str(item.get("run_id") or "") != token:
                    continue
                history_story_root = _safe_text(item.get("story_root"), default="", max_length=1200)
                if history_story_root:
                    candidate_texts.append(history_story_root)
                cfg = item.get("config") if isinstance(item.get("config"), dict) else {}
                cfg_story_root = _safe_text(cfg.get("story_root"), default="", max_length=1200)
                if cfg_story_root:
                    candidate_texts.append(cfg_story_root)
                break

        if token == current_run_id:
            runner = self._read_runner_status()
            runner_story_root = _safe_text(runner.get("last_story_root") or runner.get("story_root"), default="", max_length=1200)
            if runner_story_root:
                candidate_texts.append(runner_story_root)

        seen: set[str] = set()
        for raw in candidate_texts:
            key = str(raw)
            if not key or key in seen:
                continue
            seen.add(key)
            path = self._safe_path_under_root(raw)
            if path and path.exists() and path.is_dir():
                return path
        return None

    def _find_history_item_for_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        token = _safe_text(run_id, default="", max_length=120)
        if not token:
            return None
        with self.lock:
            for item in reversed(self.history):
                if str(item.get("run_id") or "") == token:
                    return dict(item)
        return None

    def _story_root_from_report_path(self, report_path: Path, output_root: Path) -> Optional[Path]:
        try:
            rel = report_path.relative_to(output_root)
        except Exception:
            return report_path.parent if report_path.parent.exists() and report_path.parent.is_dir() else None
        if len(rel.parts) >= 4:
            candidate = output_root / rel.parts[0] / rel.parts[1] / rel.parts[2]
        else:
            candidate = report_path.parent
        if not candidate.exists() or not candidate.is_dir():
            return None
        return candidate

    def _collect_run_story_roots(self, run_id: str, history_item: Optional[Dict[str, Any]] = None) -> List[Path]:
        token = _safe_text(run_id, default="", max_length=120)
        if not token:
            return []

        run_item = dict(history_item) if isinstance(history_item, dict) else (self._find_history_item_for_run(token) or {})
        cfg = run_item.get("config") if isinstance(run_item.get("config"), dict) else {}
        total_hint = _safe_int(
            run_item.get("total_books"),
            _safe_int(cfg.get("count"), 0, min_value=0),
            min_value=0,
        )
        category_hint = _safe_text(cfg.get("category"), default="", max_length=64).lower()
        age_hint = _safe_text(cfg.get("age"), default="", max_length=32).lower()

        started_at = _parse_iso_datetime(run_item.get("started_at"))
        finished_at = _parse_iso_datetime(run_item.get("finished_at"))
        now_utc = datetime.now(timezone.utc)

        if started_at is None:
            started_at = now_utc - timedelta(hours=6)
        if finished_at is None:
            finished_at = now_utc

        window_start = started_at - timedelta(minutes=3)
        window_end = finished_at + timedelta(minutes=8)

        roots_by_key: Dict[str, Dict[str, Any]] = {}

        def _push_root(path: Optional[Path], *, mtime_ts: Optional[float], source: str) -> None:
            if path is None:
                return
            if not path.exists() or not path.is_dir():
                return
            rel = self._to_root_relative_path(path)
            parts = rel.split("/")
            if len(parts) >= 3 and parts[0].lower() == "output":
                category_value = parts[1].lower()
                age_value = parts[2].lower()
                if category_hint and category_value != category_hint:
                    return
                if age_hint and age_value != age_hint:
                    return
            try:
                key = str(path.resolve(strict=False)).lower()
            except Exception:
                key = rel.lower()

            ts = float(mtime_ts) if isinstance(mtime_ts, (int, float)) else 0.0
            current = roots_by_key.get(key)
            if current is not None and _safe_float(current.get("mtime_ts"), 0.0) > ts:
                return

            roots_by_key[key] = {
                "path": path,
                "mtime_ts": ts,
                "source": source,
            }

        for raw_story_root in (
            run_item.get("story_root"),
            cfg.get("story_root"),
        ):
            normalized_value, normalized_path = self._normalize_story_root_value(raw_story_root)
            if normalized_path is not None:
                mtime_ts = None
                try:
                    mtime_ts = float(normalized_path.stat().st_mtime)
                except Exception:
                    mtime_ts = None
                _push_root(normalized_path, mtime_ts=mtime_ts, source="history")

        current_run_id = ""
        with self.lock:
            current_run_id = str(self.current_run_id or "")

        if token == current_run_id:
            runner = self._read_runner_status()
            runner_roots: List[Any] = []
            for key in ("story_roots", "generated_story_roots", "book_story_roots"):
                value = runner.get(key)
                if isinstance(value, list):
                    runner_roots.extend(value)
            runner_roots.append(runner.get("last_story_root"))
            runner_roots.append(runner.get("story_root"))

            for raw_story_root in runner_roots:
                normalized_value, normalized_path = self._normalize_story_root_value(raw_story_root)
                if normalized_path is not None:
                    mtime_ts = None
                    try:
                        mtime_ts = float(normalized_path.stat().st_mtime)
                    except Exception:
                        mtime_ts = None
                    _push_root(normalized_path, mtime_ts=mtime_ts, source="runner")

        output_root = self.root_dir / "output"
        if output_root.exists():
            for report_path in output_root.rglob("assessment_report.json"):
                if not report_path.exists() or not report_path.is_file():
                    continue
                story_root = self._story_root_from_report_path(report_path, output_root)
                if story_root is None:
                    continue
                try:
                    mtime_dt = datetime.fromtimestamp(float(report_path.stat().st_mtime), tz=timezone.utc)
                except Exception:
                    continue
                if mtime_dt < window_start or mtime_dt > window_end:
                    continue
                _push_root(story_root, mtime_ts=mtime_dt.timestamp(), source="report_window")

        if not roots_by_key and output_root.exists():
            for report_path in output_root.rglob("assessment_report.json"):
                if not report_path.exists() or not report_path.is_file():
                    continue
                story_root = self._story_root_from_report_path(report_path, output_root)
                if story_root is None:
                    continue
                try:
                    mtime_ts = float(report_path.stat().st_mtime)
                except Exception:
                    mtime_ts = 0.0
                _push_root(story_root, mtime_ts=mtime_ts, source="report_fallback")

        rows = sorted(
            roots_by_key.values(),
            key=lambda item: (
                _safe_float(item.get("mtime_ts"), 0.0),
                self._to_root_relative_path(item.get("path")) if isinstance(item.get("path"), Path) else "",
            ),
        )
        roots = [item.get("path") for item in rows if isinstance(item.get("path"), Path)]

        if total_hint > 0 and len(roots) > total_hint:
            roots = roots[-total_hint:]

        return roots

    def _discover_run_log_files(self, run_id: str, *, history_item: Optional[Dict[str, Any]] = None) -> List[Path]:
        records = self._discover_run_log_records(run_id, history_item=history_item)
        return [item.get("path") for item in records if isinstance(item.get("path"), Path)]

    @staticmethod
    def _parse_book_run_dir_name(name: str) -> Dict[str, Optional[int]]:
        token = _safe_text(name, default="", max_length=240)
        if not token:
            return {"source_tag": "", "book_index": None, "book_total": None, "run_seq": None}

        match = _BOOK_RUN_DIR_PATTERN.match(token)
        if match is None:
            return {
                "source_tag": token,
                "book_index": None,
                "book_total": None,
                "run_seq": None,
            }

        return {
            "source_tag": token,
            "book_index": _safe_int(match.group("book_index"), 0, min_value=1),
            "book_total": _safe_int(match.group("book_total"), 0, min_value=1),
            "run_seq": _safe_int(match.group("run_seq"), 0, min_value=1),
        }

    def _discover_run_log_records(self, run_id: str, *, history_item: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        token = _safe_text(run_id, default="", max_length=120)
        if not token:
            return []

        run_item = dict(history_item) if isinstance(history_item, dict) else (self._find_history_item_for_run(token) or {})
        cfg = run_item.get("config") if isinstance(run_item.get("config"), dict) else {}
        total_hint = _safe_int(
            run_item.get("total_books"),
            _safe_int(cfg.get("count"), 1, min_value=1),
            min_value=1,
            max_value=60,
        )

        started_at = _parse_iso_datetime(run_item.get("started_at"))
        finished_at = _parse_iso_datetime(run_item.get("finished_at"))
        now_utc = datetime.now(timezone.utc)

        if started_at is None and finished_at is None:
            started_at = now_utc - timedelta(hours=12)
            finished_at = now_utc
        elif started_at is None:
            started_at = finished_at - timedelta(hours=8)
        elif finished_at is None:
            finished_at = started_at + timedelta(hours=8)

        window_start = started_at - timedelta(minutes=8)
        window_end = finished_at + timedelta(minutes=35)

        rows_in_window: List[Dict[str, Any]] = []
        rows_all: List[Dict[str, Any]] = []
        if self.runs_dir.exists():
            for log_path in self.runs_dir.glob("*/logs/chief.log"):
                if not log_path.exists() or not log_path.is_file():
                    continue
                try:
                    mtime_dt = datetime.fromtimestamp(float(log_path.stat().st_mtime), tz=timezone.utc)
                except Exception:
                    continue

                row = {
                    "path": log_path,
                    "mtime_ts": mtime_dt.timestamp(),
                }
                rows_all.append(row)
                if window_start <= mtime_dt <= window_end:
                    rows_in_window.append(row)

        rows_all.sort(key=lambda item: _safe_float(item.get("mtime_ts"), 0.0))
        rows_in_window.sort(key=lambda item: _safe_float(item.get("mtime_ts"), 0.0))

        selected_rows = rows_in_window if rows_in_window else rows_all
        if not selected_rows:
            return []

        enriched_rows: List[Dict[str, Any]] = []
        for item in selected_rows:
            path = item.get("path")
            if not isinstance(path, Path):
                continue
            meta = self._parse_book_run_dir_name(path.parent.parent.name)
            enriched = dict(item)
            enriched.update(meta)
            enriched_rows.append(enriched)

        if not enriched_rows:
            return []

        grouped_by_book: Dict[int, Dict[str, Any]] = {}
        ungrouped: List[Dict[str, Any]] = []
        for item in enriched_rows:
            book_index = _safe_int(item.get("book_index"), 0, min_value=0)
            if book_index > 0:
                current = grouped_by_book.get(book_index)
                if current is None or _safe_float(current.get("mtime_ts"), 0.0) <= _safe_float(item.get("mtime_ts"), 0.0):
                    grouped_by_book[book_index] = item
            else:
                ungrouped.append(item)

        if grouped_by_book:
            selected: List[Dict[str, Any]] = [grouped_by_book[index] for index in sorted(grouped_by_book)]
            if total_hint > 0 and len(selected) < total_hint and ungrouped:
                used = {
                    str(item.get("path"))
                    for item in selected
                    if isinstance(item.get("path"), Path)
                }
                extras = [
                    item for item in sorted(ungrouped, key=lambda row: _safe_float(row.get("mtime_ts"), 0.0))
                    if str(item.get("path")) not in used
                ]
                while extras and len(selected) < total_hint:
                    selected.append(extras.pop())
            return selected

        if total_hint > 0 and len(enriched_rows) > total_hint:
            enriched_rows = enriched_rows[-total_hint:]
        return enriched_rows

    def _read_run_logs_from_files(
        self,
        run_id: str,
        *,
        history_item: Optional[Dict[str, Any]] = None,
        log_limit: int = 400,
        book_index: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        requested_book_index = _safe_int(book_index, 0, min_value=0)
        limit = _safe_int(log_limit, 400, min_value=1, max_value=6000)
        records = self._discover_run_log_records(run_id, history_item=history_item)
        if requested_book_index > 0:
            records = [
                item for item in records
                if _safe_int(item.get("book_index"), 0, min_value=0) == requested_book_index
            ]
            limit = max(limit, 4000)

        if not records:
            return []

        file_count = len(records)
        per_file_limit = max(120, min(1600, (limit // max(1, file_count)) + 120))
        if requested_book_index > 0 and file_count <= 1:
            per_file_limit = max(per_file_limit, limit)

        rows: List[Dict[str, Any]] = []
        seq = 1
        add_source_tag = file_count > 1 and requested_book_index <= 0

        for record in records:
            log_path = record.get("path")
            if not isinstance(log_path, Path):
                continue
            try:
                raw_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue

            if len(raw_lines) > per_file_limit:
                raw_lines = raw_lines[-per_file_limit:]

            source_tag = str(record.get("source_tag") or log_path.parent.parent.name)
            fallback_ts: Optional[str]
            try:
                fallback_ts = datetime.fromtimestamp(float(log_path.stat().st_mtime), tz=timezone.utc).isoformat()
            except Exception:
                fallback_ts = None

            for raw in raw_lines:
                line = _normalize_progress_line(str(raw).rstrip("\r\n"))
                if not line:
                    continue

                match = _LOG_LINE_PATTERN.match(line)
                level = "info"
                ts: Optional[str] = fallback_ts
                text = line
                if match is not None:
                    ts = str(match.group("ts") or ts or "") or ts
                    level = str(match.group("level") or "info").lower()
                    text = str(match.group("msg") or "").strip() or line

                if add_source_tag:
                    text = f"[{source_tag}] {text}"

                rows.append(
                    {
                        "seq": seq,
                        "ts": ts,
                        "run_id": run_id,
                        "level": level,
                        "text": text,
                        "source_tag": source_tag,
                        "book_index": _safe_int(record.get("book_index"), 0, min_value=0) or None,
                    }
                )
                seq += 1

        if len(rows) > limit:
            rows = rows[-limit:]
        return rows

    @staticmethod
    def _extract_overall_score_from_report(payload: Dict[str, Any]) -> Optional[float]:
        keys = (
            "overall_score",
            "overall_score_calibrated",
            "overall_score_raw",
            "score",
        )
        for key in keys:
            value = payload.get(key)
            if isinstance(value, (int, float)):
                return round(float(value), 2)
            if isinstance(value, str):
                try:
                    return round(float(value.strip()), 2)
                except Exception:
                    continue
        return None

    def _build_run_book_entries(self, run_id: str, *, history_item: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        token = _safe_text(run_id, default="", max_length=120)
        if not token:
            return []

        roots = self._collect_run_story_roots(token, history_item=history_item)
        log_records = self._discover_run_log_records(token, history_item=history_item)
        log_records_by_index: Dict[int, Dict[str, Any]] = {}
        for item in log_records:
            index = _safe_int(item.get("book_index"), 0, min_value=0)
            if index > 0 and index not in log_records_by_index:
                log_records_by_index[index] = item

        books: List[Dict[str, Any]] = []
        for index, story_root in enumerate(roots, start=1):
            story_root_rel = self._to_root_relative_path(story_root)
            report_file: Optional[str] = None
            report_updated_at: Optional[str] = None
            overall_score: Optional[float] = None
            log_record = log_records_by_index.get(index)

            report_path = None
            for candidate in self._evaluation_report_candidates(story_root, "canonical"):
                if candidate.exists() and candidate.is_file():
                    report_path = candidate
                    break

            if report_path is not None:
                report_file = report_path.name
                try:
                    report_updated_at = datetime.fromtimestamp(float(report_path.stat().st_mtime), tz=timezone.utc).isoformat()
                except Exception:
                    report_updated_at = None
                try:
                    report_payload = json.loads(report_path.read_text(encoding="utf-8"))
                    if isinstance(report_payload, dict):
                        overall_score = self._extract_overall_score_from_report(report_payload)
                except Exception:
                    overall_score = None

            books.append(
                {
                    "book_index": index,
                    "book_id": f"{token}::book:{index}",
                    "title": story_root.name,
                    "story_root": story_root_rel,
                    "report_file": report_file,
                    "overall_score": overall_score,
                    "updated_at": report_updated_at,
                    "artifact_run": str(log_record.get("source_tag") or "") if isinstance(log_record, dict) else None,
                    "log_path": self._to_root_relative_path(log_record.get("path")) if isinstance(log_record, dict) and isinstance(log_record.get("path"), Path) else None,
                }
            )

        if not books and log_records:
            for fallback_index, record in enumerate(log_records, start=1):
                book_index = _safe_int(record.get("book_index"), fallback_index, min_value=1)
                books.append(
                    {
                        "book_index": book_index,
                        "book_id": f"{token}::book:{book_index}",
                        "title": f"book_{book_index:02d}",
                        "story_root": None,
                        "report_file": None,
                        "overall_score": None,
                        "updated_at": None,
                        "artifact_run": str(record.get("source_tag") or "") or None,
                        "log_path": self._to_root_relative_path(record.get("path")) if isinstance(record.get("path"), Path) else None,
                    }
                )

        return books

    def _select_run_book_entry(self, books: List[Dict[str, Any]], book_token: Optional[str]) -> Optional[Dict[str, Any]]:
        if not books:
            return None

        token = _safe_text(book_token, default="", max_length=600)
        if not token:
            return books[-1]

        if token.isdigit():
            index = _safe_int(token, 0, min_value=1, max_value=len(books))
            if 1 <= index <= len(books):
                return books[index - 1]

        if "::book:" in token:
            tail = token.rsplit("::book:", 1)[-1]
            if tail.isdigit():
                index = _safe_int(tail, 0, min_value=1, max_value=len(books))
                if 1 <= index <= len(books):
                    return books[index - 1]

        for item in books:
            if token == str(item.get("book_id") or ""):
                return item
            if token == str(item.get("story_root") or ""):
                return item

        return books[-1]

    @staticmethod
    def _evaluation_report_candidates(story_root: Path, requested_branch: str) -> List[Path]:
        candidates: List[Path] = []
        branch_token = _safe_report_branch_token(requested_branch)
        if branch_token != "canonical":
            candidates.append(story_root / f"assessment_report_{branch_token}.json")
        candidates.append(story_root / "assessment_report.json")
        return candidates

    def _find_latest_story_root_with_report(self, requested_branch: str) -> Optional[Path]:
        output_root = self.root_dir / "output"
        if not output_root.exists():
            return None

        branch_token = _safe_report_branch_token(requested_branch)
        report_names: List[str] = []
        if branch_token != "canonical":
            report_names.append(f"assessment_report_{branch_token}.json")
        report_names.append("assessment_report.json")

        latest_story_root: Optional[Path] = None
        latest_mtime = -1.0
        seen_roots: set[str] = set()

        for report_name in report_names:
            for report_path in output_root.rglob(report_name):
                try:
                    rel = report_path.relative_to(output_root)
                except Exception:
                    rel = None

                if rel is not None and len(rel.parts) >= 4:
                    # Normalize to top-level story root: output/<category>/<age>/<story>/...
                    story_root = output_root / rel.parts[0] / rel.parts[1] / rel.parts[2]
                else:
                    story_root = report_path.parent

                if not story_root.exists() or not story_root.is_dir():
                    continue

                try:
                    root_key = str(story_root.resolve())
                except Exception:
                    root_key = str(story_root)
                if root_key in seen_roots:
                    continue

                seen_roots.add(root_key)
                try:
                    mtime = float(report_path.stat().st_mtime)
                except Exception:
                    mtime = 0.0

                if mtime >= latest_mtime:
                    latest_mtime = mtime
                    latest_story_root = story_root

        return latest_story_root

    def _find_resource_dirs(self, story_root: Path) -> List[Path]:
        candidates: List[Path] = []
        for name in ("resource", "resources"):
            p = story_root / name
            if p.exists() and p.is_dir():
                candidates.append(p)
        for name in ("resource", "resources"):
            for p in story_root.rglob(name):
                if p.exists() and p.is_dir():
                    candidates.append(p)
        unique: Dict[str, Path] = {}
        for p in candidates:
            try:
                unique[str(p.resolve())] = p
            except Exception:
                unique[str(p)] = p
        return sorted(unique.values(), key=lambda x: str(x))

    def _resolve_image_root_for_resource(self, story_root: Path, resource_dir: Path) -> Path:
        if resource_dir.parent.resolve() == story_root.resolve():
            return story_root / "image"
        if resource_dir.name in {"resource", "resources"}:
            return resource_dir.parent / "image"
        return story_root / "image"

    @staticmethod
    def _pick_existing_image(main_path: Path, original_path: Path) -> Path:
        if main_path.exists():
            return main_path
        if original_path.exists():
            return original_path
        return main_path

    @staticmethod
    def _compose_prompt(base_prompt: str, task_type: str) -> str:
        prompt = base_prompt.strip()
        if not prompt:
            return ""
        suffix = ""
        if task_type == "cover":
            suffix = str(DEFAULT_CHIEF_OPTIONS.photo_cover_suffix or "").strip()
        elif task_type == "character":
            suffix = str(DEFAULT_CHIEF_OPTIONS.photo_character_suffix or "").strip()
        elif task_type == "page":
            suffix = str(DEFAULT_CHIEF_OPTIONS.photo_scene_suffix or "").strip()
        if suffix:
            return f"{prompt}, {suffix}"
        return prompt

    def _resolve_image_runtime_defaults(self) -> Dict[str, Any]:
        hardware = detect_hardware_profile()
        models_dir = self.root_dir / "models"
        plan_key, image_base, image_refiner, image_profile, notes = resolve_image_defaults(
            "auto",
            models_dir=models_dir,
            hardware=hardware,
        )
        return {
            "plan_key": plan_key,
            "image_base": image_base or Path(DEFAULT_CHIEF_OPTIONS.sdxl_base),
            "image_refiner": image_refiner or Path(DEFAULT_CHIEF_OPTIONS.sdxl_refiner),
            "image_profile": image_profile,
            "notes": notes,
        }

    def _build_image_item(
        self,
        *,
        story_root: Path,
        resource_dir: Path,
        image_root: Path,
        task_type: str,
        task_name: str,
        prompt_file: Path,
        base_prompt: str,
        seed: int,
        width: int,
        height: int,
        runtime_defaults: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        image_main_dir = image_root / "main"
        image_original_dir = image_root / "original"

        if task_type == "cover":
            filename = "book_cover.png"
        elif task_type == "character":
            filename = f"character_{task_name}.png"
        else:
            filename = f"page_{task_name}_scene.png"

        main_path = image_main_dir / filename
        original_path = image_original_dir / filename
        preview_path = self._pick_existing_image(main_path, original_path)

        try:
            resource_rel = str(resource_dir.relative_to(story_root)).replace("\\", "/")
        except Exception:
            resource_rel = str(resource_dir).replace("\\", "/")
        resource_key = "root" if resource_rel in {".", ""} else resource_rel

        task_id = f"{resource_key}::{task_type}::{task_name}"
        prompt = self._compose_prompt(base_prompt, task_type)
        defaults = runtime_defaults if isinstance(runtime_defaults, dict) else self._resolve_image_runtime_defaults()
        image_profile = defaults.get("image_profile")
        steps = int(getattr(image_profile, "steps", DEFAULT_CHIEF_OPTIONS.photo_steps))
        guidance = float(getattr(image_profile, "guidance", DEFAULT_CHIEF_OPTIONS.photo_guidance))
        skip_refiner = bool(getattr(image_profile, "skip_refiner", DEFAULT_CHIEF_OPTIONS.photo_skip_refiner))
        refiner_steps = getattr(image_profile, "refiner_steps", DEFAULT_CHIEF_OPTIONS.photo_refiner_steps)

        return {
            "task_id": task_id,
            "task_type": task_type,
            "task_name": task_name,
            "story_root": str(story_root),
            "resource_dir": str(resource_dir),
            "resource_rel": resource_key,
            "prompt_file": str(prompt_file),
            "positive_prompt": prompt,
            "negative_prompt": str(DEFAULT_CHIEF_OPTIONS.photo_negative_prompt or ""),
            "seed": int(seed),
            "width": int(width),
            "height": int(height),
            "steps": steps,
            "guidance": guidance,
            "skip_refiner": skip_refiner,
            "refiner_steps": refiner_steps,
            "base_model": str(defaults.get("image_base") or ""),
            "image_plan": str(defaults.get("plan_key") or "auto"),
            "image_path": str(preview_path),
            "output_paths": [str(original_path), str(main_path)],
            "exists": preview_path.exists(),
            "updated_at": datetime.fromtimestamp(preview_path.stat().st_mtime, tz=timezone.utc).isoformat() if preview_path.exists() else None,
        }

    def _collect_image_items_for_story(self, story_root: Path, limit: int = 200) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        runtime_defaults = self._resolve_image_runtime_defaults()
        image_profile = runtime_defaults.get("image_profile")
        page_width = int(getattr(image_profile, "width", DEFAULT_CHIEF_OPTIONS.photo_width))
        page_height = int(getattr(image_profile, "height", DEFAULT_CHIEF_OPTIONS.photo_height))
        for resource_dir in self._find_resource_dirs(story_root):
            image_root = self._resolve_image_root_for_resource(story_root, resource_dir)
            seed = load_or_create_seed(resource_dir)

            cover_prompt_file = resource_dir / "book_cover_prompt.txt"
            if cover_prompt_file.exists():
                base_prompt = load_prompt(cover_prompt_file)
                if base_prompt:
                    items.append(
                        self._build_image_item(
                            story_root=story_root,
                            resource_dir=resource_dir,
                            image_root=image_root,
                            task_type="cover",
                            task_name="cover",
                            prompt_file=cover_prompt_file,
                            base_prompt=base_prompt,
                            seed=seed,
                            width=page_width,
                            height=page_height,
                            runtime_defaults=runtime_defaults,
                        )
                    )

            for char_prompt in list_character_prompt_files(resource_dir):
                base_prompt = load_prompt(char_prompt)
                if not base_prompt:
                    continue
                char_name = char_prompt.stem.replace("character_", "")
                items.append(
                    self._build_image_item(
                        story_root=story_root,
                        resource_dir=resource_dir,
                        image_root=image_root,
                        task_type="character",
                        task_name=char_name,
                        prompt_file=char_prompt,
                        base_prompt=base_prompt,
                        seed=seed,
                        width=1024,
                        height=1024,
                        runtime_defaults=runtime_defaults,
                    )
                )

            for page_prompt in list_page_prompt_files(resource_dir):
                base_prompt = load_prompt(page_prompt)
                if not base_prompt:
                    continue
                page_number = page_number_from_prompt(page_prompt)
                items.append(
                    self._build_image_item(
                        story_root=story_root,
                        resource_dir=resource_dir,
                        image_root=image_root,
                        task_type="page",
                        task_name=str(page_number),
                        prompt_file=page_prompt,
                        base_prompt=base_prompt,
                        seed=seed,
                        width=page_width,
                        height=page_height,
                        runtime_defaults=runtime_defaults,
                    )
                )

            if len(items) >= limit:
                break

        def _sort_key(item: Dict[str, Any]) -> tuple:
            task_type = str(item.get("task_type") or "")
            order = {"cover": 0, "character": 1, "page": 2}.get(task_type, 9)
            name = str(item.get("task_name") or "")
            if task_type == "page":
                try:
                    return (order, int(name))
                except Exception:
                    return (order, 0)
            return (order, name)

        items.sort(key=_sort_key)
        return items[:limit]

    def list_image_items(self, *, story_root_hint: Optional[str], limit: int = 200) -> Dict[str, Any]:
        story_roots = self._discover_story_roots_with_images(limit=24)
        selected_root = self._resolve_story_root_path(story_root_hint)
        if selected_root is None:
            return {
                "ok": True,
                "story_roots": [str(p) for p in story_roots],
                "story_root": None,
                "items": [],
            }

        items = self._collect_image_items_for_story(selected_root, limit=limit)
        return {
            "ok": True,
            "story_roots": [str(p) for p in story_roots],
            "story_root": str(selected_root),
            "items": items,
        }

    def list_gallery_stories(self, *, limit: int = 120) -> Dict[str, Any]:
        roots = self._discover_story_roots_with_images(limit=max(limit, 24) * 2)
        rows: List[Dict[str, Any]] = []

        for story_root in roots:
            story_root_rel = self._to_root_relative_path(story_root)
            rel_parts = story_root_rel.split("/")
            category = rel_parts[1] if len(rel_parts) >= 2 else "-"
            age = rel_parts[2] if len(rel_parts) >= 3 else "-"

            info: Dict[str, Any] = {}
            for candidate in (story_root / "story.json", story_root / "story" / "story.json"):
                if not candidate.exists() or not candidate.is_file():
                    continue
                try:
                    payload = json.loads(candidate.read_text(encoding="utf-8"))
                    if isinstance(payload, dict):
                        info = payload
                        break
                except Exception:
                    continue

            cover_candidates: List[Path] = [
                story_root / "image" / "main" / "book_cover.png",
                story_root / "story" / "image" / "main" / "book_cover.png",
            ]
            for resource_dir in self._find_resource_dirs(story_root):
                image_root = self._resolve_image_root_for_resource(story_root, resource_dir)
                cover_candidates.append(image_root / "main" / "book_cover.png")

            cover_path: Optional[str] = None
            cover_mtime = 0.0
            for candidate in cover_candidates:
                if not candidate.exists() or not candidate.is_file():
                    continue
                cover_path = self._to_root_relative_path(candidate)
                try:
                    cover_mtime = float(candidate.stat().st_mtime)
                except Exception:
                    cover_mtime = 0.0
                break

            root_mtime = 0.0
            try:
                root_mtime = float(story_root.stat().st_mtime)
            except Exception:
                root_mtime = 0.0

            modified = max(root_mtime, cover_mtime)
            title = str(info.get("title") or story_root.name)
            rows.append(
                {
                    "title": title,
                    "category": category,
                    "age": age,
                    "path": story_root_rel,
                    "story_root": story_root_rel,
                    "modified": modified,
                    "cover": cover_path,
                }
            )

            if len(rows) >= limit:
                break

        rows.sort(key=lambda item: float(item.get("modified") or 0.0), reverse=True)
        return {
            "ok": True,
            "images": rows[:limit],
        }

    def _discover_story_roots_with_narration(self, limit: int = 120) -> List[Path]:
        output_root = self.root_dir / "output"
        if not output_root.exists():
            return []

        latest_by_root: Dict[str, tuple[float, Path]] = {}
        for narration_path in output_root.rglob("page_*_narration.txt"):
            try:
                rel = narration_path.relative_to(output_root)
            except Exception:
                continue
            if len(rel.parts) < 5:
                continue

            story_root = output_root / rel.parts[0] / rel.parts[1] / rel.parts[2]
            if not story_root.exists() or not story_root.is_dir():
                continue

            try:
                mtime = narration_path.stat().st_mtime
            except Exception:
                mtime = 0.0

            key = str(story_root)
            prev = latest_by_root.get(key)
            if prev is None or mtime > prev[0]:
                latest_by_root[key] = (mtime, story_root)

        rows = sorted(latest_by_root.values(), key=lambda item: item[0], reverse=True)
        return [row[1] for row in rows[:limit]]

    def list_translatable_stories(self, *, limit: int = 120) -> Dict[str, Any]:
        roots = self._discover_story_roots_with_narration(limit=max(limit, 20) * 2)
        items: List[Dict[str, Any]] = []
        for root in roots:
            languages = detect_story_languages(root)
            if not languages:
                continue

            try:
                updated_at = datetime.fromtimestamp(root.stat().st_mtime, tz=timezone.utc).isoformat()
            except Exception:
                updated_at = None

            try:
                rel_under_output = str(root.relative_to(self.root_dir / "output")).replace("\\", "/")
            except Exception:
                rel_under_output = str(root).replace("\\", "/")

            items.append(
                {
                    "story_root": self._to_root_relative_path(root),
                    "story_name": root.name,
                    "story_rel": rel_under_output,
                    "languages": languages,
                    "updated_at": updated_at,
                }
            )

            if len(items) >= limit:
                break

        return {
            "ok": True,
            "items": items,
        }

    def _build_image_backend_config(self, overrides: Dict[str, Any]) -> Any:
        runtime_defaults = self._resolve_image_runtime_defaults()
        image_profile = runtime_defaults.get("image_profile")
        default_steps = int(getattr(image_profile, "steps", DEFAULT_CHIEF_OPTIONS.photo_steps))
        default_guidance = float(getattr(image_profile, "guidance", DEFAULT_CHIEF_OPTIONS.photo_guidance))
        default_skip_refiner = bool(getattr(image_profile, "skip_refiner", DEFAULT_CHIEF_OPTIONS.photo_skip_refiner))
        default_refiner_steps = getattr(image_profile, "refiner_steps", DEFAULT_CHIEF_OPTIONS.photo_refiner_steps)
        default_width = int(getattr(image_profile, "width", DEFAULT_CHIEF_OPTIONS.photo_width))
        default_height = int(getattr(image_profile, "height", DEFAULT_CHIEF_OPTIONS.photo_height))
        default_base = runtime_defaults.get("image_base") or Path(DEFAULT_CHIEF_OPTIONS.sdxl_base)
        default_refiner = runtime_defaults.get("image_refiner") or Path(DEFAULT_CHIEF_OPTIONS.sdxl_refiner)
        override_base = _safe_text(overrides.get("base_model_dir"), default="", max_length=1200)
        base_model_dir = Path(override_base) if override_base else Path(default_base)
        provider = _safe_text(overrides.get("provider"), default=classify_image_provider(base_model_dir), max_length=64).lower()
        model_family = _safe_text(overrides.get("model_family"), default=classify_image_model(base_model_dir), max_length=64).lower()
        override_refiner = _safe_text(overrides.get("refiner_model_dir"), default="", max_length=1200)
        refiner_model_dir = Path(override_refiner) if override_refiner else Path(default_refiner)
        if not str(model_family).startswith("sdxl"):
            refiner_model_dir = Path("")

        steps = _safe_int(overrides.get("steps"), default_steps, min_value=1, max_value=150)
        guidance = _safe_float(overrides.get("guidance"), default_guidance)
        skip_refiner = _safe_bool(overrides.get("skip_refiner"), default_skip_refiner)
        refiner_steps_raw = overrides.get("refiner_steps")
        refiner_steps = None
        if refiner_steps_raw not in {None, ""}:
            refiner_steps = _safe_int(refiner_steps_raw, max(1, steps // 4), min_value=1, max_value=80)
        elif default_refiner_steps not in {None, ""}:
            refiner_steps = _safe_int(default_refiner_steps, max(1, steps // 4), min_value=1, max_value=80)

        return SimpleNamespace(
            provider=provider,
            model_family=model_family,
            base_model_dir=base_model_dir,
            refiner_model_dir=refiner_model_dir,
            device=str(DEFAULT_CHIEF_OPTIONS.photo_device),
            dtype=parse_dtype(str(DEFAULT_CHIEF_OPTIONS.photo_dtype)),
            quantization_mode=_safe_text(overrides.get("quantization_mode"), default=str(getattr(DEFAULT_CHIEF_OPTIONS, "photo_quantization", "fp8")), max_length=32).lower(),
            output_mode=_safe_text(overrides.get("output_mode"), default=str(getattr(DEFAULT_CHIEF_OPTIONS, "photo_output_mode", "dual")), max_length=32).lower(),
            asset_granularity=_safe_text(overrides.get("asset_granularity"), default=str(getattr(DEFAULT_CHIEF_OPTIONS, "photo_asset_granularity", "page_bundle")), max_length=64).lower(),
            bg_removal_policy=_safe_text(overrides.get("bg_removal_policy"), default=str(getattr(DEFAULT_CHIEF_OPTIONS, "photo_bg_removal_policy", "characters_props")), max_length=64).lower(),
            reuse_strategy=_safe_text(overrides.get("reuse_strategy"), default=str(getattr(DEFAULT_CHIEF_OPTIONS, "photo_reuse_strategy", "page_bundle_first")), max_length=64).lower(),
            width=_safe_int(overrides.get("width"), default_width, min_value=256, max_value=2048),
            height=_safe_int(overrides.get("height"), default_height, min_value=256, max_value=2048),
            steps=steps,
            guidance=guidance,
            refiner_steps=refiner_steps,
            skip_refiner=skip_refiner,
            negative_prompt=_safe_text(overrides.get("negative_prompt"), default=str(DEFAULT_CHIEF_OPTIONS.photo_negative_prompt), max_length=4000),
            low_vram=_safe_bool(overrides.get("low_vram"), True),
        )

    @staticmethod
    def _image_backend_key(cfg: Any) -> Tuple[Any, ...]:
        return (
            str(getattr(cfg, "provider", "")),
            str(getattr(cfg, "model_family", "")),
            str(getattr(cfg, "base_model_dir", "")),
            str(getattr(cfg, "refiner_model_dir", "")),
            str(getattr(cfg, "device", "")),
            str(getattr(cfg, "dtype", "")),
            str(getattr(cfg, "quantization_mode", "")),
            str(getattr(cfg, "output_mode", "")),
            str(getattr(cfg, "asset_granularity", "")),
            str(getattr(cfg, "bg_removal_policy", "")),
            str(getattr(cfg, "reuse_strategy", "")),
            bool(getattr(cfg, "skip_refiner", False)),
            bool(getattr(cfg, "low_vram", False)),
        )

    def _regenerate_single_image_item(
        self,
        item: Dict[str, Any],
        overrides: Dict[str, Any],
        *,
        backend: Optional[Any] = None,
    ) -> Dict[str, Any]:
        story_root = self._safe_path_under_root(str(item.get("story_root") or ""))
        if story_root is None or not story_root.exists():
            return {"ok": False, "error": "Invalid story_root", "task_id": item.get("task_id")}

        resource_dir = self._safe_path_under_root(str(item.get("resource_dir") or ""))
        if resource_dir is None or not resource_dir.exists():
            return {"ok": False, "error": "Invalid resource_dir", "task_id": item.get("task_id")}

        prompt = _safe_text(overrides.get("positive_prompt"), default="", max_length=12000)
        if not prompt:
            prompt = _safe_text(item.get("positive_prompt"), default="", max_length=12000)
        if not prompt:
            prompt_file = self._safe_path_under_root(str(item.get("prompt_file") or ""))
            if prompt_file and prompt_file.exists():
                prompt = load_prompt(prompt_file)
                prompt = self._compose_prompt(prompt, str(item.get("task_type") or "page"))
        if not prompt:
            return {"ok": False, "error": "Prompt is empty", "task_id": item.get("task_id")}

        seed_raw = overrides.get("seed", item.get("seed"))
        if seed_raw in {None, ""}:
            seed = int(load_or_create_seed(resource_dir))
        else:
            seed = _safe_int(seed_raw, int(load_or_create_seed(resource_dir)), min_value=0)

        output_paths_raw = item.get("output_paths") if isinstance(item.get("output_paths"), list) else []
        output_paths: List[Path] = []
        for raw in output_paths_raw:
            path = self._safe_path_under_root(str(raw))
            if path is None:
                continue
            output_paths.append(path)
        if not output_paths:
            return {"ok": False, "error": "No valid output path", "task_id": item.get("task_id")}

        render_cfg = self._build_image_backend_config(
            {
                "width": overrides.get("width", item.get("width")),
                "height": overrides.get("height", item.get("height")),
                "steps": overrides.get("steps", item.get("steps")),
                "guidance": overrides.get("guidance", item.get("guidance")),
                "negative_prompt": overrides.get("negative_prompt", item.get("negative_prompt")),
                "skip_refiner": overrides.get("skip_refiner", item.get("skip_refiner")),
                "refiner_steps": overrides.get("refiner_steps", item.get("refiner_steps")),
                "low_vram": overrides.get("low_vram", True),
            }
        )

        owns_backend = backend is None
        local_backend = backend

        try:
            if local_backend is None:
                from backends.image import build_image_backend
                local_backend = build_image_backend(render_cfg)

            image = local_backend.generate_image(
                prompt=prompt,
                seed=int(seed),
                width=int(render_cfg.width),
                height=int(render_cfg.height),
                num_inference_steps=int(render_cfg.steps),
                guidance_scale=float(render_cfg.guidance),
                negative_prompt=str(render_cfg.negative_prompt or ""),
                skip_refiner=bool(render_cfg.skip_refiner),
                refiner_steps=render_cfg.refiner_steps,
            )
            for out_path in output_paths:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                image.save(out_path)

            selected = output_paths[-1]
            self._append_log_line(
                f"[image] Regenerated {item.get('task_id')} -> {selected}",
                run_id=self.current_run_id,
                level="info",
            )
            return {
                "ok": True,
                "task_id": item.get("task_id"),
                "image_path": str(selected),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "task_id": item.get("task_id"),
                "error": f"Image regeneration failed: {exc}",
            }
        finally:
            try:
                if owns_backend and local_backend is not None:
                    local_backend.cleanup()
            except Exception:
                pass

    def regenerate_images(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        overrides = payload.get("overrides") if isinstance(payload.get("overrides"), dict) else {}
        if not items:
            return {"ok": False, "error": "items is required"}

        results: List[Dict[str, Any]] = []
        backend = None
        backend_key: Optional[Tuple[Any, ...]] = None
        with self.general_lock:
            self._cleanup_cached_models(force=False)
            try:
                from backends.image import build_image_backend

                base_cfg = self._build_image_backend_config(
                    {
                        "width": overrides.get("width"),
                        "height": overrides.get("height"),
                        "steps": overrides.get("steps"),
                        "guidance": overrides.get("guidance"),
                        "negative_prompt": overrides.get("negative_prompt"),
                        "skip_refiner": overrides.get("skip_refiner"),
                        "refiner_steps": overrides.get("refiner_steps"),
                        "low_vram": overrides.get("low_vram", True),
                    }
                )
                backend_key = self._image_backend_key(base_cfg)
                backend = self._acquire_cached_backend("image", backend_key, lambda: build_image_backend(base_cfg))

                for item in items:
                    if not isinstance(item, dict):
                        continue
                    item_overrides = overrides if len(items) == 1 else {}
                    results.append(self._regenerate_single_image_item(item, item_overrides, backend=backend))
            finally:
                if backend_key is not None:
                    self._release_cached_backend("image", backend_key)

        if not results:
            return {"ok": False, "error": "No valid image items"}

        ok = all(bool(r.get("ok")) for r in results)
        return {
            "ok": ok,
            "results": results,
        }

    @staticmethod
    def _bool_flag(value: bool, true_flag: str, false_flag: str) -> str:
        return true_flag if value else false_flag

    def _build_command(self, payload: Dict[str, Any]) -> List[str]:
        cmd = [
            sys.executable,
            str(self.root_dir / "chief.py"),
            "--count",
            str(payload["count"]),
            "--status-file",
            str(self.status_file),
            "--max-retries",
            str(payload["max_retries"]),
            "--pages",
            str(payload["pages"]),
            "--story-input-mode",
            str(payload.get("story_input_mode") or "preset"),
            "--model-plan",
            str(payload.get("model_plan") or "auto"),
            "--pre-eval-policy",
            str(payload.get("pre_eval_policy") or "stop"),
            "--pre-eval-threshold",
            str(payload.get("pre_eval_threshold", 65.0)),
        ]

        if payload.get("age"):
            cmd.extend(["--age", str(payload["age"])])
        if payload.get("category"):
            cmd.extend(["--category", str(payload["category"])])
        if payload.get("theme"):
            cmd.extend(["--theme", str(payload["theme"])])
        if payload.get("subcategory"):
            cmd.extend(["--subcategory", str(payload["subcategory"])])
        if payload.get("seed") is not None:
            cmd.extend(["--seed", str(payload["seed"])])
        if payload.get("story_input_mode") == "custom":
            if payload.get("story_prompt"):
                cmd.extend(["--story-prompt", str(payload["story_prompt"])])
            if payload.get("story_materials"):
                cmd.extend(["--story-materials", str(payload["story_materials"])])
        if payload.get("speaker_wav"):
            cmd.extend(["--speaker-wav", str(payload["speaker_wav"])])
        if payload.get("speaker_dir"):
            cmd.extend(["--speaker-dir", str(payload["speaker_dir"])])

        cmd.append(self._bool_flag(bool(payload.get("photo_enabled")), "--photo", "--no-photo"))
        cmd.append(self._bool_flag(bool(payload.get("translation_enabled")), "--translation", "--no-translation"))
        cmd.append(self._bool_flag(bool(payload.get("voice_enabled")), "--voice", "--no-voice"))
        cmd.append(self._bool_flag(bool(payload.get("verify_enabled")), "--verify", "--no-verify"))
        cmd.append(self._bool_flag(bool(payload.get("low_vram")), "--low-vram", "--no-low-vram"))
        cmd.append(self._bool_flag(bool(payload.get("strict_translation")), "--strict-translation", "--no-strict-translation"))
        cmd.append(self._bool_flag(bool(payload.get("strict_voice")), "--strict-voice", "--no-strict-voice"))
        return cmd

    def _is_running(self) -> bool:
        process = self.process
        if process is None:
            return False
        try:
            if process.poll() is not None:
                return False
        except Exception:
            return False
        return self._pid_alive(getattr(process, "pid", 0))

    def _read_runner_status(self) -> Dict[str, Any]:
        if not self.status_file.exists():
            return {}
        try:
            raw = json.loads(self.status_file.read_text(encoding="utf-8"))
            return raw if isinstance(raw, dict) else {}
        except Exception:
            return {}

    def _runner_payload_from_history_item(self, history_item: Dict[str, Any], *, fallback_config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        config = dict(fallback_config or {})
        if isinstance(history_item.get("config"), dict):
            config = dict(history_item.get("config") or {})

        runner = _default_runner_payload(config)
        runner["state"] = str(history_item.get("state") or "stopped")
        runner["total_books"] = _safe_int(history_item.get("total_books"), _safe_int(config.get("count"), 0, min_value=0), min_value=0)
        runner["completed_books"] = _safe_int(history_item.get("completed_books"), 0, min_value=0)
        runner["success_books"] = _safe_int(history_item.get("success_books"), 0, min_value=0)
        runner["failed_books"] = _safe_int(history_item.get("failed_books"), 0, min_value=0)
        runner["current_book"] = _safe_int(history_item.get("completed_books"), 0, min_value=0)
        runner["current_attempt"] = 0
        runner["current_stage"] = str(history_item.get("current_stage") or runner["state"] or "stopped")
        runner["last_story_root"] = history_item.get("story_root")
        runner["last_error"] = history_item.get("last_error")
        runner["stage_progress"] = None
        runner["stage_detail"] = None
        runner["model_plan"] = _safe_text(config.get("model_plan"), default="auto", max_length=16)
        runner["updated_at"] = str(history_item.get("finished_at") or history_item.get("started_at") or _utc_now_iso())
        return runner

    def _clean_stale_status_locked(self) -> None:
        if self.status_file.exists():
            try:
                self.status_file.unlink()
            except Exception:
                pass

    def _recover_orphaned_active_run(self) -> None:
        with self.lock:
            active = dict(self.active_job) if isinstance(self.active_job, dict) else None
            run_id = str((active or {}).get("run_id") or self.current_run_id or "").strip()
            last_config = dict(self.last_config)

        if not active and not run_id:
            return

        external_chief = self._find_external_chief_process()
        if external_chief is not None:
            return

        runner = self._read_runner_status()
        updated_at = _parse_iso_datetime(runner.get("updated_at"))
        stale_sec: Optional[float] = None
        if updated_at is not None:
            stale_sec = max(0.0, (datetime.now(timezone.utc) - updated_at).total_seconds())

        with self.lock:
            history_item = None
            if run_id:
                for item in reversed(self.history):
                    if str(item.get("run_id") or "") == run_id:
                        history_item = dict(item)
                        break
            if isinstance(history_item, dict):
                final_state = str(history_item.get("state") or "").strip().lower()
                if final_state in {"completed", "failed", "stopped", "error"}:
                    history_exit = history_item.get("exit_code")
                    exit_code = None if history_exit in {None, ""} else _safe_int(history_exit, 0)
                    if isinstance(history_item.get("config"), dict):
                        self.last_config = dict(history_item.get("config") or {})
                    self.process = None
                    self.active_job = None
                    self.current_run_id = None
                    self.current_run_started_at = None
                    self.current_run_started_iso = None
                    self.current_exit_code = exit_code
                    self.current_status_signature = None
                    self._clean_stale_status_locked()
                    self._release_cross_process_run_lock()
                    self._append_log_line_locked(
                        "[dashboard] Reconciled stale active run from persisted history.",
                        run_id=run_id or None,
                        level="warning",
                    )
                    return

            if stale_sec is None or stale_sec < _STALE_RUN_RECOVERY_GRACE_SEC:
                return

            inferred_exit = self.current_exit_code if self.current_exit_code is not None else 15
            self.process = None
            self._append_log_line_locked(
                "[dashboard] Recovered orphaned active run: no chief process detected; marking run stopped.",
                run_id=run_id or None,
                level="warning",
            )
            self._finalize_run_locked(state="stopped", runner=runner or _default_runner_payload(last_config), exit_code=inferred_exit)
            self._clean_stale_status_locked()

    def _sort_queue_locked(self) -> None:
        self.pending_jobs.sort(key=lambda item: (item.get("priority_rank", 1), item.get("enqueued_at_ts", 0.0)))

    def _enqueue_job_locked(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now_ts = time.time()
        priority = _normalize_priority(payload.get("priority"))
        job = {
            "job_id": f"job-{uuid4().hex[:10]}",
            "run_id": f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:5]}",
            "priority": priority,
            "priority_rank": _priority_rank(priority),
            "status": "queued",
            "payload": dict(payload),
            "enqueued_at": _utc_now_iso(),
            "enqueued_at_ts": now_ts,
            "started_at": None,
            "started_at_ts": None,
        }
        self.pending_jobs.append(job)
        self._sort_queue_locked()
        self._record_run_event_locked(job["run_id"], "queued", {
            "job_id": job["job_id"],
            "priority": job["priority"],
        })
        self._append_log_line_locked(
            f"[queue] Job queued id={job['job_id']} priority={job['priority']} count={payload.get('count')}",
            run_id=job["run_id"],
            level="info",
        )
        return job

    def _start_log_reader(self, process: subprocess.Popen[str], run_id: str) -> None:
        if process.stdout is None:
            return

        def _consume() -> None:
            try:
                assert process.stdout is not None
                for raw in iter(process.stdout.readline, ""):
                    if raw == "":
                        break
                    self._append_log_line(raw, run_id=run_id)
            except Exception as exc:
                self._append_log_line(f"[dashboard] log stream error: {exc}", run_id=run_id, level="warning")
            finally:
                try:
                    if process.stdout is not None:
                        process.stdout.close()
                except Exception:
                    pass

        thread = threading.Thread(target=_consume, name=f"dashboard-log-reader-{run_id}", daemon=True)
        thread.start()
        self.reader_thread = thread

    def _finalize_run_locked(
        self,
        *,
        state: str,
        runner: Optional[Dict[str, Any]],
        exit_code: Optional[int],
    ) -> None:
        active = self.active_job or {}
        run_id = active.get("run_id") or self.current_run_id
        if not run_id:
            return

        started_ts = self.current_run_started_at or active.get("started_at_ts") or time.time()
        now_ts = time.time()
        duration_sec = round(max(0.0, now_ts - started_ts), 3)

        enqueued_ts = active.get("enqueued_at_ts")
        queue_delay = None
        if isinstance(enqueued_ts, (int, float)):
            queue_delay = round(max(0.0, started_ts - enqueued_ts), 3)

        final_state = (state or "").strip().lower() or "failed"
        if final_state == "running":
            final_state = "stopped"

        payload = active.get("payload") if isinstance(active.get("payload"), dict) else {}
        effective_runner = runner if isinstance(runner, dict) else _default_runner_payload(payload)

        total_books = _safe_int(effective_runner.get("total_books"), _safe_int(payload.get("count"), 0, min_value=0), min_value=0)
        success_books = _safe_int(effective_runner.get("success_books"), 0, min_value=0)
        failed_books = _safe_int(effective_runner.get("failed_books"), 0, min_value=0)
        completed_books = _safe_int(effective_runner.get("completed_books"), success_books + failed_books, min_value=0)

        story_root_value: Optional[str] = None
        story_root_path: Optional[Path] = None
        for raw_story_root in (
            effective_runner.get("last_story_root"),
            effective_runner.get("story_root"),
            payload.get("story_root"),
        ):
            normalized_value, normalized_path = self._normalize_story_root_value(raw_story_root)
            if normalized_value and story_root_value is None:
                story_root_value = normalized_value
            if normalized_path is not None:
                story_root_path = normalized_path
                story_root_value = self._to_root_relative_path(normalized_path)
                break

        evaluation_ready = False
        if story_root_path is not None:
            evaluation_ready = (story_root_path / "assessment_report.json").exists()

        history_item = {
            "run_id": run_id,
            "job_id": active.get("job_id"),
            "priority": active.get("priority"),
            "started_at": self.current_run_started_iso or active.get("started_at") or _utc_now_iso(),
            "finished_at": _utc_now_iso(),
            "duration_sec": duration_sec,
            "queued_delay_sec": queue_delay,
            "state": final_state,
            "exit_code": exit_code,
            "total_books": total_books,
            "completed_books": completed_books,
            "success_books": success_books,
            "failed_books": failed_books,
            "story_root": story_root_value,
            "evaluation_ready": evaluation_ready,
            "current_stage": effective_runner.get("current_stage"),
            "last_error": effective_runner.get("last_error") or self.last_error,
            "config": dict(payload),
        }

        self.history.append(history_item)
        self.history = self.history[-_HISTORY_LIMIT:]
        self._save_history()

        self._record_run_event_locked(run_id, "finished", {
            "state": final_state,
            "exit_code": exit_code,
            "duration_sec": duration_sec,
            "success_books": success_books,
            "failed_books": failed_books,
        })

        if final_state in {"failed", "error"}:
            self._push_alert_locked(
                level="critical",
                title="Run Failed",
                message=f"Run {run_id} ended with state={final_state}, exit={exit_code}",
                run_id=run_id,
                code="run_failed",
            )
        elif final_state == "stopped":
            self._push_alert_locked(
                level="warning",
                title="Run Stopped",
                message=f"Run {run_id} was stopped before completion.",
                run_id=run_id,
                code="run_stopped",
            )

        self.active_job = None
        self.current_run_id = None
        self.current_run_started_at = None
        self.current_run_started_iso = None
        self.current_exit_code = exit_code
        self.current_status_signature = None
        self._release_cross_process_run_lock()

    def _start_next_job_locked(self) -> Dict[str, Any]:
        if self._is_running():
            return {"ok": True, "started": False, "reason": "already_running"}
        if self.module_active_job and str(self.module_active_job.get("status") or "") in {"running", "stopping"}:
            return {"ok": True, "started": False, "reason": "module_job_running"}
        if not self.pending_jobs:
            return {"ok": True, "started": False, "reason": "queue_empty"}

        first_pending = self.pending_jobs[0] if self.pending_jobs else {}
        pending_run_id = str(first_pending.get("run_id") or "")

        external_chief = self._find_external_chief_process()
        if external_chief is not None:
            external_pid = _safe_int(external_chief.get("pid"), 0, min_value=0)
            self._append_log_line_locked(
                f"[queue] Start deferred: external chief process detected (pid={external_pid}).",
                run_id=pending_run_id,
                level="warning",
            )
            return {
                "ok": True,
                "started": False,
                "reason": "external_chief_running",
                "external_pid": external_pid,
            }

        locked, lock_reason = self._acquire_cross_process_run_lock(pending_run_id)
        if not locked:
            self._append_log_line_locked(
                f"[queue] Start deferred: {lock_reason}",
                run_id=pending_run_id,
                level="warning",
            )
            return {
                "ok": True,
                "started": False,
                "reason": "external_run_lock",
                "lock_reason": lock_reason,
            }

        # Ensure chief.py gets clean VRAM and no stale dashboard backend instances.
        with self.general_lock:
            self._cleanup_cached_models(force=True)

        job = self.pending_jobs.pop(0)
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}
        run_id = str(job.get("run_id"))

        now_ts = time.time()
        job["status"] = "starting"
        job["started_at"] = _utc_now_iso()
        job["started_at_ts"] = now_ts

        self.active_job = job
        self.current_run_id = run_id
        self.current_run_started_at = now_ts
        self.current_run_started_iso = str(job["started_at"])
        self.current_exit_code = None
        self.current_status_signature = None
        self.last_error = None

        self._clean_stale_status_locked()
        cmd = self._build_command(payload)

        try:
            env = _build_subprocess_env()
            process = subprocess.Popen(
                cmd,
                cwd=str(self.root_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=env,
                **_popen_kwargs(),
            )
        except Exception as exc:
            self._release_cross_process_run_lock()
            self.last_error = str(exc)
            self._append_log_line_locked(f"[dashboard] Failed to start run process: {exc}", run_id=run_id, level="error")
            self._record_run_event_locked(run_id, "failed_to_start", {"error": str(exc)})
            self._push_alert_locked(
                level="critical",
                title="Run Start Failed",
                message=f"Run {run_id} failed to start: {exc}",
                run_id=run_id,
                code="start_failed",
            )
            self._finalize_run_locked(
                state="failed",
                runner={
                    "state": "failed",
                    "total_books": payload.get("count", 0),
                    "completed_books": 0,
                    "success_books": 0,
                    "failed_books": payload.get("count", 0),
                    "current_stage": "start_failed",
                    "last_error": str(exc),
                },
                exit_code=-1,
            )
            if self.pending_jobs:
                return self._start_next_job_locked()
            return {"ok": False, "started": False, "error": f"Failed to start process: {exc}"}

        self.process = process
        self._update_cross_process_run_lock(process.pid)
        job["status"] = "running"

        self._record_run_event_locked(run_id, "started", {
            "job_id": job.get("job_id"),
            "priority": job.get("priority"),
            "pid": process.pid,
        })
        self._append_log_line_locked("[dashboard] Run started.", run_id=run_id)
        self._append_log_line_locked("[dashboard] Command: " + " ".join(cmd), run_id=run_id)

        self._start_log_reader(process, run_id)
        return {
            "ok": True,
            "started": True,
            "run_id": run_id,
            "job_id": job.get("job_id"),
            "pid": process.pid,
            "cmd": cmd,
            "queue_depth": len(self.pending_jobs),
            "log_next_seq": self.log_seq + 1,
        }

    def _sync_process_exit(self) -> None:
        with self.lock:
            process = self.process
            active = self.active_job
        if not active:
            return
        if not process:
            self._recover_orphaned_active_run()
            return

        exit_code = process.poll()
        if exit_code is None and self._pid_alive(getattr(process, "pid", 0)):
            return
        if exit_code is None:
            exit_code = self.current_exit_code if self.current_exit_code is not None else 15

        run_id = str(active.get("run_id") or "")
        runner = self._read_runner_status()
        runner_state = str(runner.get("state") or "").lower()
        if runner_state not in {"completed", "failed", "stopped", "error"}:
            runner_state = "completed" if exit_code == 0 else "failed"

        with self.lock:
            if self.process is process:
                self.process = None
            self.current_exit_code = exit_code
            if exit_code != 0 and not self.last_error:
                self.last_error = f"Chief exited with code {exit_code}"

            self._append_log_line_locked(
                f"[dashboard] Chief process exited (code={exit_code}).",
                run_id=run_id,
                level="warning" if exit_code != 0 else "info",
            )
            self._finalize_run_locked(state=runner_state, runner=runner, exit_code=exit_code)
            next_info = self._start_next_job_locked()
            if next_info.get("started"):
                self._append_log_line_locked(
                    f"[queue] Auto-started next job run_id={next_info.get('run_id')}",
                    run_id=next_info.get("run_id"),
                    level="info",
                )

    def start_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        with self.lock:
            if len(self.pending_jobs) >= _QUEUE_LIMIT:
                return {"ok": False, "error": f"Queue limit reached ({_QUEUE_LIMIT})."}

            self.last_config = dict(sanitized)
            job = self._enqueue_job_locked(sanitized)
            queue_index = next((idx for idx, item in enumerate(self.pending_jobs) if item.get("job_id") == job.get("job_id")), 0)

            if len(self.pending_jobs) >= 4:
                self._push_alert_locked(
                    level="warning",
                    title="Queue Pressure",
                    message=f"Queue depth reached {len(self.pending_jobs)} jobs.",
                    run_id=None,
                    code="queue_pressure",
                )

            start_info = {"ok": True, "started": False}
            if not self._is_running() and self.active_job is None:
                start_info = self._start_next_job_locked()

            response = {
                "ok": True,
                "queued": not start_info.get("started"),
                "queue_position": queue_index + 1,
                "queue_depth": len(self.pending_jobs),
                "job": _job_public_view(job),
                "started": bool(start_info.get("started")),
                "run_id": start_info.get("run_id"),
                "job_id": start_info.get("job_id"),
                "pid": start_info.get("pid"),
                "log_next_seq": start_info.get("log_next_seq", self.log_seq + 1),
            }
            return response

    def stop_run(self) -> Dict[str, Any]:
        with self.lock:
            process = self.process
            active = self.active_job

        if not process or process.poll() is not None or not active:
            return {"ok": True, "message": "No running process.", "started_next": False}

        exit_code: Optional[int] = None
        try:
            exit_code = _terminate_subprocess_tree(process, graceful_timeout=8.0, force_timeout=3.0)
        except Exception as exc:
            return {"ok": False, "error": f"Failed to stop process: {exc}"}

        runner = self._read_runner_status()
        runner = dict(runner) if isinstance(runner, dict) else _default_runner_payload(active.get("payload") if isinstance(active.get("payload"), dict) else {})
        runner["state"] = "stopped"
        runner["current_stage"] = "stopped"

        with self.lock:
            if self.process is process:
                self.process = None
            self.current_exit_code = exit_code
            self._append_log_line_locked("[dashboard] Active run stopped by user.", run_id=str(active.get("run_id")), level="warning")
            self._finalize_run_locked(state="stopped", runner=runner, exit_code=exit_code)
            next_info = self._start_next_job_locked()

        return {
            "ok": True,
            "message": "Run stopped.",
            "started_next": bool(next_info.get("started")),
            "next_run_id": next_info.get("run_id"),
        }

    def reprioritize_job(self, job_id: str, priority: str) -> Dict[str, Any]:
        normalized = _normalize_priority(priority)
        with self.lock:
            for item in self.pending_jobs:
                if str(item.get("job_id")) != str(job_id):
                    continue
                item["priority"] = normalized
                item["priority_rank"] = _priority_rank(normalized)
                self._sort_queue_locked()
                self._record_run_event_locked(str(item.get("run_id")), "reprioritized", {"priority": normalized})
                return {"ok": True, "job": _job_public_view(item)}
        return {"ok": False, "error": f"Job not found: {job_id}"}

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        with self.lock:
            for idx, item in enumerate(self.pending_jobs):
                if str(item.get("job_id")) != str(job_id):
                    continue
                removed = self.pending_jobs.pop(idx)
                self._record_run_event_locked(str(removed.get("run_id")), "canceled", {})
                self._append_log_line_locked("[queue] Job canceled by operator.", run_id=str(removed.get("run_id")), level="warning")
                return {"ok": True, "job": _job_public_view(removed)}
        return {"ok": False, "error": f"Job not found: {job_id}"}

    def get_logs(self, *, since: int = 0, limit: int = 200, run_id: Optional[str] = None) -> Dict[str, Any]:
        since = _safe_int(since, 0, min_value=0)
        limit = _safe_int(limit, 200, min_value=1, max_value=800)

        with self.lock:
            if run_id:
                source = list(self.run_logs.get(run_id, []))
            else:
                source = list(self.log_lines)
            next_seq = self.log_seq + 1

        filtered = [entry for entry in source if _safe_int(entry.get("seq"), 0, min_value=0) > since]
        if len(filtered) > limit:
            filtered = filtered[-limit:]

        return {
            "ok": True,
            "lines": filtered,
            "next_seq": next_seq,
        }

    def get_history(self, *, limit: int = 20) -> Dict[str, Any]:
        self._sync_process_exit()
        limit = _safe_int(limit, 20, min_value=1, max_value=200)
        with self.lock:
            items = list(reversed(self.history[-limit:]))
            total = len(self.history)
        return {
            "ok": True,
            "total": total,
            "items": items,
        }

    def clear_overview_view(self) -> Dict[str, Any]:
        self._sync_process_exit()
        with self.lock:
            if self._is_running() or self.active_job is not None:
                return {"ok": False, "error": "Cannot clear overview while a run is active."}
            if self.pending_jobs:
                return {"ok": False, "error": "Cannot clear overview while queue has pending jobs."}

            removed_live_lines = len(self.log_lines)

            self.log_lines.clear()
            self.log_seq = 0
            self.current_run_id = None
            self.current_run_started_at = None
            self.current_run_started_iso = None
            self.current_exit_code = None
            self.current_status_signature = None
            self.last_error = None
            self.last_config = {}
            self._clean_stale_status_locked()

        return {
            "ok": True,
            "removed_live_lines": removed_live_lines,
        }

    def clear_run_history(self) -> Dict[str, Any]:
        self._sync_process_exit()
        with self.lock:
            if self._is_running() or self.active_job is not None:
                return {"ok": False, "error": "Cannot clear history while a run is active."}
            if self.pending_jobs:
                return {"ok": False, "error": "Cannot clear history while queue has pending jobs."}

            removed_runs = len(self.history)
            removed_log_groups = len(self.run_logs)
            removed_event_groups = len(self.run_events)
            removed_live_lines = len(self.log_lines)

            removed_alerts = 0
            kept_alerts: List[Dict[str, Any]] = []
            for item in self.alerts:
                run_ref = str(item.get("run_id") or "").strip() if isinstance(item, dict) else ""
                if run_ref:
                    removed_alerts += 1
                    continue
                kept_alerts.append(item)

            if removed_alerts:
                self.alerts = kept_alerts
                self._save_alerts()
            if self.suppressed_live_alert_ids:
                self.suppressed_live_alert_ids = {}
                self._save_alert_state()

            self.history = []
            self._save_history()
            self.run_logs = {}
            self.run_events = {}
            self.log_lines.clear()
            self.log_seq = 0
            self.current_run_id = None
            self.current_run_started_at = None
            self.current_run_started_iso = None
            self.current_exit_code = None
            self.current_status_signature = None
            self.last_error = None
            self._clean_stale_status_locked()

        return {
            "ok": True,
            "removed_runs": removed_runs,
            "removed_log_groups": removed_log_groups,
            "removed_event_groups": removed_event_groups,
            "removed_live_lines": removed_live_lines,
            "removed_alerts": removed_alerts,
        }

    def get_queue(self) -> Dict[str, Any]:
        self._sync_process_exit()
        with self.lock:
            active = _job_public_view(self.active_job) if self.active_job else None
            pending = [_job_public_view(item) for item in self.pending_jobs]
        return {
            "ok": True,
            "active_job": active,
            "pending_jobs": pending,
            "queue_depth": len(pending),
        }

    def acknowledge_alert(self, alert_id: str) -> Dict[str, Any]:
        with self.lock:
            for alert in self.alerts:
                if str(alert.get("alert_id")) != str(alert_id):
                    continue
                alert["acknowledged"] = True
                alert["acknowledged_at"] = _utc_now_iso()
                self._save_alerts()
                return {"ok": True}
            live_alert_id = str(alert_id or "").strip()
            if live_alert_id.startswith("derived-"):
                self.suppressed_live_alert_ids[live_alert_id] = _utc_now_iso()
                self._save_alert_state()
                return {"ok": True, "suppressed": True}
        return {"ok": False, "error": f"Alert not found: {alert_id}"}

    def _recent_failure_ratio_locked(self, window: int = 10) -> float:
        if not self.history:
            return 0.0
        items = self.history[-window:]
        if not items:
            return 0.0
        failed = sum(1 for item in items if str(item.get("state") or "").lower() in {"failed", "error", "stopped"})
        return failed / max(1, len(items))

    def get_alerts(self, *, limit: int = 30, include_ack: bool = False) -> Dict[str, Any]:
        self._sync_process_exit()
        limit = _safe_int(limit, 30, min_value=1, max_value=200)

        with self.lock:
            base_items = [dict(item) for item in self.alerts]
            queue_depth = len(self.pending_jobs)
            running = self._is_running()
            failure_ratio = self._recent_failure_ratio_locked(window=12)
            suppressed_live_alert_ids = dict(self.suppressed_live_alert_ids)

        derived: List[Dict[str, Any]] = []
        if queue_depth >= 4:
            derived.append({
                "alert_id": "derived-queue-pressure",
                "ts": _utc_now_iso(),
                "level": "warning",
                "title": "Queue Pressure",
                "message": f"Queue depth is {queue_depth}. Consider priority tuning.",
                "run_id": None,
                "code": "queue_pressure_live",
                "acknowledged": False,
                "derived": True,
            })
        if failure_ratio >= 0.4:
            derived.append({
                "alert_id": "derived-failure-ratio",
                "ts": _utc_now_iso(),
                "level": "warning",
                "title": "Failure Ratio Elevated",
                "message": f"Recent failure ratio is {round(failure_ratio * 100, 1)}%.",
                "run_id": None,
                "code": "failure_ratio_live",
                "acknowledged": False,
                "derived": True,
            })
        if not running and queue_depth > 0:
            derived.append({
                "alert_id": "derived-queue-waiting",
                "ts": _utc_now_iso(),
                "level": "warning",
                "title": "Queue Waiting",
                "message": "Jobs are queued while no active run is detected.",
                "run_id": None,
                "code": "queue_waiting_live",
                "acknowledged": False,
                "derived": True,
            })

        active_derived_ids = {str(item.get("alert_id") or "") for item in derived}
        if suppressed_live_alert_ids:
            stale_suppressed = [key for key in suppressed_live_alert_ids if key not in active_derived_ids]
            if stale_suppressed:
                with self.lock:
                    changed = False
                    for key in stale_suppressed:
                        if key in self.suppressed_live_alert_ids:
                            self.suppressed_live_alert_ids.pop(key, None)
                            changed = True
                    if changed:
                        self._save_alert_state()
                    suppressed_live_alert_ids = dict(self.suppressed_live_alert_ids)

        all_items = base_items + derived
        all_items.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)
        if not include_ack:
            all_items = [
                item
                for item in all_items
                if (not item.get("acknowledged")) and (str(item.get("alert_id") or "") not in suppressed_live_alert_ids)
            ]
        return {
            "ok": True,
            "items": all_items[:limit],
        }

    def get_capacity(self, *, window: int = _CAPACITY_WINDOW) -> Dict[str, Any]:
        self._sync_process_exit()
        window = _safe_int(window, _CAPACITY_WINDOW, min_value=1, max_value=300)

        with self.lock:
            rows = list(self.history[-window:])
            queue_depth = len(self.pending_jobs)
            running = self._is_running()

        durations = [
            _safe_float(item.get("duration_sec"), 0.0)
            for item in rows
            if _safe_float(item.get("duration_sec"), 0.0) > 0
        ]
        queue_delays = [
            _safe_float(item.get("queued_delay_sec"), 0.0)
            for item in rows
            if _safe_float(item.get("queued_delay_sec"), 0.0) >= 0
        ]

        total_books = sum(_safe_int(item.get("total_books"), 0, min_value=0) for item in rows)
        success_books = sum(_safe_int(item.get("success_books"), 0, min_value=0) for item in rows)
        failed_books = sum(_safe_int(item.get("failed_books"), 0, min_value=0) for item in rows)

        total_duration = sum(durations)
        avg_duration = (total_duration / len(durations)) if durations else 0.0
        avg_queue_delay = (sum(queue_delays) / len(queue_delays)) if queue_delays else 0.0

        total_book_outcomes = success_books + failed_books
        success_rate = (success_books / total_book_outcomes) if total_book_outcomes > 0 else 0.0

        gpu_hours = total_duration / 3600.0 if total_duration > 0 else 0.0
        cost_per_hour = _safe_float(os.environ.get("DASHBOARD_GPU_HOURLY_USD"), _DEFAULT_GPU_HOURLY_USD)
        gpu_cost = gpu_hours * cost_per_hour

        books_per_hour = (total_books / gpu_hours) if gpu_hours > 0 else 0.0

        trend = []
        for item in rows[-12:]:
            trend.append({
                "run_id": item.get("run_id"),
                "state": item.get("state"),
                "duration_sec": item.get("duration_sec"),
                "total_books": item.get("total_books"),
                "success_books": item.get("success_books"),
            })

        return {
            "ok": True,
            "window_runs": len(rows),
            "queue_depth": queue_depth,
            "running": running,
            "total_books": total_books,
            "success_books": success_books,
            "failed_books": failed_books,
            "success_rate_pct": round(success_rate * 100.0, 2),
            "avg_duration_sec": round(avg_duration, 3),
            "avg_queue_delay_sec": round(avg_queue_delay, 3),
            "books_per_hour": round(books_per_hour, 3),
            "gpu_hours": round(gpu_hours, 4),
            "gpu_cost_usd": round(gpu_cost, 4),
            "cost_per_gpu_hour_usd": round(cost_per_hour, 4),
            "trend": trend,
        }

    def save_config_version(self, payload: Dict[str, Any], *, name: Optional[str], note: Optional[str]) -> Dict[str, Any]:
        sanitized = self._sanitize_payload(payload)
        with self.lock:
            version = {
                "version_id": f"cfg-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{uuid4().hex[:5]}",
                "name": name or f"config-{len(self.config_versions) + 1}",
                "note": note or "",
                "created_at": _utc_now_iso(),
                "usage_count": 0,
                "last_used_at": None,
                "config": sanitized,
            }
            self.config_versions.append(version)
            self.config_versions = self.config_versions[-_CONFIG_LIMIT:]
            self._save_config_versions()
            return {"ok": True, "version": version}

    def list_config_versions(self, *, limit: int = 20) -> Dict[str, Any]:
        limit = _safe_int(limit, 20, min_value=1, max_value=200)
        with self.lock:
            rows = list(reversed(self.config_versions[-limit:]))
        return {"ok": True, "items": rows}

    def apply_config_version(self, version_id: str) -> Dict[str, Any]:
        with self.lock:
            for item in self.config_versions:
                if str(item.get("version_id")) != str(version_id):
                    continue
                item["usage_count"] = _safe_int(item.get("usage_count"), 0, min_value=0) + 1
                item["last_used_at"] = _utc_now_iso()
                self._save_config_versions()
                cfg = item.get("config") if isinstance(item.get("config"), dict) else {}
                return {"ok": True, "config": cfg, "version": item}
        return {"ok": False, "error": f"Config version not found: {version_id}"}

    def get_run_detail(
        self,
        run_id: str,
        *,
        log_limit: int = 300,
        event_limit: int = 200,
        book: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._sync_process_exit()
        log_limit = _safe_int(log_limit, 300, min_value=1, max_value=1200)
        event_limit = _safe_int(event_limit, 200, min_value=1, max_value=1200)

        with self.lock:
            history_item = None
            for item in self.history:
                if str(item.get("run_id")) == str(run_id):
                    history_item = dict(item)
                    break

            if history_item is None and self.active_job and str(self.active_job.get("run_id")) == str(run_id):
                payload = self.active_job.get("payload") if isinstance(self.active_job.get("payload"), dict) else {}
                runner_status = self._read_runner_status()
                story_root_value, story_root_path = self._normalize_story_root_value(
                    runner_status.get("last_story_root") or payload.get("story_root")
                )
                history_item = {
                    "run_id": run_id,
                    "job_id": self.active_job.get("job_id"),
                    "priority": self.active_job.get("priority"),
                    "state": "running",
                    "started_at": self.current_run_started_iso,
                    "finished_at": None,
                    "duration_sec": time.time() - (self.current_run_started_at or time.time()),
                    "queued_delay_sec": None,
                    "exit_code": None,
                    "total_books": payload.get("count", 0),
                    "completed_books": 0,
                    "success_books": 0,
                    "failed_books": 0,
                    "story_root": story_root_value,
                    "evaluation_ready": bool(story_root_path and (story_root_path / "assessment_report.json").exists()),
                    "config": dict(payload),
                }

            if history_item is None:
                return {"ok": False, "error": f"Run not found: {run_id}"}

            logs = list(self.run_logs.get(run_id, []))[-log_limit:]
            events = list(self.run_events.get(run_id, []))[-event_limit:]
            related_alerts = [dict(item) for item in self.alerts if str(item.get("run_id") or "") == str(run_id)]
            related_alerts.sort(key=lambda item: str(item.get("ts") or ""), reverse=True)

        books = self._build_run_book_entries(run_id, history_item=history_item)
        selected_book = self._select_run_book_entry(books, book)
        selected_book_index = _safe_int(
            selected_book.get("book_index") if isinstance(selected_book, dict) else None,
            0,
            min_value=0,
        )

        run_state = str(history_item.get("state") or "").strip().lower()
        logs_scope = "run"
        logs_source = None
        file_logs = self._read_run_logs_from_files(str(run_id), history_item=history_item, log_limit=log_limit)
        selected_book_logs: List[Dict[str, Any]] = []
        if selected_book_index > 0:
            selected_book_logs = self._read_run_logs_from_files(
                str(run_id),
                history_item=history_item,
                log_limit=max(log_limit, 4000),
                book_index=selected_book_index,
            )
            if selected_book_logs:
                logs = selected_book_logs
                logs_scope = "book"
                if isinstance(selected_book, dict):
                    logs_source = selected_book.get("artifact_run") or selected_book.get("log_path")

        if logs_scope != "book" and file_logs:
            if run_state in {"completed", "failed", "stopped", "error"} or not logs:
                logs = file_logs[-log_limit:]
            else:
                seen: set[Tuple[str, str]] = set()
                merged: List[Dict[str, Any]] = []
                for entry in file_logs + logs:
                    key = (str(entry.get("ts") or ""), str(entry.get("text") or ""))
                    if key in seen:
                        continue
                    seen.add(key)
                    merged.append(entry)
                if len(merged) > log_limit:
                    merged = merged[-log_limit:]
                logs = merged
            if not logs_source and logs:
                first_source = logs[0].get("source_tag") if isinstance(logs[0], dict) else None
                logs_source = str(first_source or "") or None

        return {
            "ok": True,
            "run": history_item,
            "books": books,
            "selected_book": selected_book,
            "logs": logs,
            "logs_scope": logs_scope,
            "logs_source": logs_source,
            "events": events,
            "events_scope": "run",
            "alerts": related_alerts,
            "alerts_scope": "run",
        }

    def get_evaluation(
        self,
        *,
        source: Optional[str] = None,
        run_id: Optional[str] = None,
        story_root_hint: Optional[str] = None,
        book: Optional[str] = None,
        branch: Optional[str] = None,
    ) -> Dict[str, Any]:
        source_mode = _normalize_eval_source(source, default="latest")
        requested_branch = _safe_report_branch_token(branch, default="canonical").lower()
        run_token = _safe_text(run_id, default="", max_length=120)
        story_root_token = _safe_text(story_root_hint, default="", max_length=1200)
        book_token = _safe_text(book, default="", max_length=600)

        base_meta: Dict[str, Any] = {
            "source": source_mode,
            "requested_branch": requested_branch,
            "run_id": run_token or None,
            "story_root": story_root_token or None,
            "book": book_token or None,
            "report_file": None,
        }

        story_root_path: Optional[Path] = None
        run_books: List[Dict[str, Any]] = []
        selected_book: Optional[Dict[str, Any]] = None

        if source_mode == "run":
            if not run_token:
                return {
                    "ok": False,
                    "error": "run_id is required when source=run.",
                    "meta": base_meta,
                }

            run_books = self._build_run_book_entries(run_token)
            selected_book = self._select_run_book_entry(run_books, book_token)
            if selected_book is not None:
                selected_story_root = _safe_text(selected_book.get("story_root"), default="", max_length=1200)
                story_root_path = self._safe_path_under_root(selected_story_root)

            if story_root_path is None:
                story_root_path = self._resolve_story_root_for_run(run_token)

            if story_root_path is not None and not run_books:
                fallback_story_root = self._to_root_relative_path(story_root_path)
                run_books = [
                    {
                        "book_index": 1,
                        "book_id": f"{run_token}::book:1",
                        "title": story_root_path.name,
                        "story_root": fallback_story_root,
                        "report_file": None,
                        "overall_score": None,
                        "updated_at": None,
                    }
                ]
                selected_book = run_books[0]

            if story_root_path is None:
                return {
                    "ok": False,
                    "error": f"Unable to resolve story_root for run_id: {run_token}",
                    "meta": base_meta,
                }
        elif source_mode == "story_root":
            if not story_root_token:
                return {
                    "ok": False,
                    "error": "story_root is required when source=story_root.",
                    "meta": base_meta,
                }
            story_root_path = self._safe_path_under_root(story_root_token)
            if story_root_path is None or (not story_root_path.exists()) or (not story_root_path.is_dir()):
                return {
                    "ok": False,
                    "error": f"Invalid story_root: {story_root_token}",
                    "meta": base_meta,
                }
        else:
            latest_root = self._find_latest_story_root_with_report(requested_branch)
            if latest_root is None:
                latest_root = find_latest_story_root(self.root_dir / "output")
            if latest_root and latest_root.exists() and latest_root.is_dir():
                story_root_path = latest_root
            else:
                return {
                    "ok": False,
                    "error": "No stories found.",
                    "meta": base_meta,
                }

        if story_root_path is None:
            return {
                "ok": False,
                "error": "No evaluation story root resolved.",
                "meta": base_meta,
            }

        story_root_rel = self._to_root_relative_path(story_root_path)
        base_meta["story_root"] = story_root_rel

        candidate_files = self._evaluation_report_candidates(story_root_path, requested_branch)
        report_file = next((candidate for candidate in candidate_files if candidate.exists() and candidate.is_file()), None)

        if report_file is None:
            searched_files = [path.name for path in candidate_files]
            return {
                "ok": False,
                "error": "No assessment report found for selected story.",
                "meta": {
                    **base_meta,
                    "searched_files": searched_files,
                },
                "requested_branch": requested_branch,
                "searched_files": searched_files,
            }

        try:
            diagnostics = json.loads(report_file.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Failed to parse assessment report: {exc}",
                "meta": {
                    **base_meta,
                    "report_file": report_file.name,
                },
            }

        response_meta = {
            **base_meta,
            "story_root": story_root_rel,
            "report_file": report_file.name,
        }

        return {
            "ok": True,
            "diagnostics": diagnostics,
            "meta": response_meta,
            "source": source_mode,
            "run_id": run_token or None,
            "story_root": story_root_rel,
            "requested_branch": requested_branch,
            "report_file": report_file.name,
            "books": run_books,
            "selected_book": selected_book,
        }

    def get_status(self) -> Dict[str, Any]:
        self._sync_process_exit()

        with self.lock:
            running = self._is_running()
            pid = self.process.pid if running and self.process else None
            run_id = self.current_run_id
            run_started_at = self.current_run_started_at
            run_started_iso = self.current_run_started_iso
            exit_code = self.current_exit_code
            last_config = dict(self.last_config)
            last_error = self.last_error
            queue_depth = len(self.pending_jobs)
            active_job = _job_public_view(self.active_job) if self.active_job else None
            if active_job is not None and isinstance(self.active_job, dict):
                payload = self.active_job.get("payload")
                if isinstance(payload, dict):
                    active_job["payload"] = dict(payload)
            module_queue_depth = len(self.module_pending_jobs)
            module_active_job = self._module_job_public_view(self.module_active_job)
            status_signature_old = self.current_status_signature
            log_next_seq = self.log_seq + 1
            failure_ratio = self._recent_failure_ratio_locked(window=12)
            latest_history = dict(self.history[-1]) if self.history else None

        runner = self._read_runner_status()
        if not runner:
            runner = _default_runner_payload(last_config)

        runner_state = str(runner.get("state") or "").lower()
        if not running and runner_state == "running":
            if isinstance(latest_history, dict):
                latest_state = str(latest_history.get("state") or "").strip().lower()
                if latest_state in {"completed", "failed", "stopped", "error"}:
                    runner = self._runner_payload_from_history_item(latest_history, fallback_config=last_config)
                    runner_state = str(runner.get("state") or "").lower()
                else:
                    runner = dict(runner)
                    runner["state"] = "stopped"
                    runner["current_stage"] = "stopped"
            else:
                runner = dict(runner)
                runner["state"] = "stopped"
                runner["current_stage"] = "stopped"
        status_signature = "|".join(
            [
                str(runner.get("updated_at")),
                str(runner.get("state")),
                str(runner.get("current_stage")),
                str(runner.get("current_book")),
                str(runner.get("completed_books")),
            ]
        )

        if run_id and running and status_signature != status_signature_old:
            with self.lock:
                if self.current_status_signature != status_signature:
                    self.current_status_signature = status_signature
                    self._record_run_event_locked(run_id, "status_update", {
                        "state": runner.get("state"),
                        "stage": runner.get("current_stage"),
                        "book": runner.get("current_book"),
                        "completed": runner.get("completed_books"),
                    })

        total_books = _safe_int(runner.get("total_books"), _safe_int(last_config.get("count"), 0, min_value=0), min_value=0)
        completed_books = _safe_int(runner.get("completed_books"), 0, min_value=0, max_value=total_books if total_books > 0 else None)
        success_books = _safe_int(runner.get("success_books"), 0, min_value=0)
        failed_books = _safe_int(runner.get("failed_books"), 0, min_value=0)
        stage_progress = dict(runner.get("stage_progress") or {}) if isinstance(runner.get("stage_progress"), dict) else {}
        stage_detail = _safe_text(runner.get("stage_detail"), default="", max_length=400) or None

        def _stage_range_for(stage_value: str) -> Tuple[float, float]:
            token = str(stage_value or "").upper()
            if "PRE_EVAL" in token:
                return 0.0, 0.08
            if "STORY" in token or "LLM" in token:
                return 0.08, 0.35
            if "IMAGE" in token or "SDXL" in token:
                return 0.35, 0.70
            if "TRANSLATE" in token or "TRANSLATION" in token:
                return 0.70, 0.84
            if "VOICE" in token:
                return 0.84, 0.94
            if "VERIFY" in token:
                return 0.94, 0.99
            if "DONE" in token or "SUCCESS" in token:
                return 1.0, 1.0
            return 0.0, 0.0

        progress_pct = 0.0
        total_progress = float(completed_books)
        if total_books > 0:
            stage_str = str(runner.get("current_stage") or "").upper()
            fraction = 0.0
            stage_start, stage_end = _stage_range_for(stage_str)
            if stage_end > stage_start and stage_progress:
                progress_done = _safe_int(stage_progress.get("completed"), 0, min_value=0)
                progress_total = _safe_int(stage_progress.get("total"), 0, min_value=0)
                progress_ratio = min(1.0, max(0.0, (progress_done / progress_total))) if progress_total > 0 else 0.0
                fraction = stage_start + ((stage_end - stage_start) * progress_ratio)
            elif "LLM" in stage_str or "STORY" in stage_str:
                fraction = 0.1
            elif "IMAGE" in stage_str or "SDXL" in stage_str:
                fraction = 0.4
            elif "TRANSLATE" in stage_str or "TRANSLATION" in stage_str:
                fraction = 0.7
            elif "VOICE" in stage_str:
                fraction = 0.85
            elif "VERIFY" in stage_str:
                fraction = 0.95
            elif "DONE" in stage_str or "SUCCESS" in stage_str:
                fraction = 1.0

            state_str = str(runner.get("state") or "").lower()
            if state_str not in ("running", "active") and fraction < 1.0:
                fraction = 0.0

            total_progress = min(float(total_books), float(completed_books) + float(fraction))
            progress_pct = round((total_progress / total_books) * 100.0, 2)

        elapsed_sec: Optional[float] = None
        if run_started_at is not None:
            elapsed_sec = round(max(0.0, time.time() - run_started_at), 2)

        latest_run_id: Optional[str] = None
        latest_run_state: Optional[str] = None
        latest_run_started_at: Optional[str] = None
        latest_run_finished_at: Optional[str] = None
        latest_run_stage: Optional[str] = None
        latest_run_elapsed_sec: Optional[float] = None
        latest_run_exit_code: Optional[int] = None
        latest_run_last_error: Optional[str] = None
        latest_run_updated_ago_sec: Optional[float] = None
        latest_run_total_books = 0
        latest_run_completed_books = 0
        latest_run_success_books = 0
        latest_run_failed_books = 0
        if isinstance(latest_history, dict):
            latest_run_id = _safe_text(latest_history.get("run_id"), default="", max_length=120) or None
            latest_run_state = _safe_text(latest_history.get("state"), default="", max_length=32) or None
            latest_run_started_at = _safe_text(latest_history.get("started_at"), default="", max_length=64) or None
            latest_run_finished_at = _safe_text(latest_history.get("finished_at"), default="", max_length=64) or None
            latest_run_stage = _safe_text(latest_history.get("current_stage"), default="", max_length=64) or None
            latest_run_last_error = _safe_text(latest_history.get("last_error"), default="", max_length=4000) or None
            latest_duration = _safe_float(latest_history.get("duration_sec"), 0.0)
            latest_run_elapsed_sec = round(latest_duration, 2) if latest_duration > 0 else None
            raw_latest_exit = latest_history.get("exit_code")
            latest_run_exit_code = None if raw_latest_exit in {None, ""} else _safe_int(raw_latest_exit, 0)
            latest_updated_at = _parse_iso_datetime(latest_history.get("finished_at") or latest_history.get("started_at"))
            if latest_updated_at is not None:
                latest_run_updated_ago_sec = round(
                    (datetime.now(timezone.utc) - latest_updated_at).total_seconds(),
                    2,
                )
            latest_run_total_books = _safe_int(latest_history.get("total_books"), 0, min_value=0)
            latest_run_completed_books = _safe_int(
                latest_history.get("completed_books"),
                0,
                min_value=0,
                max_value=latest_run_total_books if latest_run_total_books > 0 else None,
            )
            latest_run_success_books = _safe_int(latest_history.get("success_books"), 0, min_value=0)
            latest_run_failed_books = _safe_int(latest_history.get("failed_books"), 0, min_value=0)

        eta_sec: Optional[float] = None
        if running and elapsed_sec is not None and total_books > total_progress and total_progress > 0:
            avg_per_book = elapsed_sec / total_progress
            eta_sec = round(avg_per_book * (total_books - total_progress), 2)

        updated_ago_sec: Optional[float] = None
        updated_at = _parse_iso_datetime(runner.get("updated_at"))
        if updated_at is not None:
            updated_ago_sec = round((datetime.now(timezone.utc) - updated_at).total_seconds(), 2)

        return {
            "ok": True,
            "api_version": _DASHBOARD_API_VERSION,
            "capabilities": _dashboard_capabilities(),
            "running": running,
            "pid": pid,
            "run_id": run_id,
            "run_started_at": run_started_iso,
            "exit_code": exit_code,
            "latest_run_id": latest_run_id,
            "latest_run_state": latest_run_state,
            "latest_run_started_at": latest_run_started_at,
            "latest_run_finished_at": latest_run_finished_at,
            "latest_run_stage": latest_run_stage,
            "latest_run_elapsed_sec": latest_run_elapsed_sec,
            "latest_run_exit_code": latest_run_exit_code,
            "latest_run_last_error": latest_run_last_error,
            "latest_run_updated_ago_sec": latest_run_updated_ago_sec,
            "latest_run_total_books": latest_run_total_books,
            "latest_run_completed_books": latest_run_completed_books,
            "latest_run_success_books": latest_run_success_books,
            "latest_run_failed_books": latest_run_failed_books,
            "status_file": str(self.status_file),
            "last_config": last_config,
            "last_error": last_error,
            "runner": runner,
            "stage_progress": stage_progress or None,
            "stage_detail": stage_detail,
            "progress_pct": progress_pct,
            "elapsed_sec": elapsed_sec,
            "eta_sec": eta_sec,
            "updated_ago_sec": updated_ago_sec,
            "queue_depth": queue_depth,
            "active_job": active_job,
            "module_queue_depth": module_queue_depth,
            "module_active_job": module_active_job,
            "failure_ratio_recent": round(failure_ratio, 4),
            "log_next_seq": log_next_seq,
            "server_ts": time.time(),
        }


class DashboardHandler(BaseHTTPRequestHandler):
    runtime: DashboardRuntime

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, body: bytes, *, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Dict[str, Any]:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/":
            body = get_html()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store, max-age=0, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path.startswith("/static/"):
            try:
                # Remove /static/ prefix
                safe_path = parsed.path[8:].replace("..", "")
                full_path = Path("pipeline/static") / safe_path
                if full_path.is_file():
                    with open(full_path, "rb") as static_f:
                        content = static_f.read()
                    self.send_response(200)
                    content_type = "text/css" if parsed.path.endswith(".css") else "application/javascript" if parsed.path.endswith(".js") else "application/octet-stream"
                    self.send_header("Content-Type", f"{content_type}; charset=utf-8")
                    self.send_header("Content-Length", str(len(content)))
                    self.send_header("Cache-Control", "no-store, max-age=0, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.end_headers()
                    self.wfile.write(content)
                    return
            except Exception as e:
                pass
            self.send_error(404, "File Not Found")
            return

        if parsed.path == "/api/system":
            self._send_json(get_system_status())
            return

        if parsed.path == "/api/status":
            self._send_json(self.runtime.get_status())
            return

        if parsed.path == "/api/queue":
            self._send_json(self.runtime.get_queue())
            return

        if parsed.path == "/api/alerts":
            limit = _safe_int((query.get("limit") or [30])[0], 30, min_value=1, max_value=200)
            include_ack = _safe_bool((query.get("include_ack") or ["false"])[0], False)
            self._send_json(self.runtime.get_alerts(limit=limit, include_ack=include_ack))
            return

        if parsed.path == "/api/capacity":
            window = _safe_int((query.get("window") or [_CAPACITY_WINDOW])[0], _CAPACITY_WINDOW, min_value=1, max_value=300)
            self._send_json(self.runtime.get_capacity(window=window))
            return

        if parsed.path == "/api/configs":
            limit = _safe_int((query.get("limit") or [20])[0], 20, min_value=1, max_value=200)
            self._send_json(self.runtime.list_config_versions(limit=limit))
            return

        if parsed.path == "/api/voice/preset-samples":
            self._send_json(self.runtime.list_voice_preset_samples())
            return

        if parsed.path == "/api/voice/custom-speakers":
            selected_dir = (query.get("selected_dir") or [""])[0]
            self._send_json(self.runtime.list_custom_voice_library(selected_dir))
            return

        if parsed.path == "/api/evaluation":
            try:
                source = (query.get("source") or ["latest"])[0]
                run_id = (query.get("run_id") or [""])[0]
                story_root = (query.get("story_root") or [""])[0]
                book = (query.get("book") or [""])[0]
                branch = (query.get("branch") or ["canonical"])[0]
                payload = self.runtime.get_evaluation(
                    source=source,
                    run_id=run_id,
                    story_root_hint=story_root,
                    book=book,
                    branch=branch,
                )
                self._send_json(payload)
            except Exception as e:
                try:
                    print(
                        "[dashboard] /api/evaluation failed\n" + traceback.format_exc(),
                        file=sys.stderr,
                        flush=True,
                    )
                except Exception:
                    pass
                try:
                    self._send_json({"ok": False, "error": f"evaluation endpoint failed: {e}"}, status=500)
                except Exception:
                    pass
            return

        if parsed.path == "/api/logs":
            since = _safe_int((query.get("since") or [0])[0], 0, min_value=0)
            limit = _safe_int((query.get("limit") or [200])[0], 200, min_value=1, max_value=800)
            run_id = (query.get("run_id") or [None])[0]
            self._send_json(self.runtime.get_logs(since=since, limit=limit, run_id=run_id))
            return

        if parsed.path == "/api/history":
            limit = _safe_int((query.get("limit") or [20])[0], 20, min_value=1, max_value=200)
            self._send_json(self.runtime.get_history(limit=limit))
            return

        if parsed.path == "/api/run-detail":
            run_id = (query.get("run_id") or [""])[0]
            if not str(run_id or "").strip():
                self._send_json({"ok": False, "error": "run_id is required"}, status=400)
                return
            log_limit = _safe_int((query.get("log_limit") or [300])[0], 300, min_value=1, max_value=1200)
            event_limit = _safe_int((query.get("event_limit") or [200])[0], 200, min_value=1, max_value=1200)
            book = (query.get("book") or [""])[0]
            self._send_json(self.runtime.get_run_detail(run_id=str(run_id), log_limit=log_limit, event_limit=event_limit, book=book))
            return

        if parsed.path == "/api/modules/jobs":
            limit = _safe_int((query.get("limit") or [40])[0], 40, min_value=1, max_value=400)
            self._send_json(self.runtime.list_module_jobs(limit=limit))
            return

        if parsed.path == "/api/modules/job-detail":
            job_id = (query.get("job_id") or [""])[0]
            log_limit = _safe_int((query.get("log_limit") or [300])[0], 300, min_value=1, max_value=1500)
            event_limit = _safe_int((query.get("event_limit") or [200])[0], 200, min_value=1, max_value=1200)
            self._send_json(self.runtime.get_module_job_detail(job_id=job_id, log_limit=log_limit, event_limit=event_limit))
            return

        if parsed.path == "/api/images/items":
            story_root_hint = (query.get("story_root") or [None])[0]
            limit = _safe_int((query.get("limit") or [200])[0], 200, min_value=1, max_value=800)
            self._send_json(self.runtime.list_image_items(story_root_hint=story_root_hint, limit=limit))
            return

        if parsed.path == "/api/stories/translatable":
            limit = _safe_int((query.get("limit") or [120])[0], 120, min_value=1, max_value=400)
            self._send_json(self.runtime.list_translatable_stories(limit=limit))
            return

        if parsed.path == "/api/images/file":
            raw_path = (query.get("path") or [""])[0]
            file_path = self.runtime._safe_path_under_root(raw_path)
            if not file_path or not file_path.exists() or not file_path.is_file():
                self._send_json({"ok": False, "error": "file not found"}, status=404)
                return
            mtype, _ = mimetypes.guess_type(str(file_path))
            try:
                body = file_path.read_bytes()
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", mtype or "application/octet-stream")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, status=500)
                return

        if parsed.path == "/api/templates":
            p = self.runtime.root_dir / "runs" / "prompt_templates.json"
            data = []
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, list):
                        data = loaded
                except Exception:
                    data = []
            self._send_json(data)
            return

        if parsed.path == "/api/gallery":
            limit = _safe_int((query.get("limit") or [120])[0], 120, min_value=1, max_value=400)
            self._send_json(self.runtime.list_gallery_stories(limit=limit))
            return

        self._send_json({"ok": False, "error": "not found"}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)

        if parsed.path == "/api/templates/save":
            payload = self._read_json_body()
            name = payload.get("name")
            prompt = payload.get("prompt")
            neg = payload.get("negative_prompt", "")
            story_materials = payload.get("story_materials", "")
            story_input_mode = payload.get("story_input_mode", "preset")
            if not isinstance(name, str) or not name.strip():
                self._send_json({"ok": False, "error": "name is required"}, status=400)
                return
            if not isinstance(prompt, str) or not prompt.strip():
                self._send_json({"ok": False, "error": "prompt is required"}, status=400)
                return
            if not isinstance(neg, str):
                neg = ""
            if not isinstance(story_materials, str):
                story_materials = ""
            if not isinstance(story_input_mode, str):
                story_input_mode = "preset"

            p = self.runtime.root_dir / "runs" / "prompt_templates.json"
            data = []
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    if isinstance(loaded, list):
                        data = loaded
                except Exception:
                    data = []

            name_text = name.strip()
            prompt_text = prompt.strip()
            template_index = None
            name_key = name_text.casefold()
            for idx, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                item_name = str(item.get("name") or "").strip()
                if item_name.casefold() == name_key:
                    template_index = idx
                    break

            template_item = {
                "name": name_text,
                "prompt": prompt_text,
                "negative_prompt": neg.strip(),
                "story_materials": story_materials.strip(),
                "story_input_mode": story_input_mode.strip() or "preset",
                "id": str(len(data)),
            }

            if template_index is not None:
                existing = data[template_index] if isinstance(data[template_index], dict) else {}
                template_item["id"] = str(existing.get("id") or template_index)
                merged = dict(existing)
                merged.update(template_item)
                data[template_index] = merged
            else:
                data.append(template_item)

            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._send_json({"ok": True, "templates": data, "updated": template_index is not None})
            return

        if parsed.path == "/api/start":
            payload = self._read_json_body()
            result = self.runtime.start_run(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/overview/clear":
            result = self.runtime.clear_overview_view()
            self._send_json(result, status=200 if result.get("ok") else 409)
            return

        if parsed.path == "/api/history/clear":
            result = self.runtime.clear_run_history()
            self._send_json(result, status=200 if result.get("ok") else 409)
            return

        if parsed.path == "/api/stop":
            result = self.runtime.stop_run()
            self._send_json(result, status=200 if result.get("ok") else 500)
            return

        if parsed.path == "/api/system/shutdown":
            stop_result = self.runtime.stop_run()
            module_result = self.runtime.stop_module_job(None)

            def _shutdown_server_later(server: ThreadingHTTPServer) -> None:
                time.sleep(0.1)
                try:
                    server.shutdown()
                except Exception:
                    pass

            threading.Thread(target=_shutdown_server_later, args=(self.server,), daemon=True).start()
            self._send_json(
                {
                    "ok": True,
                    "message": "Dashboard shutdown requested.",
                    "run_stop": stop_result,
                    "module_stop": module_result,
                },
                status=200,
            )
            return

        if parsed.path == "/api/queue/reprioritize":
            payload = self._read_json_body()
            job_id = str(payload.get("job_id") or "")
            priority = str(payload.get("priority") or "normal")
            if not job_id:
                self._send_json({"ok": False, "error": "job_id is required"}, status=400)
                return
            result = self.runtime.reprioritize_job(job_id, priority)
            self._send_json(result, status=200 if result.get("ok") else 404)
            return

        if parsed.path == "/api/queue/cancel":
            payload = self._read_json_body()
            job_id = str(payload.get("job_id") or "")
            if not job_id:
                self._send_json({"ok": False, "error": "job_id is required"}, status=400)
                return
            result = self.runtime.cancel_job(job_id)
            self._send_json(result, status=200 if result.get("ok") else 404)
            return

        if parsed.path == "/api/alerts/ack":
            payload = self._read_json_body()
            alert_id = str(payload.get("alert_id") or "")
            if not alert_id:
                self._send_json({"ok": False, "error": "alert_id is required"}, status=400)
                return
            result = self.runtime.acknowledge_alert(alert_id)
            self._send_json(result, status=200 if result.get("ok") else 404)
            return

        if parsed.path == "/api/configs/save":
            payload = self._read_json_body()
            config_payload = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
            name = payload.get("name") if isinstance(payload.get("name"), str) else None
            note = payload.get("note") if isinstance(payload.get("note"), str) else None
            result = self.runtime.save_config_version(config_payload, name=name, note=note)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/configs/apply":
            payload = self._read_json_body()
            version_id = str(payload.get("version_id") or "")
            if not version_id:
                self._send_json({"ok": False, "error": "version_id is required"}, status=400)
                return
            result = self.runtime.apply_config_version(version_id)
            self._send_json(result, status=200 if result.get("ok") else 404)
            return

        if parsed.path == "/api/voice/recordings/save":
            payload = self._read_json_body()
            result = self.runtime.save_voice_recording(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/general/text":
            payload = self._read_json_body()
            result = self.runtime.general_text_generate(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/general/image":
            payload = self._read_json_body()
            result = self.runtime.general_image_generate(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/general/translate":
            payload = self._read_json_body()
            result = self.runtime.general_translate_text(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/general/voice":
            payload = self._read_json_body()
            result = self.runtime.general_voice_generate(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        if parsed.path == "/api/modules/run":
          payload = self._read_json_body()
          result = self.runtime.run_module_job(payload)
          self._send_json(result, status=200 if result.get("ok") else 400)
          return

        if parsed.path == "/api/modules/stop":
          payload = self._read_json_body()
          job_id = payload.get("job_id") if isinstance(payload.get("job_id"), str) else None
          result = self.runtime.stop_module_job(job_id)
          self._send_json(result, status=200 if result.get("ok") else 404)
          return

        if parsed.path == "/api/images/regenerate":
            payload = self._read_json_body()
            result = self.runtime.regenerate_images(payload)
            self._send_json(result, status=200 if result.get("ok") else 400)
            return

        self._send_json({"ok": False, "error": "not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def run_dashboard_server(host: str = "127.0.0.1", port: int = 8765, *, auto_open: bool = True) -> None:
    """Start local dashboard server and block until interrupted."""

    _ensure_dashboard_port_ready(int(port))

    root_dir = Path(__file__).resolve().parents[1]
    runtime = DashboardRuntime(root_dir)
    DashboardHandler.runtime = runtime

    server = ThreadingHTTPServer((host, int(port)), DashboardHandler)
    bind_url = f"http://{host}:{port}"
    display_host = "127.0.0.1" if str(host).strip() in {"0.0.0.0", "::", "[::]"} else str(host)
    access_url = f"http://{display_host}:{port}"
    if access_url == bind_url:
        print(f"Dashboard started at {access_url}")
    else:
        print(f"Dashboard started. Access URL: {access_url} (bound to {bind_url})")
    print("Press Ctrl+C to stop dashboard server")

    if auto_open:
        try:
            webbrowser.open(access_url)
        except Exception:
            pass

    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        runtime.stop_run()
        runtime.shutdown()
        server.server_close()






