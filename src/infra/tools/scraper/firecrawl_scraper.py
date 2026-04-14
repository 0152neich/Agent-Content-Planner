from crewai.tools import BaseTool
from shared.settings import Settings
from shared.logging import get_logger
from shared.base import BaseModel
from shared.exceptions import ScraperToolError

logger = get_logger(__name__)


class FirecrawlScraperInput(BaseModel):
    url: str


class FirecrawlScraperOutput(BaseModel):
    text: str


def _normalize_scraper_input(
    raw: FirecrawlScraperInput,
) -> FirecrawlScraperInput:
    """CrewAI passes tool args as dict (e.g. {'input': {'url': '...'}}). Normalize to our model."""
    if isinstance(raw, FirecrawlScraperInput):
        return raw
    payload = raw.get("input", raw) if isinstance(raw, dict) else raw
    return FirecrawlScraperInput(
        **(payload if isinstance(payload, dict) else {"url": str(payload)})
    )


class FirecrawlScraperTool(BaseTool):
    name: str = "firecrawl_scraper"
    description: str = (
        "Scrapes a URL and returns its content as markdown using Firecrawl."
    )
    settings: Settings

    @staticmethod
    def _extract_markdown(result: object) -> str | None:
        if result is None:
            return None

        if isinstance(result, dict):
            markdown = result.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                return markdown.strip()

            data = result.get("data")
            if isinstance(data, dict):
                nested_markdown = data.get("markdown")
                if isinstance(nested_markdown, str) and nested_markdown.strip():
                    return nested_markdown.strip()
            return None

        markdown_attr = getattr(result, "markdown", None)
        if isinstance(markdown_attr, str) and markdown_attr.strip():
            return markdown_attr.strip()

        data_attr = getattr(result, "data", None)
        if isinstance(data_attr, dict):
            nested_markdown = data_attr.get("markdown")
            if isinstance(nested_markdown, str) and nested_markdown.strip():
                return nested_markdown.strip()
        return None

    def _run(self, input: FirecrawlScraperInput) -> FirecrawlScraperOutput:
        try:
            input = _normalize_scraper_input(input)
        except Exception as exc:
            message = f"Firecrawl scraper received invalid input: {str(exc)}"
            logger.error(message)
            raise ScraperToolError(message) from exc

        try:
            logger.info(f"Scraping data from: {input.url}")
            if not self.settings.firecrawl.api_key:
                message = "FIRECRAWL_API_KEY is not configured in the .env file"
                logger.error(message)
                raise ScraperToolError(message)

            try:
                from firecrawl import Firecrawl  # type: ignore

                client = Firecrawl(api_key=self.settings.firecrawl.api_key)
            except ImportError:
                from firecrawl import FirecrawlApp  # type: ignore

                client = FirecrawlApp(api_key=self.settings.firecrawl.api_key)

            scrape_result: object
            if hasattr(client, "scrape"):
                scrape_result = client.scrape(input.url, formats=["markdown"])
            elif hasattr(client, "scrape_url"):
                scrape_result = client.scrape_url(
                    input.url, params={"formats": ["markdown"]}
                )
            else:
                raise AttributeError(
                    "Firecrawl client does not support scrape/scrape_url."
                )

            markdown = self._extract_markdown(scrape_result)
            if not markdown:
                message = f"Firecrawl returned empty markdown for URL {input.url}."
                logger.warning(message, url=input.url)
                raise ScraperToolError(message)

            logger.info("Scraped data successfully.", url=input.url)
            return FirecrawlScraperOutput(text=markdown)

        except ImportError as exc:
            message = "'firecrawl-py' library is not installed."
            logger.error(message)
            raise ScraperToolError(message) from exc
        except ScraperToolError:
            raise
        except Exception as exc:
            message = f"Firecrawl scraper failed for URL {input.url}: {str(exc)}"
            logger.error(message)
            raise ScraperToolError(message) from exc
