from __future__ import annotations

from pathlib import Path

import pytest

from soteria.extraction import ClaudeExtractor, ClaudeExtractorConfig, ExtractionConfig
from soteria.extraction.claude_extractor import split_combined_prompt
from soteria.extraction.errors import ConfigurationError, PromptTemplateError


class FakeClaudeClient:
    def complete(self, **kwargs):
        return '{"schema_version": "1.2", "summary": "ok"}'


COMBINED_PROMPT = """## SYSTEM INSTRUCTIONS
You are careful.

================================================================
## EXTRACTION TASK
================================================================
Read this policy:

{{POLICY_TEXT}}
"""


def test_split_combined_prompt_keeps_policy_text_only_in_extraction() -> None:
    system_prompt, extraction_prompt = split_combined_prompt(COMBINED_PROMPT)

    assert "{{POLICY_TEXT}}" not in system_prompt
    assert "EXTRACTION TASK" not in system_prompt
    assert system_prompt == "## SYSTEM INSTRUCTIONS\nYou are careful."
    assert extraction_prompt.startswith("================================================================\n## EXTRACTION TASK")
    assert "{{POLICY_TEXT}}" in extraction_prompt


def test_split_combined_prompt_without_divider_raises_prompt_template_error() -> None:
    with pytest.raises(PromptTemplateError, match="## EXTRACTION TASK"):
        split_combined_prompt("## SYSTEM INSTRUCTIONS\nNo extraction divider here.")


def test_combined_prompt_env_path_builds_same_prompts_as_manual_split(tmp_path: Path) -> None:
    combined_prompt_path = tmp_path / "extract_policy_v1.2.md"
    combined_prompt_path.write_text(COMBINED_PROMPT, encoding="utf-8")

    extraction_config = ExtractionConfig.from_env(
        env={
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-test",
            "ANTHROPIC_TIMEOUT_SECONDS": "300",
            "SOTERIA_COMBINED_PROMPT_PATH": str(combined_prompt_path),
        }
    )
    expected_system_prompt, expected_extraction_prompt = split_combined_prompt(COMBINED_PROMPT)

    extractor_config = ClaudeExtractorConfig.from_combined_file(
        extraction_config,
        combined_prompt_path=extraction_config.combined_prompt_path,
    )
    extractor = ClaudeExtractor(config=extractor_config, client=FakeClaudeClient())

    assert extractor.system_prompt == expected_system_prompt
    assert extractor.extraction_prompt_template == expected_extraction_prompt
    assert extractor_config.timeout_seconds == 300.0


def test_timeout_env_unset_keeps_existing_default_for_legacy_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    extraction_config = ExtractionConfig.from_env(
        env={
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-test",
        }
    )

    extractor_config = ClaudeExtractorConfig.from_extraction_config(
        extraction_config,
        system_prompt_path=tmp_path / "system.md",
    )

    assert extraction_config.timeout_seconds == 120.0
    assert extraction_config.reasoning_effort is None
    assert extractor_config.timeout_seconds == 120.0
    assert extractor_config.reasoning_effort is None


def test_reasoning_effort_env_reaches_both_extractor_config_factories(tmp_path: Path) -> None:
    combined_prompt_path = tmp_path / "extract_policy_v1.2.md"
    combined_prompt_path.write_text(COMBINED_PROMPT, encoding="utf-8")
    extraction_config = ExtractionConfig.from_env(
        env={
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-test",
            "ANTHROPIC_REASONING_EFFORT": "medium",
            "SOTERIA_COMBINED_PROMPT_PATH": str(combined_prompt_path),
        }
    )

    legacy_extractor_config = ClaudeExtractorConfig.from_extraction_config(
        extraction_config,
        system_prompt_path=tmp_path / "system.md",
    )
    combined_extractor_config = ClaudeExtractorConfig.from_combined_file(
        extraction_config,
        combined_prompt_path=combined_prompt_path,
    )

    assert extraction_config.reasoning_effort == "medium"
    assert legacy_extractor_config.reasoning_effort == "medium"
    assert combined_extractor_config.reasoning_effort == "medium"


def test_invalid_reasoning_effort_is_rejected_during_config_load() -> None:
    with pytest.raises(ConfigurationError, match="ANTHROPIC_REASONING_EFFORT"):
        ExtractionConfig.from_env(
            env={
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-test",
                "ANTHROPIC_REASONING_EFFORT": "extreme",
            }
        )


def test_combined_prompt_env_path_set_alone_is_valid(tmp_path: Path) -> None:
    combined_prompt_path = tmp_path / "extract_policy_v1.2.md"

    config = ExtractionConfig.from_env(
        env={
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-test",
            "SOTERIA_COMBINED_PROMPT_PATH": str(combined_prompt_path),
        }
    )

    assert config.combined_prompt_path == combined_prompt_path


def test_legacy_prompt_env_vars_without_combined_path_still_work(tmp_path: Path) -> None:
    system_prompt_path = tmp_path / "system.md"
    extraction_prompt_path = tmp_path / "extract.md"

    config = ExtractionConfig.from_env(
        env={
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-test",
            "SOTERIA_SYSTEM_PROMPT_PATH": str(system_prompt_path),
            "SOTERIA_EXTRACT_PROMPT_PATH": str(extraction_prompt_path),
        }
    )

    assert config.combined_prompt_path is None
    assert config.prompt_path == extraction_prompt_path


def test_combined_prompt_path_with_legacy_system_path_is_ambiguous(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        ExtractionConfig.from_env(
            env={
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-test",
                "SOTERIA_COMBINED_PROMPT_PATH": str(tmp_path / "combined.md"),
                "SOTERIA_SYSTEM_PROMPT_PATH": str(tmp_path / "system.md"),
            }
        )

    message = str(exc_info.value)
    assert "SOTERIA_COMBINED_PROMPT_PATH" in message
    assert "SOTERIA_SYSTEM_PROMPT_PATH" in message
    assert "SOTERIA_EXTRACT_PROMPT_PATH" in message
    assert "only one prompt-loading style" in message


def test_combined_prompt_path_with_legacy_extract_path_is_ambiguous(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError) as exc_info:
        ExtractionConfig.from_env(
            env={
                "ANTHROPIC_API_KEY": "test-key",
                "ANTHROPIC_MODEL": "claude-test",
                "SOTERIA_COMBINED_PROMPT_PATH": str(tmp_path / "combined.md"),
                "SOTERIA_EXTRACT_PROMPT_PATH": str(tmp_path / "extract.md"),
            }
        )

    assert "SOTERIA_EXTRACT_PROMPT_PATH" in str(exc_info.value)


def test_no_prompt_env_style_keeps_existing_default_prompt_path_behavior() -> None:
    config = ExtractionConfig.from_env(
        env={
            "ANTHROPIC_API_KEY": "test-key",
            "ANTHROPIC_MODEL": "claude-test",
        }
    )

    assert config.combined_prompt_path is None
    assert config.prompt_path == Path("prompts/extract_policy_v1.2.md")
