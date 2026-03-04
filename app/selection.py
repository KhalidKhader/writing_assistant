from __future__ import annotations

import ctypes
import logging
import os
import subprocess
import sys
import threading
import time

import pyperclip

try:
    from pynput.keyboard import Controller, Key
except Exception:
    Controller = None
    Key = None

from .platform_utils import shortcut_modifier

logger = logging.getLogger(__name__)

# Keywords that identify the Writing Assistant process itself (so we skip it
# when tracking the "last external app that had focus").
_WA_KEYWORDS = {"python", "python3", "writing assistant", "writing_assistant"}

# ── Windows Win32 helpers ──────────────────────────────────────────────────

if sys.platform == "win32":
    _user32 = ctypes.windll.user32  # type: ignore[attr-defined]
else:
    _user32 = None


def _win_get_foreground_hwnd() -> int:
    """Return the current foreground window handle on Windows, or 0."""
    if _user32 is None:
        return 0
    try:
        return _user32.GetForegroundWindow()
    except Exception:
        return 0


def _win_hwnd_is_wa(hwnd: int) -> bool:
    """Return True if *hwnd* belongs to this process (the Writing Assistant)."""
    if not hwnd or _user32 is None:
        return False
    try:
        pid = ctypes.c_ulong(0)
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == os.getpid()
    except Exception:
        return False


def _win_activate_hwnd(hwnd: int) -> None:
    """Bring a Windows window to the foreground and wait for the OS to
    process the focus transfer (≈350 ms)."""
    if not hwnd or _user32 is None:
        return
    try:
        # AllowSetForegroundWindow is needed in some OS configurations
        _user32.AllowSetForegroundWindow(0xFFFFFFFF)
        # ShowWindow(hwnd, SW_RESTORE=9) un-minimises if needed
        _user32.ShowWindow(hwnd, 9)
        _user32.SetForegroundWindow(hwnd)
        time.sleep(0.35)  # let Windows finish the focus transfer
    except Exception:
        pass


# ── macOS helpers ──────────────────────────────────────────────────────────

def _get_frontmost_app() -> str:
    """Return the name of the current frontmost macOS process, or '' on other OSes."""
    if sys.platform != "darwin":
        return ""
    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'tell application "System Events" to get name of first process where it is frontmost',
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=2,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _activate_app(app_name: str) -> None:
    """Bring a macOS application to the foreground and wait for the OS to
    process the focus transfer (≈300 ms)."""
    if sys.platform != "darwin" or not app_name:
        return
    try:
        subprocess.run(
            ["osascript", "-e", f'tell application "{app_name}" to activate'],
            capture_output=True,
            timeout=2,
        )
        time.sleep(0.30)  # give macOS time to complete the focus transfer
    except Exception:
        pass


class SelectionService:
    """Combines clipboard-based text capture and replacement with platform focus
    management so that button-triggered actions work reliably (not only hotkeys)."""

    def __init__(self) -> None:
        self.controller = Controller() if Controller is not None else None
        self.modifier_key: object = None
        if Key is not None:
            self.modifier_key = Key.cmd if shortcut_modifier() == "cmd" else Key.ctrl

        self._lock = threading.Lock()
        self._last_external_app: str = ""   # macOS: app name
        self._last_external_hwnd: int = 0   # Windows: window handle

        # macOS: background thread polls the frontmost app name
        if sys.platform == "darwin":
            t = threading.Thread(target=self._poll_frontmost_app, daemon=True)
            t.start()

        # Windows: background thread polls the foreground window handle
        if sys.platform == "win32":
            t = threading.Thread(target=self._poll_foreground_hwnd, daemon=True)
            t.start()

    # ── Background app tracker (macOS) ───────────────────────────────────

    def _poll_frontmost_app(self) -> None:
        while True:
            time.sleep(0.5)
            try:
                name = _get_frontmost_app()
                if name and not any(kw in name.lower() for kw in _WA_KEYWORDS):
                    with self._lock:
                        self._last_external_app = name
            except Exception:
                pass

    # ── Background window tracker (Windows) ─────────────────────────────

    def _poll_foreground_hwnd(self) -> None:
        while True:
            time.sleep(0.3)
            try:
                hwnd = _win_get_foreground_hwnd()
                if hwnd and not _win_hwnd_is_wa(hwnd):
                    with self._lock:
                        self._last_external_hwnd = hwnd
            except Exception:
                pass

    def _source_app(self) -> str:
        with self._lock:
            return self._last_external_app

    def _source_hwnd(self) -> int:
        with self._lock:
            return self._last_external_hwnd

    def snapshot_source_app(self) -> str:
        """Capture and return the current source app name (macOS) or encode the
        Windows HWND as a string so it can be passed through the existing
        source_app: str parameter.

        Call this on the main thread at hotkey/button-trigger time so the
        handle is locked in *before* the executor thread picks up the request.
        """
        if sys.platform == "win32":
            hwnd = _win_get_foreground_hwnd()
            if hwnd and not _win_hwnd_is_wa(hwnd):
                with self._lock:
                    self._last_external_hwnd = hwnd
            return f"__hwnd__:{self._source_hwnd()}"
        return self._source_app()

    # ── Internal focus-restore helpers ───────────────────────────────────

    def _restore_focus(self, source_app: str) -> None:
        """Re-activate the source window/app before sending keyboard input."""
        if sys.platform == "darwin":
            src = source_app or self._source_app()
            if src:
                _activate_app(src)
        elif sys.platform == "win32":
            hwnd = 0
            if source_app and source_app.startswith("__hwnd__:"):
                try:
                    hwnd = int(source_app.split(":", 1)[1])
                except ValueError:
                    pass
            if not hwnd:
                hwnd = self._source_hwnd()
            if hwnd:
                _win_activate_hwnd(hwnd)

    # ── Public API ────────────────────────────────────────────────────────

    def get_selected_text(self, source_app: str = "") -> str:
        try:
            if self.controller is None or self.modifier_key is None:
                return ""
            self._restore_focus(source_app)
            with self.controller.pressed(self.modifier_key):
                self.controller.tap("c")
            time.sleep(0.25)  # give OS time to update clipboard
            return pyperclip.paste() or ""
        except Exception:
            logger.exception("Failed to read selected text")
            return ""

    def replace_selected_text(self, value: str, source_app: str = "") -> None:
        try:
            if self.controller is None or self.modifier_key is None:
                return
            self._restore_focus(source_app)
            pyperclip.copy(value)
            time.sleep(0.15)
            with self.controller.pressed(self.modifier_key):
                self.controller.tap("v")
        except Exception:
            logger.exception("Failed to replace selected text")

    def copy_to_clipboard(self, value: str) -> None:
        try:
            pyperclip.copy(value)
        except Exception:
            logger.exception("Failed to copy text to clipboard")
