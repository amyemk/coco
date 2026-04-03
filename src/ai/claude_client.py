"""
Claude API Client

Wrapper around the Anthropic SDK with:
- Retry logic with exponential backoff
- SQLite-backed response caching
- Request-level rate limiting
- Usage tracking
"""

import asyncio
from dataclasses import dataclass, field
from typing import Optional

import anthropic
import structlog

from src.ai.cache_manager import CacheManager
from src.ai.rate_limiter import RateLimiter

logger = structlog.get_logger()

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_BASE_DELAY = 2.0  # seconds, doubles each retry


@dataclass
class UsageStats:
    total_requests: int = 0
    cache_hits: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    errors: int = 0
    # Running cost estimate (very rough — update rates as needed)
    estimated_cost_usd: float = field(init=False)

    def __post_init__(self):
        self.estimated_cost_usd = 0.0

    def record_usage(self, input_tokens: int, output_tokens: int, model: str) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        # Approximate pricing (USD per 1M tokens, as of early 2026)
        rates = {
            "haiku": (0.80, 4.00),    # input, output per 1M tokens
            "sonnet": (3.00, 15.00),
        }
        key = "haiku" if "haiku" in model.lower() else "sonnet"
        in_rate, out_rate = rates[key]
        self.estimated_cost_usd += (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


class ClaudeClient:
    """
    Anthropic Claude API client with caching, rate limiting, and retries.

    Usage:
        client = ClaudeClient(api_key="...", config=ai_config, cache_db_path="./data/cache.db")
        response = await client.complete("Classify this email...", model="claude-haiku-4-5-20251001")
    """

    def __init__(
        self,
        api_key: str,
        default_model: str = "claude-sonnet-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        cache_db_path: str = "./data/ai_cache.db",
        cache_ttl_hours: int = 24,
        enable_cache: bool = True,
        tokens_per_minute: int = 50,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.default_model = default_model
        self.default_max_tokens = max_tokens
        self.default_temperature = temperature
        self.max_retries = max_retries
        self.enable_cache = enable_cache

        self._cache = CacheManager(cache_db_path, cache_ttl_hours) if enable_cache else None
        self._rate_limiter = RateLimiter(tokens_per_minute=tokens_per_minute)
        self.usage = UsageStats()

    async def complete(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        use_cache: bool = True,
    ) -> str:
        """
        Send a prompt to Claude and return the text response.

        Args:
            prompt: The user message
            model: Model override (defaults to default_model)
            system: System prompt
            max_tokens: Max tokens override
            temperature: Temperature override
            use_cache: Whether to check/populate the response cache

        Returns:
            Response text string
        """
        model = model or self.default_model
        max_tokens = max_tokens or self.default_max_tokens
        temperature = temperature if temperature is not None else self.default_temperature

        # Check cache first
        if use_cache and self._cache:
            cached = self._cache.get(model, prompt, system)
            if cached is not None:
                self.usage.cache_hits += 1
                return cached

        await self._rate_limiter.acquire()

        response_text = await self._call_with_retry(
            prompt=prompt,
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        if use_cache and self._cache:
            self._cache.set(model, prompt, response_text, system)

        return response_text

    async def complete_json(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Like complete(), but appends a JSON instruction and sets temperature=0
        for more deterministic structured output.
        """
        json_prompt = prompt + "\n\nRespond with valid JSON only. No markdown, no explanation."
        return await self.complete(
            prompt=json_prompt,
            model=model,
            system=system,
            max_tokens=max_tokens,
            temperature=0.0,
            use_cache=True,
        )

    async def _call_with_retry(
        self,
        prompt: str,
        model: str,
        system: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                self.usage.total_requests += 1
                response = self._client.messages.create(**kwargs)
                text = response.content[0].text
                self.usage.record_usage(
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    model=model,
                )
                logger.debug(
                    "claude_api_call",
                    model=model,
                    input_tokens=response.usage.input_tokens,
                    output_tokens=response.usage.output_tokens,
                    attempt=attempt,
                )
                return text

            except anthropic.RateLimitError as e:
                last_error = e
                delay = _DEFAULT_RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning("claude_rate_limit", attempt=attempt, wait=delay)
                await asyncio.sleep(delay)

            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    delay = _DEFAULT_RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning("claude_server_error", status=e.status_code, attempt=attempt, wait=delay)
                    await asyncio.sleep(delay)
                else:
                    self.usage.errors += 1
                    logger.error("claude_api_error", status=e.status_code, message=str(e))
                    raise

            except Exception as e:
                self.usage.errors += 1
                logger.error("claude_unexpected_error", error=str(e))
                raise

        self.usage.errors += 1
        logger.error("claude_max_retries_exceeded", attempts=self.max_retries + 1)
        raise last_error  # type: ignore

    def get_usage_stats(self) -> UsageStats:
        return self.usage

    def purge_cache(self) -> int:
        if self._cache:
            return self._cache.purge_expired()
        return 0
