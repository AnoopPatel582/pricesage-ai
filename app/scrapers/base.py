from abc import ABC, abstractmethod
import logging
import time
import requests
from requests.exceptions import RequestException, Timeout, HTTPError
from dataclasses import dataclass

from app.scrapers.exceptions import NetworkException, ParsingException, ScraperException

logger = logging.getLogger(__name__)


@dataclass
class ScrapedProduct:
    name: str
    price: float
    currency: str = "INR"  # Default or dynamically parsed
    availability: str = "In Stock"
    image_url: str = None
    original_price: float = None


class BaseScraper(ABC):
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.5):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }

    def fetch_html(self, url: str) -> str:
        """Fetch raw HTML with retry logic and defensive error handling."""
        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            try:
                logger.info(f"Fetching URL: {url} (Attempt {attempt + 1}/{self.max_retries})")
                response = requests.get(url, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response.text

            except (Timeout, HTTPError, RequestException) as err:
                attempt += 1
                last_error = err
                logger.warning(f"Fetch failed for {url} on attempt {attempt}: {err}")
                if attempt < self.max_retries:
                    sleep_time = self.backoff_factor ** attempt
                    time.sleep(sleep_time)

        raise NetworkException(
            f"Failed to fetch {url} after {self.max_retries} attempts. Last error: {last_error}"
        )

    @abstractmethod
    def parse(self, html: str, url: str) -> ScrapedProduct:
        """Parse raw HTML and return a validated ScrapedProduct."""
        pass

    def scrape(self, url: str) -> ScrapedProduct:
        """Fetch and parse with top-level error trapping."""
        html = self.fetch_html(url)
        try:
            return self.parse(html, url)
        except Exception as e:
            if isinstance(e, ScraperException):
                raise e
            raise ParsingException(f"Failed to parse product page at {url}: {e}") from e
