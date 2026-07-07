import json
from pathlib import Path

import pytest

from soteria.extraction import (
    ExtractionAdapter,
    ExtractionConfig,
    MalformedModelOutputError,
    SchemaValidationError,
)
from soteria.ingestion import CanonicalPolicyDocument, CanonicalPolicyPage


class FakeModelClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, prompt: str, model: str) -> str:
        self.calls.append((prompt, model))
        if not self.responses:
            raise AssertionError("No fake model response left.")
        return self.responses.pop(0)


def _document() -> CanonicalPolicyDocument:
    return CanonicalPolicyDocument(
        full_text="Policy wording: Room rent has no cap.",
        pages=[CanonicalPolicyPage(page_number=1, text="Policy wording: Room rent has no cap.")],
        source_type="pdf_upload",
        checksum="abc123",
        policy_kind="retail_individual",
    )


def _prompt_file(tmp_path: Path) -> Path:
    prompt_path = tmp_path / "extract_policy_v1.2.md"
    prompt_path.write_text("Analyze this policy:\n{{POLICY_TEXT}}\nReturn JSON.", encoding="utf-8")
    return prompt_path


def _config(prompt_path: Path) -> ExtractionConfig:
    return ExtractionConfig(
        prompt_path=prompt_path,
        model="claude-test",
        api_key="test-key",
        max_tokens=1024,
        temperature=0.0,
    )


def test_adapter_loads_prompt_injects_policy_text_and_returns_result(tmp_path: Path) -> None:
    model_client = FakeModelClient(
        [json.dumps({"schema_version": "1.2", "metadata": {"product_name": "Test"}})]
    )

    result = ExtractionAdapter(config=_config(_prompt_file(tmp_path)), model_client=model_client).analyze(
        _document()
    )

    assert result.schema_version == "1.2"
    assert result.json["metadata"]["product_name"] == "Test"
    assert model_client.calls == [
        (
            "Analyze this policy:\nPolicy wording: Room rent has no cap.\nReturn JSON.",
            "claude-test",
        )
    ]


def test_config_reads_model_and_api_key_from_environment(tmp_path: Path) -> None:
    env = {
        "ANTHROPIC_API_KEY": "from-env",
        "ANTHROPIC_MODEL": "claude-env",
        "ANTHROPIC_MAX_TOKENS": "2048",
        "ANTHROPIC_TEMPERATURE": "0.2",
    }

    config = ExtractionConfig.from_env(env=env, prompt_path=_prompt_file(tmp_path))

    assert config.api_key == "from-env"
    assert config.model == "claude-env"
    assert config.max_tokens == 2048
    assert config.temperature == 0.2


def test_f18_string_null_is_normalized_not_silently_stored(tmp_path: Path) -> None:
    model_client = FakeModelClient(
        [
            json.dumps(
                {
                    "schema_version": "1.2",
                    "financial_terms": {"deductible": {"type": "null", "amount": "null"}},
                }
            )
        ]
    )

    result = ExtractionAdapter(config=_config(_prompt_file(tmp_path)), model_client=model_client).analyze(
        _document()
    )

    assert result.json["financial_terms"]["deductible"]["type"] is None
    assert result.json["financial_terms"]["deductible"]["amount"] is None


def test_f19_malformed_raw_clause_is_retried_once_then_valid_response_is_returned(
    tmp_path: Path,
) -> None:
    malformed = '{"schema_version":"1.2","red_flags":[{"raw_clause":"ReAssure "Forever""}]}'
    valid = json.dumps(
        {
            "schema_version": "1.2",
            "red_flags": [{"raw_clause": 'ReAssure "Forever"'}],
        }
    )
    model_client = FakeModelClient([malformed, valid])

    result = ExtractionAdapter(config=_config(_prompt_file(tmp_path)), model_client=model_client).analyze(
        _document()
    )

    assert result.json["red_flags"][0]["raw_clause"] == 'ReAssure "Forever"'
    assert len(model_client.calls) == 2


def test_f19_second_malformed_response_raises_clear_adapter_error(tmp_path: Path) -> None:
    malformed = '{"schema_version":"1.2","red_flags":[{"raw_clause":"ReAssure "Forever""}]}'
    model_client = FakeModelClient([malformed, malformed])

    with pytest.raises(MalformedModelOutputError, match="after 2 attempts"):
        ExtractionAdapter(config=_config(_prompt_file(tmp_path)), model_client=model_client).analyze(
            _document()
        )

    assert len(model_client.calls) == 2


def test_schema_version_must_be_1_2(tmp_path: Path) -> None:
    model_client = FakeModelClient([json.dumps({"schema_version": "1.1"})])

    with pytest.raises(SchemaValidationError, match="schema_version"):
        ExtractionAdapter(config=_config(_prompt_file(tmp_path)), model_client=model_client).analyze(
            _document()
        )

