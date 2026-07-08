class EphemeralError(Exception):
    """Base class for signup-free ephemeral flow failures."""


class StorageConfigurationError(EphemeralError):
    """Raised when local ephemeral storage is configured unsafely."""


class UploadValidationError(EphemeralError):
    """Raised when an anonymous upload violates file guards."""


class RateLimitExceededError(EphemeralError):
    """Raised when an IP exceeds the anonymous upload cap."""


class NotFoundError(EphemeralError):
    """Raised when an ephemeral session or token is unavailable."""

