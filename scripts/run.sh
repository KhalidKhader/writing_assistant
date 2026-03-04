#!/usr/bin/env bash
set -euo pipefail

# ── IMPORTANT: do NOT run this script with sudo ─────────────────────────
# macOS Accessibility permission is granted per-executable under YOUR user
# account.  Running as root gives the app a different identity and pynput
# keyboard simulation will NOT work even if the permission appears granted.
if [[ "$(id -u)" -eq 0 ]]; then
    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║  ERROR: Do not run this script with sudo / as root!          ║"
    echo "║                                                              ║"
    echo "║  Run it as your normal user:                                 ║"
    echo "║      bash scripts/run.sh                                     ║"
    echo "║                                                              ║"
    echo "║  Then grant Accessibility permission to Terminal (or your    ║"
    echo "║  terminal app) in:                                           ║"
    echo "║  System Settings → Privacy & Security → Accessibility        ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    exit 1
fi

# ── Pick the best available Python ──────────────────────────────────────
pick_python() {
    for candidate in python3.11 python3.12 python3.13 python3; do
        if command -v "$candidate" >/dev/null 2>&1; then
            echo "$candidate"
            return
        fi
    done
    echo "python3"
}

PYTHON_BIN="$(pick_python)"
VENV_DIR=".venv"

# ── Detect a broken or incompatible venv ────────────────────────────────
recreate_venv=false

if [[ -d "$VENV_DIR" ]]; then
    # Broken: activate script is missing
    if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
        echo "Broken virtualenv at $VENV_DIR (no activate script) — recreating…"
        recreate_venv=true
    else
        # Check for Python binary being a dead symlink
        VENV_PYTHON="$VENV_DIR/bin/python"
        if [[ ! -x "$VENV_PYTHON" ]]; then
            echo "Broken virtualenv at $VENV_DIR (python binary missing) — recreating…"
            recreate_venv=true
        else
            CURRENT_PY_VER="$("$VENV_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")"
            # PySide6 does not support Python 3.14+ yet; recreate if needed
            if [[ "$(uname)" == "Darwin" && "$CURRENT_PY_VER" == "3.14" ]]; then
                echo "Recreating .venv: Python $CURRENT_PY_VER not yet supported by PySide6…"
                recreate_venv=true
            fi
        fi
    fi
fi

if [[ "$recreate_venv" == true ]]; then
    rm -rf "$VENV_DIR"
fi

# ── Create venv if it does not exist ────────────────────────────────────
if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    echo "Creating virtualenv with $PYTHON_BIN…"
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# ── Activate, install deps, run ─────────────────────────────────────────
# shellcheck source=/dev/null
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# Ensure we use the native macOS display, not offscreen
unset QT_QPA_PLATFORM  2>/dev/null || true
unset QT_PLUGIN_PATH   2>/dev/null || true

exec python main.py
