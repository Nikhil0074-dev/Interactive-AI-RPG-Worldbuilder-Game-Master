"""Create the initial GameState for a new campaign character."""
from __future__ import annotations

import secrets

from ..data.content import CLASSES, ITEMS
from ..models.events import make_event
from ..models.state import ATTRIBUTES, GameState, Player
from . import quest_engine
from .common import ActionRejected, init_location_state, loc_state
from .event_processor import process_events


def create_initial_state(config: dict, seed: int | None = None) -> GameState:
    return GameState(fsm_state="WORLD_CREATION", rng_seed=seed if seed is not None else secrets.randbits(31),
                     difficulty=config.get("difficulty", "normal"), combat_enabled=bool(config.get("combat_enabled", True)))


def start_adventure(world: dict, state: GameState, name: str, char_class: str, background: str = "",
                    appearance: str = "", bonus_attribute: str | None = None) -> tuple[GameState, list[dict]]:
    if state.fsm_state != "CHARACTER_CREATION":
        raise ActionRejected("BAD_STATE", "Character creation is not available in this state.")
    name = (name or "").strip()
    if not 1 <= len(name) <= 40:
        raise ActionRejected("BAD_NAME", "Character name must be 1-40 characters.")
    if char_class not in CLASSES:
        raise ActionRejected("BAD_CLASS", f"Unknown class '{char_class}'.")
    if bonus_attribute is not None and bonus_attribute not in ATTRIBUTES:
        raise ActionRejected("BAD_ATTRIBUTE", f"Unknown attribute '{bonus_attribute}'.")
    cls = CLASSES[char_class]
    attrs = dict(cls["attributes"])
    if bonus_attribute:
        attrs[bonus_attribute] += 2
    con_mod = (attrs["constitution"] - 10) // 2
    prim_mod = max(0, (attrs[cls["primary"]] - 10) // 2)
    max_hp = 20 + cls["hit_die"] + 2 * con_mod
    max_mana = cls["mana"] + 2 * prim_mod
    st = state.model_copy(deep=True)
    st.player = Player(name=name, char_class=char_class, background=background[:200], appearance=appearance[:200],
                       hp=max_hp, max_hp=max_hp, mana=max_mana, max_mana=max_mana, attributes=attrs,
                       abilities=list(cls["abilities"]), gold=30 + (10 if char_class == "rogue" else 0))
    inventory = dict(cls["items"])
    for slot, item in cls["equipment"].items():
        inventory[item] = inventory.get(item, 0) + 1
        st.player.equipped[ITEMS[item]["slot"]] = item
    st.player.inventory = inventory
    st.seen_items = list(inventory)
    init_location_state(world, st)
    st.location_id = world["start_location_id"]
    ls = loc_state(st, st.location_id)
    ls.visited = ls.discovered = True
    for c in world["locations"][st.location_id]["connections"]:
        loc_state(st, c).discovered = True
    st.fsm_state = "EXPLORATION"
    quest_engine.ensure_quests(world, st)
    events = [make_event("STATE_CHANGED", from_state="CHARACTER_CREATION", to_state="EXPLORATION"),
              make_event("PLAYER_ENTERED_LOCATION", location_id=st.location_id, first_visit=True)]
    quest_engine.refresh_availability(world, st, events)
    process_events(world, st, events)
    return st, events
