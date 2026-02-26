import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx


class RobotsChecker:
    CACHE_TTL = 86400  # 24 hours

    def __init__(self):
        self._cache: dict[str, tuple[RobotFileParser, float]] = {}

    def _get_robots_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    async def _fetch_robots(self, robots_url: str) -> RobotFileParser:
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
                resp = await client.get(robots_url)
                if resp.status_code == 200:
                    parser.parse(resp.text.splitlines())
                else:
                    parser.allow_all = True
        except Exception:
            parser.allow_all = True
        return parser

    async def is_allowed(self, url: str, user_agent: str = "*") -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check cache
        if domain in self._cache:
            parser, cached_at = self._cache[domain]
            if time.time() - cached_at < self.CACHE_TTL:
                return parser.can_fetch(user_agent, url)

        robots_url = self._get_robots_url(url)
        parser = await self._fetch_robots(robots_url)
        self._cache[domain] = (parser, time.time())
        return parser.can_fetch(user_agent, url)
