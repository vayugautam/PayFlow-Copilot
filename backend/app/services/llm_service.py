"""Bounded, typed Groq chat-completion adapter."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


class LLMError(RuntimeError):
    """Base error for safe user-facing LLM failures."""


class LLMAuthenticationError(LLMError):
    pass


class LLMRateLimitError(LLMError):
    pass


class LLMTransientError(LLMError):
    pass


class LLMResponseError(LLMError):
    pass


@dataclass(frozen=True)
class ChatCompletion:
    content: str
    tool_calls: list[dict[str, Any]]
    raw_messages: list[dict[str, Any]]


class GroqLLMClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.model = settings.llm_model
        self.timeout = settings.GROQ_TIMEOUT_SECONDS
        self.max_retries = max(0, settings.GROQ_MAX_RETRIES)
        self.api_key = settings.GROQ_API_KEY or settings.LLM_API_KEY

    async def complete(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ChatCompletion:
        if not self.api_key:
            raise LLMAuthenticationError("Groq API key is not configured")
        try:
            from groq import AsyncGroq
        except ImportError as exc:
            raise LLMError("Groq SDK is unavailable") from exc

        client = AsyncGroq(api_key=self.api_key, timeout=self.timeout, max_retries=0)
        for attempt in range(self.max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        **(
                            {"tools": tools, "tool_choice": "auto"}
                            if tools
                            else {}
                        ),
                    ),
                    timeout=self.timeout,
                )
                choice = response.choices[0] if response.choices else None
                if choice is None or choice.message is None:
                    raise LLMResponseError("Groq returned an empty response")
                message = choice.message
                content = message.content or ""
                tool_calls = []
                raw_tool_calls = getattr(message, "tool_calls", None) or []
                for call in raw_tool_calls:
                    function = getattr(call, "function", None)
                    if function is None:
                        raise LLMResponseError("Groq returned a malformed tool call")
                    tool_calls.append(
                        {
                            "id": str(getattr(call, "id", "")),
                            "type": "function",
                            "function": {
                                "name": str(getattr(function, "name", "")),
                                "arguments": str(getattr(function, "arguments", "")),
                            },
                        }
                    )
                return ChatCompletion(
                    content=content,
                    tool_calls=tool_calls,
                    raw_messages=[
                        {
                            "role": "assistant",
                            "content": content,
                            **({"tool_calls": tool_calls} if tool_calls else {}),
                        }
                    ],
                )
            except LLMResponseError:
                raise
            except Exception as exc:
                name = type(exc).__name__.lower()
                if "authentication" in name or "auth" in name:
                    raise LLMAuthenticationError("Groq authentication failed") from exc
                if "rate" in name:
                    raise LLMRateLimitError("Groq rate limit exceeded") from exc
                if attempt >= self.max_retries:
                    raise LLMTransientError("Groq request failed after bounded retries") from exc
                await asyncio.sleep(min(2**attempt, 4))
        raise LLMTransientError("Groq request failed")
