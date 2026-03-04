from __future__ import annotations

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.operations import OperationBuilder
from app.providers import ProviderManager
from app.settings import SettingsManager


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        settings_path = Path(tmp) / "settings.json"
        manager = SettingsManager(settings_path)
        settings = manager.get()

        assert settings["provider"] in {"ollama", "openai", "gemini"}
        assert "openai" in settings and "api_key" in settings["openai"]
        assert "gemini" in settings and "api_key" in settings["gemini"]

        ops = OperationBuilder()
        prompt_fix = ops.build_prompt("fix", "teh line", settings)
        prompt_sum = ops.build_prompt("summarize", "long text", settings)
        prompt_tr = ops.build_prompt("translate_es", "hello", settings)

        assert "Return ONLY" in prompt_fix
        assert "summary" in prompt_sum.lower()
        assert "spanish" in prompt_tr.lower()

        providers = ProviderManager(timeout=5)
        openai_models = providers.provider_models("openai", settings)
        gemini_models = providers.provider_models("gemini", settings)

        assert "gpt-4o" in openai_models
        assert "gpt-4o-mini" in openai_models
        assert "gpt-4-turbo" in openai_models
        assert "gemini-2.5-flash" in gemini_models
        assert "gemini-2.5-pro" in gemini_models

        ok, message = providers.ollama_health(settings)
        print("Ollama health:", ok, message)
        print("Smoke test passed")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
