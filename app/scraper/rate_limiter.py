import asyncio
import random
import time
from urllib.parse import urlparse


class TokenBucket:
    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_refill = time.monotonic()

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now

    async def acquire(self):
        while True:
            self._refill()
            if self.tokens >= 1:
                self.tokens -= 1
                return
            wait = (1 - self.tokens) / self.rate
            await asyncio.sleep(wait)


class RateLimiter:
    def __init__(self, delay_min: float = 2.0, delay_max: float = 5.0):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self._buckets: dict[str, TokenBucket] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _get_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _get_bucket(self, domain: str) -> TokenBucket:
        if domain not in self._buckets:
            avg_delay = (self.delay_min + self.delay_max) / 2
            rate = 1.0 / avg_delay
            self._buckets[domain] = TokenBucket(rate=rate, capacity=1)
        return self._buckets[domain]

    def _get_lock(self, domain: str) -> asyncio.Lock:
        if domain not in self._locks:
            self._locks[domain] = asyncio.Lock()
        return self._locks[domain]

    async def acquire(self, url: str):
        domain = self._get_domain(url)
        lock = self._get_lock(domain)
        async with lock:
            bucket = self._get_bucket(domain)
            await bucket.acquire()
            # Add random jitter
            jitter = random.uniform(self.delay_min, self.delay_max)
            await asyncio.sleep(jitter)
