"""Exceptions and exit codes shared by the CLI, the scheduler and the adapters."""

EXIT_OK = 0
EXIT_NOTHING = 1
EXIT_SESSION = 2
EXIT_FAILED = 3
EXIT_REFUSED = 4  # identity mismatch or a missing expected identity: nothing was posted


class SocialError(Exception):
    """A platform call failed. Safe to retry (bounded by the scheduler)."""


class Refused(Exception):
    """The authenticated account is not the expected company account. Never retried, always notified."""


class SessionExpired(SocialError):
    """A saved browser session or token needs Ben (login or refresh). Retrying will not help."""


class Disabled(Exception):
    """The platform is disabled or has no credentials."""


class Ambiguous(SocialError):
    """The final publish call failed in a way that may still have posted (timeout, 5xx). Never retried: a person
    checks the account, because a retry could post twice."""
