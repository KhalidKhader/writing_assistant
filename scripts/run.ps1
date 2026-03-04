# Writing Assistant Run Script for Windows

$VENV_DIR = ".venv"

# ── Pick the best available Python ──────────────────────────────────────
function Get-PythonBin {
    foreach ($candidate in "python", "py", "python3") {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }
    return "python"
}

$PYTHON_BIN = Get-PythonBin

# ── Detect a broken or incompatible venv ────────────────────────────────
$recreate_venv = $false

if (Test-Path $VENV_DIR) {
    if (-not (Test-Path "$VENV_DIR\Scripts\activate.ps1")) {
        Write-Host "Broken virtualenv at $VENV_DIR (no activate script) - recreating..." -ForegroundColor Yellow
        $recreate_venv = $true
    }
    else {
        $VENV_PYTHON = "$VENV_DIR\Scripts\python.exe"
        if (-not (Test-Path $VENV_PYTHON)) {
            Write-Host "Broken virtualenv at $VENV_DIR (python binary missing) - recreating..." -ForegroundColor Yellow
            $recreate_venv = $true
        }
    }
}

if ($recreate_venv) {
    Remove-Item -Recurse -Force $VENV_DIR -ErrorAction SilentlyContinue
}

# ── Setup venv if missing ───────────────────────────────────────────────
if (-not (Test-Path $VENV_DIR)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $PYTHON_BIN -m venv $VENV_DIR
}

# ── Activate venv ───────────────────────────────────────────────────────
Write-Host "Activating virtual environment..." -ForegroundColor Gray
. "$VENV_DIR\Scripts\activate.ps1"

# ── Install/Update requirements ─────────────────────────────────────────
if (Test-Path "requirements.txt") {
    $req_time = (Get-Item "requirements.txt").LastWriteTime
    $venv_executable = "$VENV_DIR\Scripts\python.exe"
    $venv_time = (Get-Item $venv_executable).CreationTime
    
    # Simple check: if requirements.txt is newer than venv creation, or if PySide6 is not installed
    $needs_install = $false
    if ($req_time -gt $venv_time) {
        $needs_install = $true
    } else {
        $check = & $venv_executable -c "import PySide6" 2>$null
        if ($LASTEXITCODE -ne 0) {
            $needs_install = $true
        }
    }

    if ($needs_install) {
        Write-Host "Installing/updating dependencies..." -ForegroundColor Cyan
        & $venv_executable -m pip install --upgrade pip
        & $venv_executable -m pip install -r requirements.txt
    }
}

# ── Run the application ─────────────────────────────────────────────────
Write-Host "Starting Writing Assistant..." -ForegroundColor Green
# Force UTF-8 for subprocess output on Windows (avoids cp1252 UnicodeDecodeError)
$env:PYTHONUTF8 = "1"
# Fix QFont::setPointSize warning on Windows DPI scaling
$env:QT_FONT_DPI = "96"
& $venv_executable main.py
