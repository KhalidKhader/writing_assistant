# Writing Assistant (Desktop + Global Shortcuts)

A production-style desktop writing assistant for macOS with:

- Floating mini bar UI (always on top, draggable)
- Ring launcher button (click to reopen/toggle the app)
- Draggable ring launcher (drag to move, click to toggle)
- System tray control
- Global keyboard shortcuts for each feature
- Ollama-first local model support with live health/model status
- Optional cloud models (OpenAI / Gemini) via API keys
- Real-time settings reload from a JSON config file
- Per-action output mode: replace selected text or copy to clipboard
- Rotating logs for troubleshooting and crash analysis

## Features

- **Fix** grammar, spelling, casing, punctuation
- **Summarize** selected text using a configurable prompt
- **Translate** selected text to:
  - Arabic
  - English
  - Spanish
  - French
  - German
- **Output mode control**
  - Global default in UI/config
  - Per-action override in UI/config
- **Prompt control**
  - Fix/Summary/Translate prompts editable from UI and config
- **Language expansion**
  - Choose custom target language from a dropdown list and translate to selected custom language
- **Output visibility**
  - Last model output preview panel inside the app
- **Model install control**
  - Pull selected Ollama model directly from UI (`Pull Ollama Model`)
- **Real-time behavior**
  - Settings file reload every N seconds (default 2)
  - Ollama health + model list refresh every N seconds (default 5)

## Architecture

- `main.py` - app entrypoint
- `app/settings.py` - settings defaults, merge, save, live reload watcher
- `app/providers.py` - provider abstraction for Ollama/OpenAI/Gemini
- `app/operations.py` - prompt templates for all actions
- `app/selection.py` - selected text read/replace and clipboard operations
- `app/hotkeys.py` - global shortcuts manager
- `app/ui.py` - floating bar + tray UI + orchestration

## Requirements

- macOS / Windows / Linux
- Python 3.11+ (recommended: 3.11 or 3.13; macOS + PySide6 may fail on 3.14)
- Ollama installed and running (for local mode)

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Alternative one-command bootstrap:

```bash
bash scripts/run.sh
```

`scripts/run.sh` automatically prefers `python3.11` (then `python3.13`) and recreates an incompatible macOS `3.14` virtualenv.

## Ollama Setup

1. Install Ollama.
2. Run Ollama service.
3. Pull at least one model:

```bash
ollama pull mistral:7b-instruct-v0.2-q4_K_S
```

The app automatically checks `http://localhost:11434/api/tags` for health/models.

## Settings File

Default settings path:

- `~/.writing_assistant/settings.json`

Override settings path with env var:

- `WRITING_ASSISTANT_SETTINGS=/path/to/settings.json`

You can copy from `settings.example.json`.

### Important fields

- `provider`: `ollama` | `openai` | `gemini`
- `output_mode`: `replace` | `clipboard`
- `shortcuts`: global hotkeys for each action
- `actions.<action>.output_mode`: per-action output mode override
- `actions.summarize.prompt`: custom summarize instruction
- `ollama.endpoint` and `ollama.model`
- `openai.api_key` / `gemini.api_key` for cloud providers

## UI Usage

- Start app with `python main.py`
- Floating bar appears on screen with native titlebar controls (minimize/maximize/close)
- Ring launcher appears; click it any time to reopen/toggle app visibility
- Select provider and model
- Choose global output mode
- Click action buttons (`Fix`, `Summarize`, `Arabic`, `English`, `Spanish`, `French`, `German`)
- Update per-action output mode, API keys, and provider endpoints from the bar UI
- Choose a custom language from the dropdown and run custom translation
- Save settings with **Save Settings**

### API keys in UI

- Enter OpenAI key in **OpenAI API key** field.
- Enter Gemini key in **Gemini API key** field.
- Press **Save Settings** (stored in settings file).

System tray menu allows:

- Show/Hide bar
- Show ring
- Fix selection
- Summarize selection
- Quit

## Global Shortcuts (default)

- Fix: `<cmd>+<alt>+f`
- Summarize: `<cmd>+<alt>+s`
- Translate Arabic: `<cmd>+<alt>+1`
- Translate English: `<cmd>+<alt>+2`
- Translate Spanish: `<cmd>+<alt>+3`
- Translate French: `<cmd>+<alt>+4`
- Translate German: `<cmd>+<alt>+5`
- Translate Custom: `<cmd>+<alt>+6`

All shortcuts are editable from UI and config.

## Optional Cloud Providers

The app supports OpenAI and Gemini if API keys are provided in settings:

- `openai.api_key`
- `gemini.api_key`

If provider is cloud and key is missing, the app shows a tray notification error.

Default curated cloud model lists in UI include:

- OpenAI: `gpt-5`, `gpt-5-mini`, `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`
- Gemini: `gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite`

## Real-Time Update Model

- The settings file is watched with polling and auto-applied.
- Hotkeys are re-registered automatically after settings changes.
- Ollama status is checked on a timer and reflected in UI/tray tooltip.
- Ollama model list is refreshed when provider/settings change.

## Smoke Test

Run a full core smoke test:

```bash
source .venv/bin/activate
python scripts/smoke_test.py
```

## Preflight Checks

At startup, app checks:

- Ollama CLI availability
- macOS accessibility trust for shortcuts and text replacement

If missing, app opens install/help links:

- Ollama install: `https://ollama.com/download`
- macOS input monitoring: `https://support.apple.com/guide/mac-help/control-access-to-input-monitoring-on-mac-mchl4cedafb6/mac`

## Logging

- Log file is configurable in settings under `logging.path`.
- Default: `~/.writing_assistant/logs/app.log`
- Rotating logs are used automatically.

## Docker

```bash
docker build -t writing-assistant .
docker run --rm writing-assistant
```

Notes:

- Docker image runs with `QT_QPA_PLATFORM=offscreen` and is useful for CI/smoke checks.
- Global keyboard hooks and full desktop UI behavior are intended for native host execution (not containers).
- Docker build now includes Linux headers/build deps required by `pynput`/`evdev`.
- Docker CLI run is mainly for non-GUI validation; full desktop UI should run on the host OS session.

## Packaging as a macOS App (recommended)

Use PyInstaller to generate an app bundle:

```bash
pip install pyinstaller
pyinstaller --windowed --name "WritingAssistant" main.py
```

Generated app bundle will be under `dist/`.

## Security Notes

- Keep API keys in settings file or secure environment management.
- Prefer local Ollama mode for privacy-sensitive text.

## Troubleshooting

### Hotkeys not working

- Ensure Accessibility permissions are granted to Terminal/Python app in macOS System Settings.
- Check shortcut format in settings (pynput format like `<cmd>+<alt>+f`).

If you saw this earlier:

- `This process is not trusted! Input event monitoring will not be possible...`

That means macOS permissions were not granted yet.

### No selected text

- The tool acts on current selection only.
- Highlight text in your target app before using button/shortcut.

### Ollama offline

- Start Ollama service.
- Confirm endpoint in settings matches running instance.

## What is already implemented now

- Full modular app structure
- UI + tray
- Global shortcuts for every feature
- Ollama model discovery + health checks
- Optional OpenAI/Gemini providers
- Settings file + live reload
- Replace/clipboard output behavior
- Project docs + requirements + Docker scaffold

