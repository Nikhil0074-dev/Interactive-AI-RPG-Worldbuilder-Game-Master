"""Deterministic offline provider: rule-based intent parsing, template narration, template world stages."""
from __future__ import annotations

import hashlib
import re

from .provider import LLMProvider

STOP = {"the", "a", "an", "to", "at", "of", "and", "my", "i", "with", "for", "in", "on", "it", "this", "that", "toward",
        "towards", "into", "from", "some", "up", "around", "about", "then", "please", "now"}

VERBS = [
    ("flee", ["flee", "run away", "escape", "retreat"]),
    ("attack", ["attack", "fight", "strike", "hit ", "slash", "stab", "shoot", "kill"]),
    ("equip", ["equip", "wield", "put on", "wear "]),
    ("unequip", ["unequip", "take off", "remove "]),
    ("drop", ["drop", "discard", "throw away"]),
    ("use_item", ["drink", "quaff", "use ", "consume", "eat "]),
    ("rest", ["rest", "sleep", "camp", "recover", "heal up"]),
    ("search", ["search", "rummage", "look for", "scour", "dig through", "investigate the area", "look around carefully"]),
    ("open", ["open", "unlock", "pick the lock", "pick lock", "force the"]),
    ("take", ["take", "pick up", "grab", "collect", "loot", "pocket", "get the"]),
    ("talk", ["talk", "speak", "ask", "chat", "greet", "approach", "negotiate", "converse", "persuade", "question"]),
    ("move", ["go ", "travel", "walk", "head ", "follow", "enter", "move to", "run to", "climb", "descend", "visit"]),
    ("examine", ["examine", "inspect", "look at", "study", "read", "investigate", "check", "look", "observe"]),
]


def toks(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in STOP}


def best_match(text: str, cands: list[dict]) -> str | None:
    tt = toks(text)
    best, score = None, 0
    for c in cands:
        ct = toks(c["name"] + " " + c.get("extra", ""))
        s = len(tt & ct) + 0.5 * sum(1 for a in tt for b in ct if a != b and len(a) >= 4 and (a[:4] == b[:4]))
        if s > score:
            best, score = c["id"], s
    return best if score >= 1 else None


class MockProvider(LLMProvider):
    name = "mock"
    is_mock = True

    def complete_json(self, system: str, user: str) -> dict:  # not used by the mock's specialised methods
        return {}

    # ------------------------------------------------------------------ intent
    def interpret_action(self, text: str, candidates: dict) -> dict:
        low = " " + text.lower() + " "
        state = candidates["fsm_state"]
        if state == "COMBAT":
            for ab in candidates.get("abilities", []):
                if toks(ab["name"]) & toks(text):
                    return {"type": "ability", "ability_id": ab["id"]}
            if any(w in low for w in ("flee", "run", "escape", "retreat")):
                return {"type": "flee"}
            if any(w in low for w in ("potion", "drink", "heal")):
                it = best_match(text, candidates["inventory"]) or next((i["id"] for i in candidates["inventory"] if i["id"] == "item_healing_potion"), None)
                return {"type": "use_item", "item_id": it} if it else {"type": "unknown"}
            if any(w in low for w in ("attack", "fight", "strike", "hit", "slash", "stab", "shoot", "kill", "smash")):
                return {"type": "attack"}
            return {"type": "unknown"}
        if state == "DIALOGUE":
            if any(w in low for w in ("leave", "goodbye", "farewell", "bye", "walk away", "end conversation")):
                return {"type": "end_dialogue"}
            opt = best_match(text, [{"id": o["id"], "name": o["text"]} for o in candidates.get("options", [])])
            return {"type": "dialogue_choice", "option_id": opt} if opt else {"type": "unknown"}
        if state != "EXPLORATION":
            return {"type": "unknown"}
        for verb, keys in VERBS:
            if not any(k in low for k in [" " + k.strip() if not k.endswith(" ") else " " + k for k in keys]):
                continue
            if verb == "move":
                t = best_match(text, candidates["exits"])
                if t:
                    return {"type": "move", "target_id": t}
            elif verb == "talk":
                t = best_match(text, candidates["npcs"])
                if t:
                    return {"type": "talk", "target_id": t}
            elif verb == "open":
                t = best_match(text, candidates["objects"]) or (candidates["objects"][0]["id"] if len(candidates["objects"]) == 1 else None)
                if t:
                    return {"type": "open", "target_id": t}
            elif verb == "take":
                t = best_match(text, candidates["ground"])
                if t:
                    return {"type": "take", "item_id": t}
            elif verb in ("use_item", "equip", "unequip", "drop"):
                t = best_match(text, candidates["inventory"])
                if t:
                    return {"type": verb, "item_id": t}
            elif verb == "examine":
                pool = candidates["objects"] + candidates["npcs"] + candidates["ground"]
                t = best_match(text, pool)
                return {"type": "examine", "target_id": t} if t else {"type": "examine"}
            elif verb in ("search", "rest"):
                return {"type": verb}
        return {"type": "unknown"}

    # ------------------------------------------------------------------ narration
    def narrate(self, context: dict) -> dict:
        from .game_master import template_narration
        return template_narration(context)

    # ------------------------------------------------------------------ world stages
    def generate_world_stage(self, stage: str, context: dict) -> dict:
        cfg = context["config"]
        seed = int(hashlib.sha256((cfg.get("world_name", "") + cfg.get("setting", "")).encode()).hexdigest(), 16)
        tone = cfg.get("tone", "mysterious")
        if stage == "premise":
            return {"name": cfg.get("world_name") or context["world"]["name"],
                    "premise": (cfg.get("setting") or context["world"]["premise"])[:400],
                    "central_conflict": context["world"]["central_conflict"]}
        if stage == "regions":
            names = {"dark_fantasy": ["The Ashen March", "The Cinder Reach", "The Weeping Frontier"],
                     "high_fantasy": ["The Gilded Marches", "The Sunlit Reach", "The Silver Frontier"],
                     "mystery": ["The Fogbound Quarter", "The Lantern District", "The Hushed Reach"]}.get(cfg.get("genre"), ["The Ashen March"])
            return {"regions": {r["id"]: {"name": names[seed % len(names)],
                                          "description": f"A {tone} borderland of ruined cities."} for r in context["world"]["regions"]}}
        if stage == "factions":
            return {"factions": {f["id"]: {"description": f["description"]} for f in context["world"]["factions"]}}
        if stage == "npcs":
            return {"npcs": {n: {"personality": v["personality"]} for n, v in context["world"]["npcs"].items()}}
        if stage == "lore":
            return {"lore": {l["id"]: {"text": l["text"]} for l in context["world"]["lore"]}}
        return {}
