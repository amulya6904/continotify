class PortalNotReachableError(Exception):
    """Raised when the portal URL is unreachable (network/VPN issue)."""
    pass


class LoginFailedException(Exception):
    """Raised when login fails — PROCTORSHIP link not found after submit."""
    pass


class StudentParseError(Exception):
    """Raised when a student card cannot be parsed (missing USN etc.)."""
    pass


class AttendanceParseError(Exception):
    """Raised when the Course wise - Status modal or table cannot be parsed."""
    pass
