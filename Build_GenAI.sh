#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

AUTO_ENV_DIR="genai_env"
BASE_PY_EXE=""
AUTO_INSTALL_BUILD_TOOLS_IF_MISSING=1
SETUP_ARGS=()

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --install-build-tools-if-missing)
        AUTO_INSTALL_BUILD_TOOLS_IF_MISSING=1
        ;;
      --no-install-build-tools-if-missing)
        AUTO_INSTALL_BUILD_TOOLS_IF_MISSING=0
        ;;
      *)
        SETUP_ARGS+=("$1")
        ;;
    esac
    shift
  done
}

resolve_python311() {
  if command -v python3.11 >/dev/null 2>&1; then
    BASE_PY_EXE="$(command -v python3.11)"
    return 0
  fi

  if command -v python3 >/dev/null 2>&1; then
    local py3
    py3="$(command -v python3)"
    if "$py3" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >/dev/null 2>&1; then
      BASE_PY_EXE="$py3"
      return 0
    fi
  fi

  local candidate
  for candidate in \
    "$HOME/miniconda3/envs/genai/bin/python" \
    "$HOME/anaconda3/envs/genai/bin/python" \
    "$HOME/miniforge3/envs/genai/bin/python"; do
    if [[ -x "$candidate" ]] && "$candidate" -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >/dev/null 2>&1; then
      BASE_PY_EXE="$candidate"
      return 0
    fi
  done

  return 1
}

find_cpp_compiler() {
  if command -v g++ >/dev/null 2>&1; then
    command -v g++
    return 0
  fi
  if command -v clang++ >/dev/null 2>&1; then
    command -v clang++
    return 0
  fi
  return 1
}

install_build_tools() {
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "[WARN] apt-get was not found. Cannot auto-install build tools on this distro."
    return 0
  fi

  if [[ "$(id -u)" -eq 0 ]]; then
    if ! apt-get update || ! apt-get install -y build-essential; then
      echo "[WARN] Automatic build-essential installation failed."
    fi
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    if ! sudo apt-get update || ! sudo apt-get install -y build-essential; then
      echo "[WARN] Automatic build-essential installation failed."
    fi
    return 0
  fi

  echo "[WARN] sudo was not found. Please install build-essential manually."
  return 0
}

python_missing() {
  echo "===================================================="
  echo "  GenAI Build (Ubuntu/Linux)"
  echo "===================================================="
  echo "[ERROR] Python 3.11 executable was not found."
  echo
  echo "Install Python 3.11 first, then run this script again."
  echo "Suggested commands on Ubuntu:"
  echo "  sudo apt-get update"
  echo "  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev"
  exit 1
}

parse_args "$@"

if ! resolve_python311; then
  python_missing
fi

echo "===================================================="
echo "  GenAI Build (Ubuntu/Linux)"
echo "===================================================="
echo "This script auto-detects RTX 40/50 GPU and installs matching torch profile."
echo "It also clears stale exllamav2 torch_extensions cache to avoid old toolchain artifacts."
echo "Python 3.11: $BASE_PY_EXE"
echo "Environment path: $AUTO_ENV_DIR"
echo

if [[ ! -d "$PROJECT_DIR/models" ]]; then
  echo "[WARN] models/ folder was not found."
  echo "       Environment setup can continue, but runtime doctor will warn until models are copied."
  echo
fi

if CPP_COMPILER="$(find_cpp_compiler)"; then
  echo "[INFO] C++ compiler detected on PATH: $CPP_COMPILER"
else
  echo "[WARN] No C++ compiler was found on PATH (g++/clang++)."
  echo "       The project can still install and run, but some exllamav2 first-run JIT paths may be limited."
  if [[ "$AUTO_INSTALL_BUILD_TOOLS_IF_MISSING" == "1" ]]; then
    echo "[INFO] Trying to install build tools automatically (build-essential)..."
    install_build_tools
    if CPP_COMPILER="$(find_cpp_compiler)"; then
      echo "[INFO] Build tools detected after installation: $CPP_COMPILER"
    else
      echo "[WARN] Build tools are still not detected."
      echo "       Please install build-essential manually and run this script again."
    fi
  else
    echo "       Auto-install is disabled by --no-install-build-tools-if-missing."
  fi
fi
echo

"$BASE_PY_EXE" scripts/setup_env.py --env-path "$AUTO_ENV_DIR" --install-scope full --base-python "$BASE_PY_EXE" "${SETUP_ARGS[@]}"

GENAI_PY="$PROJECT_DIR/$AUTO_ENV_DIR/bin/python"
if [[ ! -x "$GENAI_PY" ]]; then
  GENAI_PY="$BASE_PY_EXE"
fi

if [[ -f "$PROJECT_DIR/evaluation/requirements.txt" ]]; then
  echo
  echo "[INFO] Installing evaluation extras into unified environment..."
  if ! "$GENAI_PY" -m pip install -r "$PROJECT_DIR/evaluation/requirements.txt" --constraint "$PROJECT_DIR/requirements.txt"; then
    echo "[WARN] Evaluation extras install with root constraints failed."
    echo "[INFO] Retrying evaluation extras without root constraints to avoid profile conflicts..."
    if ! "$GENAI_PY" -m pip install -r "$PROJECT_DIR/evaluation/requirements.txt"; then
      echo
      echo "[ERROR] Failed to install evaluation extras."
      exit 1
    fi
  fi
fi

echo
echo "[INFO] Running environment diagnostics..."
DOCTOR_PY="$PROJECT_DIR/$AUTO_ENV_DIR/bin/python"
if [[ ! -x "$DOCTOR_PY" ]]; then
  DOCTOR_PY="$BASE_PY_EXE"
fi

set +e
"$DOCTOR_PY" scripts/doctor.py --workspace-root . --expect-cuda auto
DOCTOR_EXIT=$?
set -e

if [[ "$DOCTOR_EXIT" -ge 2 ]]; then
  echo
  echo "[ERROR] Doctor found critical runtime issues."
  exit 2
fi

echo
echo "[OK] Environment setup finished."
echo "Next steps:"
echo "  1. bash Start_GenAI.sh --terminal"
echo "  2. bash Start_GenAI.sh --dashboard"
echo "  3. bash Start_GenAI.sh --eval-only --input output --branch auto --post-process none"
