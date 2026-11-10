"""State invariants that must hold after every action. Used by fuzz tests and the evaluation script."""
from __future__ import annotations

from ..data.content import ITEMS
from ..models.state import FSM_STATES, GameState
from . import inventory_engine as inv
from . import progression_engine as prog


def check_invariants(world: dict, s: GameState) -> list[str]:
    errs: list[str] = []
    if s.fsm_state not in FSM_STATES:
        errs.append("invalid fsm state")
    p = s.player
    if p is None:
        return errs
    if not 0 <= p.hp <= p.max_hp:
        errs.append(f"hp out of range {p.hp}/{p.max_hp}")
    if p.hp == 0 and s.fsm_state != "GAME_OVER":
        errs.append("dead but not GAME_OVER")
    if s.fsm_state == "GAME_OVER" and p.hp != 0:
        errs.append("GAME_OVER with hp > 0")
    if not 0 <= p.mana <= p.max_mana:
        errs.append("mana out of range")
    if p.gold < 0:
        errs.append("negative gold")
    for i, q in p.inventory.items():
        if i not in ITEMS or q <= 0:
            errs.append(f"bad inventory entry {i}:{q}")
    if inv.carried_weight(s) > inv.capacity(s) + 1e-9:
        errs.append("over capacity")
    for slot, i in p.equipped.items():
        if i and (i not in p.inventory or ITEMS[i]["slot"] != slot):
            errs.append(f"bad equipment {slot}:{i}")
    if (s.combat is not None) != (s.fsm_state == "COMBAT"):
        errs.append("combat state mismatch")
    if s.combat and not 0 < s.combat.enemy_hp <= s.combat.enemy_max_hp:
        errs.append("enemy hp out of range")
    if (s.dialogue_npc is not None) != (s.fsm_state == "DIALOGUE"):
        errs.append("dialogue state mismatch")
    if s.location_id not in world["locations"]:
        errs.append("unknown location")
    for lid, ls in s.locations.items():
        for i, q in ls.ground.items():
            if q <= 0 or i not in ITEMS:
                errs.append(f"bad ground item {lid}:{i}")
    if p.xp < prog.xp_for_level(p.level):
        errs.append("xp below level threshold")
    for qid, q in s.quests.items():
        if len(set(q.completed_objectives)) != len(q.completed_objectives):
            errs.append(f"duplicate objectives {qid}")
        if q.status == "COMPLETED":
            req = [o["id"] for o in world["quests"][qid]["objectives"] if not o.get("optional")]
            if not all(r in q.completed_objectives for r in req):
                errs.append(f"{qid} completed without all objectives")
    if sum(bool(s.flags.get(f)) for f in ("clapper_sold", "clapper_returned", "clapper_kept")) > 1:
        errs.append("mutually exclusive outcomes both set")
    return errs
