from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from soteria.extraction.config import ExtractionConfig
from soteria.extraction.errors import (
    MalformedModelOutputError,
    PromptTemplateError,
    SchemaValidationError,
)
from soteria.extraction.model_client import AnthropicMessagesClient, ModelClient
from soteria.extraction.result import ExtractionResult
from soteria.ingestion import CanonicalPolicyDocument

_POLICY_TEXT_PLACEHOLDER = "{{POLICY_TEXT}}"
_SUPPORTED_SCHEMA_VERSION = "1.2"
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class ExtractionAdapter:
    def __init__(
        self,
        *,
        config: ExtractionConfig,
        model_client: ModelClient | None = None,
    ) -> None:
        self.config = config
        self.model_client = model_client or AnthropicMessagesClient(config)

    def analyze(self, document: CanonicalPolicyDocument) -> ExtractionResult:
        prompt = self._render_prompt(document)

        last_error: MalformedModelOutputError | None = None
        for _attempt in range(2):
            response_text = self.model_client.complete(prompt=prompt, model=self.config.model)
            try:
                return self._parse_response(response_text)
            except MalformedModelOutputError as exc:
                last_error = exc

        assert last_error is not None
        raise MalformedModelOutputError(
            f"Malformed model output after 2 attempts: {last_error}"
        ) from last_error

    def _render_prompt(self, document: CanonicalPolicyDocument) -> str:
        prompt_template = _read_prompt(self.config.prompt_path)
        if _POLICY_TEXT_PLACEHOLDER not in prompt_template:
            raise PromptTemplateError(
                f"Prompt template {self.config.prompt_path} does not contain "
                f"{_POLICY_TEXT_PLACEHOLDER}."
            )
        return prompt_template.replace(_POLICY_TEXT_PLACEHOLDER, document.full_text)

    def _parse_response(self, response_text: str) -> ExtractionResult:
        payload = _loads_json_response(response_text)
        normalized_payload = _normalize_string_nulls(payload)
        _validate_schema_version(normalized_payload)
        return ExtractionResult(
            json=normalized_payload,
            schema_version=normalized_payload["schema_version"],
        )


def _read_prompt(prompt_path: Path) -> str:
    try:
        return prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PromptTemplateError(f"Could not read prompt template: {prompt_path}") from exc


def _loads_json_response(response_text: str) -> dict[str, Any]:
    json_text = _extract_json_text(response_text)
    try:
        parsed = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise MalformedModelOutputError(f"Model returned malformed JSON: {exc.msg}") from exc

    if not isinstance(parsed, dict):
        raise MalformedModelOutputError("Model JSON response must be an object.")
    return parsed


def _extract_json_text(response_text: str) -> str:
    stripped = response_text.strip()
    fenced_match = _FENCED_JSON_RE.search(stripped)
    if fenced_match:
        return fenced_match.group(1).strip()

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise MalformedModelOutputError("Model response did not contain a JSON object.")
    return stripped[start : end + 1]


def _normalize_string_nulls(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _normalize_string_nulls(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_string_nulls(item) for item in value]
    if isinstance(value, str) and value.strip().lower() == "null":
        return None
    return value


def _validate_schema_version(payload: dict[str, Any]) -> None:
    schema_version = payload.get("schema_version")
    if schema_version != _SUPPORTED_SCHEMA_VERSION:
        raise SchemaValidationError(
            "Extraction response schema_version must be "
            f"{_SUPPORTED_SCHEMA_VERSION}; got {schema_version!r}."
        )
