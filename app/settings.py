from __future__ import annotations

import json
import os
import platform
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


def _default_shortcuts() -> dict[str, str]:
    modifier = "<cmd>" if platform.system() == "Darwin" else "<ctrl>"
    return {
        "fix": f"{modifier}+<alt>+f",
        "summarize": f"{modifier}+<alt>+s",
        "translate_ar": f"{modifier}+<alt>+1",
        "translate_en": f"{modifier}+<alt>+2",
        "translate_es": f"{modifier}+<alt>+3",
        "translate_fr": f"{modifier}+<alt>+4",
        "translate_de": f"{modifier}+<alt>+5",
    }


DEFAULT_SETTINGS: dict[str, Any] = {
    "provider": "ollama",
    "output_mode": "replace",
    "polling": {"settings_reload_seconds": 2, "ollama_health_seconds": 5},
    "logging": {"level": "INFO", "path": "~/.writing_assistant/logs/app.log"},
    "ollama": {
        "endpoint": os.environ.get("OLLAMA_ENDPOINT", "http://localhost:11434"),
        "model": "mistral:7b-instruct-v0.2-q4_K_S",
        "keep_alive": "5m",
        "suggested_models": [
            "mistral:7b-instruct-v0.2-q4_K_S",
            "llama3.1:8b",
            "qwen2.5:7b",
            "gemma3:4b",
        ],
    },
    "openai": {
        "api_key": "",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
    },
    "gemini": {
        "api_key": "",
        "model": "gemini-3.1-flash-lite-preview",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
    },
    "shortcuts": _default_shortcuts(),
    "custom_languages": [
        "Arabic",
        "Chinese (Simplified)",
        "Dutch",
        "English",
        "French",
        "German",
        "Hebrew",
        "Hindi",
        "Italian",
        "Japanese",
        "Korean",
        "Portuguese",
        "Russian",
        "Spanish",
        "Turkish",
    ],
    "selected_custom_language": "Italian",
    "actions": {
        "fix": {
            "output_mode": "replace",
            "prompt": (
                "Correct grammar, spelling, punctuation, and capitalization while preserving meaning, "
                "tone, paragraph/line structure, bullet formatting, and all proper nouns/URLs/code blocks. "
                "Do not add explanations; return only the corrected text."
            ),
        },
        "summarize": {
            "output_mode": "replace",
            "prompt": (
                "Summarize into concise bullets covering key facts, decisions, risks, dates, owners, and action "
                "items. Keep original language unless asked otherwise, avoid speculation, and return only the summary."
            ),
        },
        "translate_ar": {
            "output_mode": "replace",
            "prompt": (
                "Translate accurately and naturally, preserving meaning, tone, line breaks, list numbering, and "
                "formatting. Keep names, brand terms, URLs, emails, numbers, and code unchanged unless context requires."
            ),
        },
        "translate_en": {
            "output_mode": "replace",
            "prompt": (
                "Translate accurately and naturally, preserving meaning, tone, line breaks, list numbering, and "
                "formatting. Keep names, brand terms, URLs, emails, numbers, and code unchanged unless context requires."
            ),
        },
        "translate_es": {
            "output_mode": "replace",
            "prompt": (
                "Translate accurately and naturally, preserving meaning, tone, line breaks, list numbering, and "
                "formatting. Keep names, brand terms, URLs, emails, numbers, and code unchanged unless context requires."
            ),
        },
        "translate_fr": {
            "output_mode": "replace",
            "prompt": (
                "Translate accurately and naturally, preserving meaning, tone, line breaks, list numbering, and "
                "formatting. Keep names, brand terms, URLs, emails, numbers, and code unchanged unless context requires."
            ),
        },
        "translate_de": {
            "output_mode": "replace",
            "prompt": (
                "Translate accurately and naturally, preserving meaning, tone, line breaks, list numbering, and "
                "formatting. Keep names, brand terms, URLs, emails, numbers, and code unchanged unless context requires."
            ),
        },
        "translate_custom": {
            "output_mode": "replace",
            "prompt": (
                "Translate accurately and naturally, preserving meaning, tone, line breaks, list numbering, and "
                "formatting. Keep names, brand terms, URLs, emails, numbers, and code unchanged unless context requires."
            ),
        },
    },
}

DEFAULT_SETTINGS["shortcuts"]["translate_custom"] = (
    "<cmd>+<alt>+6" if platform.system() == "Darwin" else "<ctrl>+<alt>+6"
)


def deep_merge(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in incoming.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


@dataclass
class SettingsManager:
    path: Path

    def __post_init__(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._callbacks: list[Callable[[dict[str, Any]], None]] = []
        self._watch_thread: threading.Thread | None = None
        self._watch_stop = threading.Event()
        self._settings = deep_merge(DEFAULT_SETTINGS, {})
        self._last_mtime = 0.0
        if not self.path.exists():
            self.save(DEFAULT_SETTINGS)
        self._settings = self.load()
        self._last_mtime = self.path.stat().st_mtime

    @staticmethod
    def default_path() -> Path:
        env_path = os.getenv("WRITING_ASSISTANT_SETTINGS")
        if env_path:
            return Path(env_path).expanduser().resolve()
        return Path.home() / ".writing_assistant" / "settings.json"

    def load(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as file:
            raw = json.load(file)
        self._settings = deep_merge(DEFAULT_SETTINGS, raw)
        # Lists are replaced by deep_merge, not unioned.
        # Always ensure every default language is available so users see the full list,
        # even if their saved settings only had a subset.
        default_langs: list[str] = DEFAULT_SETTINGS["custom_languages"]
        saved_langs: list[str] = self._settings.get("custom_languages") or []
        saved_set = set(saved_langs)
        missing = [l for l in default_langs if l not in saved_set]
        self._settings["custom_languages"] = saved_langs + missing
        return deepcopy(self._settings)

    def save(self, data: dict[str, Any]) -> None:
        merged = deep_merge(DEFAULT_SETTINGS, data)
        with self.path.open("w", encoding="utf-8") as file:
            json.dump(merged, file, ensure_ascii=False, indent=2)
        self._settings = merged
        self._last_mtime = self.path.stat().st_mtime
        self._emit()

    def get(self) -> dict[str, Any]:
        return deepcopy(self._settings)

    def update(self, path: list[str], value: Any) -> None:
        data = self.get()
        cursor = data
        for segment in path[:-1]:
            cursor = cursor.setdefault(segment, {})
        cursor[path[-1]] = value
        self.save(data)

    def on_change(self, callback: Callable[[dict[str, Any]], None]) -> None:
        self._callbacks.append(callback)

    def _emit(self) -> None:
        snapshot = self.get()
        for callback in self._callbacks:
            callback(snapshot)

    def start_watch(self, seconds: int = 2) -> None:
        if self._watch_thread and self._watch_thread.is_alive():
            return

        def loop() -> None:
            while not self._watch_stop.is_set():
                time.sleep(seconds)
                try:
                    mtime = self.path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if mtime != self._last_mtime:
                    self._last_mtime = mtime
                    self.load()
                    self._emit()

        self._watch_stop.clear()
        self._watch_thread = threading.Thread(target=loop, daemon=True)
        self._watch_thread.start()

    def stop_watch(self) -> None:
        self._watch_stop.set()
        if self._watch_thread and self._watch_thread.is_alive():
            self._watch_thread.join(timeout=1)
