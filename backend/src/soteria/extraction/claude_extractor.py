from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from soteria.extraction.adapter import (
    _POLICY_TEXT_PLACEHOLDER,
    _loads_json_response,
    _normalize_string_nulls,
    _validate_schema_version,
)
from soteria.extraction.config import ExtractionConfig
from soteria.extraction.errors import ConfigurationError, ExtractionAdapterError, PromptTemplateError
from soteria.extraction.result import ExtractionResult
from soteria.ingestion import CanonicalPolicyDocument


@dataclass(frozen=True, slots=True)
class ClaudeExtractorConfig:
    system_prompt_path: Path
    extraction_prompt_path: Path
    model: str
    api_key: str
    max_tokens: int = 16000
    temperature: float = 0.0
    timeout_seconds: float = 120.0

    @classmethod
    def from_extraction_config(
        cls,
        config: ExtractionConfig,
        *,
        system_prompt_path: Path,
    ) -> "ClaudeExtractorConfig":
        return cls(
            system_prompt_path=system_prompt_path,
            extraction_prompt_path=config.prompt_path,
            model=config.model,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )


class ClaudeClient(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        """Return model text for one Claude Messages request."""


class AnthropicClaudeClient:
    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY is required.")
        self._api_key = api_key

    def complete(
        self,
        *,
        system_prompt: str,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        timeout_seconds: float,
    ) -> str:
        try:
            from anthropic import Anthropic
        except ImportError as exc:
            raise ConfigurationError(
                "The anthropic package is required to call Claude."
            ) from exc

        try:
            client = Anthropic(api_key=self._api_key, timeout=timeout_seconds)
            message = client.messages.create(
                model=model,
                system=system_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}],
            )
        except TimeoutError as exc:
            raise ExtractionAdapterError("Claude request timed out.") from exc
        except Exception as exc:
            raise ExtractionAdapterError("Claude request failed.") from exc

        text_blocks: list[str] = []
        for block in message.content:
            text = getattr(block, "text", None)
            if text is not None:
                text_blocks.append(text)
        return "\n".join(text_blocks)


class ClaudeExtractor:
    def __init__(
        self,
        *,
        config: ClaudeExtractorConfig,
        client: ClaudeClient | None = None,
    ) -> None:
        self.config = config
        self.system_prompt = _read_required_prompt(config.system_prompt_path, "system prompt")
        self.extraction_prompt_template = _read_required_prompt(
            config.extraction_prompt_path,
            "extraction prompt",
        )
        if _POLICY_TEXT_PLACEHOLDER not in self.extraction_prompt_template:
            raise PromptTemplateError(
                f"Extraction prompt {config.extraction_prompt_path} does not contain "
                f"{_POLICY_TEXT_PLACEHOLDER}."
            )
        self.client = client or AnthropicClaudeClient(api_key=config.api_key)

    def analyze(self, document: CanonicalPolicyDocument) -> ExtractionResult:
        prompt = self.extraction_prompt_template.replace(
            _POLICY_TEXT_PLACEHOLDER,
            document.full_text,
        )
        response_text = self.client.complete(
            system_prompt=self.system_prompt,
            prompt=prompt,
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            timeout_seconds=self.config.timeout_seconds,
        )
        payload = _normalize_string_nulls(_loads_json_response(response_text))
        _validate_schema_version(payload)
        return ExtractionResult(json=payload, schema_version=payload["schema_version"])


def _read_required_prompt(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptTemplateError(f"Could not read {label}: {path}") from exc
