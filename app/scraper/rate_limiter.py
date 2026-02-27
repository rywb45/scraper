import asyncio
import random
import time
from urllib.parse import urlparse


class RateLimiter:
    """Per-domain rate limiter. Only delays when hitting the same domain repeatedly."""

    def __init__(self, delay_min: float = 1.0, delay_max: float = 3.0):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._last_request: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _get_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        return self._locks[domain]

    async def acquire(self, url: str):
        domain = self._get_domain(url)
        lock = self._get_lock(domain)
        async with lock:
            now = time.monotonic()
            last = self._last_request.get(domain, 0)
            min_interval = random.uniform(self.delay_min, self.delay_max)
            elapsed = now - last

            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)

            self._last_request[domain] = time.monotonic()
