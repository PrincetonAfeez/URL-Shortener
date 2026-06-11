"""Domain exceptions used by every sniplink adapter."""


class SniplinkError(Exception):
    """Base class for project-specific failures."""


class InvalidDestinationURL(SniplinkError):
    """Raised when a destination URL is empty, malformed, or unsafe."""


class InvalidAlias(SniplinkError):
    """Raised when a vanity alias is malformed or reserved."""


class CodeNotFound(SniplinkError):
    """Raised when a short code has never existed."""


class LinkGone(SniplinkError):
    """Base class for links that existed but should now return 410."""


class CodeExpired(LinkGone):
    """Raised when a link is past its expiry date or click limit."""


class CodeDisabled(LinkGone):
    """Raised when a link has been disabled."""


class CodeDeleted(LinkGone):
    """Raised when a link has been soft-deleted."""


class AliasTaken(SniplinkError):
    """Raised when a requested or generated code violates uniqueness."""


class CollisionExhausted(SniplinkError):
    """Raised when the code-assignment retry budget is exhausted."""


class StorageError(SniplinkError):
    """Raised when persistence fails outside a known uniqueness conflict."""


class AuthError(SniplinkError):
    """Placeholder for API-key-auth stretch behavior."""


class RateLimitExceeded(SniplinkError):
    """Placeholder for rate-limiting stretch behavior."""


class HealthCheckError(SniplinkError):
    """Raised when health-check setup fails."""


class RedirectLimitExceeded(HealthCheckError):
    """Raised when the async health checker hits the redirect-hop budget."""
