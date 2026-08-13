import pytest

from capability_bridge.core.errors import (
    AuthenticationError,
    CapabilityError,
    InvalidResponseError,
    ModelUnavailableError,
    ProviderError,
    RateLimitError,
    TimeoutError,
    UnsupportedInputError,
    is_fallback_error,
)

PROVIDER_ERRORS = [
    AuthenticationError,
    RateLimitError,
    TimeoutError,
    ModelUnavailableError,
    UnsupportedInputError,
    InvalidResponseError,
]


def test_hierarchy() -> None:
    for cls in PROVIDER_ERRORS:
        assert issubclass(cls, ProviderError)
    assert issubclass(ProviderError, CapabilityError)


def test_fallback_classification() -> None:
    assert is_fallback_error(TimeoutError())
    assert is_fallback_error(RateLimitError())
    assert is_fallback_error(ModelUnavailableError())
    assert is_fallback_error(InvalidResponseError())
    assert not is_fallback_error(AuthenticationError())
    assert not is_fallback_error(UnsupportedInputError())
    assert not is_fallback_error(ValueError("unrelated"))
