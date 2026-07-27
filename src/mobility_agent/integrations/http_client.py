from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


class UpstreamError(RuntimeError):
    """A bounded, user-safe error raised for an unavailable public provider."""


@dataclass
class _CacheEntry:
    expires_at: float
    payload: Any


class JsonHttpClient:
    """Small allowlisted JSON client with TTL cache, retries and a circuit breaker."""

    def __init__(
        self,
        *,
        allowed_hosts: set[str],
        user_agent: str,
        timeout_seconds: float = 6,
        max_response_bytes: int = 1_500_000,
        retries: int = 1,
        cache_ttl_seconds: int = 60,
        opener: Callable[..., Any] | None = None,
    ) -> None:
        self.allowed_hosts = allowed_hosts
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self.retries = retries
        self.cache_ttl_seconds = cache_ttl_seconds
        self.opener = opener or urllib.request.urlopen
        self._cache: dict[str, _CacheEntry] = {}
        self._failures: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def get(self, url: str, *, cache_ttl_seconds: int | None = None) -> Any:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.allowed_hosts:
            raise ValueError("upstream URL is not in the HTTPS allowlist")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("upstream URL contains forbidden components")

        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(url)
            if cached and cached.expires_at > now:
                return cached.payload
            failure_count, opened_until = self._failures.get(parsed.hostname, (0, 0))
            if failure_count >= 3 and opened_until > now:
                raise UpstreamError("public data provider circuit is temporarily open")

        last_error: Exception | None = None
        for _attempt in range(self.retries + 1):
            try:
                request = urllib.request.Request(
                    url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": self.user_agent,
                    },
                )
                with self.opener(request, timeout=self.timeout_seconds) as response:
                    raw = response.read(self.max_response_bytes + 1)
                if len(raw) > self.max_response_bytes:
                    raise UpstreamError("public data response exceeded the size limit")
                payload = json.loads(raw.decode("utf-8"))
                ttl = self.cache_ttl_seconds if cache_ttl_seconds is None else cache_ttl_seconds
                with self._lock:
                    self._cache[url] = _CacheEntry(time.monotonic() + ttl, payload)
                    self._failures.pop(parsed.hostname, None)
                return payload
            except (
                json.JSONDecodeError,
                OSError,
                TimeoutError,
                UnicodeDecodeError,
                urllib.error.HTTPError,
                urllib.error.URLError,
            ) as exc:
                last_error = exc

        with self._lock:
            count, _ = self._failures.get(parsed.hostname, (0, 0))
            self._failures[parsed.hostname] = (count + 1, time.monotonic() + 60)
        raise UpstreamError("public data provider is unavailable") from last_error
