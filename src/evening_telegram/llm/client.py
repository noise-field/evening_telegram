"""OpenAI-compatible LLM client."""

import json
import re
from typing import Any, Optional, Type, TypeVar

import structlog
from openai import AsyncOpenAI
from pydantic import BaseModel

from ..config.models import LLMConfig
from .tracker import TokenTracker

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


def _strip_thinking_tags(content: str) -> str:
    """
    Remove thinking tags from LLM response content.

    Some models include reasoning in <think>...</think> tags which should be
    removed before parsing JSON.

    Args:
        content: Raw content from LLM

    Returns:
        Content with thinking tags removed
    """
    if "<think>" in content and "</think>" in content:
        # Remove everything from <think> to </think> inclusive
        content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    return content.strip()


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

        # Strip thinking tags if present (some models include reasoning in <think> tags)
        content = _strip_thinking_tags(content)

        # Strip markdown code blocks if present (common with Claude)
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
            logger.error(
                "Failed to parse JSON response", content_preview=content[:200], error=str(e)
            )
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    def _parse_and_validate_json(
        self,
        content: str,
        response_format: Type[T],
    ) -> T:
        """
        Parse JSON content and validate against Pydantic schema.

        Handles thinking tags and markdown code blocks before parsing.

        Args:
            content: Raw string content to parse
            response_format: Pydantic model class to validate against

        Returns:
            Validated Pydantic model instance

        Raises:
            ValueError: If parsing or validation fails
        """
        # Strip thinking tags if present
        content = _strip_thinking_tags(content)

        # Strip markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        try:
            json_response = json.loads(content)
            return response_format.model_validate(json_response)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON response", content_preview=content[:200], error=str(e)
            )
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except Exception as e:
            logger.error(
                "Failed to validate response against schema",
                error=str(e),
                response_preview=content[:200],
            )
            raise ValueError(f"Response does not match expected schema: {e}")

    async def chat_completion_structured(
        self,
        messages: list[dict[str, str]],
        response_format: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> T:
        """
        Make a chat completion request with structured output (Pydantic schema).

        This method uses the API's native structured output feature when available.
        Falls back to JSON mode with manual parsing for unsupported models.

        Args:
            messages: List of message dicts with 'role' and 'content'
            response_format: Pydantic model class to use as the response schema
            temperature: Override default temperature
            max_tokens: Override default max tokens

        Returns:
            Parsed response as Pydantic model instance
        """
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
        }

        # Use structured output if configured
        if self.config.structured_output:
            # OpenAI's structured output API
            # See: https://platform.openai.com/docs/guides/structured-outputs
            try:
                response = await self.client.beta.chat.completions.parse(
                    **kwargs,
                    response_format=response_format,
                )
                self.token_tracker.record(response)

                parsed = response.choices[0].message.parsed

                # If parsing failed, try manual parsing with thinking tag removal
                # Some providers (like Fireworks) may return thinking tags even with structured output
                if parsed is None:
                    content = response.choices[0].message.content
                    if not content:
                        raise ValueError("Empty parsed response from LLM")

                    logger.warning(
                        "Structured output parse returned None, falling back to manual parsing"
                    )
                    return self._parse_and_validate_json(content, response_format)

                return parsed

            except Exception as e:
                logger.error(
                    "Structured output API error", error=str(e), error_type=type(e).__name__
                )
                raise
        else:
            # Fallback: Use regular completion and parse manually
            # This handles cases where structured output API is not available
            content = await self.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                json_mode=True,
            )

            return self._parse_and_validate_json(content, response_format)
