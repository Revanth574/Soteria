from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    json: dict[str, Any]
    schema_version: str
