"""Three-layer memory: immediate (recent turns), campaign (structured facts), world lore. Relevance-ranked retrieval."""
from __future__ import annotations

import re

from ..game_engine.common import get_rel
from ..models.state import GameState


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", s.lower()))


def retrieve(world: dict, state: GameState, query: str = "", recent: list[str] | None = None,
             limit: int = 5, lore_limit: int = 3) -> dict:
    loc = world["locations"][state.location_id]
    present = list(loc.get("npcs", []))
    focus = {state.location_id, *present}
    qt = _tokens(query + " " + loc["name"] + " " + " ".join(world["npcs"][n]["name"] for n in present))

    def score(m) -> float:
        s = 2.0 * len(focus & set(m.entities)) + len(qt & _tokens(m.text)) + m.turn / (state.turn + 1)
        return s

    facts = sorted(state.memory, key=score, reverse=True)[:limit]
    lore = []
    for l in world["lore"]:
        if l.get("requires_flag") and not state.flags.get(l["requires_flag"]):
            continue
        lore.append((len(qt & _tokens(l["title"] + " " + l["text"])), l))
    lore = [l for sc, l in sorted(lore, key=lambda x: -x[0])][:lore_limit]
    rels = {n: {**get_rel(state, n).model_dump(), "name": world["npcs"][n]["name"]} for n in present}
    return {"immediate": (recent or [])[-3:], "campaign": [m.text for m in facts],
            "lore": [{"title": l["title"], "text": l["text"]} for l in lore], "relationships": rels}
