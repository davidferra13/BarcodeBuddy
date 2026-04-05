"""Shared test fixtures and client subclasses.

Starlette/httpx deprecated passing ``cookies=`` per-request.  The
recommended approach is to set cookies on the client instance.  These
subclasses intercept the ``cookies`` kwarg, apply it to the instance,
and forward the request without it — silencing the deprecation while
preserving the exact test semantics.
"""

from __future__ import annotations

import httpx
from starlette.testclient import TestClient as _BaseTestClient


class TestClient(_BaseTestClient):
    """Sync test client that handles per-request cookies without deprecation warnings."""

    def request(self, *args, **kwargs):  # type: ignore[override]
        cookies = kwargs.pop("cookies", None)
        if cookies is not None:
            self.cookies.clear()
            for k, v in cookies.items():
                if v is not None:
                    self.cookies.set(k, v)
        return super().request(*args, **kwargs)


class AsyncClient(httpx.AsyncClient):
    """Async test client that handles per-request cookies without deprecation warnings."""

    async def request(self, *args, **kwargs):  # type: ignore[override]
        cookies = kwargs.pop("cookies", None)
        if cookies is not None:
            self.cookies.clear()
            for k, v in cookies.items():
                if v is not None:
                    self.cookies.set(k, v)
        return await super().request(*args, **kwargs)
