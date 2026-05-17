import requests
from crewai.tools import BaseTool
from shared.logging import get_logger

from shared.base import BaseModel
from shared.exceptions import ScraperToolError

logger = get_logger(__name__)


class BS4ScraperInput(BaseModel):
    url: str


class BS4ScraperOutput(BaseModel):
    text: str


def _normalize_bs4_input(raw: BS4ScraperInput) -> BS4ScraperInput:
    """CrewAI passes tool args as dict (e.g. {'input': {'url': '...'}}). Normalize to our model."""
    if isinstance(raw, BS4ScraperInput):
        return raw
    payload = raw.get("input", raw) if isinstance(raw, dict) else raw
    return BS4ScraperInput(
        **(payload if isinstance(payload, dict) else {"url": str(payload)})
    )


class BS4ScraperTool(BaseTool):
    def _run(self, input: BS4ScraperInput) -> BS4ScraperOutput:
        try:
            input = _normalize_bs4_input(input)
        except Exception as exc:
            message = f"BS4 scraper received invalid input: {str(exc)}"
            logger.error(message)
            raise ScraperToolError(message) from exc

        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            message = (
                "BS4 scraper dependency is missing. Install 'beautifulsoup4' package."
            )
            logger.error(message)
            raise ScraperToolError(message) from exc

        try:
            logger.info(f"Scraping data from: {input.url}")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(input.url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, "html.parser")

            for element in soup(
                ["script", "style", "header", "footer", "nav", "aside", "form"]
            ):
                element.extract()

            text = soup.get_text(separator="\n", strip=True)
            return BS4ScraperOutput(text=text[:15000])

        except Exception as exc:
            message = f"BS4 scraper failed for URL {input.url}: {str(exc)}"
            logger.error(message)
            raise ScraperToolError(message) from exc
