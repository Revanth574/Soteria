class IngestionError(Exception):
    """Base class for policy ingestion failures."""


class UnsupportedFileTypeError(IngestionError):
    """Raised when an upload is not a PDF."""


class PdfExtractionError(IngestionError):
    """Raised when a PDF cannot be opened or parsed for text extraction."""


class EmptyExtractionError(IngestionError):
    """Raised when ingestion produces no usable policy text."""

