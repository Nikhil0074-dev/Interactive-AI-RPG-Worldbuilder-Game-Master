"""Staged world generation with strict validation.

Stages propose *text* (names, descriptions, lore) from the provider. The structured graph (ids, links, rules) is
validated before anything is committed, so the AI can never create dangling references.
"""
from __future__ import annotations

import copy

from ..data.content import ENEMIES, ITEMS
from ..data.world_template import new_world_from_template
from .provider import LLMProvider, ProviderError

STAGES = ["premise", "regions", "factions", "npcs", "lore"]
MAX_TEXT = 600


class WorldValidationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _all_effects(world: dict):
    for npc in world["npcs"].values():
        for o in npc["options"]:
            for key in ("effects", "on_success", "on_fail"):
                for fx in o.get(key, []):
                    yield fx
    for loc in world["locations"].values():
        for obj in loc.get("objects", []):
            for fx in obj.get("on_examine", []):
                yield fx


def validate_world(world: dict) -> list[str]:
    errs: list[str] = []
    locs, npcs, quests = world["locations"], world["npcs"], world["quests"]
    faction_ids = [f["id"] for f in world["factions"]]
    if len(faction_ids) != len(set(faction_ids)):
        errs.append("duplicate faction ids")
    if world.get("start_location_id") not in locs:
        errs.append("start location does not exist")
    if not world.get("opening_scene"):
        errs.append("missing opening scene")
    objects = {o["id"] for l in locs.values() for o in l.get("objects", [])}
    for r in world["regions"]:
        for l in r["locations"]:
            if l not in locs:
                errs.append(f"region {r['id']} references missing location {l}")
    for lid, l in locs.items():
        if l["id"] != lid:
            errs.append(f"location key/id mismatch {lid}")
        if l.get("region_id") not in {r["id"] for r in world["regions"]}:
            errs.append(f"location {lid} has unknown region")
        for c in l["connections"]:
            if c not in locs:
                errs.append(f"location {lid} connects to missing {c}")
            elif lid not in locs[c]["connections"]:
                errs.append(f"connection {lid}->{c} is not bidirectional")
        for n in l.get("npcs", []):
            if n not in npcs:
                errs.append(f"location {lid} references missing npc {n}")
        for i in l.get("ground", {}):
            if i not in ITEMS:
                errs.append(f"location {lid} ground item {i} not in catalog")
        for h in l.get("hidden", []):
            if "item" in h and h["item"] not in ITEMS:
                errs.append(f"hidden item {h['item']} not in catalog")
        enc = l.get("encounter")
        if enc and enc["enemy"] not in ENEMIES:
            errs.append(f"location {lid} encounter enemy {enc['enemy']} unknown")
        for o in l.get("objects", []):
            for i in o.get("contents", {}).get("items", {}):
                if i not in ITEMS:
                    errs.append(f"object {o['id']} contains unknown item {i}")
            if o.get("key_item") and o["key_item"] not in ITEMS:
                errs.append(f"object {o['id']} key {o['key_item']} unknown")
    for nid, n in npcs.items():
        if n["faction_id"] not in faction_ids:
            errs.append(f"npc {nid} affiliated with unknown faction {n['faction_id']}")
        if n["location_id"] not in locs or nid not in locs[n["location_id"]].get("npcs", []):
            errs.append(f"npc {nid} location inconsistent")
    choices = {fx["choice"] for fx in _all_effects(world) if fx["op"] == "choice"}
    for fx in _all_effects(world):
        op = fx["op"]
        if op in ("give_item", "take_item", "give_to_npc", "buy") and fx["item"] not in ITEMS:
            errs.append(f"effect references unknown item {fx['item']}")
        if op == "quest_start" and fx["quest"] not in quests:
            errs.append(f"effect starts unknown quest {fx['quest']}")
        if op == "rel" and fx["npc"] not in npcs:
            errs.append(f"effect references unknown npc {fx['npc']}")
        if op == "rep" and fx["faction"] not in faction_ids:
            errs.append(f"effect references unknown faction {fx['faction']}")
        if op == "unlock_object" and fx["object"] not in objects:
            errs.append(f"effect unlocks unknown object {fx['object']}")
    target_ok = {"PLAYER_ENTERED_LOCATION": set(locs), "ITEM_ACQUIRED": set(ITEMS), "ITEM_GIVEN": set(ITEMS),
                 "ENEMY_DEFEATED": set(ENEMIES), "NPC_DIALOGUE_STARTED": set(npcs), "OBJECT_EXAMINED": objects, "CHOICE_MADE": choices}
    for qid, q in quests.items():
        for obj in q["objectives"]:
            allowed = target_ok.get(obj["event"])
            if allowed is not None and obj["target"] not in allowed:
                errs.append(f"quest {qid} objective {obj['id']} references unknown target {obj['target']}")
        if q.get("giver") and q["giver"] not in npcs:
            errs.append(f"quest {qid} giver unknown")
        for r in [q.get("rewards", {})] + [o.get("rewards", {}) for o in q.get("outcomes", [])]:
            for i in r.get("items", {}):
                if i not in ITEMS:
                    errs.append(f"quest {qid} reward item {i} unknown")
    from ..data.content import CLASSES
    for c, cls in CLASSES.items():
        for i in list(cls["equipment"].values()) + list(cls["items"]):
            if i not in ITEMS:
                errs.append(f"class {c} starting item {i} not in catalog")
    return errs


def _text(v, default: str) -> str:
    return v.strip()[:MAX_TEXT] if isinstance(v, str) and v.strip() else default


def apply_stage(world: dict, stage: str, proposal: dict) -> None:
    """Merge only whitelisted text fields for ids that already exist. Unknown ids are ignored."""
    if stage == "premise":
        world["name"] = _text(proposal.get("name"), world["name"])[:80]
        world["premise"] = _text(proposal.get("premise"), world["premise"])
        world["central_conflict"] = _text(proposal.get("central_conflict"), world["central_conflict"])
    elif stage == "regions":
        for r in world["regions"]:
            p = proposal.get("regions", {}).get(r["id"], {})
            r["name"], r["description"] = _text(p.get("name"), r["name"])[:80], _text(p.get("description"), r["description"])
    elif stage == "factions":
        for f in world["factions"]:
            f["description"] = _text(proposal.get("factions", {}).get(f["id"], {}).get("description"), f["description"])
    elif stage == "npcs":
        for nid, n in world["npcs"].items():
            n["personality"] = _text(proposal.get("npcs", {}).get(nid, {}).get("personality"), n["personality"])
    elif stage == "lore":
        for l in world["lore"]:
            l["text"] = _text(proposal.get("lore", {}).get(l["id"], {}).get("text"), l["text"])


def generate_world(provider: LLMProvider, config: dict, world_id: str = "world") -> tuple[dict, list[str]]:
    world = new_world_from_template()
    world["id"] = world_id
    world["genre"] = config.get("genre", world["genre"])
    notes: list[str] = []
    for stage in STAGES:
        ctx = {"config": config, "world": {"name": world["name"], "premise": world["premise"], "central_conflict": world["central_conflict"],
                                           "regions": world["regions"], "factions": world["factions"], "npcs": world["npcs"], "lore": world["lore"]}}
        try:
            proposal = provider.generate_world_stage(stage, copy.deepcopy(ctx))
        except ProviderError as e:
            notes.append(f"stage '{stage}' fell back to defaults: {e}")
            continue
        candidate = copy.deepcopy(world)
        apply_stage(candidate, stage, proposal)
        errs = validate_world(candidate)
        if errs:
            notes.append(f"stage '{stage}' rejected: {errs[:2]}")
            continue
        world = candidate
    errs = validate_world(world)
    if errs:
        raise WorldValidationError(errs)
    return world, notes
