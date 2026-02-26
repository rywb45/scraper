import asyncio
import random

import httpx

from app.config import settings
from app.scraper.rate_limiter import RateLimiter
from app.scraper.robots import RobotsChecker

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class HttpClient:
    def __init__(self):
        self.rate_limiter = RateLimiter(
            delay_min=settings.default_delay_min,
            delay_max=settings.default_delay_max,
        )
        self.robots_checker = RobotsChecker()
        self.max_retries = settings.max_retries
        self.timeout = settings.request_timeout
        self.respect_robots = settings.respect_robots_txt

    def _random_ua(self) -> str:
        return random.choice(USER_AGENTS)

    async def get(self, url: str, follow_redirects: bool = True) -> httpx.Response | None:
        if self.respect_robots:
            allowed = await self.robots_checker.is_allowed(url)
            if not allowed:
                return None

        await self.rate_limiter.acquire(url)

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=follow_redirects,
                    headers={
                        "User-Agent": self._random_ua(),
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                        "Accept-Language": "en-US,en;q=0.9",
                    },
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    return resp
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 404, 410):
                    return None
                if attempt < self.max_retries - 1:
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)
            except (httpx.RequestError, asyncio.TimeoutError):
                if attempt < self.max_retries - 1:
                    backoff = (2 ** attempt) + random.uniform(0, 1)
                    await asyncio.sleep(backoff)

        return None
