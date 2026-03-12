import requests
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from shared.logging import get_logger

from shared.base import BaseModel

logger = get_logger(__name__)


class BS4ScraperInput(BaseModel):
    url: str


class BS4ScraperOutput(BaseModel):
    text: str


class BS4ScraperTool(BaseTool):
    def _run(self, input: BS4ScraperInput) -> BS4ScraperOutput:
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

        except Exception as e:
            logger.error(f"Error (BS4) when reading URL {input.url}: {str(e)}")
            return BS4ScraperOutput(
                text=f"Error (BS4) when reading URL {input.url}: {str(e)}"
            )
