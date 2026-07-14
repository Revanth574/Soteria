from __future__ import annotations

import json
from pathlib import Path
import sys
import types

import pytest

from soteria.extraction import AnthropicClaudeClient, ClaudeExtractor, ClaudeExtractorConfig
from soteria.extraction.errors import ExtractionAdapterError, MalformedModelOutputError, PromptTemplateError
from soteria.ingestion import CanonicalPolicyDocument


class FakeClaudeClient:
    def __init__(self, response_text: str | None = None, *, error: Exception | None = None) -> None:
        self.response_text = response_text or json.dumps(
            {"schema_version": "1.2", "summary": "Extracted"}
        )
        self.error = error
        self.calls: list[dict] = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response_text


def _config(tmp_path: Path) -> ClaudeExtractorConfig:
    system_prompt = tmp_path / "system.md"
    extraction_prompt = tmp_path / "extract.md"
    system_prompt.write_text("System prompt", encoding="utf-8")
    extraction_prompt.write_text("Read this policy: {{POLICY_TEXT}}", encoding="utf-8")
    return ClaudeExtractorConfig(
        system_prompt_path=system_prompt,
        extraction_prompt_path=extraction_prompt,
        model="claude-test",
        api_key="test-key",
    )


def _document() -> CanonicalPolicyDocument:
    return CanonicalPolicyDocument(
        full_text="Policy full text",
        source_type="pdf_upload",
        checksum="checksum",
    )


def test_claude_extractor_loads_prompts_and_calls_client_once() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        config = _config(Path(directory))
        client = FakeClaudeClient()
        extractor = ClaudeExtractor(config=config, client=client)

        result = extractor.analyze(_document())

    assert result.schema_version == "1.2"
    assert len(client.calls) == 1
    assert client.calls[0]["system_prompt"] == "System prompt"
    assert "Policy full text" in client.calls[0]["prompt"]
    assert client.calls[0]["model"] == "claude-test"
    assert "test-key" not in str(client.calls[0])


def test_missing_prompt_files_fail_during_extractor_startup(tmp_path: Path) -> None:
    config = ClaudeExtractorConfig(
        system_prompt_path=tmp_path / "missing-system.md",
        extraction_prompt_path=tmp_path / "missing-extract.md",
        model="claude-test",
        api_key="test-key",
    )

    with pytest.raises(PromptTemplateError, match="system prompt"):
        ClaudeExtractor(config=config, client=FakeClaudeClient())


def test_missing_policy_text_placeholder_fails_during_startup(tmp_path: Path) -> None:
    system_prompt = tmp_path / "system.md"
    extraction_prompt = tmp_path / "extract.md"
    system_prompt.write_text("System prompt", encoding="utf-8")
    extraction_prompt.write_text("No placeholder", encoding="utf-8")
    config = ClaudeExtractorConfig(
        system_prompt_path=system_prompt,
        extraction_prompt_path=extraction_prompt,
        model="claude-test",
        api_key="test-key",
    )

    with pytest.raises(PromptTemplateError, match="POLICY_TEXT"):
        ClaudeExtractor(config=config, client=FakeClaudeClient())


def test_malformed_response_surfaces_clear_adapter_error(tmp_path: Path) -> None:
    extractor = ClaudeExtractor(
        config=_config(tmp_path),
        client=FakeClaudeClient(response_text='{"schema_version": "1.2", "raw_clause": "bad " quote"}'),
    )

    with pytest.raises(MalformedModelOutputError, match="malformed JSON"):
        extractor.analyze(_document())


def test_client_timeout_or_api_error_surfaces_without_retry(tmp_path: Path) -> None:
    client = FakeClaudeClient(error=ExtractionAdapterError("Claude request timed out."))
    extractor = ClaudeExtractor(config=_config(tmp_path), client=client)

    with pytest.raises(ExtractionAdapterError, match="timed out"):
        extractor.analyze(_document())

    assert len(client.calls) == 1


def test_anthropic_client_omits_optional_settings_and_sends_explicit_values(monkeypatch) -> None:
    calls: list[dict] = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            return types.SimpleNamespace(content=[types.SimpleNamespace(text="{}")])

    class FakeAnthropic:
        def __init__(self, *, api_key: str, timeout: float) -> None:
            self.messages = FakeMessages()

    monkeypatch.setitem(
        sys.modules,
        "anthropic",
        types.SimpleNamespace(Anthropic=FakeAnthropic),
    )
    client = AnthropicClaudeClient(api_key="test-key")

    client.complete(
        system_prompt="System",
        prompt="Prompt",
        model="claude-test",
        max_tokens=100,
        temperature=None,
        effort=None,
        timeout_seconds=10,
    )
    client.complete(
        system_prompt="System",
        prompt="Prompt",
        model="claude-test",
        max_tokens=100,
        temperature=0.2,
        effort="medium",
        timeout_seconds=10,
    )

    assert "temperature" not in calls[0]
    assert "output_config" not in calls[0]
    assert calls[1]["temperature"] == 0.2
    assert calls[1]["output_config"] == {"effort": "medium"}
