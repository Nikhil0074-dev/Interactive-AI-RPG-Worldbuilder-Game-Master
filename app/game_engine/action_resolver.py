"""Deterministic action resolution.

Pipeline: validate (FSM + rules) -> resolve (dice by engine) -> apply state -> emit typed events -> process events.
The LLM never touches this path; it only narrates the returned events.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..data.content import ENEMIES, ITEMS
from ..models.events import make_event
from ..models.state import ActionRequest, GameState
from . import combat_engine as combat
from . import inventory_engine as inv
from . import progression_engine as prog
from . import quest_engine
from . import state_machine as fsm
from .common import (ActionRejected, check_requires, get_rel, item_def, loc_state, location_lock_reason,
                     set_flag, skill_check, attr_mod)
from .effects import apply_effects, buy_price
from .event_processor import process_events


@dataclass
class Resolution:
    state: GameState
    events: list[dict]
    status: str                      # "completed" | "rejected"
    scripted: list[str] = field(default_factory=list)   # authored text the narrator may use
    error: dict | None = None


def _loc(world: dict, state: GameState) -> dict:
    return world["locations"][state.location_id]


# ---------------------------------------------------------------- dialogue helpers
def greeting_text(world: dict, state: GameState, npc_id: str) -> str:
    for g in world["npcs"][npc_id]["greetings"]:
        if check_requires(world, state, g.get("requires"), npc_id):
            return g["text"]
    return ""


def visible_options(world: dict, state: GameState, npc_id: str) -> list[dict]:
    out = []
    for o in world["npcs"][npc_id]["options"]:
        if o.get("once") and state.flags.get(f"dlg:{npc_id}:{o['id']}"):
            continue
        if not check_requires(world, state, o.get("requires"), npc_id):
            continue
        text = o["text"]
        if "{price}" in text:
            eff = next((e for e in o.get("effects", []) if e["op"] == "buy"), None)
            if eff:
                text = text.replace("{price}", str(buy_price(state, eff["price"], npc_id)))
        out.append({"id": o["id"], "text": text})
    return out


# ---------------------------------------------------------------- handlers
def h_move(world, st, a, ev, sc):
    loc = _loc(world, st)
    dest = a.target_id
    if dest not in loc["connections"]:
        raise ActionRejected("NOT_REACHABLE", "You cannot travel there from here.")
    reason = location_lock_reason(world, st, dest)
    if reason:
        raise ActionRejected("LOCKED", reason)
    fsm.transition(st, "TRAVEL", ev)
    st.previous_location_id = st.location_id
    st.location_id = dest
    st.clock += 1
    ls = loc_state(st, dest)
    first = not ls.visited
    ls.visited = ls.discovered = True
    dloc = world["locations"][dest]
    for c in dloc["connections"]:
        loc_state(st, c).discovered = True
    ev.append(make_event("PLAYER_ENTERED_LOCATION", location_id=dest, first_visit=first))
    sc.append(dloc["description"] if first else f"You return to {dloc['name']}.")
    if first:
        prog.award_xp(st, 15, ev)
    enc = dloc.get("encounter")
    if enc and enc["trigger"] == "on_enter" and not ls.encounter_done and st.combat_enabled:
        sc.append(enc["text"])
        combat.start_combat(world, st, enc["enemy"], ev)
    else:
        fsm.transition(st, "EXPLORATION", ev)


def h_examine(world, st, a, ev, sc):
    loc = _loc(world, st)
    t = a.target_id or a.item_id
    if not t or t == st.location_id:
        sc.append(loc["description"])
        return
    for obj in loc.get("objects", []):
        if obj["id"] == t:
            sc.append(obj["description"])
            ev.append(make_event("OBJECT_EXAMINED", object_id=t))
            key = f"examined:{t}"
            if obj.get("on_examine") and not st.flags.get(key):
                st.flags[key] = True
                apply_effects(world, st, obj["on_examine"], ev)
            return
    if t in loc.get("npcs", []):
        n = world["npcs"][t]
        sc.append(f"{n['name']}, {n['role']}. {n['appearance']}")
        return
    if t in loc_state(st, st.location_id).ground or t in st.player.inventory:
        d = item_def(t)
        sc.append(f"{d['name']} ({d['rarity']} {d['category']}): {d['description']}")
        return
    raise ActionRejected("NOT_FOUND", "You see nothing like that here.")


def h_take(world, st, a, ev, sc):
    t = a.item_id or a.target_id
    ground = loc_state(st, st.location_id).ground
    if not t or ground.get(t, 0) < 1:
        raise ActionRejected("NOT_HERE", "There is nothing like that here to take.")
    d = item_def(t)
    inv.give_item(st, t, 1, "ground", ev, overflow_to_ground=False)
    ground[t] -= 1
    if ground[t] <= 0:
        del ground[t]
    sc.append(f"You pick up the {d['name']}.")


def h_open(world, st, a, ev, sc):
    loc = _loc(world, st)
    obj = next((o for o in loc.get("objects", []) if o["id"] == a.target_id), None)
    if obj is None:
        raise ActionRejected("NOT_FOUND", "There is nothing like that here to open.")
    if obj["kind"] != "chest":
        raise ActionRejected("NOT_OPENABLE", f"The {obj['name']} cannot be opened.")
    os_ = loc_state(st, st.location_id).objects[obj["id"]]
    if os_.opened:
        raise ActionRejected("ALREADY_OPEN", f"The {obj['name']} is already open and empty.")
    if os_.locked:
        p = st.player
        if p.inventory.get(obj.get("key_item", ""), 0) > 0:
            os_.locked = False
            ev.append(make_event("OBJECT_UNLOCKED", object_id=obj["id"], method="key"))
            sc.append(f"The brass key turns with a click.")
        elif p.inventory.get("item_lockpicks", 0) > 0:
            bonus = ITEMS["item_lockpicks"]["properties"]["bonus"] + (2 if p.char_class == "rogue" else 0)
            if skill_check(st, "dexterity", obj["lock_dc"], "Pick the lock", ev, bonus=bonus):
                os_.locked = False
                ev.append(make_event("OBJECT_UNLOCKED", object_id=obj["id"], method="lockpick"))
                sc.append("The tumblers surrender one by one.")
            else:
                sc.append("The lock holds firm against your picks.")
                return
        else:
            raise ActionRejected("LOCKED", f"The {obj['name']} is locked. You need a key or lockpicks.")
    os_.opened = True
    ev.append(make_event("OBJECT_OPENED", object_id=obj["id"]))
    sc.append(f"The {obj['name']} swings open.")
    c = obj.get("contents", {})
    if c.get("gold"):
        inv.change_gold(st, c["gold"], ev)
    for item, qty in c.get("items", {}).items():
        inv.give_item(st, item, qty, "chest", ev)


def h_search(world, st, a, ev, sc):
    loc = _loc(world, st)
    ls = loc_state(st, st.location_id)
    remaining = [h for h in loc.get("hidden", []) if h["id"] not in ls.found_hidden]
    if not remaining:
        raise ActionRejected("NOTHING_MORE", "You have searched thoroughly and find nothing more.")
    low = min(h["dc"] for h in remaining)
    skill_check(st, "wisdom", low, "Search the area", ev)
    roll, total = ev[-1]["roll"], ev[-1]["total"]
    found_any = False
    for h in sorted(remaining, key=lambda x: x["dc"]):
        if roll == 20 or (roll != 1 and total >= h["dc"]):
            found_any = True
            ls.found_hidden.append(h["id"])
            ev.append(make_event("HIDDEN_FOUND", hidden_id=h["id"], location_id=st.location_id))
            sc.append(h["text"])
            if "item" in h:
                ls.ground[h["item"]] = ls.ground.get(h["item"], 0) + h.get("qty", 1)
            if "flag" in h:
                set_flag(world, st, h["flag"], True, ev)
    ev.append(make_event("SEARCH_RESULT", found=found_any, location_id=st.location_id))
    if not found_any:
        sc.append("You search carefully but find nothing of note.")


def h_talk(world, st, a, ev, sc):
    loc = _loc(world, st)
    if a.target_id not in loc.get("npcs", []):
        raise ActionRejected("NOT_HERE", "There is no one like that here.")
    fsm.transition(st, "DIALOGUE", ev)
    st.dialogue_npc = a.target_id
    ev.append(make_event("NPC_DIALOGUE_STARTED", npc_id=a.target_id))
    sc.append(greeting_text(world, st, a.target_id))


def h_dialogue_choice(world, st, a, ev, sc):
    npc_id = st.dialogue_npc
    opt = next((o for o in world["npcs"][npc_id]["options"] if o["id"] == a.option_id), None)
    if opt is None or a.option_id not in [v["id"] for v in visible_options(world, st, npc_id)]:
        raise ActionRejected("OPTION_UNAVAILABLE", "That dialogue option is not available.")
    ev.append(make_event("DIALOGUE_OPTION_CHOSEN", npc_id=npc_id, option_id=opt["id"]))
    if opt.get("once"):
        st.flags[f"dlg:{npc_id}:{opt['id']}"] = True
    if "check" in opt:
        c = opt["check"]
        ok = skill_check(st, c["attr"], c["dc"], c["label"], ev)
        sc.append(opt["reply_success"] if ok else opt["reply_fail"])
        apply_effects(world, st, opt["on_success"] if ok else opt["on_fail"], ev)
    else:
        sc.append(opt["reply"])
        apply_effects(world, st, opt.get("effects", []), ev)
    if opt.get("ends_dialogue"):
        fsm.transition(st, "EXPLORATION", ev)
        ev.append(make_event("NPC_DIALOGUE_ENDED", npc_id=npc_id))
        st.dialogue_npc = None


def h_end_dialogue(world, st, a, ev, sc):
    npc = st.dialogue_npc
    fsm.transition(st, "EXPLORATION", ev)
    ev.append(make_event("NPC_DIALOGUE_ENDED", npc_id=npc))
    st.dialogue_npc = None


def h_attack(world, st, a, ev, sc):
    combat.player_attack(world, st, ev)


def h_ability(world, st, a, ev, sc):
    combat.player_ability(world, st, a.ability_id or "", ev)


def h_flee(world, st, a, ev, sc):
    combat.player_flee(world, st, ev)


def h_use_item(world, st, a, ev, sc):
    if not a.item_id:
        raise ActionRejected("MISSING_ITEM", "Choose an item to use.")
    if st.fsm_state == "COMBAT":
        combat.player_use_item(world, st, a.item_id, ev)
    else:
        inv.use_item(st, a.item_id, ev)


def h_equip(world, st, a, ev, sc):
    inv.equip(st, a.item_id or "", ev)


def h_unequip(world, st, a, ev, sc):
    inv.unequip(st, a.item_id or "", ev)


def h_drop(world, st, a, ev, sc):
    inv.drop(st, a.item_id or "", ev)


def h_rest(world, st, a, ev, sc):
    if not _loc(world, st).get("safe"):
        raise ActionRejected("NOT_SAFE", "It is not safe to rest here.")
    p = st.player
    if p.hp >= p.max_hp and p.mana >= p.max_mana:
        raise ActionRejected("ALREADY_FULL", "You are already fully rested.")
    fsm.transition(st, "RESTING", ev)
    hp, mp = p.max_hp - p.hp, p.max_mana - p.mana
    p.hp, p.mana = p.max_hp, p.max_mana
    st.clock += 2
    ev.append(make_event("REST_TAKEN", hp_restored=hp, mana_restored=mp))
    fsm.transition(st, "EXPLORATION", ev)


def h_open_inventory(world, st, a, ev, sc):
    fsm.transition(st, "INVENTORY", ev)


def h_open_quest_log(world, st, a, ev, sc):
    fsm.transition(st, "QUEST_LOG", ev)


def h_close_menu(world, st, a, ev, sc):
    fsm.transition(st, "EXPLORATION", ev)


def h_abandon(world, st, a, ev, sc):
    quest_engine.abandon_quest(world, st, a.target_id or "", ev)


HANDLERS = {"move": h_move, "examine": h_examine, "take": h_take, "open": h_open, "search": h_search, "talk": h_talk,
            "dialogue_choice": h_dialogue_choice, "end_dialogue": h_end_dialogue, "attack": h_attack,
            "ability": h_ability, "flee": h_flee, "use_item": h_use_item, "equip": h_equip, "unequip": h_unequip,
            "drop": h_drop, "rest": h_rest, "open_inventory": h_open_inventory, "open_quest_log": h_open_quest_log,
            "close_menu": h_close_menu, "abandon_quest": h_abandon}


MENU_ACTIONS = {"open_inventory", "open_quest_log", "close_menu"}


def resolve(world: dict, state: GameState, action: ActionRequest) -> Resolution:
    """Resolve one action against a *copy* of the state. Rejections never change state."""
    st = state.model_copy(deep=True)
    ev: list[dict] = []
    sc: list[str] = []
    try:
        if st.player is None or st.fsm_state in ("MAIN_MENU", "WORLD_CREATION", "CHARACTER_CREATION"):
            raise ActionRejected("NOT_IN_GAME", "The adventure has not started yet.")
        if st.fsm_state == "GAME_OVER":
            raise ActionRejected("GAME_OVER", "Your character has fallen. Load a save or start anew.")
        if action.type == "custom":
            ev.append(make_event("CUSTOM_ACTION_NOOP", text=(action.text or "")[:300]))
            sc.append("Nothing mechanical comes of it; the world carries on.")
        else:
            if not fsm.action_allowed(st, action.type):
                raise ActionRejected("INVALID_STATE", f"You cannot do that while in {st.fsm_state.lower()} mode.")
            HANDLERS[action.type](world, st, action, ev, sc)
        if action.type not in MENU_ACTIONS:
            st.turn += 1
        quest_engine.refresh_availability(world, st, ev)
        process_events(world, st, ev)
        return Resolution(st, ev, "completed", sc)
    except (ActionRejected, fsm.InvalidTransition) as e:
        code = getattr(e, "code", "INVALID_TRANSITION")
        msg = getattr(e, "message", str(e))
        return Resolution(state.model_copy(deep=True), [make_event("ACTION_REJECTED", code=code, message=msg)],
                          "rejected", [], {"code": code, "message": msg})
