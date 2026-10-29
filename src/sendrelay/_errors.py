from __future__ import annotations

from typing import Any, Optional


class RelayError(Exception):
    """Base class for every error this SDK raises."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ApiError(RelayError):
    """The API answered with an error status.

    ``code`` is the API's error code (for example ``NOT_FOUND`` or ``CONFLICT``) and ``details``
    carries anything extra the API sent, such as validation problems.
    """

    def __init__(self, status_code: int, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.details = details

    def __repr__(self) -> str:
        return f"ApiError(status_code={self.status_code}, code={self.code!r}, message={self.message!r})"


class NetworkError(RelayError):
    """The request never got an answer: the connection failed or timed out."""

    def __init__(self, message: str, cause: Optional[BaseException] = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class ValidationError(RelayError):
    """The SDK rejected the input before sending anything."""

    def __init__(self, message: str, field: Optional[str] = None) -> None:
        super().__init__(message)
        self.field = field
