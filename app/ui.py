from __future__ import annotations

import logging
import os
import sys
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from PySide6.QtCore import QPoint, QRect, QSize, QTimer, Qt, Signal, Slot
from PySide6.QtGui import QAction, QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QSystemTrayIcon,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .hotkeys import HotkeyManager
from .logging_utils import configure_logging
from .operations import OperationBuilder
from .platform_utils import (
    accessibility_docs_url,
    has_ollama_cli,
    is_macos_accessibility_trusted,
    ollama_install_url,
    platform_name,
)
from .providers import ProviderError, ProviderManager
from .selection import SelectionService
from .settings import SettingsManager

logger = logging.getLogger(__name__)


def _safe_call(fn_name: str, fn, *args, **kwargs):
    """Call fn(*args, **kwargs) and swallow any exception, logging it instead.

    Used as the last safety net for every Qt slot so that no exception ever
    escapes into PySide6's C++ layer (which would trigger SIGTRAP on macOS).
    """
    try:
        return fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        logger.exception("Unhandled exception in slot %s", fn_name)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Shared style constants
# ─────────────────────────────────────────────────────────────────────────────
APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: Arial, sans-serif;
    font-size: 14px;
}
QTabWidget::pane {
    border: 1px solid #313244;
    border-radius: 6px;
    background-color: #1e1e2e;
}
QTabBar::tab {
    background: #181825;
    color: #a6adc8;
    padding: 8px 20px;
    border: 1px solid #313244;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    min-width: 100px;
}
QTabBar::tab:selected {
    background: #1e1e2e;
    color: #cba6f7;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    background: #252535;
    color: #cdd6f4;
    border-color: #45475a;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 500;
    min-height: 30px;
}
QPushButton:hover {
    background-color: #3d3f53;
    border-color: #7287fd;
    color: #ffffff;
}
QPushButton:pressed {
    background-color: #585b70;
    border-color: #89b4fa;
}
QPushButton#primary {
    background-color: #7287fd;
    color: #1e1e2e;
    border-color: #7287fd;
    font-weight: 700;
}
QPushButton#primary:hover {
    background-color: #8296ff;
    border-color: #89b4fa;
    color: #1e1e2e;
}
QPushButton#primary:pressed {
    background-color: #6272e8;
}
QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
    border-color: #f38ba8;
    font-weight: 600;
}
QPushButton#danger:hover {
    background-color: #ff9eb9;
    border-color: #ff9eb9;
}
QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
    border-color: #a6e3a1;
    font-weight: 700;
}
QPushButton#success:hover {
    background-color: #bdf0b8;
    border-color: #bdf0b8;
}
QPushButton#accent {
    background-color: #cba6f7;
    color: #1e1e2e;
    border-color: #cba6f7;
    font-weight: 700;
}
QPushButton#accent:hover {
    background-color: #d8b8ff;
    border-color: #d8b8ff;
}
QComboBox {
    background-color: #252535;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 32px 6px 12px;
    min-height: 30px;
    min-width: 140px;
}
QComboBox:hover {
    border-color: #7287fd;
    background-color: #2e2e42;
}
QComboBox:focus {
    border-color: #89b4fa;
    background-color: #2e2e42;
}
QComboBox:on {
    border-color: #89b4fa;
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
}
QComboBox::drop-down {
    border: none;
    width: 28px;
    border-left: 1px solid #45475a;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
}
QComboBox::drop-down:hover {
    background-color: #45475a;
}
QComboBox::down-arrow {
    width: 8px;
    height: 8px;
    border-left: 2px solid #a6adc8;
    border-bottom: 2px solid #a6adc8;
    margin-right: 4px;
}
QComboBox QAbstractItemView {
    background-color: #1e1e2e;
    color: #cdd6f4;
    selection-background-color: transparent;
    selection-color: #cba6f7;
    border: 1px solid #585b70;
    border-top: none;
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 8px 14px;
    min-height: 28px;
    border-radius: 4px;
    color: #cdd6f4;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #313244;
    color: #cdd6f4;
}
QComboBox QAbstractItemView::item:selected {
    background-color: #45475a;
    color: #cba6f7;
    font-weight: 600;
}
QLineEdit {
    background-color: #252535;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 30px;
}
QLineEdit:hover {
    border-color: #7f849c;
    background-color: #2e2e42;
}
QLineEdit:focus {
    border-color: #89b4fa;
    background-color: #2e2e42;
}
QTextEdit {
    background-color: #181825;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 10px;
    selection-background-color: #585b70;
    selection-color: #cdd6f4;
}
QTextEdit:hover { border-color: #7f849c; }
QTextEdit:focus { border-color: #89b4fa; }
QLabel {
    color: #a6adc8;
    padding: 2px 0;
}
QLabel#title {
    color: #cba6f7;
    font-size: 15px;
    font-weight: 700;
}
QLabel#section {
    color: #89b4fa;
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
}
QLabel#status_ok { color: #a6e3a1; font-weight: 600; }
QLabel#status_warn { color: #f9e2af; font-weight: 600; }
QLabel#status_err { color: #f38ba8; font-weight: 600; }
QGroupBox {
    color: #89b4fa;
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: 600;
    font-size: 12px;
    background-color: #1a1a2a;
}
QGroupBox:hover {
    border-color: #45475a;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    top: -2px;
    padding: 2px 6px;
    color: #89b4fa;
    background-color: #1e1e2e;
    border-radius: 3px;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical {
    background: #181825;
    width: 10px;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 5px;
    min-height: 20px;
}
QScrollBar::handle:vertical:hover { background: #7287fd; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #181825;
    height: 8px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal {
    background: #45475a;
    border-radius: 4px;
    min-width: 20px;
}
QScrollBar::handle:horizontal:hover { background: #7287fd; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QFrame#divider {
    background-color: #313244;
    max-height: 1px;
    min-height: 1px;
}
QFrame#access_banner {
    background-color: #2a1f2e;
    border: 1px solid #f38ba8;
    border-radius: 8px;
    padding: 4px;
}
QLabel#access_label {
    color: #f38ba8;
    font-size: 13px;
    font-weight: 600;
}
QPushButton#access_btn {
    background-color: #f38ba8;
    color: #1e1e2e;
    border: none;
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 700;
}
QPushButton#access_btn:hover { background-color: #ff9eb9; }
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #585b70;
    border-radius: 5px;
    padding: 5px 8px;
    font-size: 12px;
    opacity: 230;
}
QMenu {
    background-color: #1e1e2e;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item {
    padding: 7px 24px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #313244;
    color: #cba6f7;
}
QMenu::separator {
    height: 1px;
    background: #313244;
    margin: 4px 8px;
}
"""

# Per-language avatar colors (shown as circular badges on action buttons)
LANG_COLORS: dict[str, str] = {
    "AR": "#f38ba8",  # Arabic   – rose
    "EN": "#89b4fa",  # English  – blue
    "ES": "#f9e2af",  # Spanish  – yellow
    "FR": "#74c7ec",  # French   – sky
    "DE": "#a6e3a1",  # German   – green
    "HE": "#fab387",  # Hebrew   – peach
    "IT": "#cba6f7",  # Italian  – lavender
    "PT": "#94e2d5",  # Portuguese – teal
    "RU": "#eba0ac",  # Russian  – flamingo
    "ZH": "#e5c890",  # Chinese  – gold
    "JA": "#f2cdcd",  # Japanese – rosewater
    "KO": "#b4befe",  # Korean   – lavender-blue
    "TR": "#a6d189",  # Turkish  – green2
    "HI": "#ef9f76",  # Hindi    – orange
    "NL": "#81c8be",  # Dutch    – teal2
}


class LangButton(QPushButton):
    """Action button with a small colored circular letter-avatar on the left.

    Renders reliably on every platform without relying on flag emoji support
    (Windows does not render regional-indicator emoji as actual flags).
    """

    def __init__(self, code: str, language: str, parent=None) -> None:
        # Leading spaces to leave room for the painted avatar circle
        super().__init__(f"   {language}", parent)
        self._code = code[:2].upper()
        color_hex = LANG_COLORS.get(self._code, "#cba6f7")
        self._circle_color = QColor(color_hex)
        self.setMinimumHeight(36)
        self.setCursor(Qt.PointingHandCursor)

    def paintEvent(self, event) -> None:  # type: ignore[override]
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 13
        cx = 22
        cy = self.height() // 2
        # Filled circle
        painter.setBrush(self._circle_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)
        # Two-letter code inside circle
        painter.setPen(QColor("#1e1e2e"))
        f = QFont("Arial", 8)
        f.setBold(True)
        painter.setFont(f)
        painter.drawText(QRect(cx - r, cy - r, r * 2, r * 2), Qt.AlignmentFlag.AlignCenter, self._code)
        painter.end()


LANG_CHIP_ACTIVE = (
    "QPushButton {"
    "  background:#cba6f7; color:#1e1e2e; border-radius:12px; padding:4px 14px;"
    "  font-weight:700; font-size:12px; min-height:26px; border:none;"
    "}"
    "QPushButton:hover {"
    "  background:#d8b8ff; color:#1e1e2e;"
    "}"
    "QPushButton:pressed {"
    "  background:#b890f7;"
    "}"
)
LANG_CHIP_INACTIVE = (
    "QPushButton {"
    "  background:#252535; color:#a6adc8; border-radius:12px; padding:4px 14px;"
    "  font-size:12px; min-height:26px; border:1px solid #45475a;"
    "}"
    "QPushButton:hover {"
    "  background:#313244; color:#cdd6f4; border-color:#7287fd;"
    "}"
    "QPushButton:pressed {"
    "  background:#45475a; color:#cdd6f4;"
    "}"
)


# ─────────────────────────────────────────────────────────────────────────────
# Ring launcher  (draggable floating button)
# ─────────────────────────────────────────────────────────────────────────────
class RingLauncher(QWidget):
    """Small always-on-top draggable button.  Drag to move, click to toggle.

    The inner QPushButton normally consumes all mouse events, so drag and
    click logic is routed through an event-filter installed on the button.
    """

    def __init__(self, on_toggle) -> None:
        super().__init__()
        self.on_toggle = on_toggle
        self._drag_origin: QPoint | None = None
        self._moved = False
        self.setWindowTitle("Writing Assistant")
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(60, 60)

        self.btn = QPushButton("WA", self)
        self.btn.setGeometry(0, 0, 60, 60)
        self.btn.setStyleSheet(
            "QPushButton {"
            "  border-radius: 30px;"
            "  font-weight: 800;"
            "  font-size: 14px;"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #7287fd, stop:1 #cba6f7);"
            "  color: #1e1e2e;"
            "  border: 2px solid #89b4fa;"
            "}"
            "QPushButton:hover {"
            "  background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "    stop:0 #89b4fa, stop:1 #cba6f7);"
            "}"
            "QPushButton:pressed { background: #585b70; }"
        )
        self.btn.setToolTip("Click to show/hide · Drag to move")
        # Install event filter so we intercept mouse events before the button
        # consumes them; this enables both drag-to-move and click-to-toggle.
        self.btn.installEventFilter(self)
        # clicked fires reliably for non-drag releases (after eventFilter runs)
        self.btn.clicked.connect(self._on_btn_clicked)

    # ── Event filter on the inner button ─────────────────────────────────────
    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        try:
            from PySide6.QtCore import QEvent
            if obj is self.btn:
                t = event.type()
                if t == QEvent.Type.MouseButtonPress and event.button() == Qt.LeftButton:
                    self._drag_origin = (
                        event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    )
                    self._moved = False
                    # Don't consume — let btn show the pressed style
                elif t == QEvent.Type.MouseMove and bool(event.buttons() & Qt.LeftButton):
                    if self._drag_origin is not None:
                        self.move(event.globalPosition().toPoint() - self._drag_origin)
                        self._moved = True
                        return True  # consume so Qt doesn't pass move to btn internals
                elif t == QEvent.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
                    # _on_btn_clicked fires right after; just ensure we can read _moved
                    pass
        except Exception:
            logger.exception("RingLauncher eventFilter error")
        try:
            return super().eventFilter(obj, event)
        except Exception:
            return False

    def _on_btn_clicked(self) -> None:
        """Called by btn.clicked — only toggle when it was a click, not a drag."""
        if not self._moved:
            try:
                self.on_toggle()
            except Exception:
                pass  # never let a toggle error crash the ring
        self._moved = False
        self._drag_origin = None


# ─────────────────────────────────────────────────────────────────────────────
# Language chip row
# ─────────────────────────────────────────────────────────────────────────────
class LanguageChips(QWidget):
    """Horizontal row of pill/chip buttons for language selection."""

    language_selected = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._layout.addStretch()
        self._selected: str = ""
        self._buttons: dict[str, QPushButton] = {}

    def set_languages(self, languages: list[str], selected: str = "") -> None:
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._buttons.clear()
        for lang in languages:
            btn = QPushButton(lang)
            btn.setCheckable(False)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(LANG_CHIP_ACTIVE if lang == selected else LANG_CHIP_INACTIVE)
            btn.clicked.connect(lambda _checked, l=lang: self._select(l))
            self._layout.insertWidget(self._layout.count() - 1, btn)
            self._buttons[lang] = btn
        self._selected = selected

    def _select(self, lang: str) -> None:
        for name, btn in self._buttons.items():
            btn.setStyleSheet(LANG_CHIP_ACTIVE if name == lang else LANG_CHIP_INACTIVE)
        self._selected = lang
        self.language_selected.emit(lang)

    def add_language(self, lang: str) -> None:
        if lang in self._buttons:
            self._select(lang)
            return
        all_langs = list(self._buttons.keys()) + [lang]
        self.set_languages(all_langs, lang)
        self.language_selected.emit(lang)

    def remove_language(self, lang: str) -> None:
        current = list(self._buttons.keys())
        current = [l for l in current if l != lang]
        new_sel = current[0] if current else ""
        self.set_languages(current, new_sel)
        if new_sel:
            self.language_selected.emit(new_sel)

    @property
    def selected(self) -> str:
        return self._selected

    @property
    def all_languages(self) -> list[str]:
        return list(self._buttons.keys())


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────
class FloatingBar(QMainWindow):
    notify_signal = Signal(str)
    apply_output_signal = Signal(str, str, str)  # output_mode, output, source_app
    # These signals marshal cross-thread calls back to the main thread
    _settings_reload_signal = Signal(object)   # carries a dict snapshot
    _models_refresh_signal = Signal()
    # Hotkeys fire from a pynput background thread; use a signal for safe dispatch
    _hotkey_trigger_signal = Signal(str)
    # Streaming: each token/chunk updates the preview on the main thread
    _stream_preview_signal = Signal(str)
    # Background health/model list results marshalled back to main thread
    _health_update_signal = Signal(object)   # carries list[str] of issues
    _models_loaded_signal = Signal(object)   # carries tuple(list[str], str, str)
    # Pull model progress: True=show spinner, False=hide
    _pull_progress_signal = Signal(bool)

    def __init__(self, settings_manager: SettingsManager) -> None:
        super().__init__()
        self.settings_manager = settings_manager
        self.settings = settings_manager.get()
        self.providers = ProviderManager()
        self.selection = SelectionService()
        self.ops = OperationBuilder()
        self.hotkeys = HotkeyManager(self._on_hotkey)
        self.executor = ThreadPoolExecutor(max_workers=4)
        # Tracks which provider the model combo currently reflects so we only
        # trigger a model-list refresh when the provider actually changes.
        self._active_provider: str = self.settings.get("provider", "ollama")

        self.notify_signal.connect(self._show_notification)
        self.apply_output_signal.connect(self._apply_output)
        # Force QueuedConnection so _apply_settings_change always runs on the
        # next event-loop tick — never synchronously inside another slot dispatch
        # (e.g. on_provider_changed → update → save → _emit).
        self._settings_reload_signal.connect(self._apply_settings_change, Qt.QueuedConnection)
        self._models_refresh_signal.connect(self.refresh_models)
        self._hotkey_trigger_signal.connect(self._on_hotkey_main)
        self._stream_preview_signal.connect(self._update_preview_stream)
        self._health_update_signal.connect(self._apply_health_result)
        self._models_loaded_signal.connect(self._apply_models_result)
        self._pull_progress_signal.connect(self._set_pull_progress)

        self.setStyleSheet(APP_STYLESHEET)
        self._build_ui()
        self._wire_signals()
        self.refresh_models()
        self.apply_settings_to_ui()
        self.settings_manager.on_change(self._on_settings_changed)

        poll_interval = int(self.settings["polling"].get("ollama_health_seconds", 5) * 1000)
        self.health_timer = QTimer(self)
        self.health_timer.timeout.connect(self.refresh_health)
        self.health_timer.start(max(1000, poll_interval))

        self._start_hotkeys_safely()
        self.refresh_health()
        self.run_preflight()

    # ── Layout ──────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Writing Assistant")
        self.setMinimumSize(1000, 700)
        self.resize(1180, 800)

        root = QWidget(self)
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(10)

        # ── Header bar ──────────────────────────────────────────────────────
        header = QHBoxLayout()
        brand = QLabel("✍  Writing Assistant")
        brand.setObjectName("title")
        header.addWidget(brand)
        header.addStretch()

        self.health_label = QLabel("● checking…")
        self.health_label.setObjectName("status_warn")
        header.addWidget(self.health_label)

        self.status_label = QLabel("Ready")
        self.status_label.setObjectName("status_ok")
        self.status_label.setMinimumWidth(280)
        header.addWidget(self.status_label)

        outer.addLayout(header)
        outer.addWidget(self._hr())

        # ── macOS accessibility warning banner ───────────────────────────────
        self.access_banner = self._build_access_banner()
        outer.addWidget(self.access_banner)

        # ── Provider / model row ─────────────────────────────────────────────
        prov_row = QHBoxLayout()
        prov_row.setSpacing(10)

        prov_lbl = QLabel("Provider")
        prov_lbl.setObjectName("section")
        prov_row.addWidget(prov_lbl)

        self.provider_combo = QComboBox()
        self.provider_combo.addItem("🤖  Ollama  (local)", "ollama")
        self.provider_combo.addItem("🔑  OpenAI", "openai")
        self.provider_combo.addItem("💎  Gemini", "gemini")
        self.provider_combo.setMinimumWidth(170)
        self.provider_combo.setCursor(Qt.PointingHandCursor)
        self.provider_combo.setToolTip("Select the AI provider to use")
        prov_row.addWidget(self.provider_combo)

        prov_row.addWidget(QLabel("Model"))
        self.model_combo = QComboBox()
        self.model_combo.setMinimumWidth(240)
        self.model_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.model_combo.setCursor(Qt.PointingHandCursor)
        prov_row.addWidget(self.model_combo)

        prov_row.addWidget(QLabel("Output"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("↩  Replace in place", "replace")
        self.mode_combo.addItem("📋  Copy to clipboard", "clipboard")
        self.mode_combo.setMinimumWidth(175)
        self.mode_combo.setCursor(Qt.PointingHandCursor)
        self.mode_combo.setToolTip(
            "Replace: overwrite the selected text in the source app.\n"
            "Clipboard: copy the result — paste manually wherever you like."
        )
        prov_row.addWidget(self.mode_combo)

        self.pull_model_button = QPushButton("⬇  Pull Model")
        self.pull_model_button.setObjectName("primary")
        self.pull_model_button.setToolTip("Pull the selected Ollama model (Ollama only)")
        self.pull_model_button.setCursor(Qt.PointingHandCursor)
        prov_row.addWidget(self.pull_model_button)

        self.pull_progress = QProgressBar()
        self.pull_progress.setRange(0, 0)  # indeterminate / spinning
        self.pull_progress.setFixedWidth(120)
        self.pull_progress.setFixedHeight(18)
        self.pull_progress.setTextVisible(False)
        self.pull_progress.setStyleSheet(
            "QProgressBar { border: 1px solid #45475a; border-radius: 9px;"
            "  background: #252535; }"
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 #7287fd, stop:1 #cba6f7); border-radius: 8px; }"
        )
        self.pull_progress.setVisible(False)
        prov_row.addWidget(self.pull_progress)

        self.toggle_ring_button = QPushButton("◉  Ring")
        self.toggle_ring_button.setToolTip("Show/hide the floating ring button")
        self.toggle_ring_button.setCursor(Qt.PointingHandCursor)
        prov_row.addWidget(self.toggle_ring_button)

        self.minimize_button = QPushButton("⊟  Tray")
        self.minimize_button.setToolTip("Minimize to system tray")
        self.minimize_button.setCursor(Qt.PointingHandCursor)
        prov_row.addWidget(self.minimize_button)

        outer.addLayout(prov_row)
        outer.addWidget(self._hr())

        # ── Tabs ─────────────────────────────────────────────────────────────
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        self.tabs.addTab(self._build_actions_tab(), "🚀  Actions")
        self.tabs.addTab(self._build_prompts_tab(), "📝  Prompts")
        self.tabs.addTab(self._build_settings_tab(), "⚙  Settings")

        # ── Tray & ring ──────────────────────────────────────────────────────
        self._build_tray()
        self.ring = RingLauncher(self.toggle_visibility)
        self.ring.move(80, 80)
        self.ring.show()

    # ── Actions tab ─────────────────────────────────────────────────────────

    def _build_actions_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # Quick-action buttons
        btn_group = QGroupBox("Quick Actions  (select text first)")
        btn_layout = QGridLayout(btn_group)
        btn_layout.setSpacing(8)

        self.fix_button = QPushButton("✏  Fix Grammar")
        self.fix_button.setObjectName("success")
        self.fix_button.setToolTip("Fix grammar, spelling, punctuation and casing")
        self.fix_button.setCursor(Qt.PointingHandCursor)

        self.summary_button = QPushButton("📋  Summarize")
        self.summary_button.setObjectName("accent")
        self.summary_button.setToolTip("Summarize the selected text")
        self.summary_button.setCursor(Qt.PointingHandCursor)

        self.settings_button = QPushButton("💾  Save Settings")
        self.settings_button.setObjectName("primary")
        self.settings_button.setCursor(Qt.PointingHandCursor)

        btn_layout.addWidget(self.fix_button, 0, 0)
        btn_layout.addWidget(self.summary_button, 0, 1)
        btn_layout.addWidget(self.settings_button, 0, 2)
        layout.addWidget(btn_group)

        # Language section
        lang_group = QGroupBox("Translate To")
        lang_vlayout = QVBoxLayout(lang_group)
        lang_vlayout.setSpacing(10)

        # Built-in language buttons
        builtin_row = QHBoxLayout()
        builtin_row.setSpacing(8)
        self.ar_button = LangButton("AR", "Arabic")
        self.en_button = LangButton("EN", "English")
        self.es_button = LangButton("ES", "Spanish")
        self.fr_button = LangButton("FR", "French")
        self.de_button = LangButton("DE", "German")
        for b in [self.ar_button, self.en_button, self.es_button, self.fr_button, self.de_button]:
            builtin_row.addWidget(b)
        builtin_row.addStretch()
        lang_vlayout.addLayout(builtin_row)

        # Custom language select row
        chip_lbl = QLabel("Custom Language")
        chip_lbl.setObjectName("section")
        lang_vlayout.addWidget(chip_lbl)

        add_row = QHBoxLayout()
        add_row.setSpacing(8)
        self.custom_language_combo = QComboBox()
        self.custom_language_combo.setMinimumWidth(260)
        self.custom_language_combo.setToolTip("Select target language for Custom translation")
        self.custom_language_combo.setCursor(Qt.PointingHandCursor)
        self.custom_language_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.custom_button = QPushButton("▶  Translate Selected")
        self.custom_button.setObjectName("accent")
        self.custom_button.setCursor(Qt.PointingHandCursor)
        add_row.addWidget(self.custom_language_combo)
        add_row.addWidget(self.custom_button)
        lang_vlayout.addLayout(add_row)
        layout.addWidget(lang_group)

        # Output preview
        out_group = QGroupBox("Last Output Preview")
        out_layout = QVBoxLayout(out_group)
        self.output_preview = QTextEdit()
        self.output_preview.setReadOnly(True)
        self.output_preview.setMinimumHeight(140)
        self.output_preview.setPlaceholderText("AI output will appear here after running an action…")
        self.output_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        out_layout.addWidget(self.output_preview)

        # Action buttons for the preview result
        preview_btn_row = QHBoxLayout()
        preview_btn_row.setSpacing(8)
        self.copy_result_button = QPushButton("📋  Copy Result")
        self.copy_result_button.setObjectName("primary")
        self.copy_result_button.setToolTip("Copy the AI output to clipboard")
        self.copy_result_button.setCursor(Qt.PointingHandCursor)
        self.paste_result_button = QPushButton("↩  Paste to Source")
        self.paste_result_button.setObjectName("accent")
        self.paste_result_button.setToolTip(
            "Replace the selected text in the source app with the AI output.\n"
            "Make sure the target app still has the text selected."
        )
        self.paste_result_button.setCursor(Qt.PointingHandCursor)
        preview_btn_row.addStretch()
        preview_btn_row.addWidget(self.copy_result_button)
        preview_btn_row.addWidget(self.paste_result_button)
        out_layout.addLayout(preview_btn_row)
        layout.addWidget(out_group, 1)

        return page

    # ── Prompts tab ──────────────────────────────────────────────────────────

    def _build_prompts_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        hint = QLabel(
            "Customize the instruction given to the AI for each operation.  "
            "Changes are applied when you click <b>Save Settings</b>.  "
            "Use explicit constraints (tone, formatting, output shape) for better results."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#a6adc8; padding:4px 0;")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setSpacing(12)

        self.fix_prompt = QTextEdit()
        self.fix_prompt.setMinimumHeight(88)
        self.fix_prompt.setPlaceholderText(
            "E.g. Correct grammar and punctuation while preserving tone, structure, lists, and line breaks. Return only corrected text."
        )

        self.summary_prompt = QTextEdit()
        self.summary_prompt.setMinimumHeight(88)
        self.summary_prompt.setPlaceholderText(
            "E.g. Summarize in concise bullets with key facts, decisions, risks, dates, and action items."
        )

        self.translate_prompt = QTextEdit()
        self.translate_prompt.setMinimumHeight(88)
        self.translate_prompt.setPlaceholderText(
            "E.g. Translate naturally while preserving formatting, terminology, proper names, URLs, numbers, and code blocks."
        )

        form.addRow("✏  Fix prompt", self.fix_prompt)
        form.addRow("📋  Summary prompt", self.summary_prompt)
        form.addRow("🌐  Translate prompt", self.translate_prompt)
        layout.addLayout(form)

        save_btn = QPushButton("💾  Save Prompts")
        save_btn.setObjectName("primary")
        save_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        save_btn.setCursor(Qt.PointingHandCursor)
        save_btn.clicked.connect(self.save_settings_from_ui)
        layout.addWidget(save_btn, alignment=Qt.AlignRight)
        layout.addStretch()

        return page

    # ── Settings tab ─────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        scroll.setWidget(inner)
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(18)

        # Provider credentials
        cred_group = QGroupBox("Provider Credentials & Endpoints")
        cred_form = QFormLayout(cred_group)
        cred_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        cred_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        cred_form.setSpacing(10)

        self.ollama_endpoint_input = QLineEdit()
        self.ollama_endpoint_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.ollama_keep_alive_input = QLineEdit()
        self.openai_key_input = QLineEdit()
        self.openai_key_input.setEchoMode(QLineEdit.Password)
        self.openai_key_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.openai_base_url_input = QLineEdit()
        self.openai_base_url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.gemini_key_input = QLineEdit()
        self.gemini_key_input.setEchoMode(QLineEdit.Password)
        self.gemini_key_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.gemini_base_url_input = QLineEdit()
        self.gemini_base_url_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        ollama_lbl = QLabel("🤖  Ollama")
        ollama_lbl.setObjectName("section")
        cred_form.addRow(ollama_lbl, QLabel(""))
        cred_form.addRow("Endpoint", self.ollama_endpoint_input)
        cred_form.addRow("Keep-alive", self.ollama_keep_alive_input)

        openai_lbl = QLabel("🔑  OpenAI")
        openai_lbl.setObjectName("section")
        cred_form.addRow(openai_lbl, QLabel(""))
        cred_form.addRow("API key", self.openai_key_input)
        cred_form.addRow("Base URL", self.openai_base_url_input)

        gemini_lbl = QLabel("💎  Gemini")
        gemini_lbl.setObjectName("section")
        cred_form.addRow(gemini_lbl, QLabel(""))
        cred_form.addRow("API key", self.gemini_key_input)
        cred_form.addRow("Base URL", self.gemini_base_url_input)
        layout.addWidget(cred_group)

        # Per-action output mode
        mode_group = QGroupBox("Per-Action Output Mode")
        mode_form = QFormLayout(mode_group)
        mode_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        mode_form.setSpacing(8)
        self.action_output_mode_inputs: dict[str, QComboBox] = {}
        action_labels = {
            "fix": "✏  Fix",
            "summarize": "📋  Summarize",
            "translate_ar": "🇸🇦  Arabic",
            "translate_en": "🇬🇧  English",
            "translate_es": "🇪🇸  Spanish",
            "translate_fr": "🇫🇷  French",
            "translate_de": "🇩🇪  German",
            "translate_custom": "🌍  Custom",
        }
        for action, label in action_labels.items():
            cb = QComboBox()
            cb.addItem("↩  Replace", "replace")
            cb.addItem("📋  Clipboard", "clipboard")
            cb.setMaximumWidth(160)
            cb.setCursor(Qt.PointingHandCursor)
            self.action_output_mode_inputs[action] = cb
            mode_form.addRow(label, cb)
        layout.addWidget(mode_group)

        # Keyboard shortcuts
        sc_group = QGroupBox("Keyboard Shortcuts")
        sc_form = QFormLayout(sc_group)
        sc_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        sc_form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        sc_form.setSpacing(8)
        self.shortcut_inputs: dict[str, QLineEdit] = {}
        for action, label in action_labels.items():
            field = QLineEdit()
            field.setPlaceholderText("e.g.  <cmd>+<alt>+f")
            self.shortcut_inputs[action] = field
            sc_form.addRow(label, field)
        layout.addWidget(sc_group)

        # ── macOS Accessibility permission ───────────────────────────────────
        if sys.platform == "darwin":
            perm_group = QGroupBox("macOS Accessibility Permission")
            perm_layout = QVBoxLayout(perm_group)
            perm_layout.setSpacing(8)
            perm_info = QLabel(
                "Global hotkeys and 'Replace in place' require Accessibility access.\n"
                "Do NOT use sudo — run the script as your normal user.\n"
                "Then grant access to Terminal (or your terminal app) in System Settings."
            )
            perm_info.setWordWrap(True)
            perm_info.setStyleSheet("color: #f9e2af; font-size: 12px;")
            perm_layout.addWidget(perm_info)
            open_perm_btn = QPushButton("⚙  Open  Privacy & Security  →  Accessibility")
            open_perm_btn.setObjectName("accent")
            open_perm_btn.setCursor(Qt.PointingHandCursor)
            open_perm_btn.clicked.connect(self._open_accessibility_settings)
            perm_layout.addWidget(open_perm_btn, alignment=Qt.AlignLeft)
            layout.addWidget(perm_group)

        # Save row
        save_row = QHBoxLayout()
        save_all_btn = QPushButton("💾  Save All Settings")
        save_all_btn.setObjectName("primary")
        save_all_btn.setMinimumWidth(200)
        save_all_btn.setCursor(Qt.PointingHandCursor)
        save_all_btn.clicked.connect(self.save_settings_from_ui)
        save_row.addStretch()
        save_row.addWidget(save_all_btn)
        layout.addLayout(save_row)
        layout.addStretch()

        return scroll

    # ── Tray ─────────────────────────────────────────────────────────────────

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(self)
        icon = self.style().standardIcon(QStyle.SP_ComputerIcon)
        self.tray.setIcon(icon)
        self.setWindowIcon(icon)

        menu = QMenu()
        toggle_action = QAction("Show / Hide", self)
        toggle_action.triggered.connect(self.toggle_visibility)
        show_ring_action = QAction("Show ring button", self)
        show_ring_action.triggered.connect(lambda: self.ring.show())
        fix_action = QAction("Fix selection", self)
        fix_action.triggered.connect(lambda: self.run_action("fix"))
        summarize_action = QAction("Summarize selection", self)
        summarize_action.triggered.connect(lambda: self.run_action("summarize"))
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)

        menu.addAction(toggle_action)
        menu.addAction(show_ring_action)
        menu.addSeparator()
        menu.addAction(fix_action)
        menu.addAction(summarize_action)
        menu.addSeparator()
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.setToolTip("Writing Assistant")
        self.tray.show()

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _hr(self) -> QFrame:
        line = QFrame()
        line.setObjectName("divider")
        line.setFrameShape(QFrame.HLine)
        return line

    def _build_access_banner(self) -> QFrame:
        """Build the collapsible macOS accessibility warning banner."""
        banner = QFrame()
        banner.setObjectName("access_banner")
        banner.setFixedHeight(48)
        row = QHBoxLayout(banner)
        row.setContentsMargins(12, 4, 12, 4)
        row.setSpacing(12)
        icon_lbl = QLabel("⚠")
        icon_lbl.setStyleSheet("color:#f38ba8; font-size:18px;")
        row.addWidget(icon_lbl)
        msg = QLabel(
            "<b>Accessibility permission missing.</b>  "
            "Hotkeys &amp; Replace-in-place won't work.  "
            "<i>Do NOT run with sudo—run as your normal user, then grant access below.</i>"
        )
        msg.setObjectName("access_label")
        msg.setWordWrap(False)
        row.addWidget(msg, 1)
        btn = QPushButton("⚙  Open System Settings")
        btn.setObjectName("access_btn")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(self._open_accessibility_settings)
        row.addWidget(btn)
        banner.setVisible(False)  # shown only when permission is missing
        return banner

    def _open_accessibility_settings(self) -> None:
        """Open macOS Privacy & Security → Accessibility in System Settings."""
        try:
            import subprocess as _sp
            _sp.run(
                [
                    "open",
                    "x-apple.systempreferences:com.apple.preference.security"
                    "?Privacy_Accessibility",
                ],
                check=False,
            )
        except Exception:
            logger.exception("Failed to open System Settings")

    @Slot()
    def _copy_preview_to_clipboard(self) -> None:
        """Copy the current output preview text to the clipboard."""
        try:
            text = self.output_preview.toPlainText().strip()
            if text:
                self.selection.copy_to_clipboard(text)
                self._show_notification("✔  Result copied to clipboard")
            else:
                self._show_notification("⚠  Preview is empty")
        except Exception:
            logger.exception("Failed to copy preview")

    @Slot()
    def _paste_preview_to_source(self) -> None:
        """Replace the currently selected text in the source app with the
        content from the output preview (useful when the automatic replace
        did not fire or when the user is reviewing first)."""
        try:
            text = self.output_preview.toPlainText().strip()
            if not text:
                self._show_notification("⚠  Preview is empty — run an action first")
                return
            self.executor.submit(self._paste_preview_sync, text)
        except Exception:
            logger.exception("Failed to schedule paste preview")

    def _paste_preview_sync(self, text: str) -> None:
        try:
            self.selection.replace_selected_text(text)
            self.notify_signal.emit("✔  Pasted to source app")
        except Exception:
            logger.exception("Paste preview failed")

    # ── Signal wiring ────────────────────────────────────────────────────────

    def _wire_signals(self) -> None:
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        self.model_combo.currentTextChanged.connect(self.on_model_changed)
        self.mode_combo.currentTextChanged.connect(self.on_mode_changed)
        self.custom_language_combo.currentTextChanged.connect(self.on_custom_language_changed)

        self.fix_button.clicked.connect(lambda: self._run_action_from_button("fix"))
        self.summary_button.clicked.connect(lambda: self._run_action_from_button("summarize"))
        self.ar_button.clicked.connect(lambda: self._run_action_from_button("translate_ar"))
        self.en_button.clicked.connect(lambda: self._run_action_from_button("translate_en"))
        self.es_button.clicked.connect(lambda: self._run_action_from_button("translate_es"))
        self.fr_button.clicked.connect(lambda: self._run_action_from_button("translate_fr"))
        self.de_button.clicked.connect(lambda: self._run_action_from_button("translate_de"))
        self.custom_button.clicked.connect(lambda: self._run_action_from_button("translate_custom"))

        self.settings_button.clicked.connect(self.save_settings_from_ui)
        self.minimize_button.clicked.connect(self.hide_to_tray)
        self.pull_model_button.clicked.connect(self.pull_current_model)
        self.toggle_ring_button.clicked.connect(self.toggle_ring)
        self.copy_result_button.clicked.connect(self._copy_preview_to_clipboard)
        self.paste_result_button.clicked.connect(self._paste_preview_to_source)

        # Auto-save credentials when the user leaves any credential field.
        # This prevents the provider-change cascade from wiping unsaved keys.
        for _field in (
            self.openai_key_input,
            self.openai_base_url_input,
            self.gemini_key_input,
            self.gemini_base_url_input,
            self.ollama_endpoint_input,
            self.ollama_keep_alive_input,
        ):
            _field.editingFinished.connect(self.save_settings_from_ui)

    # ── Preflight ────────────────────────────────────────────────────────────

    def run_preflight(self) -> None:
        try:
            platform_value = platform_name()
            issues: list[str] = []
            needs_access = platform_value == "Darwin" and not is_macos_accessibility_trusted()
            if not has_ollama_cli():
                issues.append("Ollama CLI not installed")
            if needs_access:
                issues.append("Accessibility permission missing")
            # Show/hide the accessibility banner
            if hasattr(self, "access_banner"):
                self.access_banner.setVisible(needs_access)
            if issues:
                msg = " · ".join(issues)
                self.status_label.setText("⚠  " + msg)
                self._restyle_label(self.status_label, "status_warn")
                self._notify(msg)
            else:
                self.status_label.setText(f"✔  Preflight OK  ({platform_value})")
                self._restyle_label(self.status_label, "status_ok")
        except Exception:
            logger.exception("Preflight failed")

    # ── Visibility helpers ───────────────────────────────────────────────────

    @Slot()
    def hide_to_tray(self) -> None:
        self.hide()
        self._notify("Minimized to tray")

    @Slot()
    def toggle_ring(self) -> None:
        try:
            self.ring.setVisible(not self.ring.isVisible())
        except Exception:
            logger.exception("Failed toggling ring")

    @Slot()
    def toggle_visibility(self) -> None:
        try:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()
                self.activateWindow()
        except Exception:
            logger.exception("Failed toggling window")

    # ── Apply / save settings ────────────────────────────────────────────────

    def apply_settings_to_ui(self) -> None:
        try:
            s = self.settings
            # Block signals on combos that have slots wired to them so that
            # programmatic index changes don't re-trigger on_provider_changed /
            # on_mode_changed and cause re-entrant saves or double refreshes.
            self.provider_combo.blockSignals(True)
            self.mode_combo.blockSignals(True)
            try:
                # Use findData so display-name combos map correctly to internal values.
                _prov_idx = self.provider_combo.findData(s.get("provider", "ollama"))
                self.provider_combo.setCurrentIndex(max(0, _prov_idx))
                _mode_idx = self.mode_combo.findData(s.get("output_mode", "replace"))
                self.mode_combo.setCurrentIndex(max(0, _mode_idx))
            finally:
                self.provider_combo.blockSignals(False)
                self.mode_combo.blockSignals(False)
            # Keep pull button in sync with the loaded provider
            self._update_pull_button_visibility()
            self.fix_prompt.setPlainText(s["actions"]["fix"].get("prompt", ""))
            self.summary_prompt.setPlainText(s["actions"]["summarize"].get("prompt", ""))
            self.translate_prompt.setPlainText(s["actions"]["translate_custom"].get("prompt", ""))
            for action, field in self.shortcut_inputs.items():
                field.setText(s.get("shortcuts", {}).get(action, ""))
            for action, cb in self.action_output_mode_inputs.items():
                _val = s["actions"].get(action, {}).get("output_mode", "replace")
                _idx = cb.findData(_val)
                cb.setCurrentIndex(max(0, _idx))

            langs = s.get("custom_languages", [])
            if not langs:
                langs = ["English"]
            sel = s.get("selected_custom_language", langs[0])
            self.custom_language_combo.blockSignals(True)
            self.custom_language_combo.clear()
            self.custom_language_combo.addItems(langs)
            idx = self.custom_language_combo.findText(sel)
            self.custom_language_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.custom_language_combo.blockSignals(False)

            # ── Credential fields ─────────────────────────────────────────────
            # Do NOT overwrite a field the user is actively typing in. This
            # prevents the provider-change cascade from wiping an unsaved key.
            def _set_if_idle(field: QLineEdit, value: str) -> None:
                if not field.hasFocus():
                    field.setText(value)

            _set_if_idle(self.ollama_endpoint_input, s["ollama"].get("endpoint", ""))
            _set_if_idle(self.ollama_keep_alive_input, s["ollama"].get("keep_alive", "5m"))
            _set_if_idle(self.openai_key_input, s["openai"].get("api_key", ""))
            _set_if_idle(self.openai_base_url_input, s["openai"].get("base_url", "https://api.openai.com/v1"))
            _set_if_idle(self.gemini_key_input, s["gemini"].get("api_key", ""))
            _set_if_idle(
                self.gemini_base_url_input,
                s["gemini"].get("base_url", "https://generativelanguage.googleapis.com/v1beta"),
            )
        except Exception:
            logger.exception("Failed to apply settings to UI")

    @Slot()
    def save_settings_from_ui(self) -> None:
        try:
            data = self.settings_manager.get()
            data["provider"] = self.provider_combo.currentData() or self.provider_combo.currentText()
            data["output_mode"] = self.mode_combo.currentData() or self.mode_combo.currentText()
            data["actions"]["fix"]["prompt"] = self.fix_prompt.toPlainText().strip()
            data["actions"]["summarize"]["prompt"] = self.summary_prompt.toPlainText().strip()
            translate_prompt = self.translate_prompt.toPlainText().strip()
            for key in ["translate_ar", "translate_en", "translate_es", "translate_fr",
                        "translate_de", "translate_custom"]:
                data["actions"][key]["prompt"] = translate_prompt

            data["selected_custom_language"] = self.custom_language_combo.currentText().strip()
            data["custom_languages"] = [
                self.custom_language_combo.itemText(i)
                for i in range(self.custom_language_combo.count())
            ]

            provider = data["provider"]
            if provider == "ollama":
                data["ollama"]["model"] = self.model_combo.currentText()
            elif provider == "openai":
                data["openai"]["model"] = self.model_combo.currentText()
            elif provider == "gemini":
                data["gemini"]["model"] = self.model_combo.currentText()

            for action, field in self.shortcut_inputs.items():
                data["shortcuts"][action] = field.text().strip()
            for action, cb in self.action_output_mode_inputs.items():
                data["actions"][action]["output_mode"] = cb.currentData() or cb.currentText()

            data["ollama"]["endpoint"] = (
                self.ollama_endpoint_input.text().strip() or "http://localhost:11434"
            )
            data["ollama"]["keep_alive"] = self.ollama_keep_alive_input.text().strip() or "5m"
            data["openai"]["api_key"] = self.openai_key_input.text().strip()
            data["openai"]["base_url"] = (
                self.openai_base_url_input.text().strip() or "https://api.openai.com/v1"
            )
            data["gemini"]["api_key"] = self.gemini_key_input.text().strip()
            data["gemini"]["base_url"] = (
                self.gemini_base_url_input.text().strip()
                or "https://generativelanguage.googleapis.com/v1beta"
            )

            self.settings_manager.save(data)
            self.status_label.setText("✔  Settings saved")
            self._restyle_label(self.status_label, "status_ok")
            self._notify("Settings saved")
        except Exception:
            logger.exception("Failed to save settings")
            self._notify("Failed to save settings")

    def _on_settings_changed(self, settings: dict[str, Any]) -> None:
        # Called from the file-watcher background thread — emit a signal
        # instead of touching Qt objects directly.
        try:
            self._settings_reload_signal.emit(settings)
        except Exception:
            logger.exception("_on_settings_changed failed")

    @Slot(object)
    def _apply_settings_change(self, settings: dict[str, Any]) -> None:
        """Runs on the main thread via _settings_reload_signal."""
        try:
            new_provider = settings.get("provider", "ollama")
            provider_changed = new_provider != self._active_provider
            self.settings = settings
            self.apply_settings_to_ui()
            self._start_hotkeys_safely()
            if provider_changed:
                self._active_provider = new_provider
                # Defer refresh_models to the next event-loop iteration so it
                # never runs while Qt is still dispatching a signal from the
                # model combo (e.g. currentTextChanged → on_model_changed →
                # save → here).  Calling model_combo.clear() inside an active
                # signal dispatch from that same combo causes a SIGTRAP crash.
                QTimer.singleShot(0, self.refresh_models)
        except Exception:
            logger.exception("Failed applying settings change")

    # ── Provider / model ─────────────────────────────────────────────────────

    @Slot(str)
    def on_provider_changed(self, provider: str) -> None:
        try:
            # `provider` is the combo display text; read the internal data value.
            internal = self.provider_combo.currentData() or provider
            # Update Pull Model button visibility immediately on provider change
            self._update_pull_button_visibility()
            # Saving triggers _apply_settings_change (synchronous direct-signal
            # on the main thread) which already schedules refresh_models() via
            # QTimer.singleShot.  Calling refresh_models() here too would cause
            # a double fetch and could clear the model combo a second time.
            self.settings_manager.update(["provider"], internal)
        except Exception:
            logger.exception("Provider change failed")

    @Slot(str)
    def on_model_changed(self, model: str) -> None:
        try:
            # Ignore transient placeholder emitted while the background fetch is running
            if not model or model in ("Loading\u2026", "default", ""):
                return
            provider = self.provider_combo.currentData() or self.provider_combo.currentText()
            key = {"ollama": "ollama", "openai": "openai", "gemini": "gemini"}.get(provider, "ollama")
            self.settings_manager.update([key, "model"], model)
        except Exception:
            logger.exception("Model change failed")

    @Slot(str)
    def on_mode_changed(self, mode: str) -> None:
        try:
            internal = self.mode_combo.currentData() or mode
            self.settings_manager.update(["output_mode"], internal)
        except Exception:
            logger.exception("Mode change failed")

    @Slot(str)
    def on_custom_language_changed(self, language: str) -> None:
        try:
            if language.strip():
                self.settings_manager.update(["selected_custom_language"], language.strip())
        except Exception:
            logger.exception("Custom language change failed")

    @Slot()
    def refresh_models(self) -> None:
        """Kick off a background fetch of the model list so the main thread never blocks."""
        try:
            self.settings = self.settings_manager.get()
            provider = self.settings.get("provider", "ollama")
            # Show a placeholder while loading
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItem("Loading…")
            self.model_combo.blockSignals(False)
            self.executor.submit(self._refresh_models_sync, provider, self.settings)
        except Exception:
            logger.exception("Failed to schedule model list refresh")

    def _refresh_models_sync(self, provider: str, settings: dict) -> None:
        """Background thread: fetch models and emit result to main thread."""
        try:
            models = self.providers.provider_models(provider, settings)
            if not models:
                models = ["default"]
            if provider == "ollama":
                current = settings["ollama"].get("model", models[0])
            elif provider == "openai":
                current = settings["openai"].get("model", models[0])
            else:
                current = settings["gemini"].get("model", models[0])
            self._models_loaded_signal.emit((models, provider, current))
        except Exception:
            logger.exception("Background model list refresh failed")
            self._models_loaded_signal.emit((["default"], provider, "default"))

    @Slot(object)
    def _apply_models_result(self, payload: object) -> None:
        """Main thread: populate model combo with the fetched list."""
        try:
            models, result_provider, current_model = payload  # type: ignore[misc]
            # Discard result if the user has already switched to a different provider
            # since this background task was submitted.
            if result_provider != self._active_provider:
                logger.debug(
                    "Discarding stale model list for '%s' (active: '%s')",
                    result_provider, self._active_provider,
                )
                return
            self.model_combo.blockSignals(True)
            self.model_combo.clear()
            self.model_combo.addItems(models)
            idx = self.model_combo.findText(current_model)
            self.model_combo.setCurrentIndex(idx if idx >= 0 else 0)
            self.model_combo.blockSignals(False)
        except Exception:
            logger.exception("Failed applying model list update")

    @Slot()
    def pull_current_model(self) -> None:
        try:
            model = self.model_combo.currentText().strip()
            if not model:
                self._notify("No model selected")
                return
            self.status_label.setText(f"⟳  Pulling {model}…")
            self._restyle_label(self.status_label, "status_warn")
            self.pull_model_button.setEnabled(False)
            self._pull_progress_signal.emit(True)
            self.executor.submit(self._pull_model_sync, model)
        except Exception:
            logger.exception("Failed to schedule model pull")

    def _pull_model_sync(self, model: str) -> None:
        try:
            ok, message = self.providers.pull_ollama_model(model)
            if ok:
                self._notify(f"✔  Pulled {model}")
                # refresh_models() touches Qt widgets — emit signal to run on main thread
                self._models_refresh_signal.emit()
            else:
                self._notify(f"✘  Pull failed: {message}")
        except Exception:
            logger.exception("Model pull failed")
            self._notify("Model pull failed")
        finally:
            self._pull_progress_signal.emit(False)

    @Slot(bool)
    def _set_pull_progress(self, visible: bool) -> None:
        """Show/hide the pull progress bar and re-enable the pull button."""
        try:
            self.pull_progress.setVisible(visible)
            self.pull_model_button.setEnabled(not visible)
        except Exception:
            logger.exception("Failed updating pull progress")

    def _update_pull_button_visibility(self) -> None:
        """Show the Pull Model button only for Ollama; hide it for OpenAI / Gemini."""
        try:
            provider = self.provider_combo.currentData() or self.provider_combo.currentText()
            is_ollama = str(provider).lower() == "ollama"
            self.pull_model_button.setVisible(is_ollama)
            if not is_ollama:
                # Hide progress bar too if switching away from Ollama mid-pull
                self.pull_progress.setVisible(False)
        except Exception:
            logger.exception("Failed updating pull button visibility")

    def _restyle_label(self, label, name: str) -> None:
        """Change a QLabel's objectName and force QSS re-evaluation."""
        label.setObjectName(name)
        label.style().unpolish(label)
        label.style().polish(label)

    @Slot()
    def refresh_health(self) -> None:
        """Schedule an async health check so the main thread is never blocked by I/O."""
        try:
            self.settings = self.settings_manager.get()
            provider = self.settings.get("provider", "")
            if provider == "ollama":
                # Offload the HTTP call to the thread-pool; result comes back via signal
                self.executor.submit(self._refresh_health_sync, self.settings)
            else:
                # No network call needed for OpenAI/Gemini — just check for a key
                issues: list[str] = []
                if provider == "openai" and not self.settings.get("openai", {}).get("api_key"):
                    issues.append("OpenAI key missing")
                elif provider == "gemini" and not self.settings.get("gemini", {}).get("api_key"):
                    issues.append("Gemini key missing")
                self._apply_health_result(issues)
        except Exception:
            logger.exception("Health refresh failed")

    def _refresh_health_sync(self, settings: dict) -> None:
        """Background thread: perform the Ollama health-check HTTP call."""
        try:
            ok, msg = self.providers.ollama_health(settings)
            issues: list[str] = [] if ok else [msg]
            self._health_update_signal.emit(issues)
        except Exception as exc:
            logger.exception("Background health check failed")
            self._health_update_signal.emit([f"Health check failed: {exc}"])

    @Slot(object)
    def _apply_health_result(self, issues: object) -> None:
        """Main thread: update the health label from the background result."""
        try:
            issue_list: list[str] = issues if isinstance(issues, list) else []
            if issue_list:
                self.health_label.setText("⚠ " + " · ".join(issue_list))
                self._restyle_label(self.health_label, "status_warn")
            else:
                self.health_label.setText("● online")
                self._restyle_label(self.health_label, "status_ok")
            self.tray.setToolTip("Writing Assistant " + ("- Issues" if issue_list else "- Online"))
        except Exception:
            logger.exception("Apply health result failed")

    # ── Hotkeys ──────────────────────────────────────────────────────────────

    def _start_hotkeys_safely(self) -> None:
        try:
            if sys.platform == "darwin" and not is_macos_accessibility_trusted():
                self.status_label.setText("⚠  Grant Accessibility permission to enable shortcuts")
                self._restyle_label(self.status_label, "status_warn")
                self.hotkeys.stop()
                return
            self.hotkeys.start(self.settings.get("shortcuts", {}))
            if self.hotkeys.enabled:
                self.status_label.setText(f"✔  Shortcuts active ({self.hotkeys.active_shortcuts})")
                self._restyle_label(self.status_label, "status_ok")
            else:
                message = self.hotkeys.last_error or "Shortcuts disabled"
                self.status_label.setText(f"⚠  {message}")
                self._restyle_label(self.status_label, "status_warn")
        except Exception:
            logger.exception("Hotkey startup failed")

    def _on_hotkey(self, action: str) -> None:
        # pynput runs in its own OS thread — emit a Qt signal to safely
        # dispatch to the main thread instead of calling run_action directly.
        try:
            self._hotkey_trigger_signal.emit(action)
        except Exception:
            logger.exception("_on_hotkey emit failed")

    @Slot(str)
    def _on_hotkey_main(self, action: str) -> None:
        """Called on the main thread via _hotkey_trigger_signal.
        Snapshot the source app *now* (before the executor adds delay) then
        schedule the action in the background."""
        try:
            source_app = self.selection.snapshot_source_app()
            self.run_action(action, source_app=source_app)
        except Exception:
            logger.exception("_on_hotkey_main failed")

    # ── Action execution ─────────────────────────────────────────────────────

    def _run_action_from_button(self, action: str) -> None:
        """Wrapper for button-click connections.

        Snapshots the source window *on the main thread right now* — before the
        background executor thread picks up the work — so that focus management
        (Ctrl+C / Ctrl+V targeting) has the correct window handle even though
        the Writing Assistant window has already stolen focus.
        """
        try:
            source_app = self.selection.snapshot_source_app()
            self.run_action(action, source_app=source_app)
        except Exception:
            logger.exception("_run_action_from_button failed")

    def run_action(self, action: str, source_app: str = "") -> None:
        try:
            self.status_label.setText(f"⟳  Running {action}…")
            # Clear preview so streaming output is visible immediately
            self.output_preview.setPlainText("")
            self.executor.submit(self._run_action_sync, action, source_app)
        except Exception:
            logger.exception("Failed scheduling action")

    def _run_action_sync(self, action: str, source_app: str = "") -> None:
        try:
            text = self.selection.get_selected_text(source_app=source_app).strip()
            if not text:
                self._notify("⚠  No text selected")
                return

            settings = self.settings_manager.get()
            prompt = self.ops.build_prompt(action, text, settings)

            def _on_chunk(chunk: str) -> None:
                self._stream_preview_signal.emit(chunk)

            output = self.providers.generate_streaming(settings, prompt, _on_chunk)

            if not output:
                self._notify("⚠  Model returned empty output")
                return

            output_mode = self.ops.output_mode_for(action, settings)
            # Emit final cleaned text so _apply_output can replace/copy as needed
            self.apply_output_signal.emit(output_mode, output, source_app)

        except ProviderError as exc:
            logger.error("Provider error: %s", exc)
            self._notify(f"✘  {exc}")
        except Exception as exc:
            logger.exception("Action failed")
            self._notify(f"✘  Unknown error: {exc}")

    def _notify(self, message: str) -> None:
        self.notify_signal.emit(message)

    @Slot(str)
    def _update_preview_stream(self, chunk: str) -> None:
        """Update the preview text-box with each streaming chunk (main thread)."""
        try:
            self.output_preview.setPlainText(chunk)
            # Auto-scroll so the user sees the latest tokens
            sb = self.output_preview.verticalScrollBar()
            sb.setValue(sb.maximum())
        except Exception:
            logger.exception("Failed updating streaming preview")

    @Slot(str, str, str)
    def _apply_output(self, output_mode: str, output: str, source_app: str) -> None:
        try:
            # Always persist the final cleaned output in the preview
            self.output_preview.setPlainText(output)
            if output_mode == "clipboard":
                self.selection.copy_to_clipboard(output)
                self._show_notification("✔  Output copied to clipboard")
            elif output_mode == "replace":
                self.selection.replace_selected_text(output, source_app=source_app)
                self._show_notification("✔  Selection replaced")
            # "preview_only" — streaming intermediate; no clipboard/replace action needed
        except Exception:
            logger.exception("Failed applying output")

    @Slot(str)
    def _show_notification(self, message: str) -> None:
        try:
            self.status_label.setText(message)
            # Keep the colour consistent: errors/warnings in red/yellow, successes in green
            if message.startswith(("✘", "⚠")):
                self._restyle_label(self.status_label, "status_err" if message.startswith("✘") else "status_warn")
            else:
                self._restyle_label(self.status_label, "status_ok")
            self.tray.showMessage("Writing Assistant", message, QSystemTrayIcon.Information, 2500)
        except Exception:
            logger.exception("Failed showing notification")

    def closeEvent(self, event) -> None:
        try:
            self.hide()
            event.ignore()
            self._notify("Still running in the background. Use tray to quit.")
        except Exception:
            logger.exception("closeEvent failed")
            try:
                event.ignore()
            except Exception:
                pass

    def open_install_links(self) -> None:
        try:
            webbrowser.open(ollama_install_url())
            if sys.platform == "darwin":
                webbrowser.open(accessibility_docs_url())
        except Exception:
            logger.exception("Failed opening help links")


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def run() -> int:
    settings_manager = SettingsManager(SettingsManager.default_path())
    settings = settings_manager.get()
    configure_logging(
        settings.get("logging", {}).get("path", "~/.writing_assistant/logs/app.log"),
        settings.get("logging", {}).get("level", "INFO"),
    )
    logger.info("Starting Writing Assistant")

    # macOS: clear environment overrides that break native display
    if sys.platform == "darwin":
        qt_qpa = os.environ.get("QT_QPA_PLATFORM", "").strip().lower()
        if qt_qpa == "offscreen":
            os.environ.pop("QT_QPA_PLATFORM", None)
        if not os.environ.get("QT_PLUGIN_PATH", "").strip():
            os.environ.pop("QT_PLUGIN_PATH", None)

    # ── Global exception safety net ──────────────────────────────────────────
    # On macOS, an unhandled Python exception that escapes a PySide6 slot
    # propagates into Qt's C++ layer and triggers SIGTRAP (abort).
    # Installing sys.excepthook lets us log it and keep the process alive.
    _orig_excepthook = sys.excepthook

    import traceback as _traceback
    import threading as _threading

    def _global_excepthook(exc_type, exc_value, exc_tb):
        # Build the traceback text defensively — repr() of PySide6 objects can
        # raise RuntimeError if the C++ wrapper was deleted, which causes the
        # standard `exc_info=` logger path to fail with "--- Logging error ---".
        try:
            exc_text = "".join(_traceback.format_exception(exc_type, exc_value, exc_tb))
        except Exception as _fmt_err:
            try:
                exc_text = f"<traceback formatting failed: {_fmt_err}> {exc_type.__name__}: {exc_value}"
            except Exception:
                exc_text = "<could not format exception>"
        # Log using a plain string so the formatter never touches the raw exc_info.
        try:
            logger.error("Unhandled exception:\n%s", exc_text)
        except Exception:
            pass
        # Fallback: write directly to the original stderr so it always appears.
        try:
            print(f"UNHANDLED EXCEPTION:\n{exc_text}", file=sys.__stderr__, flush=True)
        except Exception:
            pass

    sys.excepthook = _global_excepthook

    # Mirror the excepthook for background threads (Python 3.8+).
    def _thread_excepthook(args: _threading.ExceptHookArgs) -> None:
        _global_excepthook(args.exc_type, args.exc_value, args.exc_traceback)
    _threading.excepthook = _thread_excepthook

    # On macOS, intercept SIGTRAP so a stray signal doesn't kill the process.
    if sys.platform == "darwin":
        import signal as _signal
        try:
            _signal.signal(_signal.SIGTRAP, _signal.SIG_IGN)
        except (OSError, ValueError):
            pass  # may fail in certain environments; non-fatal

    # Fix "QFont::setPointSize: Point size <= 0 (-1)" warnings on Windows/Linux
    # where no physical display DPI is available at font-metrics time.
    if sys.platform in ("win32", "linux"):
        os.environ.setdefault("QT_FONT_DPI", "96")

    app = QApplication(sys.argv)
    app.setApplicationName("Writing Assistant")
    app.setApplicationVersion("1.0")

    settings_manager.start_watch(
        seconds=int(settings.get("polling", {}).get("settings_reload_seconds", 2))
    )
    try:
        window = FloatingBar(settings_manager)
    except Exception:
        logger.exception("Fatal error during window initialisation")
        # Let Qt show an error dialog rather than silently dying
        from PySide6.QtWidgets import QMessageBox
        err_app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Writing Assistant — startup error",
            "A fatal error occurred during startup.\n"
            "Check the log file for details:\n"
            f"  {settings.get('logging', {}).get('path', '~/.writing_assistant/logs/app.log')}",
        )
        return 1

    window.show()

    if not has_ollama_cli() or (sys.platform == "darwin" and not is_macos_accessibility_trusted()):
        window.open_install_links()

    code = app.exec()
    settings_manager.stop_watch()
    window.hotkeys.stop()
    logger.info("Writing Assistant stopped")
    return code


if __name__ == "__main__":
    raise SystemExit(run())


