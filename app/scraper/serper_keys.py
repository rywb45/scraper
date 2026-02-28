"""Serper API key rotation manager.

Supports unlimited comma-separated keys in SCRAPER_SERP_API_KEY env var.
Automatically rotates to the next key when one is exhausted (403/429).
"""

import logging
import threading

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SerperKeyManager:
    def __init__(self):
        raw = settings.serp_api_key or ""
        self._keys = [k.strip() for k in raw.split(",") if k.strip()]
        self._index = 0
        self._lock = threading.Lock()
        self._exhausted: set[int] = set()
        if self._keys:
            logger.info(f"Serper key manager initialized with {len(self._keys)} key(s)")

    @property
    def has_keys(self) -> bool:
        return len(self._keys) > 0

    @property
    def total_keys(self) -> int:
        return len(self._keys)

    @property
    def active_keys(self) -> int:
        return len(self._keys) - len(self._exhausted)

    def get_key(self) -> str:
        """Get the current active API key."""
        if not self._keys:
            return ""
        with self._lock:
            # If current key is exhausted, find next available
            if self._index in self._exhausted:
                self._rotate()
            return self._keys[self._index] if self._index < len(self._keys) else ""

    def mark_exhausted(self):
        """Mark the current key as exhausted and rotate to next."""
        if not self._keys:
            return
        with self._lock:
            self._exhausted.add(self._index)
            logger.warning(
                f"Serper key #{self._index + 1} exhausted. "
                f"{self.active_keys}/{self.total_keys} keys remaining."
            )
            self._rotate()

    def _rotate(self):
        """Rotate to the next non-exhausted key."""
        if len(self._exhausted) >= len(self._keys):
            logger.error("All Serper API keys exhausted!")
            return
        start = self._index
        while True:
            self._index = (self._index + 1) % len(self._keys)
            if self._index not in self._exhausted:
                logger.info(f"Rotated to Serper key #{self._index + 1}")
                return
            if self._index == start:
                break

    def reset(self):
        """Reset all keys to active (e.g. on new day/billing cycle)."""
        with self._lock:
            self._exhausted.clear()
            self._index = 0

    async def get_all_balances(self) -> list[dict]:
        """Check credit balance for all keys."""
        balances = []
        for i, key in enumerate(self._keys):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://google.serper.dev/account",
                        headers={"X-API-KEY": key},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    credit = data.get("credit", data.get("balance", 0))
                    balances.append({
                        "key_index": i + 1,
                        "credit": credit,
                        "exhausted": i in self._exhausted,
                    })
            except Exception as e:
                balances.append({
                    "key_index": i + 1,
                    "credit": 0,
                    "exhausted": True,
                    "error": str(e),
                })
        return balances

    async def get_total_balance(self) -> int:
        """Get sum of credits across all keys."""
        balances = await self.get_all_balances()
        return sum(b.get("credit", 0) for b in balances)


async def serper_search(query: str, num: int = 10, gl: str = "us", location: str = "") -> dict | None:
    """Make a Serper search request with automatic key rotation."""
    if not key_manager.has_keys:
        return None
    if key_manager.active_keys == 0:
        return None

    key = key_manager.get_key()
    if not key:
        return None

    try:
        payload = {"q": query, "num": num, "gl": gl}
        if location:
            payload["location"] = location
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                json=payload,
                headers={"X-API-KEY": key},
            )
            # Serper returns 400 "Not enough credits", 403, or 429 when exhausted
            if resp.status_code in (400, 403, 429):
                body = resp.text.lower()
                if "credit" in body or resp.status_code in (403, 429):
                    key_manager.mark_exhausted()
                    if key_manager.active_keys > 0:
                        return await serper_search(query, num, gl)
                    return None
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 403, 429):
            key_manager.mark_exhausted()
            if key_manager.active_keys > 0:
                return await serper_search(query, num, gl)
        return None
    except Exception:
        return None


async def serper_account(key: str | None = None) -> dict | None:
    """Check account balance for a specific key or the current active key."""
    k = key or key_manager.get_key()
    if not k:
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://google.serper.dev/account",
                headers={"X-API-KEY": k},
            )
            resp.raise_for_status()
            return resp.json()
    except Exception:
        return None


# Singleton instance
key_manager = SerperKeyManager()
