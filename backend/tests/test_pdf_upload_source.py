import hashlib
from datetime import UTC, datetime

import pytest

from soteria.ingestion import (
    CanonicalPolicyDocument,
    EmptyExtractionError,
    PdfExtractionError,
    PdfUploadSource,
    UnsupportedFileTypeError,
)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(pages: list[str]) -> bytes:
    objects: list[tuple[int, bytes]] = []

    def add(object_number: int, body: str | bytes) -> None:
        if isinstance(body, str):
            body = body.encode("latin-1")
        objects.append((object_number, body))

    page_object_numbers = [4 + (index * 2) for index in range(len(pages))]
    kids = " ".join(f"{object_number} 0 R" for object_number in page_object_numbers)

    add(1, "<< /Type /Catalog /Pages 2 0 R >>")
    add(2, f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    add(3, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    for index, page_text in enumerate(pages):
        page_object_number = 4 + (index * 2)
        content_object_number = page_object_number + 1
        commands = ["BT", "/F1 12 Tf", "72 720 Td"]
        for line_index, line in enumerate(page_text.splitlines()):
            if line_index:
                commands.append("0 -16 Td")
            commands.append(f"({_escape_pdf_text(line)}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1")

        add(
            page_object_number,
            (
                "<< /Type /Page /Parent 2 0 R "
                "/Resources << /Font << /F1 3 0 R >> >> "
                "/MediaBox [0 0 612 792] "
                f"/Contents {content_object_number} 0 R >>"
            ),
        )
        add(
            content_object_number,
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\n"
            b"stream\n" + stream + b"\nendstream",
        )

    pdf = b"%PDF-1.4\n"
    offsets: dict[int, int] = {}
    for object_number, body in objects:
        offsets[object_number] = len(pdf)
        pdf += f"{object_number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    startxref = len(pdf)
    max_object_number = max(offsets)
    pdf += f"xref\n0 {max_object_number + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for object_number in range(1, max_object_number + 1):
        pdf += f"{offsets[object_number]:010d} 00000 n \n".encode("ascii")
    pdf += (
        f"trailer << /Size {max_object_number + 1} /Root 1 0 R >>\n"
        f"startxref\n{startxref}\n%%EOF\n"
    ).encode("ascii")
    return pdf


def test_pdf_upload_source_returns_canonical_document() -> None:
    pdf_bytes = _pdf_bytes(
        [
            "Health Insurance Policy\nRoom rent cap is 1 percent of sum insured.",
            "Claims Process\nEmergency intimation must happen within 24 hours.",
        ]
    )

    document = PdfUploadSource(pdf_bytes, filename="policy.pdf").ingest()

    assert isinstance(document, CanonicalPolicyDocument)
    assert document.source_type == "pdf_upload"
    assert document.policy_kind == "unknown"
    assert document.checksum == hashlib.sha256(pdf_bytes).hexdigest()
    assert document.source_metadata == {"filename": "policy.pdf"}
    assert document.structured_fields is None
    assert document.ingested_at.tzinfo == UTC
    assert document.ingested_at <= datetime.now(UTC)
    assert document.pages is not None
    assert len(document.pages) == 2
    assert document.pages[0].page_number == 1
    assert "Health Insurance Policy" in document.full_text
    assert "Emergency intimation" in document.full_text


def test_pdf_upload_source_rejects_non_pdf_magic_bytes() -> None:
    with pytest.raises(UnsupportedFileTypeError, match="PDF"):
        PdfUploadSource(b"not a pdf", filename="policy.txt").ingest()


def test_blank_pdf_fails_with_clear_ingestion_error() -> None:
    with pytest.raises(EmptyExtractionError, match="No extractable text"):
        PdfUploadSource(_pdf_bytes([""]), filename="blank.pdf").ingest()


def test_corrupt_pdf_fails_with_clear_ingestion_error() -> None:
    with pytest.raises(PdfExtractionError, match="Could not extract text"):
        PdfUploadSource(b"%PDF-1.4\nnot a valid pdf body", filename="broken.pdf").ingest()


def test_canonical_document_rejects_empty_full_text() -> None:
    with pytest.raises(EmptyExtractionError, match="empty canonical document"):
        CanonicalPolicyDocument(
            full_text="   ",
            pages=[],
            source_type="pdf_upload",
            checksum="abc",
            policy_kind="unknown",
        )


def test_canonical_document_allows_page_less_structured_sources() -> None:
    document = CanonicalPolicyDocument(
        full_text="Policy wording reconstructed from structured payload.",
        pages=None,
        structured_fields={"sum_insured": 500000},
        source_type="structured_policy",
        source_metadata={"source": "test"},
        checksum="abc",
        policy_kind="retail_individual",
    )

    assert document.pages is None
    assert document.structured_fields == {"sum_insured": 500000}
