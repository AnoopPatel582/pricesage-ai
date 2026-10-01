from urllib.parse import urlparse
from typing import Dict, Type
from app.scrapers.base import BaseScraper
from app.scrapers.book_scraper import BookToScrapeScraper
from app.scrapers.amazon import AmazonScraper
from app.scrapers.exceptions import UnsupportedSiteException

class ScraperFactory:
    """Factory mapping domain names to their respective scraper adapters."""

    _scrapers: Dict[str, Type[BaseScraper]] = {
        "books.toscrape.com": BookToScrapeScraper,
        "amazon.in": AmazonScraper,
        "www.amazon.in": AmazonScraper,
        "amazon.com": AmazonScraper,
        "www.amazon.com": AmazonScraper,
    }

    @classmethod
    def get_scraper(cls, url: str) -> BaseScraper:
        domain = urlparse(url).netloc.lower()
        scraper_cls = cls._scrapers.get(domain)
        if not scraper_cls:
            normalized_domain = domain.removeprefix("www.")
            scraper_cls = cls._scrapers.get(normalized_domain)

        if not scraper_cls:
            supported = ", ".join(sorted(set(k.removeprefix("www.") for k in cls._scrapers.keys())))
            raise UnsupportedSiteException(
                f"Domain '{domain}' is not supported. Supported domains: {supported}"
            )

        return scraper_cls()
