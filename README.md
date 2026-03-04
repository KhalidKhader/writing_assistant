t> cd "C:\Users\khalid.khader\OneDrive - Medido Health\Desktop\Work\writing_assi
stant"; $content = @'
>> #  Writing Assistant
>>
>> A production-grade cross-platform desktop writing assistant with a floating t
oolbar, global keyboard shortcuts, and support for local (Ollama) and cloud (Ope
nAI, Gemini) AI models.
>>
>> ---
>>
>> ## Features at a Glance
>>
>> | Feature | Details |
>> |---|---|
>> | **Fix Grammar** | Corrects grammar, spelling, punctuation, capitalization w
hile preserving structure |
>> | **Summarize** | Condenses selected text into concise bullet points |       
>> | **Translate** | Built-in buttons for Arabic, English, Spanish, French, Germ
an + 15+ custom languages (including Hebrew) |
>> | **Output Modes** | Replace selected text in-place **or** copy result to cli
pboard |
>> | **Providers** | Ollama (local, private), OpenAI, Gemini |
>> | **Global Hotkeys** | Keyboard shortcuts that work from any app |
>> | **Streaming Output** | See the AI response build in real-time in the previe
w panel |
>> | **Floating Ring** | Draggable always-on-top button to toggle the main windo
w |
>> | **System Tray** | Minimize to tray; run actions from tray menu |
>> | **Live Config** | Edit `settings.json` and changes apply instantly  no rest
art needed |
>>
>> ---
>>
>> ## Quick Start
>>
>> ### Windows
>>
>> ```powershell
>> .\scripts\run.ps1
>> ```
>>
>> The script automatically:
>> 1. Creates a `.venv` virtual environment if one does not exist
>> 2. Installs all dependencies from `requirements.txt`
>> 3. Launches the Writing Assistant
>>
>> > **Requires Python 3.11+**  download from https://www.python.org/downloads/ 
>>
>> ### macOS
>>
>> ```bash
>> bash scripts/run.sh
>> ```
>>
>> > **macOS Accessibility Permission required** for global hotkeys and "Replace
 in place":
>> > System Settings  Privacy & Security  Accessibility  enable your Terminal ap
p.
>> > The app shows a warning banner and a direct button to open that settings pa
ge if permission is missing.
>>
>> ### Linux
>>
>> ```bash
>> bash scripts/run.sh
>> ```
>>
>> ### Manual Setup (any platform)
>>
>> ```bash
>> python3 -m venv .venv
>> source .venv/bin/activate     # macOS / Linux
>> .venv\Scripts\Activate.ps1    # Windows PowerShell
>> pip install -r requirements.txt
>> python main.py
>> ```
>>
>> ---
>>
>> ## Provider Setup
>>
>> ### Ollama  Local AI (default, free, private)
>>
>> Runs AI models entirely on your machine. No internet or API key needed.      
>>
>> **Install Ollama:**
>>
>> - **Windows**: Download from https://ollama.com/download  it starts automatic
ally as a Windows service.
>> - **macOS**: Download from https://ollama.com/download or:
>>   ```bash
>>   brew install ollama
>>   ollama serve
>>   ```
>> - **Linux**:
>>   ```bash
>>   curl -fsSL https://ollama.com/install.sh | sh
>>   ```
>>
>> **Pull a model** (do this once):
>>
>> ```bash
>> ollama pull mistral:7b-instruct-v0.2-q4_K_S   # ~4 GB, recommended
>> ollama pull gemma3:4b                           # ~2.5 GB, lighter
>> ollama pull llama3.1:8b                         # ~5 GB, smarter
>> ```
>>
>> You can also pull directly from the app  select a model in the dropdown and c
lick ** Pull Model**
>> (the button is only visible when Ollama is the selected provider).
>>
>> > Default endpoint: `http://localhost:11434`  change it in Settings if Ollama
 runs elsewhere.
>>
>> ---
>>
>> ### OpenAI
>>
>> 1. Get a key from https://platform.openai.com/api-keys
>> 2. Open the **Settings** tab  **Provider Credentials**  paste into **OpenAI A
PI key**  **Save All Settings**
>>
>> Available models: `gpt-5-nano`, `gpt-5-mini`, `gpt-4o-mini`, `gpt-4-turbo`   
>>
>> > The  Pull Model button is **hidden** for OpenAI  it only applies to Ollama.
>>
>> ---
>>
>> ### Gemini
>>
>> 1. Get a key from https://aistudio.google.com/app/apikey
>> 2. Open the **Settings** tab  paste into **Gemini API key**  **Save All Setti
ngs**
>>
>> Available models (default: `gemini-3.1-flash-lite-preview`):
>> - `gemini-3-flash-preview`
>> - `gemini-3.1-flash-lite-preview`  **default**
>> - `gemini-2.5-flash`
>> - `gemini-2.5-flash-lite`
>>
>> > The  Pull Model button is **hidden** for Gemini  it only applies to Ollama.
>>
>> ---
>>
>> ## Using the App
>>
>> ### Workflow
>>
>> 1. **Select text** in any application (browser, Word, Slack, VS Code, etc.)  
>> 2. **Click an action button** or press a keyboard shortcut
>> 3. The result appears in the **Last Output Preview** panel (streamed in real-
time for Ollama)
>> 4. Depending on **Output Mode**:
>>    - **Replace in place**  the selected text in the source app is replaced au
tomatically
>>    - **Copy to clipboard**  result is copied; paste manually wherever you wan
t
>> 5. Use ** Copy Result** or ** Paste to Source** for manual control after revi
ewing
>>
>> ### Output Modes
>>
>> | Mode | Behavior |
>> |---|---|
>> | **Replace in place** | Automatically replaces your selected text |
>> | **Copy to clipboard** | Copies the result; paste manually |
>>
>> Switch using the **Output** dropdown in the header.
>> Per-action overrides are available in the **Settings** tab.
>>
>> > **Note**: When "Copy to clipboard" is set as the global output mode, it ove
rrides individual per-action settings  all actions will copy to clipboard.      
>>
>> ---
>>
>> ## Language Buttons
>>
>> The language action buttons display colored circular letter-avatars (e.g. **A
R**, **EN**, **ES**).
>> This approach renders correctly on all platforms  Windows does not support Un
icode flag emoji in Qt applications.
>>
>> Built-in quick buttons: **AR** Arabic  **EN** English  **ES** Spanish  **FR**
 French  **DE** German
>>
>> Custom language dropdown includes 15+ languages:
>> Arabic, Chinese (Simplified), Dutch, English, French, German, **Hebrew**, Hin
di, Italian, Japanese, Korean, Portuguese, Russian, Spanish, Turkish
>>
>> ---
>>
>> ## Global Keyboard Shortcuts
>>
>> These shortcuts fire from any app, even when the Writing Assistant window is 
hidden.
>>
>> | Action | Windows / Linux | macOS |
>> |---|---|---|
>> | Fix Grammar | `Ctrl+Alt+F` | `++F` |
>> | Summarize | `Ctrl+Alt+S` | `++S` |
>> | Translate  Arabic | `Ctrl+Alt+1` | `++1` |
>> | Translate  English | `Ctrl+Alt+2` | `++2` |
>> | Translate  Spanish | `Ctrl+Alt+3` | `++3` |
>> | Translate  French | `Ctrl+Alt+4` | `++4` |
>> | Translate  German | `Ctrl+Alt+5` | `++5` |
>> | Translate  Custom | `Ctrl+Alt+6` | `++6` |
>>
>> All shortcuts are fully customizable from the **Settings** tab or in `setting
s.json`.
>>
>> ---
>>
>> ## Pulling Ollama Models
>>
>> When Ollama is the active provider:
>>
>> 1. Select a model from the **Model** dropdown
>> 2. Click ** Pull Model**
>> 3. A progress bar appears while the model downloads (can take several minutes
 for large models)
>> 4. Once done, the model is ready to use
>>
>> > The  Pull Model button and its loading bar are **only visible when Ollama i
s selected**.
>> > They are hidden for OpenAI and Gemini since those providers do not require 
local downloads.
>>
>> ---
>>
>> ## Settings File
>>
>> Default path: `~/.writing_assistant/settings.json`
>> Windows: `C:\Users\<YourName>\.writing_assistant\settings.json`
>>
>> Override with an environment variable:
>> ```bash
>> WRITING_ASSISTANT_SETTINGS=/path/to/settings.json python main.py
>> ```
>>
>> A full example is in `settings.example.json`.
>>
>> ### Key settings
>>
>> ```json
>> {
>>   "provider": "ollama",
>>   "output_mode": "replace",
>>   "ollama": {
>>     "endpoint": "http://localhost:11434",
>>     "model": "mistral:7b-instruct-v0.2-q4_K_S",
>>     "keep_alive": "5m"
>>   },
>>   "openai": { "api_key": "sk-...", "model": "gpt-4o-mini" },
>>   "gemini": { "api_key": "AIza...", "model": "gemini-3.1-flash-lite-preview" 
},
>>   "shortcuts": { "fix": "<ctrl>+<alt>+f", "summarize": "<ctrl>+<alt>+s" },   
>>   "custom_languages": ["Arabic", "Hebrew", "French"],
>>   "selected_custom_language": "Hebrew",
>>   "logging": { "level": "INFO", "path": "~/.writing_assistant/logs/app.log" }
>> }
>> ```
>>
>> Settings reload automatically every 2 seconds  no restart needed.
>>
>> ---
>>
>> ## Customizing Prompts
>>
>> Go to the **Prompts** tab, edit the instruction text for Fix / Summarize / Tr
anslate, and click **Save Prompts**.
>> You can also edit `actions.<action>.prompt` directly in `settings.json`.     
>>
>> ---
>>
>> ## Architecture
>>
>> ```
>> writing_assistant/
>>  main.py                  # Entry point
>>  app/
>>     ui.py                # Floating bar, tray, all UI logic
>>     providers.py         # Ollama / OpenAI / Gemini API calls
>>     operations.py        # Prompt templates (fix, summarize, translate)      
>>     settings.py          # Settings defaults, merge, file watch, save        
>>     selection.py         # Read selected text, replace, clipboard
>>     hotkeys.py           # Global keyboard shortcut manager (pynput)
>>     platform_utils.py    # Platform detection helpers
>>     logging_utils.py     # Rotating file log setup
>>  scripts/
>>     run.ps1              # Windows one-command launcher
>>     run.sh               # macOS / Linux one-command launcher
>>     smoke_test.py        # Headless CI test (no GUI or Ollama needed)        
>>  requirements.txt
>>  Dockerfile               # CI / smoke-test only  NOT for running the GUI app
>>  settings.example.json
>> ```
>>
>> ---
>>
>> ## Troubleshooting
>>
>> ### Hotkeys don't work on macOS
>>
>> Grant Accessibility permission:
>> 1. **System Settings  Privacy & Security  Accessibility**
>> 2. Add your terminal application and enable it
>> 3. **Do NOT use `sudo`**  run as your normal user
>> 4. Restart the app after granting permission
>>
>> ### "Replace in place" does not work
>>
>> - Make sure the target app still has text **selected** before clicking or pre
ssing the shortcut
>> - Some apps (browser address bars, password fields) block programmatic paste 
 use **Copy to clipboard** mode instead
>>
>> ### Ollama offline
>>
>> - **Windows**: Check the system tray for the Ollama icon; start from Start Me
nu if missing
>> - **macOS / Linux**: Run `ollama serve` in a terminal
>> - Check that the endpoint in Settings matches your running instance
>>
>> ### Model not found / not pulled
>>
>> Click ** Pull Model** in the app, or run:
>> ```bash
>> ollama pull <model-name>
>> ```
>>
>> ### `QFont::setPointSize: Point size <= 0 (-1)` warnings
>>
>> These are cosmetic Qt warnings on some configurations. The app now sets `QT_F
ONT_DPI=96` automatically on Windows/Linux, which suppresses them.
>>
>> ### OpenAI / Gemini key missing error
>>
>> Enter your API key in **Settings  Provider Credentials** and click **Save All
 Settings**.
>>
>> ---
>>
>> ## Docker  CI / Smoke Testing Only
>>
>> >  **Docker does not run the desktop GUI.** There is no display server in a c
ontainer, so the floating bar, system tray, and global hotkeys cannot work. Dock
er is only for CI smoke testing.
>>
>> ```bash
>> # Build
>> docker build -t writing-assistant .
>>
>> # Run headless smoke test (default CMD)
>> docker run --rm writing-assistant
>>
>> # Against a real Ollama instance on the host (CI)
>> docker run --rm --add-host=host.docker.internal:host-gateway \
>>   -e OLLAMA_ENDPOINT=http://host.docker.internal:11434 \
>>   writing-assistant
>> ```
>>
>> **To use the app, always run it natively:**
>> ```bash
>> .\scripts\run.ps1    # Windows
>> bash scripts/run.sh  # macOS / Linux
>> ```
>>
>> ---
>>
>> ## Logs
>>
>> Default: `~/.writing_assistant/logs/app.log`
>> Windows: `C:\Users\<YourName>\.writing_assistant\logs\app.log`
>>
>> Configure in `settings.json`:
>> ```json
>> { "logging": { "level": "INFO", "path": "~/.writing_assistant/logs/app.log" }
 }
>> ```
>>
>> ---
>>
>> ## Requirements
>>
>> | Requirement | Version |
>> |---|---|
>> | Python | 3.11+ (3.12 recommended) |
>> | PySide6 |  6.8.0 |
>> | httpx |  0.27.0 |
>> | pynput |  1.7.7 |
>> | pyperclip |  1.9.0 |
>> | Ollama | Any recent release (for local AI) |
>>
>> ---
>>
>> ## Security Notes
>>
>> - API keys are stored in `~/.writing_assistant/settings.json`  keep this file
 private
>> - For maximum privacy use **Ollama**  text never leaves your machine
>> - Do not commit `settings.json` to version control
>> '@
PS C:\Users\khalid.khader\OneDrive - Medido Health\Desktop\Work\writing_assistan
t> $content | Set-Content README.md -Encoding UTF8
