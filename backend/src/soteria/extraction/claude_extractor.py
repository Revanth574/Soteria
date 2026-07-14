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

_EXTRACTION_TASK_DIVIDER = "## EXTRACTION TASK"


@dataclass(frozen=True, slots=True)
class ClaudeExtractorConfig:
    system_prompt_path: Path
    extraction_prompt_path: Path
    model: str
    api_key: str
    max_tokens: int = 16000
    temperature: float | None = None
    reasoning_effort: str | None = None
    timeout_seconds: float = 120.0
    system_prompt_text: str | None = None
    extraction_prompt_text: str | None = None

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
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
        )

    @classmethod
    def from_combined_file(
        cls,
        config: ExtractionConfig,
        *,
        combined_prompt_path: Path,
    ) -> "ClaudeExtractorConfig":
        try:
            combined_prompt = combined_prompt_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptTemplateError(
                f"Could not read combined prompt: {combined_prompt_path}"
            ) from exc
        system_prompt, extraction_prompt = split_combined_prompt(combined_prompt)
        return cls(
            system_prompt_path=combined_prompt_path,
            extraction_prompt_path=combined_prompt_path,
            model=config.model,
            api_key=config.api_key,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
            reasoning_effort=config.reasoning_effort,
            timeout_seconds=config.timeout_seconds,
            system_prompt_text=system_prompt,
            extraction_prompt_text=extraction_prompt,
        )


class ClaudeClient(Protocol):
    def complete(
        self,
        *,
        system_prompt: str,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float | None,
        effort: str | None,
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
        temperature: float | None,
        effort: str | None,
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
            request_kwargs = {
                "model": model,
                "system": system_prompt,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if temperature is not None:
                request_kwargs["temperature"] = temperature
            if effort is not None:
                request_kwargs["output_config"] = {"effort": effort}
            message = client.messages.create(**request_kwargs)
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
        self.system_prompt = (
            config.system_prompt_text
            if config.system_prompt_text is not None
            else _read_required_prompt(
                config.system_prompt_path,
                "system prompt",
            )
        )
        self.extraction_prompt_template = (
            config.extraction_prompt_text
            if config.extraction_prompt_text is not None
            else _read_required_prompt(
                config.extraction_prompt_path,
                "extraction prompt",
            )
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
            effort=self.config.reasoning_effort,
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


def split_combined_prompt(text: str) -> tuple[str, str]:
    """Split the combined prompt before the extraction divider block.

    The returned extraction prompt includes the divider line immediately before
    ``## EXTRACTION TASK``, the heading itself, and the rest of the file. The
    returned system prompt is everything before that block, with trailing
    whitespace stripped.
    """

    lines = text.splitlines(keepends=True)
    heading_index = next(
        (index for index, line in enumerate(lines) if line.strip() == _EXTRACTION_TASK_DIVIDER),
        None,
    )
    if heading_index is None:
        raise PromptTemplateError(
            f"Combined prompt must contain the expected divider text: "
            f"{_EXTRACTION_TASK_DIVIDER}"
        )

    extraction_start_index = heading_index
    if heading_index > 0 and _is_equals_divider(lines[heading_index - 1]):
        extraction_start_index = heading_index - 1

    system_prompt = "".join(lines[:extraction_start_index]).rstrip()
    extraction_prompt = "".join(lines[extraction_start_index:])
    return system_prompt, extraction_prompt


def _is_equals_divider(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and set(stripped) == {"="}
