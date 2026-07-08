from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping
import os

from soteria.ephemeral.errors import StorageConfigurationError


@dataclass(frozen=True, slots=True)
class EphemeralConfig:
    database_url: str
    ephemeral_data_dir: Path
    ttl_seconds: int = 24 * 60 * 60
    max_upload_bytes: int = 25 * 1024 * 1024
    anonymous_uploads_per_ip_per_hour: int = 5

    def __post_init__(self) -> None:
        if self.ttl_seconds > 24 * 60 * 60:
            raise StorageConfigurationError("Ephemeral TTL must be <= 24 hours.")
        if self.ttl_seconds <= 0:
            raise StorageConfigurationError("Ephemeral TTL must be positive.")
        if self.max_upload_bytes <= 0:
            raise StorageConfigurationError("Max upload size must be positive.")
        if self.anonymous_uploads_per_ip_per_hour <= 0:
            raise StorageConfigurationError("Anonymous upload rate limit must be positive.")

        data_dir = self.ephemeral_data_dir.resolve()
        database_path = self.database_path.resolve()
        if not _is_relative_to(database_path, data_dir):
            raise StorageConfigurationError(
                "SQLite database file must live under EPHEMERAL_DATA_DIR."
            )

    @property
    def database_path(self) -> Path:
        if not self.database_url.startswith("sqlite:///"):
            raise StorageConfigurationError("Only sqlite:/// DATABASE_URL values are supported.")
        raw_path = self.database_url.removeprefix("sqlite:///")
        if not raw_path:
            raise StorageConfigurationError("DATABASE_URL must include a SQLite file path.")
        return Path(raw_path)

    @classmethod
    def from_env(
        cls,
        *,
        env: Mapping[str, str] | None = None,
        dotenv_paths: tuple[Path, ...] | None = None,
    ) -> EphemeralConfig:
        merged_env = _load_environment(env=env, dotenv_paths=dotenv_paths)
        database_url = merged_env.get("DATABASE_URL", "")
        data_dir = merged_env.get("EPHEMERAL_DATA_DIR", "")
        if not database_url:
            raise StorageConfigurationError("DATABASE_URL is required.")
        if not data_dir:
            raise StorageConfigurationError("EPHEMERAL_DATA_DIR is required.")

        return cls(
            database_url=database_url,
            ephemeral_data_dir=Path(data_dir),
            ttl_seconds=int(merged_env.get("EPHEMERAL_TTL_SECONDS", str(24 * 60 * 60))),
            max_upload_bytes=int(merged_env.get("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024))),
            anonymous_uploads_per_ip_per_hour=int(
                merged_env.get("ANONYMOUS_UPLOADS_PER_IP_PER_HOUR", "5")
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


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True

