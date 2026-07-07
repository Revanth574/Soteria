from __future__ import annotations

from typing import Protocol

from soteria.ingestion.models import CanonicalPolicyDocument


class PolicyIngestionSource(Protocol):
    source_type: str

    def ingest(self) -> CanonicalPolicyDocument:
        """Convert an ingestion source into a canonical policy document."""

