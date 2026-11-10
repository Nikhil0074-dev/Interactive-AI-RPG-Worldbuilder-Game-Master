"""Processes the event queue: quest objectives, memory, and availability refresh."""
from __future__ import annotations

from ..models.events import event_key, validate_event
from ..models.state import GameState
from . import quest_engine
from .common import add_memory

MEMORY_EVENTS = {"ENEMY_DEFEATED", "QUEST_COMPLETED", "LEVEL_UP"}


def process_events(world: dict, state: GameState, events: list) -> list:
    i = 0
    guard = 0
    while i < len(events):
        ev = events[i]
        validate_event(ev)
        key = event_key(ev)
        if key and key not in state.seen_events:
            state.seen_events.append(key)
        if ev["type"] == "ENEMY_DEFEATED":
            if ev["enemy_id"] not in state.defeated_enemies:
                state.defeated_enemies.append(ev["enemy_id"])
            add_memory(state, f'The player defeated {ev["enemy_id"].replace("enemy_", "").replace("_", " ")}.', [ev["enemy_id"]])
        if ev["type"] == "NPC_DIALOGUE_STARTED" and ev["npc_id"] not in state.met_npcs:
            state.met_npcs.append(ev["npc_id"])
        quest_engine.on_event(world, state, ev, events)
        i += 1
        guard += 1
        if guard > 500:
            raise RuntimeError("Event processing loop exceeded safety limit")
        if i == len(events):
            quest_engine.refresh_availability(world, state, events)
    return events
