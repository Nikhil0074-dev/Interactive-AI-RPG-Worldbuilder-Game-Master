"""Explicit finite state machine with guarded transitions."""
from __future__ import annotations

from ..models.events import make_event
from ..models.state import FSM_STATES, GameState

TRANSITIONS: dict[str, set[str]] = {
    "MAIN_MENU": {"WORLD_CREATION"},
    "WORLD_CREATION": {"CHARACTER_CREATION", "MAIN_MENU"},
    "CHARACTER_CREATION": {"EXPLORATION", "WORLD_CREATION"},
    "EXPLORATION": {"DIALOGUE", "COMBAT", "INVENTORY", "QUEST_LOG", "TRAVEL", "RESTING", "GAME_OVER", "MAIN_MENU"},
    "DIALOGUE": {"EXPLORATION"},
    "COMBAT": {"EXPLORATION", "GAME_OVER"},
    "INVENTORY": {"EXPLORATION"},
    "QUEST_LOG": {"EXPLORATION"},
    "TRAVEL": {"EXPLORATION", "COMBAT"},
    "RESTING": {"EXPLORATION"},
    "GAME_OVER": {"MAIN_MENU"},
}

ALLOWED_ACTIONS: dict[str, set[str]] = {
    "EXPLORATION": {"move", "examine", "take", "open", "search", "talk", "use_item", "equip", "unequip", "drop",
                    "rest", "open_inventory", "open_quest_log", "abandon_quest"},
    "DIALOGUE": {"dialogue_choice", "end_dialogue"},
    "COMBAT": {"attack", "ability", "flee", "use_item"},
    "INVENTORY": {"use_item", "equip", "unequip", "drop", "close_menu"},
    "QUEST_LOG": {"abandon_quest", "close_menu"},
}

assert set(TRANSITIONS) == set(FSM_STATES)


class InvalidTransition(Exception):
    pass


def can_transition(src: str, dst: str) -> bool:
    return dst in TRANSITIONS.get(src, set())


def transition(state: GameState, dst: str, events: list | None = None) -> None:
    if not can_transition(state.fsm_state, dst):
        raise InvalidTransition(f"Cannot move from {state.fsm_state} to {dst}.")
    if events is not None:
        events.append(make_event("STATE_CHANGED", from_state=state.fsm_state, to_state=dst))
    state.fsm_state = dst


def action_allowed(state: GameState, action_type: str) -> bool:
    return action_type in ALLOWED_ACTIONS.get(state.fsm_state, set())
