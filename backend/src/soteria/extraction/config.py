from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os

from soteria.extraction.errors import ConfigurationError

_DEFAULT_MAX_TOKENS = 16000
_DEFAULT_TEMPERATURE = 0.0
_DEFAULT_PROMPT_PATH = Path("prompts/extract_policy_v1.2.md")


@dataclass(frozen=True, slots=True)
class ExtractionConfig:
    prompt_path: Path
    model: str
    api_key: str
    max_tokens: int = _DEFAULT_MAX_TOKENS
    temperature: float = _DEFAULT_TEMPERATURE

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        prompt_path: Path | None = None,
        dotenv_paths: tuple[Path, ...] | None = None,
    ) -> ExtractionConfig:
        merged_env = _load_environment(env=env, dotenv_paths=dotenv_paths)
        api_key = merged_env.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ConfigurationError("ANTHROPIC_API_KEY is required.")
        model = merged_env.get("ANTHROPIC_MODEL", "")
        if not model:
            raise ConfigurationError("ANTHROPIC_MODEL is required.")

        return cls(
            prompt_path=prompt_path
            or Path(merged_env.get("SOTERIA_EXTRACT_PROMPT_PATH", str(_DEFAULT_PROMPT_PATH))),
            model=model,
            api_key=api_key,
            max_tokens=int(merged_env.get("ANTHROPIC_MAX_TOKENS", str(_DEFAULT_MAX_TOKENS))),
            temperature=float(
                merged_env.get("ANTHROPIC_TEMPERATURE", str(_DEFAULT_TEMPERATURE))
            ),
        )


def _load_environment(
    *,
    env: Mapping[str, str] | None,
    dotenv_paths: tuple[Path, ...] | None,
) -> dict[str, str]:
    merged: dict[str, str] = {}
    for dotenv_path in dotenv_paths or _default_dotenv_paths():
        merged.update(_read_dotenv(dotenv_path))
    merged.update(dict(os.environ if env is None else env))
    return merged


def _default_dotenv_paths() -> tuple[Path, ...]:
    cwd = Path.cwd()
    return (cwd / ".env", cwd / "backend" / ".env")


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values
