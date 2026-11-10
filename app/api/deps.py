from __future__ import annotations

import re
import time
from collections import defaultdict, deque

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from ..service import GameService, ServiceError

PLAYER_ID = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")


class RateLimiter:
    """Sliding-window limiter (in-memory; swap for Redis when scaling horizontally)."""

    def __init__(self):
        self.hits: dict[tuple, deque] = defaultdict(deque)

    def check(self, key: tuple, limit: int, window: float = 60.0) -> None:
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            raise HTTPException(429, {"code": "RATE_LIMITED", "message": "Too many requests. Please slow down."})
        q.append(now)


def get_service(request: Request) -> GameService:
    return request.app.state.service


def get_session(request: Request):
    with request.app.state.service.sessions() as s:
        yield s


def get_owner(x_player_id: str | None = Header(default=None)) -> str:
    if not x_player_id or not PLAYER_ID.match(x_player_id):
        raise HTTPException(401, {"code": "MISSING_PLAYER_ID", "message": "A valid X-Player-Id header is required."})
    return x_player_id


def limit(bucket: str):
    def dep(request: Request, owner: str = Depends(get_owner)):
        cfg = request.app.state.service.settings
        n = {"action": cfg.rate_action_per_min, "generate": cfg.rate_generate_per_min, "asset": cfg.rate_asset_per_min}[bucket]
        request.app.state.limiter.check((owner, bucket), n)
    return dep
