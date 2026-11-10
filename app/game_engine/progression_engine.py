"""Experience and levelling. The LLM narrates growth; this module computes it."""
from __future__ import annotations

from ..data.content import CLASSES, MAX_LEVEL, XP_PER_LEVEL_STEP
from ..models.events import make_event
from ..models.state import GameState
from .common import attr_mod


def xp_for_level(level: int) -> int:
    """Total XP required to *reach* ``level`` (level 1 = 0)."""
    return XP_PER_LEVEL_STEP * (level - 1) * level // 2


def award_xp(state: GameState, amount: int, events: list) -> None:
    if amount <= 0:
        return
    p = state.player
    p.xp += amount
    events.append(make_event("XP_GAINED", amount=amount, xp_after=p.xp))
    while p.level < MAX_LEVEL and p.xp >= xp_for_level(p.level + 1):
        p.level += 1
        cls = CLASSES[p.char_class]
        hp_gain = cls["hit_die"] // 2 + 1 + max(0, attr_mod(state, "constitution"))
        mana_gain = 2 + max(0, attr_mod(state, cls["primary"]))
        p.max_hp += hp_gain
        p.max_mana += mana_gain
        p.hp = min(p.max_hp, p.hp + hp_gain)
        p.mana = min(p.max_mana, p.mana + mana_gain)
        p.attributes[cls["primary"]] += 1
        events.append(make_event("LEVEL_UP", level=p.level, hp_gain=hp_gain, mana_gain=mana_gain, attribute=cls["primary"]))
