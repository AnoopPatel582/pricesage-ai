class ScraperException(Exception):
    """Base exception for scraping errors."""
    pass


class NetworkException(ScraperException):
    """Raised when an HTTP, connection, or timeout error occurs."""
    pass


class ParsingException(ScraperException):
    """Raised when expected HTML tags or attributes are missing/malformed."""
    pass


class UnsupportedSiteException(ScraperException):
    """Raised when no scraper adapter is registered for the given domain."""
    pass
