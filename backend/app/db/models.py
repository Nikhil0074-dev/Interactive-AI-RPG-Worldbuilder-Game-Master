from __future__ import annotations

import datetime as dt
import json
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)


class World(Base):
    __tablename__ = "worlds"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    campaign_id: Mapped[str] = mapped_column(String(36), index=True)
    name: Mapped[str] = mapped_column(String(120))
    genre: Mapped[str] = mapped_column(String(40))
    content: Mapped[dict] = mapped_column(JSON)          # validated static world graph


class Campaign(Base):
    __tablename__ = "campaigns"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    owner_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    config: Mapped[dict] = mapped_column(JSON)
    world_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    current_state: Mapped[str] = mapped_column(String(32), default="WORLD_CREATION")
    current_location_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    version: Mapped[int] = mapped_column(Integer, default=0)       # optimistic concurrency counter
    state_json: Mapped[str] = mapped_column(Text)                   # authoritative mutable GameState
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class ActionLog(Base):
    """One row per submitted action id: guarantees idempotency and caches the response."""
    __tablename__ = "action_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"))
    action_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(16))
    response_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (UniqueConstraint("campaign_id", "action_id", name="uq_action"),)


class CampaignEvent(Base):
    __tablename__ = "campaign_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    action_id: Mapped[str] = mapped_column(String(80))
    event_type: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class NarrativeHistory(Base):
    __tablename__ = "narrative_history"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_text: Mapped[str] = mapped_column(String(400), default="")
    narrative_text: Mapped[str] = mapped_column(Text)
    referenced_entities: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    entity_id: Mapped[str] = mapped_column(String(64))
    asset_type: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(40))
    model_id: Mapped[str] = mapped_column(String(80))
    prompt: Mapped[str] = mapped_column(Text)
    prompt_hash: Mapped[str] = mapped_column(String(40))
    storage_key: Mapped[str | None] = mapped_column(String(200), nullable=True)
    mime: Mapped[str] = mapped_column(String(40), default="image/png")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    __table_args__ = (Index("ix_asset_lookup", "campaign_id", "entity_id", "prompt_hash"),)


class SaveCheckpoint(Base):
    __tablename__ = "saves"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    campaign_id: Mapped[str] = mapped_column(String(36), ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(80))
    state_json: Mapped[str] = mapped_column(Text)
    schema_version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
