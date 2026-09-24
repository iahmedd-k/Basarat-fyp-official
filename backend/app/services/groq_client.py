"""Groq API client wrapper for the Stock AI Assistant."""

import logging
from typing import Optional

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
    """Async Groq API client for chat completions."""

    def __init__(self):
        self.settings = get_settings()
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.groq.com/openai/v1",
                headers={
                    "Authorization": f"Bearer {self.settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2048,
        model: Optional[str] = None,
    ) -> str:
        """
        Send a chat completion request to Groq.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens in response
            model: Model name (defaults to config)

        Returns:
            Assistant response content

        Raises:
            GroqError: On API error or timeout
        """
        if not self.settings.GROQ_API_KEY:
            raise GroqError("Groq API key not configured", 503)

        payload = {
            "model": model or self.settings.GROQ_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        try:
            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.TimeoutException:
            log.error("Groq API timeout")
            raise GroqError("Groq API timeout", 504)
        except httpx.HTTPStatusError as e:
            log.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
            if e.response.status_code == 401:
                raise GroqError("Invalid Groq API key", 503)
            elif e.response.status_code == 429:
                raise GroqError("Groq rate limit exceeded", 429)
            else:
                raise GroqError(f"Groq API error: {e.response.text}", 502)
        except httpx.RequestError as e:
            log.error(f"Groq request error: {e}")
            raise GroqError("Failed to connect to Groq API", 502)

        try:
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except (KeyError, IndexError, ValueError) as e:
            log.error(f"Invalid Groq response format: {e}")
            raise GroqError("Invalid response from Groq API", 502)

    async def stream_chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 800,
        model: Optional[str] = None,
    ):
        """
        Stream chat completion tokens from Groq.

        Yields:
            str: Buffered text chunks suitable for rendering in a chat UI.
        """
        import json

        if not self.settings.GROQ_API_KEY:
            raise GroqError("Groq API key not configured", 503)

        payload = {
            "model": model or self.settings.GROQ_MODEL,
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
                    log.error(f"Groq stream error: {response.status_code} - {error_msg}")
                    if response.status_code == 429:
                        raise GroqError("Groq rate limit exceeded", 429)
                    raise GroqError(f"Groq API error: {error_msg}", response.status_code)

                pending: list[str] = []
                pending_chars = 0
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                pending.append(content)
                                pending_chars += len(content)
                                # Providers often emit tiny tokenizer fragments. Batch them
                                # into useful UI updates while flushing promptly at line breaks.
                                if pending_chars >= 48 or "\n" in content:
                                    yield "".join(pending)
                                    pending.clear()
                                    pending_chars = 0
                        except (KeyError, IndexError, json.JSONDecodeError):
                            continue
                if pending:
                    yield "".join(pending)
        except httpx.TimeoutException:
            log.error("Groq API streaming timeout")
            raise GroqError("Groq API timeout", 504)
        except httpx.HTTPStatusError as e:
            log.error(f"Groq API streaming HTTP error: {e}")
            raise GroqError(f"Groq API error: {e}", 502)
        except httpx.RequestError as e:
            log.error(f"Groq streaming request error: {e}")
            raise GroqError("Failed to connect to Groq API", 502)


groq_client = GroqClient()
