"""Token usage tracking for LLM API calls."""

import logging

logger = logging.getLogger(__name__)


class TokenTracker:
    """Accumulate token usage across all LLM calls."""

    def __init__(self) -> None:
        """Initialize token tracker."""
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0

    def record(self, response: any) -> None:
        """
        Record usage from an LLM API response.

        Args:
            response: API response object with usage information
        """
        if hasattr(response, "usage") and response.usage:
            self.prompt_tokens += response.usage.prompt_tokens
            self.completion_tokens += response.usage.completion_tokens
            self.calls += 1
            logger.debug(
                f"Recorded {response.usage.prompt_tokens} prompt + "
                f"{response.usage.completion_tokens} completion tokens"
            )

    @property
    def total_tokens(self) -> int:
        """Total tokens used across all calls."""
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        """
        Convert to dictionary format.

        Returns:
            Dictionary with token usage statistics
        """
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "api_calls": self.calls,
        }
