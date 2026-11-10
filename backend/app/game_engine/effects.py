"""Declarative effect interpreter used by dialogue options and examinable objects."""
from __future__ import annotations

from ..models.events import make_event
from ..models.state import GameState
from . import inventory_engine as inv
from . import progression_engine as prog
from . import quest_engine
from .common import ActionRejected, get_rel, loc_state, set_flag


def buy_price(state: GameState, base: int, npc_id: str | None) -> int:
    trust = get_rel(state, npc_id).trust if npc_id else 0
    discount = min(max(trust, 0), 60) * base // 200   # up to 30% off for trusted customers
    return max(1, base - discount)


def apply_effects(world: dict, state: GameState, effects: list[dict], events: list) -> None:
    for fx in effects:
        op = fx["op"]
        if op == "set_flag":
            set_flag(world, state, fx["flag"], fx.get("value", True), events)
        elif op == "give_item":
            inv.give_item(state, fx["item"], fx.get("qty", 1), fx.get("source", "reward"), events)
        elif op == "take_item":
            inv.remove_item(state, fx["item"], fx.get("qty", 1))
        elif op == "give_to_npc":
            inv.remove_item(state, fx["item"], 1)
            events.append(make_event("ITEM_GIVEN", item_id=fx["item"], npc_id=fx["npc"]))
        elif op == "quest_start":
            quest_engine.start_quest(world, state, fx["quest"], events)
        elif op == "rel":
            rel = get_rel(state, fx["npc"])
            for k in ("score", "trust", "fear", "respect"):
                if fx.get(k):
                    setattr(rel, k, max(-100, min(100, getattr(rel, k) + fx[k])))
            events.append(make_event("RELATIONSHIP_CHANGED", npc_id=fx["npc"], delta=fx.get("score", 0)))
        elif op == "rep":
            state.faction_rep[fx["faction"]] = state.faction_rep.get(fx["faction"], 0) + fx["amount"]
            events.append(make_event("FACTION_REP_CHANGED", faction_id=fx["faction"], delta=fx["amount"]))
        elif op == "xp":
            prog.award_xp(state, fx["amount"], events)
        elif op == "gold":
            inv.change_gold(state, fx["amount"], events)
        elif op == "heal":
            inv.heal(state, fx["amount"], events)
        elif op == "unlock_object":
            for ls in state.locations.values():
                if fx["object"] in ls.objects:
                    ls.objects[fx["object"]].locked = False
                    events.append(make_event("OBJECT_UNLOCKED", object_id=fx["object"], method="story"))
        elif op == "choice":
            events.append(make_event("CHOICE_MADE", choice=fx["choice"], option=fx["option"]))
        elif op == "buy":
            price = buy_price(state, fx["price"], fx.get("npc"))
            inv.change_gold(state, -price, events)
            inv.give_item(state, fx["item"], fx.get("qty", 1), "purchase", events)
            events.append(make_event("ITEM_PURCHASED", item_id=fx["item"], quantity=fx.get("qty", 1), price=price))
        else:
            raise ActionRejected("BAD_EFFECT", f"Unknown effect op '{op}'.")
