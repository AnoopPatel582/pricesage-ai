import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from app.scrapers.base import BaseScraper, ScrapedProduct
from app.scrapers.exceptions import ScraperException


class BookToScrapeScraper(BaseScraper):
    """Scraper adapter for books.toscrape.com."""

    def parse(self, html_content: str, base_url: str = "") -> ScrapedProduct:
        """Required by BaseScraper abstract definition."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Title
        title_el = soup.select_one(".product_main h1")
        if not title_el:
            raise ScraperException("Could not extract title from page")
        title = title_el.get_text(strip=True)

        # Price
        price_el = soup.select_one(".product_main .price_color")
        if not price_el:
            raise ScraperException("Could not extract price from page")

        raw_price = price_el.get_text(strip=True)
        cleaned_price = re.sub(r"[^\d.]", "", raw_price)
        try:
            price = float(cleaned_price)
        except ValueError as exc:
            raise ScraperException("Could not parse product price") from exc

        # Availability
        avail_el = soup.select_one(".product_main .availability")
        availability = "In Stock" if avail_el and "In stock" in avail_el.get_text() else "Out of Stock"

        # Image
        img_el = soup.select_one("#product_gallery img")
        image_url = None
        if img_el and img_el.get("src"):
            image_url = urljoin(base_url, img_el.get("src"))

        return ScrapedProduct(
            name=title,
            price=price,
            currency="GBP",
            availability=availability,
            image_url=image_url,
        )


    def scrape(self, url: str) -> ScrapedProduct:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                timeout=10,
            )
            if response.status_code != 200:
                raise ScraperException(f"Target returned status code {response.status_code}")

            return self.parse(response.text, base_url=url)

        except ScraperException:
            raise
        except Exception as exc:
            raise ScraperException(f"Scraping failed: {exc}") from exc


# Alias in case another file imports BooksToScrapeScraper
BooksToScrapeScraper = BookToScrapeScraper
