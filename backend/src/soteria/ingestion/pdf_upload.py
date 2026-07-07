from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import re

import pdfplumber

from soteria.ingestion.errors import (
    EmptyExtractionError,
    PdfExtractionError,
    UnsupportedFileTypeError,
)
from soteria.ingestion.models import CanonicalPolicyDocument, CanonicalPolicyPage

_PDF_MAGIC = b"%PDF-"
_WHITESPACE_RE = re.compile(r"[ \t]+\n")


@dataclass(frozen=True, slots=True)
class PdfUploadSource:
    pdf_bytes: bytes
    filename: str | None = None
    source_type: str = "pdf_upload"

    def ingest(self) -> CanonicalPolicyDocument:
        self._validate_pdf_upload()

        try:
            pages = self._extract_pages()
        except EmptyExtractionError:
            raise
        except Exception as exc:  # pdfminer/pdfplumber expose several parser errors.
            name = self.filename or "uploaded PDF"
            raise PdfExtractionError(f"Could not extract text from {name}.") from exc

        usable_pages = [page for page in pages if page.text.strip()]
        if not usable_pages:
            raise EmptyExtractionError(
                "No extractable text found in uploaded PDF. The file may be scanned, "
                "image-only, or too garbled for text extraction."
            )

        full_text = "\n\n".join(page.text for page in usable_pages)
        return CanonicalPolicyDocument(
            full_text=full_text,
            pages=usable_pages,
            source_type="pdf_upload",
            checksum=sha256(self.pdf_bytes).hexdigest(),
            structured_fields=None,
            source_metadata={"filename": self.filename},
            policy_kind="unknown",
        )

    def _validate_pdf_upload(self) -> None:
        if not self.pdf_bytes.startswith(_PDF_MAGIC):
            name = self.filename or "uploaded file"
            raise UnsupportedFileTypeError(f"{name} is not a PDF upload.")

    def _extract_pages(self) -> list[CanonicalPolicyPage]:
        pages: list[CanonicalPolicyPage] = []
        with pdfplumber.open(BytesIO(self.pdf_bytes)) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(layout=True) or page.extract_text() or ""
                pages.append(
                    CanonicalPolicyPage(
                        page_number=page_index,
                        text=_normalize_page_text(text),
                    )
                )
        return pages


def _normalize_page_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub("\n", text)
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()
