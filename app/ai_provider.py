"""AI provider abstraction layer.

Routes requests to Ollama (local) or cloud APIs (Anthropic/OpenAI) based on
the AIConfig stored in the database.  Every public function returns a result
object — nothing raises to the caller on provider errors.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.database import AIConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

@dataclass
class AIChatMessage:
    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        return d


@dataclass
class AICompletionRequest:
    messages: list[AIChatMessage]
    model: str | None = None
    temperature: float = 0.3
    max_tokens: int = 1024
    tools: list[dict] | None = None
    task_type: str = "chat"  # "chat", "vision", "csv_cleanup", "inventory_suggest"
    images: list[str] | None = None  # base64-encoded images for vision tasks


@dataclass
class AICompletionResponse:
    content: str = ""
    model_used: str = ""
    provider: str = ""  # "ollama", "anthropic", "openai"
    tool_calls: list[dict] | None = None
    usage: dict | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# API key encryption helpers (Fernet, derived from app secret_key)
# ---------------------------------------------------------------------------

def _derive_fernet_key(secret: str) -> bytes:
    """Derive a 32-byte URL-safe base64-encoded Fernet key from the app secret."""
    raw = hashlib.sha256(f"barcode-buddy-ai-{secret}".encode()).digest()
    return base64.urlsafe_b64encode(raw)


def encrypt_api_key(plaintext: str, secret: str) -> str:
    """Encrypt an API key for storage in the database."""
    if not plaintext:
        return ""
    from cryptography.fernet import Fernet
    f = Fernet(_derive_fernet_key(secret))
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str, secret: str) -> str:
    """Decrypt an API key from the database."""
    if not ciphertext:
        return ""
    from cryptography.fernet import Fernet
    f = Fernet(_derive_fernet_key(secret))
    return f.decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Provider interface
# ---------------------------------------------------------------------------

class AIProvider(ABC):
    @abstractmethod
    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        ...

    @abstractmethod
    async def health_check(self) -> dict:
        ...

    @abstractmethod
    async def list_models(self) -> list[dict]:
        ...


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------

class OllamaProvider(AIProvider):
    """Communicates with a local Ollama instance via HTTP."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        model = request.model or "llama3.2"
        messages = []
        for msg in request.messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.role == "tool" and msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            messages.append(m)

        # Attach images to the last user message for vision tasks
        if request.images and messages:
            for m in reversed(messages):
                if m["role"] == "user":
                    m["images"] = request.images
                    break

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        if request.tools:
            payload["tools"] = _format_tools_for_ollama(request.tools)

        try:
            async with httpx.AsyncClient(timeout=90.0) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                data = resp.json()
        except httpx.TimeoutException:
            return AICompletionResponse(error="Ollama request timed out. The model may be loading or the server is busy.")
        except httpx.ConnectError:
            return AICompletionResponse(error="Could not connect to Ollama. Is it running?")
        except httpx.HTTPStatusError as exc:
            return AICompletionResponse(error=f"Ollama error: {exc.response.status_code} — {exc.response.text[:200]}")
        except Exception as exc:
            return AICompletionResponse(error=f"Ollama error: {exc}")

        message = data.get("message", {})
        tool_calls = _parse_ollama_tool_calls(message)

        return AICompletionResponse(
            content=message.get("content", ""),
            model_used=model,
            provider="ollama",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": data.get("prompt_eval_count", 0),
                "completion_tokens": data.get("eval_count", 0),
            },
        )

    async def health_check(self) -> dict:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return {"status": "ok", "models": len(resp.json().get("models", []))}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return [
                    {"name": m["name"], "size": m.get("size", 0), "modified_at": m.get("modified_at", "")}
                    for m in resp.json().get("models", [])
                ]
        except Exception:
            return []

    async def pull_model(self, model_name: str) -> dict:
        """Start pulling a model. Returns the final status."""
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:
                resp = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model_name, "stream": False},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Cloud provider (Anthropic / OpenAI)
# ---------------------------------------------------------------------------

class CloudProvider(AIProvider):
    """Routes to Anthropic or OpenAI cloud APIs via their official SDKs."""

    def __init__(self, provider_name: str, api_key: str):
        self.provider_name = provider_name  # "anthropic" or "openai"
        self.api_key = api_key

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        if self.provider_name == "anthropic":
            return await self._complete_anthropic(request)
        elif self.provider_name == "openai":
            return await self._complete_openai(request)
        return AICompletionResponse(error=f"Unknown cloud provider: {self.provider_name}")

    async def _complete_anthropic(self, request: AICompletionRequest) -> AICompletionResponse:
        try:
            import anthropic
        except ImportError:
            return AICompletionResponse(error="Anthropic SDK not installed. Run: pip install anthropic")

        model = request.model or "claude-sonnet-4-20250514"
        system_text = ""
        messages = []
        for msg in request.messages:
            if msg.role == "system":
                system_text = msg.content
                continue
            content: Any = msg.content
            if msg.role == "user" and request.images:
                content = []
                for img in request.images:
                    content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img}})
                content.append({"type": "text", "text": msg.content})
            messages.append({"role": msg.role, "content": content})

        try:
            client = anthropic.Anthropic(api_key=self.api_key)
            kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": request.max_tokens,
                "messages": messages,
            }
            if system_text:
                kwargs["system"] = system_text
            if request.tools:
                kwargs["tools"] = _format_tools_for_anthropic(request.tools)

            response = client.messages.create(**kwargs)

            content_text = ""
            tool_calls = []
            for block in response.content:
                if block.type == "text":
                    content_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append({
                        "id": block.id,
                        "name": block.name,
                        "arguments": block.input,
                    })

            return AICompletionResponse(
                content=content_text,
                model_used=model,
                provider="anthropic",
                tool_calls=tool_calls if tool_calls else None,
                usage={"prompt_tokens": response.usage.input_tokens, "completion_tokens": response.usage.output_tokens},
            )
        except Exception as exc:
            return AICompletionResponse(error=f"Anthropic API error: {exc}")

    async def _complete_openai(self, request: AICompletionRequest) -> AICompletionResponse:
        try:
            import openai
        except ImportError:
            return AICompletionResponse(error="OpenAI SDK not installed. Run: pip install openai")

        model = request.model or "gpt-4o"
        messages = []
        for msg in request.messages:
            m: dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.role == "user" and request.images:
                m["content"] = []
                for img in request.images:
                    m["content"].append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}})
                m["content"].append({"type": "text", "text": msg.content})
            if msg.role == "tool" and msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            messages.append(m)

        try:
            client = openai.OpenAI(api_key=self.api_key)
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature,
            }
            if request.tools:
                kwargs["tools"] = _format_tools_for_openai(request.tools)

            response = client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            tool_calls = None
            if choice.message.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments) if tc.function.arguments else {},
                    }
                    for tc in choice.message.tool_calls
                ]

            return AICompletionResponse(
                content=choice.message.content or "",
                model_used=model,
                provider="openai",
                tool_calls=tool_calls,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                },
            )
        except Exception as exc:
            return AICompletionResponse(error=f"OpenAI API error: {exc}")

    async def health_check(self) -> dict:
        if self.provider_name == "anthropic":
            try:
                import anthropic
                client = anthropic.Anthropic(api_key=self.api_key)
                client.messages.create(
                    model="claude-sonnet-4-20250514", max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}],
                )
                return {"status": "ok", "provider": "anthropic"}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
        elif self.provider_name == "openai":
            try:
                import openai
                client = openai.OpenAI(api_key=self.api_key)
                client.chat.completions.create(
                    model="gpt-4o-mini", max_tokens=10,
                    messages=[{"role": "user", "content": "Hi"}],
                )
                return {"status": "ok", "provider": "openai"}
            except Exception as exc:
                return {"status": "error", "error": str(exc)}
        return {"status": "error", "error": f"Unknown provider: {self.provider_name}"}

    async def list_models(self) -> list[dict]:
        if self.provider_name == "anthropic":
            return [
                {"name": "claude-sonnet-4-20250514", "label": "Claude Sonnet 4"},
                {"name": "claude-haiku-4-5-20251001", "label": "Claude Haiku 4.5"},
            ]
        elif self.provider_name == "openai":
            return [
                {"name": "gpt-4o", "label": "GPT-4o"},
                {"name": "gpt-4o-mini", "label": "GPT-4o Mini"},
            ]
        return []


# ---------------------------------------------------------------------------
# AI Router — main entry point
# ---------------------------------------------------------------------------

@dataclass
class _CachedConfig:
    config: dict = field(default_factory=dict)
    timestamp: float = 0.0


_config_cache = _CachedConfig()
_CACHE_TTL = 60.0  # seconds


def _load_ai_config(db: Session) -> AIConfig:
    """Load the singleton AIConfig row."""
    return db.query(AIConfig).filter(AIConfig.id == 1).first()


def get_ai_config_dict(db: Session) -> dict:
    """Return AI config as a dictionary, using a short cache."""
    now = time.time()
    if _config_cache.config and (now - _config_cache.timestamp) < _CACHE_TTL:
        return _config_cache.config
    cfg = _load_ai_config(db)
    if cfg:
        _config_cache.config = cfg.to_dict()
        _config_cache.timestamp = now
    return _config_cache.config


def invalidate_ai_config_cache() -> None:
    """Force the next get_ai_config_dict call to reload from DB."""
    _config_cache.config = {}
    _config_cache.timestamp = 0.0


class AIRouter:
    """Main entry point. Reads config from DB, resolves provider, routes request."""

    def __init__(self, db: Session, secret_key: str):
        self._db = db
        self._secret_key = secret_key
        self._config = _load_ai_config(db)

    def is_enabled(self) -> bool:
        return bool(self._config and self._config.ai_enabled)

    async def complete(self, request: AICompletionRequest) -> AICompletionResponse:
        if not self.is_enabled():
            return AICompletionResponse(error="AI is not enabled. Complete the AI setup first.")

        provider = self._resolve_provider(request.task_type)
        if provider is None:
            return AICompletionResponse(error="No AI provider is configured for this task type.")

        result = await provider.complete(request)

        # If preferred provider failed and the other is available, try fallback
        if result.error:
            fallback = self._get_fallback_provider(request.task_type)
            if fallback is not None:
                logger.info("Primary provider failed, trying fallback: %s", result.error)
                result = await fallback.complete(request)
                if not result.error:
                    result.content = result.content  # keep fallback result as-is

        return result

    def _resolve_provider(self, task_type: str) -> AIProvider | None:
        cfg = self._config
        if not cfg:
            return None

        routing_map = {
            "chat": cfg.chat_provider,
            "vision": cfg.vision_provider,
            "csv_cleanup": cfg.csv_provider,
            "inventory_suggest": cfg.suggest_provider,
        }
        preferred = routing_map.get(task_type, "local")
        return self._get_provider(preferred)

    def _get_fallback_provider(self, task_type: str) -> AIProvider | None:
        cfg = self._config
        if not cfg:
            return None
        routing_map = {
            "chat": cfg.chat_provider,
            "vision": cfg.vision_provider,
            "csv_cleanup": cfg.csv_provider,
            "inventory_suggest": cfg.suggest_provider,
        }
        preferred = routing_map.get(task_type, "local")
        fallback_side = "cloud" if preferred == "local" else "local"
        return self._get_provider(fallback_side)

    def _get_provider(self, side: str) -> AIProvider | None:
        cfg = self._config
        if not cfg:
            return None
        if side == "local" and cfg.ollama_enabled:
            return OllamaProvider(cfg.ollama_base_url)
        if side == "cloud" and cfg.cloud_enabled and cfg.cloud_api_key_encrypted:
            api_key = decrypt_api_key(cfg.cloud_api_key_encrypted, self._secret_key)
            if api_key:
                return CloudProvider(cfg.cloud_provider, api_key)
        return None

    def get_ollama(self) -> OllamaProvider | None:
        if self._config and self._config.ollama_enabled:
            return OllamaProvider(self._config.ollama_base_url)
        return None


# ---------------------------------------------------------------------------
# Tool format helpers
# ---------------------------------------------------------------------------

def _format_tools_for_ollama(tools: list[dict]) -> list[dict]:
    """Convert our generic tool definitions to Ollama's tool format."""
    formatted = []
    for tool in tools:
        formatted.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return formatted


def _format_tools_for_anthropic(tools: list[dict]) -> list[dict]:
    """Convert to Anthropic's tool format."""
    formatted = []
    for tool in tools:
        formatted.append({
            "name": tool["name"],
            "description": tool["description"],
            "input_schema": tool.get("parameters", {"type": "object", "properties": {}}),
        })
    return formatted


def _format_tools_for_openai(tools: list[dict]) -> list[dict]:
    """Convert to OpenAI's tool format."""
    formatted = []
    for tool in tools:
        formatted.append({
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool.get("parameters", {"type": "object", "properties": {}}),
            },
        })
    return formatted


def _parse_ollama_tool_calls(message: dict) -> list[dict] | None:
    """Parse tool calls from an Ollama response message."""
    raw_calls = message.get("tool_calls")
    if not raw_calls:
        return None
    parsed = []
    for i, tc in enumerate(raw_calls):
        fn = tc.get("function", {})
        parsed.append({
            "id": f"ollama_call_{i}",
            "name": fn.get("name", ""),
            "arguments": fn.get("arguments", {}),
        })
    return parsed if parsed else None


# ---------------------------------------------------------------------------
# Rate limiter (simple in-memory per-user)
# ---------------------------------------------------------------------------

@dataclass
class _RateBucket:
    count: int = 0
    window_start: float = 0.0


_rate_buckets: dict[str, _RateBucket] = {}


def check_rate_limit(user_id: str, max_per_minute: int) -> bool:
    """Return True if the user is within the rate limit, False if exceeded."""
    now = time.time()
    bucket = _rate_buckets.get(user_id)
    if bucket is None or (now - bucket.window_start) > 60.0:
        _rate_buckets[user_id] = _RateBucket(count=1, window_start=now)
        return True
    if bucket.count >= max_per_minute:
        return False
    bucket.count += 1
    return True
