"""Structured API error type.

Messages are safe to show to the client; internals, stack traces and secrets
never appear in error responses.
"""


class ApiError(Exception):
    """Raise anywhere in the API to return a structured error response."""

    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        super().__init__(message)
