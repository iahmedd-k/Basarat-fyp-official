"""Groq API client for the Basarat Stock AI Assistant (free-tier friendly)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Optional

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)


class GroqError(Exception):
    """Groq API error."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GroqClient:
    """Async Groq chat client with retry + free-tier model fallback."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            base_url = (self.settings.GROQ_BASE_URL or "https://api.groq.com/openai/v1").rstrip("/")
            self._client = httpx.AsyncClient(
                base_url=base_url,
                headers={
                    "Authorization": f"Bearer {self.settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(35.0, connect=8.0, read=30.0, write=8.0),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _models_to_try(self, model: Optional[str]) -> list[str]:
        primary = model or self.settings.GROQ_MODEL
        models = [primary]
        fallback = getattr(self.settings, "GROQ_FALLBACK_MODEL", "") or ""
        if fallback and fallback not in models:
            models.append(fallback)
        return models

    def _ensure_key(self):
        if not self.settings.GROQ_API_KEY or len(self.settings.GROQ_API_KEY.strip()) < 10:
            raise GroqError("Groq API key not configured", 503)

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.55,
        max_tokens: int = 700,
        model: Optional[str] = None,
    ) -> str:
        self._ensure_key()
        last_error: Optional[GroqError] = None

        for model_id in self._models_to_try(model):
            for attempt in range(3):
                try:
                    return await self._chat_once(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=model_id,
                        stream=False,
                    )
                except GroqError as e:
                    last_error = e
                    if e.status_code == 429 and attempt < 2:
                        wait = 1.2 * (attempt + 1)
                        log.warning("Groq 429 on %s; retry in %.1fs", model_id, wait)
                        await asyncio.sleep(wait)
                        continue
                    if e.status_code in (404, 429, 502, 503, 504):
                        log.warning("Groq error %s on %s; trying next model if any", e.status_code, model_id)
                        break
                    raise

        raise last_error or GroqError("Groq API unavailable", 502)

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.55,
        max_tokens: int = 800,
        model: Optional[str] = None,
    ) -> AsyncIterator[str]:
        self._ensure_key()
        last_error: Optional[GroqError] = None

        for model_id in self._models_to_try(model):
            for attempt in range(3):
                try:
                    async for chunk in self._stream_once(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        model=model_id,
                    ):
                        yield chunk
                    return
                except GroqError as e:
                    last_error = e
                    if e.status_code == 429 and attempt < 2:
                        wait = 1.2 * (attempt + 1)
                        log.warning("Groq stream 429 on %s; retry in %.1fs", model_id, wait)
                        await asyncio.sleep(wait)
                        continue
                    if e.status_code in (404, 429, 502, 503, 504):
                        log.warning("Groq stream error %s on %s; trying next model", e.status_code, model_id)
                        break
                    raise

        raise last_error or GroqError("Groq API unavailable", 502)

    async def _chat_once(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
        stream: bool,
    ) -> str:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException:
            raise GroqError("Groq API timeout", 504)
        except httpx.HTTPStatusError as e:
            log.error("Groq API error: %s - %s", e.response.status_code, e.response.text[:300])
            if e.response.status_code == 401:
                raise GroqError("Invalid Groq API key", 503)
            if e.response.status_code == 429:
                raise GroqError("Groq rate limit exceeded", 429)
            if e.response.status_code == 404:
                raise GroqError(f"Groq model not found: {model}", 404)
            raise GroqError(f"Groq API error: {e.response.text[:200]}", e.response.status_code or 502)
        except httpx.RequestError as e:
            raise GroqError(f"Failed to connect to Groq API: {e}", 502)

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return _strip_markdown_noise(content)
        except (KeyError, IndexError, ValueError) as e:
            raise GroqError(f"Invalid response from Groq API: {e}", 502)

    async def _stream_once(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
    ) -> AsyncIterator[str]:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        try:
            async with self.client.stream("POST", "/chat/completions", json=payload) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    error_msg = body.decode("utf-8", errors="ignore")
                    log.error("Groq stream error: %s - %s", response.status_code, error_msg[:300])
                    if response.status_code == 429:
                        raise GroqError("Groq rate limit exceeded", 429)
                    raise GroqError(f"Groq API error: {error_msg[:200]}", response.status_code)

                pending: list[str] = []
                pending_chars = 0
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = data["choices"][0].get("delta", {}).get("content", "")
                        if not content:
                            continue
                        pending.append(content)
                        pending_chars += len(content)
                        if pending_chars >= 40 or "\n" in content:
                            yield _strip_markdown_noise("".join(pending))
                            pending.clear()
                            pending_chars = 0
                    except (KeyError, IndexError, json.JSONDecodeError):
                        continue
                if pending:
                    yield _strip_markdown_noise("".join(pending))
        except GroqError:
            raise
        except httpx.TimeoutException:
            raise GroqError("Groq API timeout", 504)
        except httpx.HTTPStatusError as e:
            raise GroqError(f"Groq API error: {e}", 502)
        except httpx.RequestError as e:
            raise GroqError(f"Failed to connect to Groq API: {e}", 502)


def _strip_markdown_noise(text: str) -> str:
    return (
        text.replace("**", "")
        .replace("__", "")
        .replace("### ", "")
        .replace("## ", "")
        .replace("# ", "")
        .strip()
    )


groq_client = GroqClient()
