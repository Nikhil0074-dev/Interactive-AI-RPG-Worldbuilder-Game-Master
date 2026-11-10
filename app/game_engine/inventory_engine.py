"""Inventory, equipment and consumables. The backend alone controls inventory."""
from __future__ import annotations

from ..models.events import make_event
from ..models.state import EQUIP_SLOTS, GameState
from .common import ActionRejected, item_def, loc_state


def capacity(state: GameState) -> float:
    return 20 + state.player.attributes["strength"] * 2


def carried_weight(state: GameState) -> float:
    return round(sum(item_def(i)["weight"] * q for i, q in state.player.inventory.items()), 2)


def can_carry(state: GameState, item_id: str, qty: int = 1) -> bool:
    return carried_weight(state) + item_def(item_id)["weight"] * qty <= capacity(state)


def _add(state: GameState, item_id: str, qty: int) -> None:
    d = item_def(item_id)
    inv = state.player.inventory
    if not d["stackable"] and inv.get(item_id, 0) + qty > 1 and d["category"] not in ("quest", "key", "book", "tool"):
        # non-stackable duplicates are allowed but tracked by count
        pass
    inv[item_id] = inv.get(item_id, 0) + qty
    if item_id not in state.seen_items:
        state.seen_items.append(item_id)


def give_item(state: GameState, item_id: str, qty: int, source: str, events: list, overflow_to_ground: bool = True) -> int:
    """Add items; anything that does not fit is left on the ground at the current location."""
    item_def(item_id)
    added = 0
    for _ in range(qty):
        if can_carry(state, item_id):
            _add(state, item_id, 1)
            added += 1
        elif overflow_to_ground and state.location_id:
            g = loc_state(state, state.location_id).ground
            g[item_id] = g.get(item_id, 0) + 1
            events.append(make_event("ITEM_LEFT_BEHIND", item_id=item_id, quantity=1))
        else:
            raise ActionRejected("TOO_HEAVY", f"You cannot carry the {item_def(item_id)['name']}.")
    if added:
        events.append(make_event("ITEM_ACQUIRED", item_id=item_id, quantity=added, source=source))
    return added


def remove_item(state: GameState, item_id: str, qty: int = 1) -> None:
    have = state.player.inventory.get(item_id, 0)
    if have < qty:
        raise ActionRejected("NOT_IN_INVENTORY", f"You do not have {item_def(item_id)['name']}.")
    if have == qty:
        del state.player.inventory[item_id]
        for slot, eq in state.player.equipped.items():
            if eq == item_id:
                state.player.equipped[slot] = None
    else:
        state.player.inventory[item_id] = have - qty


def change_gold(state: GameState, amount: int, events: list) -> None:
    if state.player.gold + amount < 0:
        raise ActionRejected("NOT_ENOUGH_GOLD", "You cannot afford that.")
    state.player.gold += amount
    events.append(make_event("GOLD_CHANGED", amount=amount, gold_after=state.player.gold))


def heal(state: GameState, amount: int, events: list) -> int:
    p = state.player
    gained = max(0, min(amount, p.max_hp - p.hp))
    p.hp += gained
    events.append(make_event("HEALED", target_id="player", amount=gained, hp_after=p.hp))
    return gained


def use_item(state: GameState, item_id: str, events: list) -> None:
    d = item_def(item_id)
    p = state.player
    if p.inventory.get(item_id, 0) < 1:
        raise ActionRejected("NOT_IN_INVENTORY", f"You do not have a {d['name']}.")
    if d["category"] != "consumable":
        raise ActionRejected("NOT_USABLE", f"The {d['name']} cannot be used that way.")
    props = d["properties"]
    if "heal" in props and p.hp >= p.max_hp and "mana" not in props:
        raise ActionRejected("ALREADY_FULL", "You are already at full health.")
    if "mana" in props and p.mana >= p.max_mana and "heal" not in props:
        raise ActionRejected("ALREADY_FULL", "Your mana is already full.")
    remove_item(state, item_id, 1)
    events.append(make_event("ITEM_CONSUMED", item_id=item_id, quantity=1))
    if "heal" in props:
        heal(state, props["heal"], events)
    if "mana" in props:
        p.mana = min(p.max_mana, p.mana + props["mana"])


def equip(state: GameState, item_id: str, events: list) -> None:
    d = item_def(item_id)
    p = state.player
    if p.inventory.get(item_id, 0) < 1:
        raise ActionRejected("NOT_IN_INVENTORY", f"You do not have a {d['name']}.")
    slot = d.get("slot")
    if slot not in EQUIP_SLOTS:
        raise ActionRejected("NOT_EQUIPPABLE", f"The {d['name']} cannot be equipped.")
    for attr, need in d["requirements"].items():
        if p.attributes.get(attr, 0) < need:
            raise ActionRejected("REQUIREMENT_NOT_MET", f"The {d['name']} requires {attr.title()} {need}.")
    if p.equipped.get(slot) == item_id:
        raise ActionRejected("ALREADY_EQUIPPED", f"The {d['name']} is already equipped.")
    old = p.equipped.get(slot)
    if old:
        events.append(make_event("ITEM_UNEQUIPPED", item_id=old, slot=slot))
    p.equipped[slot] = item_id
    events.append(make_event("ITEM_EQUIPPED", item_id=item_id, slot=slot))


def unequip(state: GameState, item_id: str, events: list) -> None:
    p = state.player
    for slot, eq in p.equipped.items():
        if eq == item_id:
            p.equipped[slot] = None
            events.append(make_event("ITEM_UNEQUIPPED", item_id=item_id, slot=slot))
            return
    raise ActionRejected("NOT_EQUIPPED", "That item is not equipped.")


def drop(state: GameState, item_id: str, events: list) -> None:
    d = item_def(item_id)
    p = state.player
    if p.inventory.get(item_id, 0) < 1:
        raise ActionRejected("NOT_IN_INVENTORY", f"You do not have a {d['name']}.")
    if d["properties"].get("quest"):
        raise ActionRejected("QUEST_ITEM", f"The {d['name']} is too important to drop.")
    if p.equipped.get(d.get("slot")) == item_id and p.inventory[item_id] == 1:
        raise ActionRejected("EQUIPPED", "Unequip it before dropping it.")
    remove_item(state, item_id, 1)
    g = loc_state(state, state.location_id).ground
    g[item_id] = g.get(item_id, 0) + 1
    events.append(make_event("ITEM_DROPPED", item_id=item_id, quantity=1))


def equipped_bonus(state: GameState, prop: str) -> int:
    total = 0
    for item_id in state.player.equipped.values():
        if item_id:
            total += item_def(item_id)["properties"].get(prop, 0)
    return total
