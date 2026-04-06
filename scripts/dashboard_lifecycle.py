"""Dashboard lifecycle helper.

This script provides a safe way to stop stale dashboard instances bound on a port,
with API-first shutdown and process-tree fallback.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib import error, request

import psutil


def _safe_int(value: Any, default: int = 0) -> int:
	try:
		return int(value)
	except (TypeError, ValueError):
		return default


def _cmdline_text(parts: Sequence[str]) -> str:
	return " ".join(str(part) for part in parts if part is not None)


def _looks_like_dashboard_cmd(parts: Sequence[str]) -> bool:
	text = _cmdline_text(parts).lower().replace('"', " ")
	normalized = " ".join(text.split())
	return "--dashboard" in normalized and "-m pipeline" in normalized


def _listener_pids(port: int) -> List[int]:
	target_port = _safe_int(port, 8765)
	if target_port <= 0:
		return []

	try:
		conns = psutil.net_connections(kind="tcp")
	except Exception:
		return []

	seen: Dict[int, int] = {}
	for conn in conns:
		if conn.status != psutil.CONN_LISTEN:
			continue

		laddr = conn.laddr
		local_port: Optional[int] = None
		if hasattr(laddr, "port"):
			local_port = _safe_int(getattr(laddr, "port"), default=0)
		elif isinstance(laddr, tuple) and len(laddr) >= 2:
			local_port = _safe_int(laddr[1], default=0)
		if local_port != target_port:
			continue

		pid = _safe_int(getattr(conn, "pid", 0), default=0)
		if pid > 0:
			seen[pid] = pid
	return sorted(seen.values())


def _describe_process(pid: int) -> str:
	try:
		proc = psutil.Process(pid)
	except Exception:
		return f"pid={pid}"

	try:
		exe = proc.exe()
	except Exception:
		exe = ""
	try:
		cmdline = _cmdline_text(proc.cmdline())
	except Exception:
		cmdline = ""

	if exe and cmdline:
		return f"pid={pid} | {exe} | {cmdline}"
	if exe:
		return f"pid={pid} | {exe}"
	if cmdline:
		return f"pid={pid} | {cmdline}"
	return f"pid={pid}"


def _terminate_tree(pid: int, *, graceful_timeout: float = 5.0, force_timeout: float = 2.0) -> bool:
	try:
		root = psutil.Process(pid)
	except Exception:
		return False

	targets = []
	try:
		targets.extend(root.children(recursive=True))
	except Exception:
		pass
	targets.append(root)

	unique: Dict[int, psutil.Process] = {}
	for proc in targets:
		try:
			unique[proc.pid] = proc
		except Exception:
			continue
	all_targets = list(unique.values())
	if not all_targets:
		return True

	for proc in all_targets:
		try:
			proc.terminate()
		except Exception:
			pass

	_, alive = psutil.wait_procs(all_targets, timeout=max(0.3, float(graceful_timeout)))
	if alive:
		for proc in alive:
			try:
				proc.kill()
			except Exception:
				pass
		psutil.wait_procs(alive, timeout=max(0.3, float(force_timeout)))

	return True


def _post_shutdown(host: str, port: int, timeout_sec: float = 2.5) -> Tuple[bool, str]:
	url = f"http://{host}:{port}/api/system/shutdown"
	payload = b"{}"
	req = request.Request(
		url,
		data=payload,
		method="POST",
		headers={"Content-Type": "application/json"},
	)
	try:
		with request.urlopen(req, timeout=max(0.2, float(timeout_sec))) as resp:
			raw = resp.read().decode("utf-8", errors="replace")
			if raw:
				try:
					data = json.loads(raw)
					message = str(data.get("message") or "ok")
				except Exception:
					message = raw.strip()
			else:
				message = "ok"
			return True, message
	except error.HTTPError as exc:
		return False, f"HTTP {exc.code}"
	except Exception as exc:
		return False, str(exc)


def _wait_port_clear(port: int, timeout_sec: float = 2.5) -> bool:
	deadline = time.time() + max(0.3, float(timeout_sec))
	while time.time() < deadline:
		if not _listener_pids(port):
			return True
		time.sleep(0.15)
	return not _listener_pids(port)


def _stop_dashboard(
	host: str,
	port: int,
	*,
	quiet: bool,
	force_non_dashboard: bool,
	timeout_sec: float,
) -> int:
	ok, message = _post_shutdown(host, port, timeout_sec=timeout_sec)
	if not quiet:
		if ok:
			print(f"[INFO] Sent API shutdown request: {message}")
		else:
			print(f"[INFO] API shutdown unavailable: {message}")

	if _wait_port_clear(port, timeout_sec=timeout_sec):
		if not quiet:
			print(f"[INFO] Port {port} is clear.")
		return 0

	remaining = _listener_pids(port)
	if not remaining:
		return 0

	blocked_non_dashboard = False
	for pid in remaining:
		try:
			proc = psutil.Process(pid)
			cmdline = proc.cmdline()
		except Exception:
			cmdline = []

		is_dashboard = _looks_like_dashboard_cmd(cmdline)
		if (not is_dashboard) and (not force_non_dashboard):
			blocked_non_dashboard = True
			if not quiet:
				print(f"[WARN] Listener is not dashboard, skipped: {_describe_process(pid)}")
			continue

		if not quiet:
			print(f"[INFO] Terminating listener tree: {_describe_process(pid)}")
		_terminate_tree(pid)

	if _wait_port_clear(port, timeout_sec=timeout_sec):
		if not quiet:
			print(f"[INFO] Port {port} is clear.")
		return 0

	if blocked_non_dashboard and not quiet:
		print(f"[ERROR] Port {port} still in use by non-dashboard process.")
	elif not quiet:
		print(f"[ERROR] Port {port} still in use after termination attempts.")
	return 1


def _status_dashboard(port: int) -> int:
	pids = _listener_pids(port)
	if not pids:
		print(json.dumps({"listening": False, "port": port, "listeners": []}, ensure_ascii=False))
		return 0

	listeners: List[Dict[str, Any]] = []
	for pid in pids:
		entry: Dict[str, Any] = {
			"pid": pid,
			"dashboard_like": False,
			"exe": None,
			"cmdline": None,
		}
		try:
			proc = psutil.Process(pid)
			cmdline = proc.cmdline()
			entry["dashboard_like"] = _looks_like_dashboard_cmd(cmdline)
			entry["cmdline"] = _cmdline_text(cmdline)
			try:
				entry["exe"] = proc.exe()
			except Exception:
				entry["exe"] = None
		except Exception:
			pass
		listeners.append(entry)

	print(
		json.dumps(
			{
				"listening": True,
				"port": port,
				"listeners": listeners,
			},
			ensure_ascii=False,
			indent=2,
		)
	)
	return 0


def _build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Dashboard lifecycle helper")
	sub = parser.add_subparsers(dest="command", required=True)

	stop_parser = sub.add_parser("stop", help="Stop dashboard listener on a port")
	stop_parser.add_argument("--host", default="127.0.0.1", help="Dashboard host for API shutdown")
	stop_parser.add_argument("--port", type=int, default=8765, help="Dashboard port")
	stop_parser.add_argument("--timeout", type=float, default=2.5, help="Shutdown timeout seconds")
	stop_parser.add_argument("--quiet", action="store_true", help="Suppress non-error logs")
	stop_parser.add_argument(
		"--force-non-dashboard",
		action="store_true",
		help="Allow force-killing listeners even if cmdline does not look like pipeline dashboard",
	)

	status_parser = sub.add_parser("status", help="Print listener status on a port")
	status_parser.add_argument("--port", type=int, default=8765, help="Dashboard port")
	return parser


def main() -> int:
	parser = _build_parser()
	args = parser.parse_args()

	if args.command == "stop":
		return _stop_dashboard(
			host=str(args.host),
			port=_safe_int(args.port, 8765),
			quiet=bool(args.quiet),
			force_non_dashboard=bool(args.force_non_dashboard),
			timeout_sec=float(args.timeout),
		)
	if args.command == "status":
		return _status_dashboard(_safe_int(args.port, 8765))
	parser.print_help()
	return 2


if __name__ == "__main__":
	raise SystemExit(main())
