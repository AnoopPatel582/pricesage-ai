import re
from app.scrapers.base import BaseScraper, ScrapedProduct
from app.scrapers.exceptions import ScraperException


class AmazonScraper(BaseScraper):
    """Headless browser adapter for scraping Amazon product details."""

    def parse(self, html_content: str, base_url: str = "") -> ScrapedProduct:
        # We can leverage BeautifulSoup here for clean HTML parsing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        title_tag = soup.select_one("#productTitle") or soup.select_one("h1#title")
        if not title_tag:
            if "Robot Check" in html_content or "api-services-support@amazon.com" in html_content:
                raise ScraperException("Amazon bot check triggered. Please try again later.")
            raise ScraperException("Could not find product title on Amazon page.")
        title = title_tag.get_text(strip=True)

        price = None
        price_selectors = [
            ".a-price .a-offscreen",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "#corePriceDisplay_desktop_feature_div .a-price .a-offscreen",
            "#corePrice_desktop .a-price .a-offscreen",
            "span.apexPriceToPay span.a-offscreen",
        ]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el:
                raw_val = el.get_text(strip=True)
                cleaned = re.sub(r"[^\d.]", "", raw_val.replace(",", ""))
                try:
                    price = float(cleaned)
                    break
                except (ValueError, TypeError):
                    continue

        if price is None:
            raise ScraperException("Could not find price on Amazon page.")

        currency = "INR" if "amazon.in" in base_url else "USD"

        image_url = None
        img_tag = soup.select_one("#landingImage") or soup.select_one("#imgBlkFront") or soup.select_one("#main-image")
        if img_tag:
            image_url = img_tag.get("data-old-hires") or img_tag.get("src")

        avail_tag = soup.select_one("#availability")
        availability = "In Stock"
        if avail_tag:
            avail_text = avail_tag.get_text(strip=True).lower()
            if "currently unavailable" in avail_text or "out of stock" in avail_text:
                availability = "Out of Stock"

        return ScrapedProduct(

            name=title,
            price=price,
            currency=currency,
            availability=availability,
            image_url=image_url,
        )

    def scrape(self, url: str) -> ScrapedProduct:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                # Launch headless browser with realistic user arguments
                browser = p.chromium.launch(
                    headless=True,
                    args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
                )
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    viewport={"width": 1920, "height": 1080}
                )
                page = context.new_page()

                # Navigate to product page and wait for content network load
                page.goto(url, timeout=30000, wait_until="domcontentloaded")

                # Small wait to let dynamic price/title scripts evaluate
                page.wait_for_timeout(2000)

                html_content = page.content()
                browser.close()

                return self.parse(html_content, base_url=url)

        except ScraperException:
            raise
        except Exception as exc:
            raise ScraperException(f"Playwright scraper error: {exc}") from exc


AmazonScraper = AmazonScraper
