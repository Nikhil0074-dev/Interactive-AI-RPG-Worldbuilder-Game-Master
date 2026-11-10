"""Typed game events. Every state change is described by an event with a defined schema."""
from __future__ import annotations

from typing import Any

EVENT_SCHEMAS: dict[str, list[str]] = {
    "STATE_CHANGED": ["from_state", "to_state"],
    "PLAYER_ENTERED_LOCATION": ["location_id", "first_visit"],
    "NPC_DIALOGUE_STARTED": ["npc_id"],
    "NPC_DIALOGUE_ENDED": ["npc_id"],
    "DIALOGUE_OPTION_CHOSEN": ["npc_id", "option_id"],
    "ITEM_ACQUIRED": ["item_id", "quantity", "source"],
    "ITEM_CONSUMED": ["item_id", "quantity"],
    "ITEM_EQUIPPED": ["item_id", "slot"],
    "ITEM_UNEQUIPPED": ["item_id", "slot"],
    "ITEM_DROPPED": ["item_id", "quantity"],
    "ITEM_GIVEN": ["item_id", "npc_id"],
    "ITEM_LEFT_BEHIND": ["item_id", "quantity"],
    "ITEM_PURCHASED": ["item_id", "quantity", "price"],
    "GOLD_CHANGED": ["amount", "gold_after"],
    "QUEST_AVAILABLE": ["quest_id"],
    "QUEST_STARTED": ["quest_id"],
    "QUEST_DECLINED": ["quest_id"],
    "QUEST_OBJECTIVE_COMPLETED": ["quest_id", "objective_id"],
    "QUEST_COMPLETED": ["quest_id", "outcome"],
    "QUEST_ABANDONED": ["quest_id"],
    "RELATIONSHIP_CHANGED": ["npc_id", "delta"],
    "FACTION_REP_CHANGED": ["faction_id", "delta"],
    "FLAG_SET": ["flag", "value"],
    "CHOICE_MADE": ["choice", "option"],
    "SKILL_CHECK": ["attr", "roll", "modifier", "total", "dc", "success", "label"],
    "OBJECT_EXAMINED": ["object_id"],
    "OBJECT_UNLOCKED": ["object_id", "method"],
    "OBJECT_OPENED": ["object_id"],
    "SEARCH_RESULT": ["found", "location_id"],
    "HIDDEN_FOUND": ["hidden_id", "location_id"],
    "REST_TAKEN": ["hp_restored", "mana_restored"],
    "COMBAT_STARTED": ["enemy_id", "player_first"],
    "ATTACK_RESOLVED": ["attacker_id", "target_id", "damage", "target_health_after", "hit", "critical"],
    "ABILITY_USED": ["ability_id", "user_id"],
    "STATUS_APPLIED": ["target_id", "status", "turns"],
    "HEALED": ["target_id", "amount", "hp_after"],
    "ENEMY_DEFEATED": ["enemy_id"],
    "PLAYER_DEFEATED": ["enemy_id"],
    "COMBAT_ENDED": ["result"],
    "XP_GAINED": ["amount", "xp_after"],
    "LEVEL_UP": ["level", "hp_gain", "mana_gain", "attribute"],
    "CUSTOM_ACTION_NOOP": ["text"],
    "ACTION_REJECTED": ["code", "message"],
}

# Which payload key identifies an event for quest-objective matching.
EVENT_TARGET_KEY: dict[str, str] = {
    "PLAYER_ENTERED_LOCATION": "location_id",
    "ITEM_ACQUIRED": "item_id",
    "ITEM_GIVEN": "item_id",
    "ENEMY_DEFEATED": "enemy_id",
    "NPC_DIALOGUE_STARTED": "npc_id",
    "CHOICE_MADE": "choice",
    "OBJECT_EXAMINED": "object_id",
    "FLAG_SET": "flag",
}


class EventSchemaError(ValueError):
    pass


def make_event(type_: str, **payload: Any) -> dict[str, Any]:
    schema = EVENT_SCHEMAS.get(type_)
    if schema is None:
        raise EventSchemaError(f"Unknown event type: {type_}")
    missing = [k for k in schema if k not in payload]
    if missing:
        raise EventSchemaError(f"Event {type_} missing fields: {missing}")
    return {"type": type_, **payload}


def validate_event(ev: dict[str, Any]) -> None:
    make_event(ev.get("type", ""), **{k: v for k, v in ev.items() if k != "type"})


def event_key(ev: dict[str, Any]) -> str | None:
    key = EVENT_TARGET_KEY.get(ev["type"])
    if key is None:
        return None
    return f'{ev["type"]}:{ev.get(key)}'
