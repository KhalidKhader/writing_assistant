from __future__ import annotations

import logging
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
    """Combines clipboard-based text capture and replacement with macOS focus
    management so that button-triggered actions work reliably (not only hotkeys)."""

    def __init__(self) -> None:
        self.controller = Controller() if Controller is not None else None
        self.modifier_key: object = None
        if Key is not None:
            self.modifier_key = Key.cmd if shortcut_modifier() == "cmd" else Key.ctrl

        self._lock = threading.Lock()
        self._last_external_app: str = ""

        # On macOS start a lightweight background thread that remembers the most
        # recent non-WA app that had focus.  This lets us switch back to it
        # before copy/paste even after the WA window has stolen focus.
        if sys.platform == "darwin":
            t = threading.Thread(target=self._poll_frontmost_app, daemon=True)
            t.start()

    # ── Background app tracker ────────────────────────────────────────────

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

    def _source_app(self) -> str:
        with self._lock:
            return self._last_external_app

    def snapshot_source_app(self) -> str:
        """Capture and return the current source app name.

        Call this on the main thread at hotkey-trigger time so the app is
        locked in *before* the executor thread picks up the request and the
        background polling thread can overwrite ``_last_external_app``.
        """
        return self._source_app()

    # ── Public API ────────────────────────────────────────────────────────

    def get_selected_text(self, source_app: str = "") -> str:
        try:
            if self.controller is None or self.modifier_key is None:
                return ""
            # Prefer the caller-supplied hint; fall back to the polled value.
            src = source_app or self._source_app()
            if sys.platform == "darwin" and src:
                _activate_app(src)
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
            src = source_app or self._source_app()
            if sys.platform == "darwin" and src:
                _activate_app(src)
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
