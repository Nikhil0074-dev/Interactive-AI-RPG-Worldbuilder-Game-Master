from __future__ import annotations

import pathlib

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from ..config import Settings
from .models import Base


def make_engine(url: str):
    if url.startswith("sqlite:///") and ":memory:" not in url:
        pathlib.Path(url.replace("sqlite:///", "", 1)).parent.mkdir(parents=True, exist_ok=True)
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
    if ":memory:" in url:
        from sqlalchemy.pool import StaticPool
        kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _fk(dbapi_conn, _):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


def init_db(settings: Settings):
    engine = make_engine(settings.database_url)
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)
