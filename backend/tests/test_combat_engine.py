from conftest import act, make_state
from app.data.content import ENEMIES
from app.game_engine.action_resolver import resolve
from app.game_engine.combat_engine import calc_damage


def to_belfry(world, state):
    s = resolve(world, state, act("move", target_id="loc_mist_street")).state
    return resolve(world, s, act("move", target_id="loc_hollow_belfry"))


def test_damage_formula():
    assert calc_damage(8, 2, 2) == 8
    assert calc_damage(1, 0, 10) == 1      # floor at 1
    assert calc_damage(10, -3, 0) == 7


def test_belfry_triggers_combat_once(world, state):
    r = to_belfry(world, state)
    assert r.state.fsm_state in ("COMBAT", "GAME_OVER")
    assert r.state.combat.enemy_id == "enemy_bell_ringer"
    ev = [e for e in r.events if e["type"] == "COMBAT_STARTED"]
    assert len(ev) == 1


def test_combat_disabled_skips_encounter(world):
    s = make_state(world, combat_enabled=False)
    s = resolve(world, s, act("move", target_id="loc_mist_street")).state
    r = resolve(world, s, act("move", target_id="loc_hollow_belfry"))
    assert r.state.fsm_state == "EXPLORATION" and r.state.combat is None


def test_attack_events_match_state(world, state):
    s = to_belfry(world, state).state
    hp0 = s.combat.enemy_hp
    r = resolve(world, s, act("attack"))
    atk = [e for e in r.events if e["type"] == "ATTACK_RESOLVED" and e["attacker_id"] == "player"][0]
    assert atk["target_health_after"] == r.state.combat.enemy_hp == hp0 - atk["damage"]
    assert atk["damage"] >= 0


def test_movement_blocked_during_combat(world, state):
    s = to_belfry(world, state).state
    assert resolve(world, s, act("move", target_id="loc_mist_street")).error["code"] == "INVALID_STATE"


def test_ability_mana_cost_and_validation(world):
    s = make_state(world, "mage")
    s = to_belfry(world, s).state
    r = resolve(world, s, act("ability", ability_id="arcane_bolt"))
    assert r.state.player.mana == s.player.mana - 5
    assert resolve(world, s, act("ability", ability_id="healing_light")).error["code"] == "UNKNOWN_ABILITY"
    s.player.mana = 1
    assert resolve(world, s, act("ability", ability_id="arcane_bolt")).error["code"] == "NOT_ENOUGH_MANA"


def test_victory_flow_rewards_once(world):
    s = make_state(world, "warrior", seed=3)
    s.player.max_hp = s.player.hp = 500       # make the fight winnable regardless of dice
    s = to_belfry(world, s).state
    for _ in range(40):
        if s.fsm_state != "COMBAT":
            break
        s = resolve(world, s, act("attack")).state
    assert s.fsm_state == "EXPLORATION" and "enemy_bell_ringer" in s.defeated_enemies
    assert s.player.inventory.get("item_memory_clapper") == 1
    assert s.player.xp >= 120 and s.locations["loc_hollow_belfry"].encounter_done
    # re-entering does not retrigger the encounter
    s = resolve(world, s, act("move", target_id="loc_mist_street")).state
    r = resolve(world, s, act("move", target_id="loc_hollow_belfry"))
    assert r.state.fsm_state == "EXPLORATION"


def test_defeat_leads_to_game_over(world):
    s = make_state(world, "mage", seed=5)
    s = to_belfry(world, s).state
    if s.fsm_state == "COMBAT":
        s.player.hp = 1
        for _ in range(30):
            if s.fsm_state != "COMBAT":
                break
            s = resolve(world, s, act("flee")).state
    assert s.fsm_state in ("GAME_OVER", "EXPLORATION")
    if s.fsm_state == "GAME_OVER":
        assert s.player.hp == 0
        assert resolve(world, s, act("move", target_id="loc_mist_street")).error["code"] == "GAME_OVER"


def test_hp_never_negative_and_enemy_hp_bounds(world, state):
    s = to_belfry(world, state).state
    for _ in range(25):
        if s.fsm_state != "COMBAT":
            break
        s = resolve(world, s, act("attack")).state
        assert s.player.hp >= 0
        if s.combat:
            assert 0 <= s.combat.enemy_hp <= ENEMIES["enemy_bell_ringer"]["hp"]


def test_status_effects_decay(world):
    s = make_state(world, "warrior")
    s = to_belfry(world, s).state
    s.player.hp = s.player.max_hp = 999
    s = resolve(world, s, act("ability", ability_id="shield_break")).state
    if s.combat:
        assert s.combat.enemy_statuses["defense_down"]["turns"] == 2   # ticked once after the enemy turn
