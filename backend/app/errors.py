class ConflictError(Exception):
    """Action conflicts with current authoritative state (HTTP 409)."""


class InvalidError(Exception):
    """Invalid application input (HTTP 400)."""
