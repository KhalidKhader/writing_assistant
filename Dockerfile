FROM python:3.12-slim

WORKDIR /app

# Install all system deps required by PySide6/Qt in one layer.
# libgl1 + libgles2 cover libGL.so.1 / libGLESv2.so.2 on Debian Bookworm.
# libxcb-* and libx11-xcb1 are needed for the xcb platform plugin.
RUN apt-get update && apt-get install -y --no-install-recommends \
	build-essential \
	python3-dev \
	linux-libc-dev \
	libgl1 \
	libgl1-mesa-dev \
	libgles2 \
	libx11-6 \
	libx11-xcb1 \
	libxext6 \
	libxkbcommon-x11-0 \
	libxcb-icccm4 \
	libxcb-image0 \
	libxcb-keysyms1 \
	libxcb-randr0 \
	libxcb-render-util0 \
	libxcb-xinerama0 \
	libxcb1 \
	libdbus-1-3 \
	libegl1 \
	libglib2.0-0 \
	libfontconfig1 \
	&& rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Offscreen platform so Qt doesn't crash without a display.
ENV QT_QPA_PLATFORM=offscreen
# Fix QFont::setPointSize <= 0 warning that appears when no real DPI is available.
ENV QT_FONT_DPI=96
# Force UTF-8 subprocess output; prevents codec errors on non-UTF-8 locales.
ENV PYTHONUTF8=1
# When running in Docker, Ollama runs on the host.
# docker run --add-host=host.docker.internal:host-gateway ...
# Override at runtime with:  -e OLLAMA_ENDPOINT=http://host.docker.internal:11434
ENV OLLAMA_ENDPOINT=http://host.docker.internal:11434

# Docker cannot display the GUI (no X server / display server available).
# The default CMD runs the headless smoke test, which validates settings,
# prompts, and provider config without needing a screen or Ollama running.
# To run the full app on a real desktop use scripts/run.ps1 (Windows) or
# scripts/run.sh (macOS/Linux) instead.
CMD ["python", "scripts/smoke_test.py"]
