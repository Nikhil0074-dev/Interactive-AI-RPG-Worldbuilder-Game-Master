"""Read-model builders: turn (world, state) into UI-ready views. Pure and side-effect free."""
from __future__ import annotations

from ..data.content import ABILITIES, ATTR_SHORT, CLASSES, ENEMIES, ITEMS
from ..models.state import GameState
from . import combat_engine as combat
from . import inventory_engine as inv
from . import progression_engine as prog
from .action_resolver import greeting_text, visible_options
from .common import check_requires, get_rel, loc_state, location_lock_reason, time_of_day
from .effects import buy_price


def _act(label: str, category: str, **action) -> dict:
    key = ":".join(str(v) for v in action.values() if v)
    return {"id": key, "label": label, "category": category, "action": action}


def exits_view(world: dict, state: GameState) -> list[dict]:
    loc = world["locations"][state.location_id]
    out = []
    for cid in loc["connections"]:
        reason = location_lock_reason(world, state, cid)
        out.append({"id": cid, "name": world["locations"][cid]["name"], "locked": reason is not None, "reason": reason,
                    "visited": loc_state(state, cid).visited})
    return out


def available_actions(world: dict, state: GameState) -> list[dict]:
    s = state.fsm_state
    acts: list[dict] = []
    if state.player is None:
        return acts
    loc = world["locations"][state.location_id]
    ls = loc_state(state, state.location_id)
    if s == "EXPLORATION":
        for e in exits_view(world, state):
            if not e["locked"]:
                acts.append(_act(f"Travel to {e['name']}", "travel", type="move", target_id=e["id"]))
        for n in loc.get("npcs", []):
            acts.append(_act(f"Speak to {world['npcs'][n]['name']}", "talk", type="talk", target_id=n))
        for o in loc.get("objects", []):
            if o["kind"] == "chest" and not ls.objects[o["id"]].opened:
                acts.append(_act(f"Open the {o['name']}" if not ls.objects[o["id"]].locked else f"Inspect the {o['name']} lock",
                                 "interact", type="open", target_id=o["id"]))
            else:
                acts.append(_act(f"Examine {o['name']}", "examine", type="examine", target_id=o["id"]))
        for item in ls.ground:
            acts.append(_act(f"Take {ITEMS[item]['name']}", "take", type="take", item_id=item))
        if any(h["id"] not in ls.found_hidden for h in loc.get("hidden", [])):
            acts.append(_act("Search the area", "search", type="search"))
        if loc.get("safe") and (state.player.hp < state.player.max_hp or state.player.mana < state.player.max_mana):
            acts.append(_act("Rest and recover", "rest", type="rest"))
        acts.append(_act("Look around", "examine", type="examine"))
    elif s == "DIALOGUE":
        for o in visible_options(world, state, state.dialogue_npc):
            acts.append(_act(o["text"], "dialogue", type="dialogue_choice", option_id=o["id"]))
        acts.append(_act("End conversation", "dialogue", type="end_dialogue"))
    elif s == "COMBAT":
        acts.append(_act("Attack", "combat", type="attack"))
        for ab in state.player.abilities:
            d = ABILITIES[ab]
            acts.append({**_act(f"{d['name']} ({d['mana']} mana)", "combat", type="ability", ability_id=ab),
                         "enabled": state.player.mana >= d["mana"]})
        for it, q in state.player.inventory.items():
            if ITEMS[it]["category"] == "consumable":
                acts.append(_act(f"Use {ITEMS[it]['name']} (x{q})", "combat", type="use_item", item_id=it))
        acts.append(_act("Flee", "combat", type="flee"))
    return acts


def dialogue_view(world: dict, state: GameState) -> dict | None:
    if state.fsm_state != "DIALOGUE" or not state.dialogue_npc:
        return None
    n = world["npcs"][state.dialogue_npc]
    return {"npc_id": n["id"], "npc_name": n["name"], "role": n["role"], "greeting": greeting_text(world, state, n["id"]),
            "options": visible_options(world, state, n["id"])}


def combat_view(state: GameState) -> dict | None:
    c = state.combat
    if not c:
        return None
    e = ENEMIES[c.enemy_id]
    return {"enemy_id": c.enemy_id, "name": e["name"], "description": e["description"], "hp": c.enemy_hp, "max_hp": c.enemy_max_hp,
            "statuses": c.enemy_statuses, "round": c.round, "player_first": c.player_first}


def audio_view(world: dict, state: GameState) -> dict:
    loc = world["locations"][state.location_id]
    mood = "tense" if state.fsm_state == "COMBAT" else loc["mood"]
    profile = "combat" if state.fsm_state == "COMBAT" else loc.get("audio_profile", "default")
    return {"profile": profile, "mood": mood, "weather": loc["weather"], "time_of_day": time_of_day(state),
            "location_type": loc["biome"]}


def scene_view(world: dict, state: GameState) -> dict:
    if state.player is None or not state.location_id:
        return {"fsm_state": state.fsm_state}
    loc = world["locations"][state.location_id]
    ls = loc_state(state, state.location_id)
    return {
        "fsm_state": state.fsm_state, "turn": state.turn, "time_of_day": time_of_day(state),
        "location": {k: loc[k] for k in ("id", "name", "description", "biome", "weather", "mood", "safe", "visual_features")},
        "exits": exits_view(world, state),
        "npcs": [{"id": n, "name": world["npcs"][n]["name"], "role": world["npcs"][n]["role"],
                  "relationship": get_rel(state, n).model_dump() if n in state.relationships else None}
                 for n in loc.get("npcs", [])],
        "objects": [{"id": o["id"], "name": o["name"], "kind": o["kind"], "locked": ls.objects[o["id"]].locked,
                     "opened": ls.objects[o["id"]].opened} for o in loc.get("objects", [])],
        "ground_items": [{"id": i, "name": ITEMS[i]["name"], "quantity": q} for i, q in ls.ground.items()],
        "dialogue": dialogue_view(world, state), "combat": combat_view(state),
        "available_actions": available_actions(world, state), "audio": audio_view(world, state),
    }


def player_view(state: GameState) -> dict | None:
    p = state.player
    if not p:
        return None
    cls = CLASSES[p.char_class]
    return {
        **p.model_dump(), "class_name": cls["name"], "xp_next": prog.xp_for_level(p.level + 1), "xp_current_level": prog.xp_for_level(p.level),
        "armor_class": combat.player_ac(state), "defense": combat.player_defense(state),
        "attribute_mods": {a: (v - 10) // 2 for a, v in p.attributes.items()},
        "capacity": inv.capacity(state), "weight": inv.carried_weight(state),
        "ability_details": [{"id": a, **ABILITIES[a]} for a in p.abilities],
        "equipment_details": {s: (ITEMS[i] if i else None) for s, i in p.equipped.items()},
    }


def inventory_view(state: GameState) -> dict:
    p = state.player
    items = []
    for iid, q in p.inventory.items():
        d = ITEMS[iid]
        equipped = p.equipped.get(d.get("slot")) == iid if d.get("slot") else False
        acts = []
        if d["category"] == "consumable":
            acts.append("use")
        if d.get("slot"):
            acts.append("unequip" if equipped else "equip")
        if not d["properties"].get("quest"):
            acts.append("drop")
        items.append({**d, "quantity": q, "equipped": equipped, "actions": acts})
    return {"items": items, "gold": p.gold, "weight": inv.carried_weight(state), "capacity": inv.capacity(state),
            "equipped": p.equipped}


def quests_view(world: dict, state: GameState) -> list[dict]:
    out = []
    for qid, q in world["quests"].items():
        pr = state.quests.get(qid)
        if not pr or pr.status == "LOCKED":
            continue
        out.append({"id": qid, "title": q["title"], "description": q["description"], "category": q["category"], "status": pr.status,
                    "giver": q.get("giver"), "outcome": pr.outcome,
                    "outcome_text": next((o["text"] for o in q.get("outcomes", []) if o["id"] == pr.outcome), None),
                    "objectives": [{"id": o["id"], "text": o["text"], "done": o["id"] in pr.completed_objectives,
                                    "optional": bool(o.get("optional"))} for o in q["objectives"]],
                    "rewards": q.get("rewards", {})})
    order = {"ACTIVE": 0, "AVAILABLE": 1, "COMPLETED": 2, "FAILED": 3, "ABANDONED": 4}
    return sorted(out, key=lambda x: order.get(x["status"], 9))


def codex_view(world: dict, state: GameState) -> dict:
    locs = [{"id": lid, "name": world["locations"][lid]["name"], "visited": ls.visited,
             "description": world["locations"][lid]["description"] if ls.visited else "You have heard of this place, but never seen it."}
            for lid, ls in state.locations.items() if ls.discovered]
    npcs = [{"id": n, "name": world["npcs"][n]["name"], "role": world["npcs"][n]["role"],
             "faction": world["npcs"][n]["faction_id"], "appearance": world["npcs"][n]["appearance"],
             "relationship": get_rel(state, n).model_dump()} for n in state.met_npcs]
    known_f = {world["npcs"][n]["faction_id"] for n in state.met_npcs} | {f for f, v in state.faction_rep.items() if v}
    factions = [{**f, "reputation": state.faction_rep.get(f["id"], 0)} for f in world["factions"] if f["id"] in known_f]
    creatures = [{"id": e, "name": ENEMIES[e]["name"], "description": ENEMIES[e]["description"]} for e in state.defeated_enemies]
    artifacts = [{"id": i, "name": ITEMS[i]["name"], "description": ITEMS[i]["description"], "rarity": ITEMS[i]["rarity"]}
                 for i in state.seen_items if ITEMS[i]["rarity"] in ("rare", "legendary", "uncommon")]
    lore = [l for l in world["lore"] if not l.get("requires_flag") or state.flags.get(l["requires_flag"])]
    return {"locations": locs, "characters": npcs, "factions": factions, "creatures": creatures, "artifacts": artifacts,
            "lore": lore, "campaign_memory": [m.model_dump() for m in state.memory]}


def shop_price_hint(state: GameState, npc_id: str, base: int) -> int:
    return buy_price(state, base, npc_id)
