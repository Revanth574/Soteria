from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
import os

from soteria.extraction.errors import ConfigurationError

_DEFAULT_PUBLIC_BASE_URL = "http://localhost:8000"


@dataclass(frozen=True, slots=True)
class EmailConfig:
    resend_api_key: str | None
    from_address: str | None
    public_base_url: str = _DEFAULT_PUBLIC_BASE_URL

    @classmethod
    def from_env(cls, *, env: Mapping[str, str] | None = None) -> "EmailConfig":
        merged_env = dict(os.environ if env is None else env)
        resend_api_key = _optional_string(merged_env.get("RESEND_API_KEY"))
        from_address = _optional_string(merged_env.get("EMAIL_FROM_ADDRESS"))
        public_base_url = (
            _optional_string(merged_env.get("SOTERIA_PUBLIC_BASE_URL"))
            or _DEFAULT_PUBLIC_BASE_URL
        ).rstrip("/")

        if resend_api_key:
            if not from_address:
                raise ConfigurationError("EMAIL_FROM_ADDRESS is required when RESEND_API_KEY is set.")
            if not public_base_url.startswith("https://"):
                raise ConfigurationError(
                    "SOTERIA_PUBLIC_BASE_URL must be an absolute HTTPS URL when "
                    "RESEND_API_KEY is set."
                )

        return cls(
            resend_api_key=resend_api_key,
            from_address=from_address,
            public_base_url=public_base_url,
        )


def _optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
