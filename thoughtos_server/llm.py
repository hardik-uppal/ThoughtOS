"""Multi-provider LLM abstraction.

Supports Ollama (local), Gemini (Google), OpenAI (cloud).
Any provider can be used for extraction, rule generation, or improvement.
"""

from __future__ import annotations

import json
import time
from typing import Optional

from .config import LLMConfig

# --- Provider implementations ---


def _call_ollama(
    prompt: str,
    config: LLMConfig,
    json_mode: bool = False,
) -> str:
    """Call Ollama API."""
    import urllib.request
    import urllib.error

    url = f"{config.base_url}/api/generate"
    body = json.dumps({
        "model": config.model,
        "prompt": prompt,
        "stream": False,
        "temperature": config.temperature,
        "options": {"num_predict": config.max_tokens},
        **({"format": "json"} if json_mode else {}),
    }).encode("utf-8")

    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data.get("response", "")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama unreachable at {config.base_url}: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Ollama returned invalid JSON: {e}")


def _call_gemini(prompt: str, config: LLMConfig, json_mode: bool = False) -> str:
    """Call Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai not installed. "
            "Run: pip install google-generativeai"
        )

    api_key = config.api_key
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY not set for Gemini provider")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(config.model or "gemini-2.0-flash")
    response = model.generate_content(prompt)
    text = response.text or ""
    if json_mode:
        text = text.replace("```json", "").replace("```", "").strip()
    return text


def _call_openai(prompt: str, config: LLMConfig, json_mode: bool = False) -> str:
    """Call OpenAI-compatible API."""
    import urllib.request
    import urllib.error

    api_key = config.api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set for OpenAI provider")

    base = config.base_url.rstrip("/")
    url = f"{base}/chat/completions"
    body = json.dumps({
        "model": config.model or "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": config.temperature,
        "max_tokens": config.max_tokens,
        **({"response_format": {"type": "json_object"}} if json_mode else {}),
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenAI API error: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Unexpected OpenAI response: {e}")


PROVIDERS = {
    "ollama": _call_ollama,
    "gemini": _call_gemini,
    "openai": _call_openai,
}


# --- Public API ---


def call_llm(
    prompt: str,
    config: LLMConfig,
    json_mode: bool = False,
    retries: int = 2,
) -> str:
    """Call an LLM with retries. Returns text response or raises RuntimeError."""
    provider_fn = PROVIDERS.get(config.provider)
    if not provider_fn:
        raise ValueError(
            f"Unknown LLM provider: {config.provider}. "
            f"Must be one of: {list(PROVIDERS.keys())}"
        )

    last_error = None
    for attempt in range(retries + 1):
        try:
            return provider_fn(prompt, config, json_mode=json_mode)
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(
        f"LLM call failed after {retries + 1} attempts: {last_error}"
    )


def call_llm_json(
    prompt: str,
    config: LLMConfig,
    retries: int = 2,
) -> Optional[dict]:
    """Call an LLM and parse JSON response. Returns dict or None on failure."""
    try:
        text = call_llm(prompt, config, json_mode=True, retries=retries)
        text = text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        return json.loads(text)
    except (json.JSONDecodeError, RuntimeError) as e:
        print(f"[LLM JSON] Failed: {e}")
        return None


def check_provider(config: LLMConfig) -> dict:
    """Check if a provider is available and which models are accessible."""
    try:
        if config.provider == "ollama":
            import urllib.request
            url = f"{config.base_url}/api/tags"
            with urllib.request.urlopen(url, timeout=5) as resp:
                data = json.loads(resp.read())
                models = [m["name"] for m in data.get("models", [])]
            return {
                "status": "ok",
                "provider": "ollama",
                "models": models,
                "current_model": config.model,
                "model_available": any(
                    config.model in m for m in models
                ),
            }
        elif config.provider == "gemini":
            import google.generativeai as genai
            if not config.api_key:
                return {"status": "error", "reason": "Missing GOOGLE_API_KEY"}
            genai.configure(api_key=config.api_key)
            models = [m.name for m in genai.list_models()]
            return {
                "status": "ok",
                "provider": "gemini",
                "models": models,
                "current_model": config.model,
            }
        elif config.provider == "openai":
            if not config.api_key:
                return {"status": "error", "reason": "Missing OPENAI_API_KEY"}
            import urllib.request
            url = f"{config.base_url.rstrip('/')}/models"
            headers = {"Authorization": f"Bearer {config.api_key}"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read())
            models = [m["id"] for m in data.get("data", [])]
            return {
                "status": "ok",
                "provider": "openai",
                "models": models,
                "current_model": config.model,
            }
        else:
            return {"status": "error", "reason": f"Unknown provider: {config.provider}"}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
