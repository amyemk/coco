"""
API Rate Limiter

Token bucket rate limiter for Claude API calls.
Prevents hitting Anthropic's rate limits during batch processing.
"""

import asyncio
import time

import structlog

logger = structlog.get_logger()


class RateLimiter:
    """
    Async token bucket rate limiter.

    Allows bursting up to max_tokens, refilling at tokens_per_minute rate.
    Each API call costs 1 token regardless of size (request-level limiting).
    For token-level limiting, set tokens_per_minute to match your API tier.
    """

    def __init__(self, tokens_per_minute: int = 50, max_tokens: int = 10):
        self.tokens_per_minute = tokens_per_minute
        self.max_tokens = max_tokens
        self._tokens = float(max_tokens)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        async with self._lock:
            await self._refill()
            while self._tokens < 1.0:
                wait = (1.0 - self._tokens) / (self.tokens_per_minute / 60.0)
                logger.debug("rate_limiter_waiting", wait_seconds=round(wait, 2))
                await asyncio.sleep(wait)
                await self._refill()
            self._tokens -= 1.0

    async def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        added = elapsed * (self.tokens_per_minute / 60.0)
        self._tokens = min(self.max_tokens, self._tokens + added)
        self._last_refill = now
