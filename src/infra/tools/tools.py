from infra.tools.scraper import BS4ScraperTool
from infra.tools.scraper import FirecrawlScraperTool

from shared.settings import Settings

settings = Settings()


def get_scraper_tool():
    """Factory function to return the appropriate scraper tool based on the environment variable.

    Set SCRAPER_PROVIDER in .env to 'firecrawl' or 'bs4'.
    Defaults to 'bs4' if the variable is not set.
    """
    provider = settings.provider.lower()
    if provider == "firecrawl":
        return FirecrawlScraperTool()
    elif provider == "bs4":
        return BS4ScraperTool()
    else:
        raise ValueError(
            f"Invalid SCRAPER_PROVIDER value: '{provider}'. "
            "Must be 'firecrawl' or 'bs4'."
        )
