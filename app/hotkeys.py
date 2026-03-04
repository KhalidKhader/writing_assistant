from __future__ import annotations

import logging
from typing import Callable

from .platform_utils import is_macos_accessibility_trusted

logger = logging.getLogger(__name__)

try:
    from pynput import keyboard
    _PYNPUT_ERROR: str = ""
except Exception as _exc:
    keyboard = None  # type: ignore[assignment]
    _PYNPUT_ERROR = str(_exc)


class HotkeyManager:
    def __init__(self, callback: Callable[[str], None]) -> None:
        self.callback = callback
        self.listener = None
        self.enabled = False
        self.last_error = ""
        self.active_shortcuts = 0

    @staticmethod
    def _normalize_combo(combo: str) -> str:
        return combo.strip().lower().replace(" ", "")

    @staticmethod
    def _looks_valid_combo(combo: str) -> bool:
        """A valid pynput combo must contain at least one modifier in <...>
        notation plus a regular key, e.g. '<cmd>+<alt>+f'."""
        return "+" in combo and "<" in combo and ">" in combo

    def start(self, shortcuts: dict[str, str]) -> None:
        try:
            self.stop()
            self.last_error = ""
            self.active_shortcuts = 0

            if keyboard is None:
                self.enabled = False
                self.last_error = f"pynput unavailable{': ' + _PYNPUT_ERROR if _PYNPUT_ERROR else ''}"
                logger.warning("pynput is unavailable; global shortcuts disabled. %s", _PYNPUT_ERROR)
                return

            if not is_macos_accessibility_trusted():
                self.enabled = False
                self.last_error = "Accessibility permission missing"
                logger.warning("macOS accessibility permission missing; global shortcuts disabled")
                return

            mapping: dict[str, Callable[[], None]] = {}
            duplicates: list[str] = []
            invalid: list[str] = []

            for action, combo in shortcuts.items():
                if not combo:
                    continue
                normalized = self._normalize_combo(combo)
                if not self._looks_valid_combo(normalized):
                    invalid.append(f"{action}={combo!r} (expected format: <modifier>+<modifier>+key)")
                    continue
                if normalized in mapping:
                    duplicates.append(f"{action}={combo!r}")
                    continue
                mapping[normalized] = self._make_handler(action)

            if invalid:
                logger.warning("Invalid shortcut(s) ignored: %s", ", ".join(invalid))
            if duplicates:
                logger.warning("Duplicate shortcut(s) ignored: %s", ", ".join(duplicates))

            if not mapping:
                self.enabled = False
                self.last_error = "No valid shortcuts configured"
                return

            try:
                self.listener = keyboard.GlobalHotKeys(mapping)
                self.listener.start()
            except Exception as exc:
                # pynput raises OSError / RuntimeError when accessibility is denied
                self.enabled = False
                self.last_error = f"Shortcut listener failed: {exc}"
                logger.warning("GlobalHotKeys failed to start: %s", exc)
                return

            self.enabled = True
            self.active_shortcuts = len(mapping)

        except Exception:
            self.enabled = False
            self.last_error = "Failed to start global shortcuts"
            logger.exception("Failed to start global shortcuts")

    def stop(self) -> None:
        try:
            if self.listener:
                self.listener.stop()
                self.listener = None
            self.enabled = False
            self.active_shortcuts = 0
        except Exception:
            logger.exception("Failed to stop global shortcuts")

    def _make_handler(self, action: str) -> Callable[[], None]:
        def handler() -> None:
            self.callback(action)

        return handler
