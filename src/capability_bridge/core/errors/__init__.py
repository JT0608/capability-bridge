class CapabilityError(Exception):
    """Base error for capability-bridge."""


class ProviderError(CapabilityError):
    """A provider failed while handling a request."""


class AuthenticationError(ProviderError):
    """Credentials are invalid (e.g. HTTP 401). Never fallback."""


class RateLimitError(ProviderError):
    """Rate limited (e.g. HTTP 429). Fallback allowed."""


class TimeoutError(ProviderError):
    """The provider request timed out. Fallback allowed."""


class ModelUnavailableError(ProviderError):
    """The model/provider is unavailable or errored. Fallback allowed."""


class UnsupportedInputError(ProviderError):
    """The input is invalid (bad image, unsupported scheme). Never fallback."""


class InvalidResponseError(ProviderError):
    """The provider returned a response that failed schema checks. Retry/fallback allowed."""


#: Error types that should trigger retry/fallback.
_FALLBACK_ERRORS = (
    RateLimitError,
    TimeoutError,
    ModelUnavailableError,
    InvalidResponseError,
)


def is_fallback_error(exc: Exception) -> bool:
    """Return True if this error should trigger fallback to another provider."""
    return isinstance(exc, _FALLBACK_ERRORS)
