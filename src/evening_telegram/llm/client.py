"""OpenAI-compatible LLM client."""

import json
from typing import Any, Optional

import structlog
from openai import AsyncOpenAI

from ..config.models import LLMConfig
from .tracker import TokenTracker

logger = structlog.get_logger(__name__)


class LLMClient:
    """OpenAI-compatible LLM client wrapper."""

    def __init__(self, config: LLMConfig, token_tracker: TokenTracker):
        """
        Initialize LLM client.

        Args:
            config: LLM configuration
            token_tracker: Token usage tracker
        """
        self.config = config
        self.token_tracker = token_tracker
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=config.timeout,
        )

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> str:
        """
        Make a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens
            json_mode: Whether to request JSON output (only works with OpenAI-compatible APIs)

        Returns:
            Response content as string
        """
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        # Only add response_format for OpenAI models
        # Anthropic's API doesn't support this parameter - just ask for JSON in the prompt
        if json_mode and "gpt" in self.config.model.lower():
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.chat.completions.create(**kwargs)
            self.token_tracker.record(response)

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from LLM")

            return content

        except Exception as e:
            logger.error("LLM API error", error=str(e), error_type=type(e).__name__)
            raise

    async def chat_completion_json(
        self,
        messages: list[dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Make a chat completion request expecting JSON response.

        Args:
            messages: List of message dicts with 'role' and 'content'
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Parsed JSON response
        """
        content = await self.chat_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )

        # Strip markdown code blocks if present (common with Claude)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]  # Remove ```json
        elif content.startswith("```"):
            content = content[3:]  # Remove ```
        if content.endswith("```"):
            content = content[:-3]  # Remove trailing ```
        content = content.strip()

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response",
                        content_preview=content[:200],
                        error=str(e))
            raise ValueError(f"Invalid JSON response from LLM: {e}")
