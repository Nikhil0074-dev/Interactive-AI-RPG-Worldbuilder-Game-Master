"""Deterministic turn-based combat. Damage formula: max(1, base + attack_bonus - defense)."""
from __future__ import annotations

from ..data.content import ABILITIES, DIFFICULTY_ENEMY_MULT, ENEMIES
from ..models.events import make_event
from ..models.state import CombatState, GameState
from . import inventory_engine as inv
from . import progression_engine as prog
from . import state_machine as fsm
from .common import ActionRejected, attr_mod, d20, item_def, loc_state, skill_check


def calc_damage(base: int, attack_bonus: int, defense: int) -> int:
    return max(1, base + attack_bonus - defense)


def _status_value(statuses: dict, name: str) -> int:
    return statuses.get(name, {}).get("value", 0)


def _tick(statuses: dict) -> None:
    for name in list(statuses):
        statuses[name]["turns"] -= 1
        if statuses[name]["turns"] <= 0:
            del statuses[name]


def player_defense(state: GameState) -> int:
    return inv.equipped_bonus(state, "defense")


def player_ac(state: GameState) -> int:
    return 8 + attr_mod(state, "dexterity") + player_defense(state)


def weapon_info(state: GameState) -> tuple[int, str]:
    w = state.player.equipped.get("weapon")
    if not w:
        return 2, "strength"
    props = item_def(w)["properties"]
    return props.get("damage", 2), props.get("scaling", "strength")


def start_combat(world: dict, state: GameState, enemy_id: str, events: list) -> None:
    if not state.combat_enabled:
        raise ActionRejected("COMBAT_DISABLED", "Combat is disabled in this campaign.")
    enemy = ENEMIES[enemy_id]
    fsm.transition(state, "COMBAT", events)
    p_init = d20(state) + attr_mod(state, "dexterity")
    e_init = d20(state) + enemy["initiative"]
    first = p_init >= e_init
    state.combat = CombatState(enemy_id=enemy_id, enemy_hp=enemy["hp"], enemy_max_hp=enemy["hp"], player_first=first)
    events.append(make_event("COMBAT_STARTED", enemy_id=enemy_id, player_first=first))
    if not first:
        enemy_turn(world, state, events)


def _enemy_defense(state: GameState) -> int:
    c = state.combat
    return max(0, ENEMIES[c.enemy_id]["defense"] - _status_value(c.enemy_statuses, "defense_down"))


def _damage_enemy(state: GameState, dmg: int, hit: bool, crit: bool, events: list) -> None:
    c = state.combat
    c.enemy_hp = max(0, c.enemy_hp - dmg)
    events.append(make_event("ATTACK_RESOLVED", attacker_id="player", target_id=c.enemy_id, damage=dmg,
                             target_health_after=c.enemy_hp, hit=hit, critical=crit))


def player_attack(world: dict, state: GameState, events: list) -> None:
    base, scaling = weapon_info(state)
    bonus = attr_mod(state, scaling) + inv.equipped_bonus(state, "attack_bonus") + _status_value(state.player.statuses, "attack_up")
    roll = d20(state)
    if roll == 1:
        _damage_enemy(state, 0, False, False, events)
    else:
        crit = roll == 20
        dmg = calc_damage(base, bonus, _enemy_defense(state)) * (2 if crit else 1)
        _damage_enemy(state, dmg, True, crit, events)
    _after_player_turn(world, state, events)


def player_ability(world: dict, state: GameState, ability_id: str, events: list) -> None:
    p = state.player
    ab = ABILITIES.get(ability_id)
    if ab is None or ability_id not in p.abilities:
        raise ActionRejected("UNKNOWN_ABILITY", "You do not know that ability.")
    if p.mana < ab["mana"]:
        raise ActionRejected("NOT_ENOUGH_MANA", f"{ab['name']} needs {ab['mana']} mana.")
    p.mana -= ab["mana"]
    events.append(make_event("ABILITY_USED", ability_id=ability_id, user_id="player"))
    mod = attr_mod(state, ab.get("scaling", "strength"))
    if "heal" in ab:
        inv.heal(state, ab["heal"] + max(0, mod), events)
    if "damage" in ab:
        wdmg, _ = weapon_info(state)
        base = ab["damage"] + (wdmg if ab.get("uses_weapon") else 0)
        bonus = mod + inv.equipped_bonus(state, "attack_bonus") + _status_value(p.statuses, "attack_up")
        defense = 0 if ab.get("ignore_defense") else _enemy_defense(state)
        dmg = calc_damage(base, bonus, defense)
        crit = bool(ab.get("critical"))
        _damage_enemy(state, dmg * (2 if crit else 1), True, crit, events)
    if "status" in ab and state.combat.enemy_hp > 0:
        s = ab["status"]
        state.combat.enemy_statuses[s["name"]] = {"value": s["value"], "turns": s["turns"]}
        events.append(make_event("STATUS_APPLIED", target_id=state.combat.enemy_id, status=s["name"], turns=s["turns"]))
    if "self_status" in ab:
        s = ab["self_status"]
        p.statuses[s["name"]] = {"value": s["value"], "turns": s["turns"]}
        events.append(make_event("STATUS_APPLIED", target_id="player", status=s["name"], turns=s["turns"]))
    _after_player_turn(world, state, events)


def player_use_item(world: dict, state: GameState, item_id: str, events: list) -> None:
    inv.use_item(state, item_id, events)
    _after_player_turn(world, state, events)


def player_flee(world: dict, state: GameState, events: list) -> None:
    if skill_check(state, "dexterity", 12, "Flee from combat", events):
        state.combat = None
        events.append(make_event("COMBAT_ENDED", result="fled"))
        fsm.transition(state, "EXPLORATION", events)
        if state.previous_location_id:
            state.location_id, state.previous_location_id = state.previous_location_id, None
        return
    enemy_turn(world, state, events)


def _after_player_turn(world: dict, state: GameState, events: list) -> None:
    if state.combat.enemy_hp <= 0:
        _victory(world, state, events)
        return
    enemy_turn(world, state, events)


def enemy_turn(world: dict, state: GameState, events: list) -> None:
    c = state.combat
    enemy = ENEMIES[c.enemy_id]
    if "stunned" in c.enemy_statuses:
        pass  # enemy loses its turn
    else:
        roll = d20(state)
        hit = roll != 1 and (roll == 20 or roll + enemy["accuracy"] >= player_ac(state))
        base = round(enemy["attack"] * DIFFICULTY_ENEMY_MULT.get(state.difficulty, 1.0))
        dmg = calc_damage(base, 0, player_defense(state)) * (2 if roll == 20 else 1) if hit else 0
        state.player.hp = max(0, state.player.hp - dmg)
        events.append(make_event("ATTACK_RESOLVED", attacker_id=c.enemy_id, target_id="player", damage=dmg,
                                 target_health_after=state.player.hp, hit=hit, critical=roll == 20 and hit))
        if state.player.hp <= 0:
            events.append(make_event("PLAYER_DEFEATED", enemy_id=c.enemy_id))
            events.append(make_event("COMBAT_ENDED", result="defeat"))
            state.combat = None
            fsm.transition(state, "GAME_OVER", events)
            return
    _tick(c.enemy_statuses)
    _tick(state.player.statuses)
    c.round += 1


def _victory(world: dict, state: GameState, events: list) -> None:
    c = state.combat
    enemy = ENEMIES[c.enemy_id]
    events.append(make_event("ENEMY_DEFEATED", enemy_id=c.enemy_id))
    events.append(make_event("COMBAT_ENDED", result="victory"))
    state.player.statuses.clear()
    state.combat = None
    fsm.transition(state, "EXPLORATION", events)
    loc_state(state, state.location_id).encounter_done = True
    prog.award_xp(state, enemy["xp"], events)
    if enemy["loot"].get("gold"):
        inv.change_gold(state, enemy["loot"]["gold"], events)
    for item, qty in enemy["loot"].get("items", {}).items():
        inv.give_item(state, item, qty, "loot", events)
