#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

MODE="toggle_dashboard"
AUTO_DASHBOARD=1
FORCE_NON_DASHBOARD=0
COMPAT_GENAI_ONLY=0
COMPAT_WITH_EVAL=0
DASH_RUNNING=0

DASH_ARGS=()
EVAL_ARGS=()
COLLECT_EVAL_ARGS=0

while [[ $# -gt 0 ]]; do
  if [[ "$COLLECT_EVAL_ARGS" == "1" ]]; then
    if [[ "$1" == "--stories" ]]; then
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] --stories requires a path argument."
        exit 2
      fi
      EVAL_ARGS+=(--input "$2")
      shift 2
      continue
    fi
    EVAL_ARGS+=("$1")
    shift
    continue
  fi

  case "$1" in
    --dashboard)
      MODE="dashboard"
      ;;
    --terminal)
      MODE="terminal"
      ;;
    --dashboard-status)
      MODE="dashboard_status"
      ;;
    --dashboard-stop)
      MODE="dashboard_stop"
      ;;
    --dashboard-restart)
      MODE="dashboard_restart"
      ;;
    --force-non-dashboard)
      FORCE_NON_DASHBOARD=1
      ;;
    --no-dashboard)
      AUTO_DASHBOARD=0
      ;;
    --eval-only)
      MODE="eval"
      COLLECT_EVAL_ARGS=1
      ;;
    --genai-only)
      COMPAT_GENAI_ONLY=1
      ;;
    --with-eval)
      COMPAT_WITH_EVAL=1
      ;;
    *)
      DASH_ARGS+=("$1")
      ;;
  esac
  shift
done

AUTO_ENV_DIR="genai_env"
AUTO_ACTIVATE="$PROJECT_DIR/$AUTO_ENV_DIR/bin/activate"
AUTO_PY="$PROJECT_DIR/$AUTO_ENV_DIR/bin/python"

has_conda_genai() {
  if ! command -v conda >/dev/null 2>&1; then
    return 1
  fi
  conda run -n genai python -c "import sys" >/dev/null 2>&1
}

run_python() {
  if [[ -x "$AUTO_PY" ]]; then
    "$AUTO_PY" "$@"
    return $?
  fi

  if has_conda_genai; then
    conda run -n genai python "$@"
    return $?
  fi

  echo "[ERROR] Failed to find Python runtime."
  echo "Please verify either:"
  echo "  - $AUTO_ENV_DIR exists, or"
  echo "  - conda env \"genai\" is available."
  return 1
}

print_python_identity_with() {
  local py_exe="$1"
  if [[ ! -x "$py_exe" ]]; then
    echo "[WARN] Python executable not found: $py_exe"
    return 0
  fi
  "$py_exe" -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
}

print_python_identity_runtime() {
  run_python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
}

run_dashboard_lifecycle() {
  local life_cmd="${1:-status}"
  local life_args=(--port 8765)

  if [[ "$life_cmd" == "stop" && "$FORCE_NON_DASHBOARD" == "1" ]]; then
    life_args+=(--force-non-dashboard)
  fi

  run_python scripts/dashboard_lifecycle.py "$life_cmd" "${life_args[@]}"
}

post_dashboard_cleanup() {
  echo "[CLEANUP] Verifying complete dashboard shutdown..."
  local keep_force_flag="$FORCE_NON_DASHBOARD"
  FORCE_NON_DASHBOARD=1

  set +e
  run_dashboard_lifecycle stop
  local post_exit=$?
  set -e

  FORCE_NON_DASHBOARD="$keep_force_flag"

  if [[ "$post_exit" -eq 0 ]]; then
    echo "[CLEANUP] Port 8765 is clear."
  else
    echo "[CLEANUP] Port check failed; run Start_GenAI.sh --dashboard-stop once."
  fi

  return "$post_exit"
}

is_dashboard_running() {
  DASH_RUNNING=0
  local tmp_status
  tmp_status="$(mktemp "${TMPDIR:-/tmp}/genai_dashboard_status.XXXXXX")"

  set +e
  run_python scripts/dashboard_lifecycle.py status --port 8765 >"$tmp_status" 2>/dev/null
  set -e

  if grep -q '"dashboard_like": true' "$tmp_status"; then
    DASH_RUNNING=1
  fi

  rm -f "$tmp_status"
}

activate_conda_shell() {
  if ! command -v conda >/dev/null 2>&1; then
    return 1
  fi

  local conda_base
  conda_base="$(conda info --base 2>/dev/null || true)"
  if [[ -z "$conda_base" || ! -f "$conda_base/etc/profile.d/conda.sh" ]]; then
    return 1
  fi

  # shellcheck source=/dev/null
  source "$conda_base/etc/profile.d/conda.sh"
  if ! conda activate genai >/dev/null 2>&1; then
    return 1
  fi
  return 0
}

launch_dashboard_background() {
  mkdir -p "$PROJECT_DIR/logs"
  echo "[INFO] Launching dashboard in background..."
  nohup bash "$PROJECT_DIR/Start_GenAI.sh" --dashboard "${DASH_ARGS[@]}" >"$PROJECT_DIR/logs/dashboard_linux_launcher.log" 2>&1 </dev/null &
  echo "[INFO] Dashboard launcher PID: $!"
}

run_dashboard() {
  echo "===================================================="
  echo "  GenAI Local Dashboard Mode (Unified)"
  echo "===================================================="
  echo
  if [[ "$COMPAT_GENAI_ONLY" == "1" ]]; then
    echo "[INFO] --genai-only is now a no-op in local mode (single unified entrypoint)."
  fi
  if [[ "$COMPAT_WITH_EVAL" == "1" ]]; then
    echo "[INFO] --with-eval is now a no-op in local mode. Use --eval-only to run evaluation."
  fi
  echo "Dashboard URL default: http://127.0.0.1:8765"
  echo "Press Ctrl+C once to stop. Cleanup verification will run automatically."
  echo
  echo "[PRECHECK] Clearing stale dashboard listener on port 8765..."

  set +e
  run_dashboard_lifecycle stop
  local precheck_exit=$?
  set -e
  if [[ "$precheck_exit" -ne 0 ]]; then
    echo "[ERROR] Failed to clear dashboard listener. You can inspect with:"
    echo "  Start_GenAI.sh --dashboard-status"
    return "$precheck_exit"
  fi

  local dash_exit=0
  if [[ -x "$AUTO_PY" ]]; then
    echo "[1/1] Using auto environment python"
    print_python_identity_with "$AUTO_PY"

    set +e
    "$AUTO_PY" -m pipeline --dashboard "${DASH_ARGS[@]}"
    dash_exit=$?
    set -e
  elif has_conda_genai; then
    echo "[INFO] Auto environment not found, using conda env: genai"
    conda run -n genai python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"

    set +e
    conda run -n genai python -m pipeline --dashboard "${DASH_ARGS[@]}"
    dash_exit=$?
    set -e
  else
    echo "[ERROR] Failed to start local mode."
    echo "Please verify either:"
    echo "  - $AUTO_ENV_DIR exists, or"
    echo "  - conda env \"genai\" is available."
    return 1
  fi

  if [[ "$dash_exit" -ne 0 ]]; then
    echo "[WARN] Dashboard process exited with non-zero code."
    set +e
    post_dashboard_cleanup
    local cleanup_exit=$?
    set -e
    if [[ "$cleanup_exit" -ne 0 ]]; then
      echo "[WARN] Cleanup verification found residual listeners."
    fi
    return "$dash_exit"
  fi

  set +e
  post_dashboard_cleanup
  local cleanup_exit=$?
  set -e
  if [[ "$cleanup_exit" -ne 0 ]]; then
    echo "[WARN] Cleanup verification found residual listeners."
  fi

  return 0
}

run_terminal() {
  echo "===================================================="
  echo "  GenAI Local Terminal Mode (Unified)"
  echo "===================================================="
  echo

  if [[ "$COMPAT_GENAI_ONLY" == "1" ]]; then
    echo "[INFO] --genai-only is now a no-op in local mode (single unified entrypoint)."
  fi
  if [[ "$COMPAT_WITH_EVAL" == "1" ]]; then
    echo "[INFO] --with-eval is now a no-op in local mode. Use --eval-only to run evaluation."
  fi

  if [[ "$AUTO_DASHBOARD" == "1" ]]; then
    launch_dashboard_background
  fi

  if [[ -f "$AUTO_ACTIVATE" ]]; then
    echo "[1/1] Activating auto environment: $AUTO_ENV_DIR"
    # shellcheck source=/dev/null
    source "$AUTO_ACTIVATE"
    print_python_identity_runtime
    echo
    echo "Environment ready. You can run:"
    echo "  python chief.py --count 1"
    echo "  python -m pipeline --dashboard"
    echo "  Start_GenAI.sh --dashboard-status"
    echo "  Start_GenAI.sh --dashboard-stop"
    echo "  Start_GenAI.sh --dashboard-restart"
    echo "  Start_GenAI.sh --eval-only --input output --branch auto --post-process none"
    echo
    exec "${SHELL:-bash}" -i
  fi

  echo "[INFO] Auto environment not found, using conda env: genai"
  if ! activate_conda_shell; then
    echo "[ERROR] conda env \"genai\" not found or activation failed."
    return 1
  fi

  python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
  echo
  echo "Environment ready (conda: genai)."
  echo
  exec "${SHELL:-bash}" -i
}

run_eval() {
  echo "===================================================="
  echo "  GenAI Unified Eval Mode"
  echo "===================================================="
  echo

  if [[ "$COMPAT_GENAI_ONLY" == "1" ]]; then
    echo "[INFO] --genai-only ignored in --eval-only mode."
  fi
  if [[ "$COMPAT_WITH_EVAL" == "1" ]]; then
    echo "[INFO] --with-eval ignored in --eval-only mode."
  fi

  if [[ ${#EVAL_ARGS[@]} -eq 0 ]]; then
    EVAL_ARGS=(--input output --branch auto --post-process none)
    echo "[INFO] No eval args supplied. Using default: ${EVAL_ARGS[*]}"
  fi

  if [[ -x "$AUTO_PY" ]]; then
    print_python_identity_with "$AUTO_PY"
    echo "Running: $AUTO_PY evaluation/main.py ${EVAL_ARGS[*]}"
    set +e
    "$AUTO_PY" evaluation/main.py "${EVAL_ARGS[@]}"
    local eval_exit=$?
    set -e
    return "$eval_exit"
  fi

  if has_conda_genai; then
    echo "[INFO] Auto environment not found, fallback to conda env: genai"
    conda run -n genai python -c "import platform,sys; print('[INFO] Python executable:', sys.executable); print('[INFO] Python version:', platform.python_version())"
    set +e
    conda run -n genai python evaluation/main.py "${EVAL_ARGS[@]}"
    local eval_exit=$?
    set -e
    return "$eval_exit"
  fi

  echo "[ERROR] Failed to run eval mode."
  echo "Please verify either:"
  echo "  - $AUTO_ENV_DIR exists, or"
  echo "  - conda env \"genai\" is available."
  return 1
}

run_dashboard_status() {
  echo "===================================================="
  echo "  GenAI Dashboard Status"
  echo "===================================================="
  echo
  run_dashboard_lifecycle status
}

run_dashboard_stop() {
  echo "===================================================="
  echo "  GenAI Dashboard Stop"
  echo "===================================================="
  echo
  run_dashboard_lifecycle stop
}

run_dashboard_restart() {
  echo "===================================================="
  echo "  GenAI Dashboard Restart"
  echo "===================================================="
  echo
  run_dashboard_lifecycle stop
  run_dashboard
}

run_toggle_dashboard() {
  echo "===================================================="
  echo "  GenAI One-Click Toggle"
  echo "===================================================="
  echo
  is_dashboard_running

  if [[ "$DASH_RUNNING" == "1" ]]; then
    echo "[INFO] Dashboard detected on port 8765. Closing now..."
    set +e
    run_dashboard_lifecycle stop
    local stop_exit=$?
    set -e
    if [[ "$stop_exit" -eq 0 ]]; then
      echo "[DONE] Dashboard closed."
    fi
    return "$stop_exit"
  fi

  echo "[INFO] Dashboard not running. Opening now..."
  run_dashboard
}

case "$MODE" in
  eval)
    run_eval
    ;;
  toggle_dashboard)
    run_toggle_dashboard
    ;;
  dashboard)
    run_dashboard
    ;;
  dashboard_status)
    run_dashboard_status
    ;;
  dashboard_stop)
    run_dashboard_stop
    ;;
  dashboard_restart)
    run_dashboard_restart
    ;;
  terminal)
    run_terminal
    ;;
  *)
    run_terminal
    ;;
esac
