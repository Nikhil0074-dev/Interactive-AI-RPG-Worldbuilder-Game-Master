"""Shared helpers for the deterministic game engine."""
from __future__ import annotations

import random
from typing import Any

from ..data.content import ITEMS
from ..models.events import make_event
from ..models.state import GameState, LocationState, MemoryFact, ObjectState, Relationship


class ActionRejected(Exception):
    """Raised when an action fails validation. Never changes state."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def item_def(item_id: str) -> dict:
    if item_id not in ITEMS:
        raise ActionRejected("UNKNOWN_ITEM", f"Item '{item_id}' does not exist.")
    return ITEMS[item_id]


def attr_mod(state: GameState, attr: str) -> int:
    return (state.player.attributes.get(attr, 10) - 10) // 2


def d20(state: GameState) -> int:
    """Deterministic, seeded roll. The engine - never the LLM - rolls dice."""
    state.rng_counter += 1
    return random.Random(f"{state.rng_seed}:{state.rng_counter}").randint(1, 20)


def skill_check(state: GameState, attr: str, dc: int, label: str, events: list, bonus: int = 0) -> bool:
    roll = d20(state)
    mod = attr_mod(state, attr)
    total = roll + mod + bonus
    success = roll == 20 or (roll != 1 and total >= dc)
    events.append(make_event("SKILL_CHECK", attr=attr, roll=roll, modifier=mod + bonus, total=total, dc=dc,
                             success=success, label=label))
    return success


def loc_state(state: GameState, loc_id: str) -> LocationState:
    if loc_id not in state.locations:
        state.locations[loc_id] = LocationState()
    return state.locations[loc_id]


def init_location_state(world: dict, state: GameState) -> None:
    for lid, loc in world["locations"].items():
        ls = LocationState(ground=dict(loc.get("ground", {})))
        for obj in loc.get("objects", []):
            ls.objects[obj["id"]] = ObjectState(locked=bool(obj.get("locked", False)))
        state.locations[lid] = ls


def add_memory(state: GameState, text: str, entities: list[str] | None = None) -> None:
    if any(m.text == text for m in state.memory):
        return
    state.memory.append(MemoryFact(turn=state.turn, text=text, entities=entities or []))


def get_rel(state: GameState, npc_id: str) -> Relationship:
    if npc_id not in state.relationships:
        state.relationships[npc_id] = Relationship()
    return state.relationships[npc_id]


def set_flag(world: dict, state: GameState, flag: str, value: Any, events: list) -> None:
    if state.flags.get(flag) == value:
        return
    state.flags[flag] = value
    events.append(make_event("FLAG_SET", flag=flag, value=value))
    fact = world.get("flag_facts", {}).get(flag)
    if fact and value:
        add_memory(state, fact["text"], list(fact.get("npcs", [])))
        if fact.get("action"):
            for npc in fact.get("npcs", []):
                rel = get_rel(state, npc)
                if fact["action"] not in rel.known_player_actions:
                    rel.known_player_actions.append(fact["action"])


def quest_status(state: GameState, quest_id: str) -> str:
    q = state.quests.get(quest_id)
    return q.status if q else "LOCKED"


def check_requires(world: dict, state: GameState, req: dict | None, npc_id: str | None = None) -> bool:
    """Evaluate a declarative requirement block (used by dialogue, locations, quests)."""
    if not req:
        return True
    p = state.player
    flags = req.get("flags", {})
    if isinstance(flags, list):          # shorthand: all listed flags must be truthy
        flags = {f: True for f in flags}
    for flag, val in flags.items():
        if bool(state.flags.get(flag, False)) != val:
            return False
    if any(state.flags.get(f) for f in req.get("not_flags", [])):
        return False
    if req.get("any_flags") and not any(state.flags.get(f) for f in req["any_flags"]):
        return False
    for item, qty in req.get("items", {}).items():
        if p.inventory.get(item, 0) < qty:
            return False
    if p.gold < req.get("gold", 0):
        return False
    for qid, st in req.get("quest_status", {}).items():
        allowed = st if isinstance(st, list) else [st]
        if quest_status(state, qid) not in allowed:
            return False
    if "rel_min" in req and npc_id and get_rel(state, npc_id).score < req["rel_min"]:
        return False
    if p.level < req.get("level_min", 1):
        return False
    return True


def location_lock_reason(world: dict, state: GameState, loc_id: str) -> str | None:
    loc = world["locations"][loc_id]
    if loc.get("locked_flags") and not all(state.flags.get(f) for f in loc["locked_flags"]):
        return loc.get("locked_hint", "The way is blocked.")
    if loc.get("locked_any_flags") and not any(state.flags.get(f) for f in loc["locked_any_flags"]):
        return loc.get("locked_hint", "The way is blocked.")
    return None


def time_of_day(state: GameState) -> str:
    from ..data.content import TIMES_OF_DAY
    return TIMES_OF_DAY[(state.clock + 3) % 4]  # campaign begins at night
