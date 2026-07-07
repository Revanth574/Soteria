from __future__ import annotations

from typing import Protocol

from soteria.extraction.config import ExtractionConfig
from soteria.extraction.errors import ConfigurationError, ExtractionAdapterError


class ModelClient(Protocol):
    def complete(self, *, prompt: str, model: str) -> str:
        """Return model text for a rendered prompt."""


class AnthropicMessagesClient:
    def __init__(self, config: ExtractionConfig) -> None:
        self.config = config

    def complete(self, *, prompt: str, model: str) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ConfigurationError(
                "The anthropic package is required to call the extraction model."
            ) from exc

        try:
            client = Anthropic(api_key=self.config.api_key)
            message = client.messages.create(
                model=model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ExtractionAdapterError("Anthropic model call failed.") from exc

        text_blocks: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text is not None:
                text_blocks.append(text)
        return "\n".join(text_blocks)
