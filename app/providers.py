from __future__ import annotations

import json
import logging
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from .platform_utils import has_ollama_cli

logger = logging.getLogger(__name__)


OPENAI_MODELS = ["gpt-5-nano", "gpt-5-mini", "gpt-4o-mini", "gpt-4-turbo"]
GEMINI_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]


class ProviderError(Exception):
    pass


@dataclass
class ProviderManager:
    # Very short timeout for health checks and model listing — avoids blocking the UI.
    list_timeout: float = 15.0
    # Slightly longer timeout for one-off probes (kept for compatibility).
    timeout: float = 15.0
    # Generate calls can run for several minutes on slow hardware;
    # use an unlimited *read* timeout so we never cut the model short.
    generate_timeout: httpx.Timeout = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.generate_timeout is None:
            self.generate_timeout = httpx.Timeout(
                connect=15.0,
                read=None,   # unlimited – wait as long as the model needs
                write=30.0,
                pool=10.0,
            )

    def _make_client(self, timeout: Any) -> httpx.Client:
        """Return an httpx.Client, falling back to verify=False if certifi is missing."""
        try:
            return httpx.Client(timeout=timeout, trust_env=False)
        except FileNotFoundError:
            logger.warning("CA bundle missing; using fallback client with verify=False")
            return httpx.Client(timeout=timeout, trust_env=False, verify=False)

    def _list_client(self) -> httpx.Client:
        """Short-timeout client for health checks and model listing (non-blocking UI use)."""
        return self._make_client(self.list_timeout)

    def _client(self) -> httpx.Client:
        return self._make_client(self.timeout)

    def _generate_client(self) -> httpx.Client:
        return self._make_client(self.generate_timeout)

    def list_ollama_models(self, settings: dict[str, Any]) -> list[str]:
        endpoint = settings["ollama"]["endpoint"].rstrip("/")
        url = f"{endpoint}/api/tags"
        try:
            with self._list_client() as client:
                response = client.get(url)
                response.raise_for_status()
            models = response.json().get("models", [])
            local_models = [m.get("name", "") for m in models if m.get("name")]
            suggested = settings.get("ollama", {}).get("suggested_models", [])
            merged = list(dict.fromkeys(local_models + suggested))
            logger.debug("Ollama models fetched: %d local, %d total", len(local_models), len(merged))
            return merged
        except Exception:
            logger.warning("Failed to fetch ollama models; falling back to suggested list")
            return settings.get("ollama", {}).get("suggested_models", [])

    def pull_ollama_model(self, model_name: str) -> tuple[bool, str]:
        try:
            if not has_ollama_cli():
                return False, "Ollama CLI not found"
            process = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60 * 30,
                check=False,
            )
            if process.returncode != 0:
                stderr = process.stderr.strip() or process.stdout.strip() or "Unknown error"
                return False, stderr
            return True, process.stdout.strip() or f"Model {model_name} pulled successfully"
        except Exception as exc:
            logger.exception("Failed to pull ollama model")
            return False, str(exc)

    def ollama_health(self, settings: dict[str, Any]) -> tuple[bool, str]:
        endpoint = settings["ollama"]["endpoint"].rstrip("/")
        try:
            with self._list_client() as client:
                response = client.get(f"{endpoint}/api/tags")
                response.raise_for_status()
            count = len(response.json().get("models", []))
            return True, f"Ollama online ({count} models)"
        except httpx.ConnectError:
            logger.debug("Ollama unreachable at %s", endpoint)
            return False, f"Ollama offline (connection refused at {endpoint})"
        except httpx.TimeoutException:
            logger.debug("Ollama health check timed out at %s", endpoint)
            return False, "Ollama offline (timeout)"
        except Exception as exc:
            logger.debug("Ollama health check failed: %s", exc)
            return False, f"Ollama offline: {exc}"

    def provider_models(self, provider: str, settings: dict[str, Any]) -> list[str]:
        if provider == "ollama":
            return self.list_ollama_models(settings)
        if provider == "openai":
            current = settings.get("openai", {}).get("model", "gpt-4o-mini")
            if current in OPENAI_MODELS:
                return list(dict.fromkeys([current] + OPENAI_MODELS))
            return list(OPENAI_MODELS)
        if provider == "gemini":
            current = settings.get("gemini", {}).get("model", "gemini-3.1-flash-lite-preview")
            if current in GEMINI_MODELS:
                return list(dict.fromkeys([current] + GEMINI_MODELS))
            return list(GEMINI_MODELS)
        return []

    # ── Output cleanup ───────────────────────────────────────────────────────

    _PREAMBLE_RE = re.compile(
        r'^(here\s+is\b|here\'s\b|sure[,!]?\s*|of\s+course[,!]?\s*|certainly[,!]?\s*|'
        r'translation[:：]\s*|translated\s+text[:：]\s*|summary[:：]\s*|'
        r'fixed\s+text[:：]\s*|corrected\s+text[:：]\s*|result[:：]\s*|'
        r'output[:：]\s*|answer[:：]\s*)',
        re.IGNORECASE,
    )

    def _clean_output(self, text: str) -> str:
        """Strip common AI artifacts: surrounding quotes, preamble phrases, blank lead/trail."""
        text = text.strip()
        if not text:
            return text
        # Remove surrounding triple or single quotes/backticks
        for q in ('"""', "'''", '```', '"', "'", "`"):
            if (
                len(text) > len(q) * 2
                and text.startswith(q)
                and text.endswith(q)
            ):
                inner = text[len(q) : -len(q)].strip()
                # Only strip quotes when the inner content looks like real text
                if inner and not inner.startswith(q):
                    text = inner
                break
        # Strip leading preamble lines one by one
        lines = text.splitlines()
        while lines and self._PREAMBLE_RE.match(lines[0].strip()):
            lines.pop(0)
        text = "\n".join(lines).strip()
        return text

    # ── Unified generate API ─────────────────────────────────────────────────

    def generate(self, settings: dict[str, Any], prompt: str) -> str:
        provider = settings.get("provider", "ollama")
        if provider == "ollama":
            return self._ollama_generate(settings, prompt)
        if provider == "openai":
            return self._openai_generate(settings, prompt)
        if provider == "gemini":
            return self._gemini_generate(settings, prompt)
        raise ProviderError(f"Unsupported provider: {provider}")

    def generate_streaming(
        self,
        settings: dict[str, Any],
        prompt: str,
        on_chunk: Callable[[str], None],
    ) -> str:
        """Stream generation (Ollama only).  Falls back to non-streaming for
        OpenAI and Gemini, calling *on_chunk* once with the full result."""
        provider = settings.get("provider", "ollama")
        if provider == "ollama":
            return self._ollama_generate_streaming(settings, prompt, on_chunk)
        # Non-streaming path: compute full result then emit once
        result = self.generate(settings, prompt)
        on_chunk(result)
        return result

    def _ollama_generate(self, settings: dict[str, Any], prompt: str) -> str:
        """Use /api/chat (works for all modern Ollama models).
        Falls back to /api/generate if the chat endpoint returns 404."""
        endpoint = settings["ollama"]["endpoint"].rstrip("/")
        model = settings["ollama"]["model"]
        chat_payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": settings["ollama"].get("keep_alive", "5m"),
        }
        model_name = settings["ollama"]["model"]
        logger.debug("Ollama generate: model=%s endpoint=%s", model_name, endpoint)
        try:
            with self._generate_client() as client:
                response = client.post(f"{endpoint}/api/chat", json=chat_payload)
                response.raise_for_status()
            raw = response.json().get("message", {}).get("content", "").strip()
            return self._clean_output(raw)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                err_body = e.response.text.lower()
                if "model" in err_body and ("not found" in err_body or "pull" in err_body):
                    raise ProviderError(
                        f"Model '{model_name}' is not pulled. "
                        f"Click '⬇ Pull Model' or run: ollama pull {model_name}"
                    ) from e
                logger.warning("Ollama /api/chat not found; retrying with /api/generate")
                return self._ollama_generate_legacy(settings, prompt)
            logger.error("Ollama chat error (model=%s): %s", model_name, e.response.text)
            raise ProviderError(f"Ollama HTTP error: {e.response.status_code} — {e.response.text}") from e
        except httpx.ConnectError as e:
            endpoint_url = settings["ollama"]["endpoint"]
            raise ProviderError(
                f"Cannot reach Ollama at {endpoint_url}. Is Ollama running?"
            ) from e
        except Exception as e:
            logger.exception("Ollama chat generate failed (model=%s)", model_name)
            raise ProviderError(f"Ollama generation failed: {e}") from e

    def _ollama_generate_streaming(
        self,
        settings: dict[str, Any],
        prompt: str,
        on_chunk: Callable[[str], None],
    ) -> str:
        """Stream tokens from Ollama /api/chat, calling on_chunk with the
        accumulated text after every token.  Falls back to /api/generate on 404."""
        endpoint = settings["ollama"]["endpoint"].rstrip("/")
        model = settings["ollama"]["model"]
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
            "keep_alive": settings["ollama"].get("keep_alive", "5m"),
        }
        model_name = settings["ollama"]["model"]
        logger.debug("Ollama stream: model=%s endpoint=%s", model_name, endpoint)
        accumulated: list[str] = []
        try:
            with self._generate_client() as client:
                with client.stream("POST", f"{endpoint}/api/chat", json=payload) as resp:
                    if resp.status_code == 404:
                        resp.read()
                        err_body = resp.text.lower()
                        if "model" in err_body and ("not found" in err_body or "pull" in err_body):
                            raise ProviderError(
                                f"Model '{model_name}' is not pulled. "
                                f"Click '⬇ Pull Model' or run: ollama pull {model_name}"
                            )
                        logger.warning("Ollama /api/chat (stream) not found; falling back to generate")
                        return self._ollama_generate_legacy(settings, prompt)
                    
                    resp.raise_for_status()

                    for raw_line in resp.iter_lines():
                        if not raw_line:
                            continue
                        try:
                            chunk = json.loads(raw_line)
                        except json.JSONDecodeError:
                            continue
                        delta = chunk.get("message", {}).get("content", "")
                        if delta:
                            accumulated.append(delta)
                            on_chunk("".join(accumulated))
                        if chunk.get("done"):
                            break
            # Ensure we got *something*
            full_text = "".join(accumulated)
            if not full_text:
                logger.warning("Ollama stream returned empty content (model=%s)", model_name)
            return self._clean_output(full_text)
        except httpx.HTTPStatusError as e:
            try:
                e.response.read()
                msg = f"Ollama HTTP error: {e.response.status_code} — {e.response.text}"
            except Exception:
                msg = f"Ollama HTTP error: {e.response.status_code}"
            raise ProviderError(msg) from e
        except httpx.ConnectError as e:
            endpoint_url = settings["ollama"]["endpoint"]
            raise ProviderError(
                f"Cannot reach Ollama at {endpoint_url}. Is Ollama running?"
            ) from e
        except Exception as e:
            logger.exception("Ollama streaming failed (model=%s)", model_name)
            raise ProviderError(f"Ollama streaming failed: {e}") from e

    def _ollama_generate_legacy(self, settings: dict[str, Any], prompt: str) -> str:
        """Fallback: /api/generate (older Ollama versions)."""
        endpoint = settings["ollama"]["endpoint"].rstrip("/")
        payload = {
            "model": settings["ollama"]["model"],
            "prompt": prompt,
            "keep_alive": settings["ollama"].get("keep_alive", "5m"),
            "stream": False,
        }
        try:
            with self._generate_client() as client:
                response = client.post(f"{endpoint}/api/generate", json=payload)
                response.raise_for_status()
            raw = response.json().get("response", "").strip()
            return self._clean_output(raw)
        except httpx.HTTPStatusError as e:
            logger.error("Ollama generate error: %s", e.response.text)
            raise ProviderError(f"Ollama HTTP error: {e.response.status_code} — {e.response.text}") from e
        except Exception as e:
            logger.exception("Ollama legacy generate failed")
            raise ProviderError(f"Ollama generation failed: {e}") from e

    def _openai_generate(self, settings: dict[str, Any], prompt: str) -> str:
        api_key = settings["openai"].get("api_key", "")
        if not api_key:
            raise ProviderError("OpenAI API key is missing")
        base_url = settings["openai"].get("base_url", "https://api.openai.com/v1").rstrip("/")
        model = settings["openai"].get("model", "gpt-4o-mini")
        if model not in OPENAI_MODELS:
            model = "gpt-5-mini"
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a text-transformation assistant. "
                        "Return ONLY the transformed text — no preamble, no explanation, "
                        "no surrounding quotes, no labels, no metadata. "
                        "Never begin your response with phrases like 'Here is', 'Sure', "
                        "'Certainly', 'Translation:', 'Summary:', 'Result:', or similar."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
        # Avoid passing temperature. Some models reject non-default values
        # and some reject the parameter entirely.
        headers = {"Authorization": f"Bearer {api_key}"}
        try:
            with self._generate_client() as client:
                response = client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
                response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"].strip()
            return self._clean_output(raw)
        except httpx.HTTPStatusError as e:
            logger.error("OpenAI error: %s", e.response.text)
            raise ProviderError(f"OpenAI error: {e.response.status_code} — {e.response.text}") from e
        except Exception as e:
            logger.exception("OpenAI generate failed")
            raise ProviderError(f"OpenAI generation failed: {e}") from e

    def _gemini_generate(self, settings: dict[str, Any], prompt: str) -> str:
        api_key = settings["gemini"].get("api_key", "")
        if not api_key:
            raise ProviderError("Gemini API key is missing")
        base_url = settings["gemini"].get("base_url", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
        model = settings["gemini"].get("model", "gemini-3.1-flash-lite-preview")
        if model not in GEMINI_MODELS:
            model = "gemini-3.1-flash-lite-preview"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2},
        }
        url = f"{base_url}/models/{model}:generateContent?key={api_key}"
        try:
            with self._generate_client() as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
            body = response.json()
            candidates = body.get("candidates", [])
            if not candidates:
                raise ProviderError("Gemini returned an empty response")
            raw = candidates[0]["content"]["parts"][0]["text"].strip()
            return self._clean_output(raw)
        except httpx.HTTPStatusError as e:
            logger.error(f"Gemini error: {e.response.text}")
            raise ProviderError(f"Gemini error: {e.response.status_code} - {e.response.text}") from e
        except Exception as e:
            logger.exception("Gemini generate failed")
            raise ProviderError(f"Gemini generation failed: {str(e)}") from e
