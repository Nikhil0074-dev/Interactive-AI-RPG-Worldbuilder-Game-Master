"""Turn typed events into (prose lines, mechanical lines). Used by the fallback narrator and the UI results log."""
from __future__ import annotations

from ..data.content import ABILITIES, ATTR_SHORT, ENEMIES, ITEMS


def _iname(i: str) -> str:
    return ITEMS[i]["name"] if i in ITEMS else i


def describe_events(world: dict, events: list[dict]) -> tuple[list[str], list[str]]:
    prose: list[str] = []
    mech: list[str] = []
    for e in events:
        t = e["type"]
        if t == "SKILL_CHECK":
            mech.append(f"{e['label']}: d20 {e['roll']} {e['modifier']:+d} = {e['total']} vs DC {e['dc']} ({ATTR_SHORT.get(e['attr'], e['attr'])}) - "
                        f"{'success' if e['success'] else 'failure'}")
        elif t == "ATTACK_RESOLVED":
            if e["attacker_id"] == "player":
                en = ENEMIES[e["target_id"]]["name"]
                if e["hit"]:
                    prose.append(f"You strike the {en}{' with a devastating critical blow' if e['critical'] else ''}.")
                    mech.append(f"You deal {e['damage']} damage to the {en} ({e['target_health_after']} HP left).")
                else:
                    prose.append(f"Your attack goes wide of the {en}.")
                    mech.append("You miss.")
            else:
                en = ENEMIES[e["attacker_id"]]
                if e["hit"]:
                    prose.append(f"The {en['name']} {en['attack_text']}{' in a savage critical blow' if e['critical'] else ''}.")
                    mech.append(f"The {en['name']} deals {e['damage']} damage to you ({e['target_health_after']} HP left).")
                else:
                    prose.append(f"The {en['name']} lunges, but you evade it.")
                    mech.append(f"The {en['name']} misses.")
        elif t == "ABILITY_USED":
            prose.append(f"You call upon {ABILITIES[e['ability_id']]['name']}.")
        elif t == "STATUS_APPLIED":
            mech.append(f"Status applied: {e['status'].replace('_', ' ')} ({e['turns']} turns).")
        elif t == "HEALED":
            prose.append("Warmth spreads through your wounds." if e["amount"] else "You are already in good health.")
            mech.append(f"Recovered {e['amount']} HP ({e['hp_after']} HP).")
        elif t == "ITEM_ACQUIRED":
            prose.append(f"You acquire {_iname(e['item_id'])}.")
            mech.append(f"+{e['quantity']} {_iname(e['item_id'])}")
        elif t == "ITEM_CONSUMED":
            mech.append(f"Used 1 {_iname(e['item_id'])}.")
        elif t == "ITEM_EQUIPPED":
            prose.append(f"You equip the {_iname(e['item_id'])}.")
        elif t == "ITEM_UNEQUIPPED":
            prose.append(f"You stow the {_iname(e['item_id'])}.")
        elif t == "ITEM_DROPPED":
            prose.append(f"You set down the {_iname(e['item_id'])}.")
        elif t == "ITEM_LEFT_BEHIND":
            prose.append(f"Your pack is full; the {_iname(e['item_id'])} is left behind.")
        elif t == "ITEM_GIVEN":
            mech.append(f"Gave {_iname(e['item_id'])}.")
        elif t == "ITEM_PURCHASED":
            mech.append(f"Bought {_iname(e['item_id'])} for {e['price']} gold.")
        elif t == "GOLD_CHANGED":
            mech.append(f"{e['amount']:+d} gold ({e['gold_after']} total).")
        elif t == "XP_GAINED":
            mech.append(f"+{e['amount']} XP")
        elif t == "LEVEL_UP":
            prose.append(f"A surge of resolve: you reach level {e['level']}!")
            mech.append(f"Level {e['level']}: +{e['hp_gain']} max HP, +{e['mana_gain']} max mana, +1 {e['attribute']}.")
        elif t == "ENEMY_DEFEATED":
            prose.append(f"The {ENEMIES[e['enemy_id']]['name']} falls, defeated.")
        elif t == "PLAYER_DEFEATED":
            prose.append("Darkness closes in. Your journey ends here.")
        elif t == "COMBAT_STARTED":
            prose.append(f"Combat begins against the {ENEMIES[e['enemy_id']]['name']}.")
        elif t == "COMBAT_ENDED" and e["result"] == "fled":
            prose.append("You break away and escape.")
        elif t == "QUEST_STARTED":
            mech.append(f"Quest started: {world['quests'][e['quest_id']]['title']}")
        elif t == "QUEST_OBJECTIVE_COMPLETED":
            q = world["quests"][e["quest_id"]]
            obj = next(o for o in q["objectives"] if o["id"] == e["objective_id"])
            mech.append(f"Objective complete: {obj['text']}")
        elif t == "QUEST_COMPLETED":
            mech.append(f"Quest completed: {world['quests'][e['quest_id']]['title']}")
        elif t == "QUEST_ABANDONED":
            mech.append(f"Quest abandoned: {world['quests'][e['quest_id']]['title']}")
        elif t == "RELATIONSHIP_CHANGED" and e["delta"]:
            mech.append(f"{world['npcs'][e['npc_id']]['name']} regards you {'more warmly' if e['delta'] > 0 else 'more coldly'} ({e['delta']:+d}).")
        elif t == "FACTION_REP_CHANGED":
            mech.append(f"{next(f['name'] for f in world['factions'] if f['id'] == e['faction_id'])} reputation {e['delta']:+d}.")
        elif t == "OBJECT_UNLOCKED":
            mech.append("Unlocked.")
        elif t == "REST_TAKEN":
            prose.append("You rest by the shelter of the stones until your strength returns.")
            mech.append(f"Rested: +{e['hp_restored']} HP, +{e['mana_restored']} mana.")
        elif t == "HIDDEN_FOUND":
            mech.append("You discovered something hidden.")
        elif t == "ACTION_REJECTED":
            mech.append(e["message"])
    return prose, mech
