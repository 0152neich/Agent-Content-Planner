from crewai.tools import BaseTool
from shared.settings import Settings
from shared.logging import get_logger
from shared.base import BaseModel

logger = get_logger(__name__)


class FirecrawlScraperInput(BaseModel):
    url: str


class FirecrawlScraperOutput(BaseModel):
    text: str


class FirecrawlScraperTool(BaseTool):
    settings: Settings

    def _run(self, input: FirecrawlScraperInput) -> FirecrawlScraperOutput:
        try:
            logger.info(f"Scraping data from: {input.url}")
            if not self.settings.firecrawl.api_key:
                logger.error("FIRECRAWL_API_KEY is not configured in the .env file")
                return FirecrawlScraperOutput(
                    text=f"Error (Firecrawl) when reading URL {input.url}: FIRECRAWL_API_KEY is not configured in the .env file"
                )

            from firecrawl import FirecrawlApp

            app = FirecrawlApp(api_key=self.settings.firecrawl.api_key)
            scrape_result = app.scrape_url(input.url, params={"formats": ["markdown"]})

            logger.info(
                f"Scraped data successfully: {scrape_result.get('markdown', 'No Markdown content found.')}"
            )
            return FirecrawlScraperOutput(
                text=f"Scraped data successfully: {scrape_result.get('markdown', 'No Markdown content found.')}"
            )

        except ImportError:
            logger.error("'firecrawl-py' library is not installed.")
            return FirecrawlScraperOutput(
                text=f"Error (Firecrawl) when reading URL {input.url}: 'firecrawl-py' library is not installed."
            )
        except Exception as e:
            logger.error(f"Error (Firecrawl) when reading URL {input.url}: {str(e)}")
            return FirecrawlScraperOutput(
                text=f"Error (Firecrawl) when reading URL {input.url}: {str(e)}"
            )
