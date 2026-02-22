"""Anthropic Claude client for prompt analysis."""

import logging

import anthropic

from prompt_analyzer.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    LLM_MAX_TOKENS,
    LLM_TEMPERATURE,
)

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Wrapper around the Anthropic Messages API."""

    def __init__(self):
        if not ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set in .env")

        self.client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.model = ANTHROPIC_MODEL
        self.max_tokens = LLM_MAX_TOKENS
        self.temperature = LLM_TEMPERATURE

    async def invoke(self, system_prompt: str, user_message: str) -> str:
        """
        Send a message to Claude and return the text response.
        Uses the Anthropic Messages API directly.
        """
        logger.info("Invoking Anthropic model=%s", self.model)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message},
                ],
            )

            # Extract text from the response
            result = ""
            for block in message.content:
                if block.type == "text":
                    result += block.text

            logger.info("Anthropic response received, length=%d chars", len(result))
            return result

        except anthropic.AuthenticationError:
            logger.error("Anthropic authentication failed — check your API key")
            raise
        except anthropic.RateLimitError:
            logger.error("Anthropic rate limit hit")
            raise
        except Exception as e:
            logger.error("Anthropic invocation failed: %s", str(e))
            raise
