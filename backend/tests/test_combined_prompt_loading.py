from __future__ import annotations

from pathlib import Path

import pytest

from soteria.extraction import ClaudeExtractor, ClaudeExtractorConfig, ExtractionConfig
from soteria.extraction.claude_extractor import split_combined_prompt
from soteria.extraction.errors import PromptTemplateError


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
