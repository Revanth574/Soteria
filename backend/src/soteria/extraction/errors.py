class ExtractionAdapterError(Exception):
    """Base class for extraction adapter failures."""


class ConfigurationError(ExtractionAdapterError):
    """Raised when required extraction configuration is missing."""


class PromptTemplateError(ExtractionAdapterError):
    """Raised when the versioned prompt asset cannot be loaded or rendered."""


class MalformedModelOutputError(ExtractionAdapterError):
    """Raised when the model output cannot be parsed as valid extraction JSON."""


class SchemaValidationError(ExtractionAdapterError):
    """Raised when model JSON does not match the supported schema contract."""
