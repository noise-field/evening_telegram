"""OpenAI-compatible LLM client."""

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from ..config.models import LLMConfig
from .tracker import TokenTracker

logger = logging.getLogger(__name__)


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
            json_mode: Whether to request JSON output

        Returns:
            Response content as string
        """
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self.client.chat.completions.create(**kwargs)
            self.token_tracker.record(response)

            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from LLM")

            return content

        except Exception as e:
            logger.error(f"LLM API error: {e}")
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

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {content}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
