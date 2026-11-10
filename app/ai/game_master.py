"""AI Game Master: assembles context, calls the provider, validates the structured response, falls back safely."""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from ..data.content import ENEMIES, ITEMS
from ..game_engine.action_resolver import Resolution
from ..game_engine.event_text import describe_events
from ..game_engine.scene import available_actions
from ..models.state import ActionRequest, GameState
from . import memory_retriever
from .provider import LLMProvider, ProviderError

Mood = Literal["calm", "mysterious", "tense", "ominous", "hopeful", "triumphant", "grim", "uneasy"]


class NarrationResponse(BaseModel):
    model_config = {"extra": "ignore"}
    narration: str = Field(min_length=1, max_length=1600)
    scene_mood: Mood = "mysterious"
    suggested_actions: list[str] = Field(default_factory=list, max_length=5)
    referenced_entities: list[str] = Field(default_factory=list, max_length=12)


def known_entity_ids(world: dict) -> set[str]:
    ids = set(world["locations"]) | set(world["npcs"]) | set(world["quests"]) | set(ITEMS) | set(ENEMIES)
    ids |= {f["id"] for f in world["factions"]} | {r["id"] for r in world["regions"]}
    for loc in world["locations"].values():
        ids |= {o["id"] for o in loc.get("objects", [])}
    return ids


def template_narration(ctx: dict) -> dict:
    parts = list(ctx.get("scripted", [])) + list(ctx.get("prose", []))
    if ctx.get("rejected"):
        parts = [ctx["rejected"]]
    if not parts:
        parts = [ctx["location"]["description"]]
    return {"narration": " ".join(parts)[:1500], "scene_mood": ctx["location"]["mood"] if ctx["location"]["mood"] in
            ("calm", "mysterious", "tense", "ominous", "hopeful", "triumphant", "grim", "uneasy") else "mysterious",
            "suggested_actions": ctx.get("suggestions", [])[:4], "referenced_entities": ctx.get("entities", [])[:12]}


def build_context(world: dict, state: GameState, res: Resolution, action: ActionRequest, recent: list[str]) -> dict:
    loc = world["locations"][state.location_id]
    prose, mech = describe_events(world, res.events)
    entities = [state.location_id] + list(loc.get("npcs", []))
    for e in res.events:
        for k in ("item_id", "npc_id", "enemy_id", "quest_id", "location_id", "object_id"):
            if k in e and e[k] and e[k] not in entities:
                entities.append(e[k])
    mood = "tense" if state.fsm_state == "COMBAT" else loc["mood"]
    return {
        "action": {"type": action.type, "text": action.text},
        "location": {"id": loc["id"], "name": loc["name"], "description": loc["description"], "mood": mood, "weather": loc["weather"]},
        "scripted": res.scripted, "prose": prose, "mechanics": mech,
        "rejected": res.error["message"] if res.error else None,
        "events": [e for e in res.events if e["type"] != "STATE_CHANGED"][:25],
        "memory": memory_retriever.retrieve(world, state, action.text or "", recent),
        "suggestions": [a["label"] for a in available_actions(world, state)][:4],
        "entities": entities, "player": {"name": state.player.name, "class": state.player.char_class,
                                         "hp": state.player.hp, "max_hp": state.player.max_hp},
    }


_DMG = re.compile(r"\b(\d+)\s+(?:points?\s+of\s+)?damage", re.I)
_BAD = re.compile(r"(https?://|<script|system prompt|ignore (all|previous) instructions)", re.I)


def validate_narration(raw: dict, world: dict, ctx: dict) -> NarrationResponse:
    """Reject malformed, unsafe, or state-contradicting model output."""
    resp = NarrationResponse.model_validate(raw)
    unknown = [e for e in resp.referenced_entities if e not in known_entity_ids(world)]
    if unknown:
        raise ValueError(f"unknown referenced entities: {unknown}")
    if _BAD.search(resp.narration):
        raise ValueError("narration contains disallowed content")
    allowed = {e["damage"] for e in ctx["events"] if e["type"] == "ATTACK_RESOLVED"}
    for m in _DMG.findall(resp.narration):
        if int(m) not in allowed:
            raise ValueError("narration states a damage value that does not match the engine")
    return resp


class GameMaster:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def narrate(self, world: dict, state: GameState, res: Resolution, action: ActionRequest, recent: list[str]) -> dict:
        ctx = build_context(world, state, res, action, recent)
        if res.error:   # rejections are explained by the engine itself; no model call needed
            out = NarrationResponse.model_validate(template_narration(ctx)).model_dump()
            out["source"], out["warning"], out["mechanics"] = "engine", None, []
            return out
        warning = None
        source = "mock" if self.provider.is_mock else "llm"
        try:
            resp = validate_narration(self.provider.narrate(ctx), world, ctx)
            out = resp.model_dump()
        except (ProviderError, ValidationError, ValueError) as e:
            warning = f"narration fallback used: {str(e)[:160]}"
            source = "fallback"
            out = NarrationResponse.model_validate(template_narration(ctx)).model_dump()
        out["source"], out["warning"], out["mechanics"] = source, warning, ctx["mechanics"]
        return out
