from __future__ import annotations

import platform
import shutil


def platform_name() -> str:
    return platform.system()


def is_macos() -> bool:
    return platform_name() == "Darwin"


def is_windows() -> bool:
    return platform_name() == "Windows"


def is_linux() -> bool:
    return platform_name() == "Linux"


def shortcut_modifier() -> str:
    return "cmd" if is_macos() else "ctrl"


def has_ollama_cli() -> bool:
    return shutil.which("ollama") is not None


def ollama_install_url() -> str:
    return "https://ollama.com/download"


def accessibility_docs_url() -> str:
    return "https://support.apple.com/guide/mac-help/control-access-to-input-monitoring-on-mac-mchl4cedafb6/mac"


def is_macos_accessibility_trusted() -> bool:
    if not is_macos():
        return True
    try:
        from Quartz import AXIsProcessTrusted  # type: ignore[import]

        return bool(AXIsProcessTrusted())
    except ImportError:
        # Quartz (pyobjc-framework-Quartz) not installed — assume trusted
        # and let pynput raise naturally if permission is actually missing.
        return True
    except Exception:
        return False
