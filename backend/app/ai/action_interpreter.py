"""Step 1 of the Game Master pipeline: free text -> structured ActionRequest. Output is strictly validated."""
from __future__ import annotations

import re

from ..data.content import ABILITIES, ITEMS
from ..game_engine.action_resolver import visible_options
from ..game_engine.common import loc_state
from ..models.state import ActionRequest, GameState
from .provider import LLMProvider, ProviderError

INTERPRETABLE = {"move", "examine", "take", "open", "search", "talk", "attack", "ability", "flee", "use_item", "equip",
                 "unequip", "drop", "rest", "end_dialogue", "dialogue_choice"}
_CTRL = re.compile(r"[\x00-\x1f\x7f]+")


def sanitize_text(text: str, max_chars: int = 300) -> str:
    return _CTRL.sub(" ", text or "").strip()[:max_chars]


def build_candidates(world: dict, state: GameState) -> dict:
    loc = world["locations"][state.location_id]
    ls = loc_state(state, state.location_id)
    return {
        "fsm_state": state.fsm_state,
        "exits": [{"id": c, "name": world["locations"][c]["name"], "extra": " ".join(world["locations"][c].get("visual_features", [])) + " " + world["locations"][c]["description"]}
                  for c in loc["connections"]],
        "npcs": [{"id": n, "name": world["npcs"][n]["name"], "extra": world["npcs"][n]["role"]} for n in loc.get("npcs", [])],
        "objects": [{"id": o["id"], "name": o["name"], "extra": o["kind"]} for o in loc.get("objects", [])],
        "ground": [{"id": i, "name": ITEMS[i]["name"]} for i in ls.ground],
        "inventory": [{"id": i, "name": ITEMS[i]["name"]} for i in state.player.inventory],
        "abilities": [{"id": a, "name": ABILITIES[a]["name"]} for a in state.player.abilities],
        "options": visible_options(world, state, state.dialogue_npc) if state.dialogue_npc else [],
    }


def _valid_id(value, cands: list[dict]) -> bool:
    return value is None or any(c["id"] == value for c in cands)


def interpret(provider: LLMProvider, world: dict, state: GameState, text: str, action_id: str,
              max_chars: int = 300) -> tuple[ActionRequest, str]:
    """Return (ActionRequest, source). Anything the model returns that is not a known, in-scene id becomes a no-op."""
    clean = sanitize_text(text, max_chars)
    noop = ActionRequest(action_id=action_id, type="custom", text=clean)
    if not clean:
        return noop, "empty"
    cands = build_candidates(world, state)
    try:
        raw = provider.interpret_action(clean, cands)
    except ProviderError:
        return noop, "provider_error"
    kind = raw.get("type")
    if kind not in INTERPRETABLE:
        return noop, "unknown"
    tid, iid, oid, aid = raw.get("target_id"), raw.get("item_id"), raw.get("option_id"), raw.get("ability_id")
    scene_targets = cands["exits"] + cands["npcs"] + cands["objects"] + cands["ground"]
    ok = (_valid_id(tid, scene_targets) and _valid_id(iid, cands["inventory"] + cands["ground"]) and
          _valid_id(oid, cands["options"]) and _valid_id(aid, cands["abilities"]))
    if not ok:
        return noop, "invalid_reference"
    return ActionRequest(action_id=action_id, type=kind, target_id=tid, item_id=iid, option_id=oid, ability_id=aid, text=clean), "interpreted"
