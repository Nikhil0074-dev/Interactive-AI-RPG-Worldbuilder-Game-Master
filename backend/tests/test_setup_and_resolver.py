import pytest
from conftest import act, make_state
from app.game_engine.action_resolver import resolve
from app.game_engine.setup import start_adventure
from app.game_engine.common import ActionRejected
from app.game_engine import inventory_engine as inv
from app.models.state import ATTRIBUTES


@pytest.mark.parametrize("cls", ["warrior", "mage", "rogue", "ranger", "cleric", "bard", "engineer"])
def test_every_class_starts_validly(world, cls):
    s = make_state(world, cls)
    p = s.player
    assert s.fsm_state == "EXPLORATION" and p.hp == p.max_hp > 0
    assert p.equipped["weapon"] in p.inventory and p.abilities
    assert inv.carried_weight(s) <= inv.capacity(s)


def test_bad_character_inputs_rejected(world):
    from app.game_engine.setup import create_initial_state
    s = create_initial_state({}, seed=1); s.fsm_state = "CHARACTER_CREATION"
    for kw in [dict(name="", char_class="mage"), dict(name="x", char_class="paladin"), dict(name="x", char_class="mage", bonus_attribute="luck")]:
        with pytest.raises(ActionRejected):
            start_adventure(world, s, **kw)


def test_rejection_never_mutates_state(world, state):
    before = state.model_dump()
    r = resolve(world, state, act("attack"))   # not in combat
    assert r.status == "rejected" and r.error["code"] == "INVALID_STATE"
    assert r.state.model_dump() == before and state.model_dump() == before


def test_move_and_first_visit_xp(world, state):
    r = resolve(world, state, act("move", target_id="loc_mist_street"))
    assert r.status == "completed" and r.state.location_id == "loc_mist_street" and r.state.fsm_state == "EXPLORATION"
    assert r.state.player.xp == 15
    r2 = resolve(world, r.state, act("move", target_id="loc_veyr_gate"))
    r3 = resolve(world, r2.state, act("move", target_id="loc_mist_street"))
    assert r3.state.player.xp == 15  # no repeat discovery XP


def test_unreachable_and_locked_locations(world, state):
    assert resolve(world, state, act("move", target_id="loc_forgotten_shrine")).error["code"] == "NOT_REACHABLE"
    s = resolve(world, state, act("move", target_id="loc_mist_street")).state
    r = resolve(world, s, act("move", target_id="loc_forgotten_shrine"))
    assert r.error["code"] == "LOCKED"


def test_locked_chest_requires_key_or_picks(world, state):
    r = resolve(world, state, act("open", target_id="obj_iron_chest"))
    assert r.error["code"] == "LOCKED"
    s = state.model_copy(deep=True)
    s.player.inventory["item_orsin_key"] = 1
    r = resolve(world, s, act("open", target_id="obj_iron_chest"))
    assert r.status == "completed" and r.state.player.gold == 70
    assert "item_ember_charm" in r.state.player.inventory
    again = resolve(world, r.state, act("open", target_id="obj_iron_chest"))
    assert again.error["code"] == "ALREADY_OPEN"


def test_lockpicking_is_seeded_and_deterministic(world):
    outs = []
    for _ in range(2):
        s = make_state(world, "rogue", seed=7)
        outs.append(resolve(world, s, act("open", target_id="obj_iron_chest")).events)
    assert outs[0] == outs[1]
    assert any(e["type"] == "SKILL_CHECK" for e in outs[0])


def test_take_search_and_capacity(world, state):
    s = resolve(world, state, act("move", target_id="loc_mist_street")).state
    r = resolve(world, s, act("take", item_id="item_healing_potion"))
    assert r.state.player.inventory["item_healing_potion"] == 3
    assert resolve(world, r.state, act("take", item_id="item_healing_potion")).error["code"] == "NOT_HERE"
    # heavy item cannot be taken beyond capacity
    s2 = r.state.model_copy(deep=True)
    s2.player.inventory["item_chain_hauberk"] = 3
    s2.locations["loc_mist_street"].ground["item_chain_hauberk"] = 1
    assert resolve(world, s2, act("take", item_id="item_chain_hauberk")).error["code"] == "TOO_HEAVY"


def test_search_finds_hidden_key_eventually(world, state):
    s = resolve(world, state, act("move", target_id="loc_mist_street")).state
    found = False
    for _ in range(12):
        r = resolve(world, s, act("search"))
        if r.status == "rejected":
            break
        s = r.state
        if "hid_key" in s.locations["loc_mist_street"].found_hidden:
            found = True
            break
    assert found and s.locations["loc_mist_street"].ground.get("item_orsin_key") == 1


def test_use_potion_respects_max_hp_and_consumes(world, state):
    assert resolve(world, state, act("use_item", item_id="item_healing_potion")).error["code"] == "ALREADY_FULL"
    s = state.model_copy(deep=True); s.player.hp = s.player.max_hp - 5
    r = resolve(world, s, act("use_item", item_id="item_healing_potion"))
    assert r.state.player.hp == r.state.player.max_hp
    assert r.state.player.inventory["item_healing_potion"] == 1
    heal = [e for e in r.events if e["type"] == "HEALED"][0]
    assert heal["amount"] == 5     # capped, the model cannot invent stronger healing


def test_use_item_not_owned_or_not_consumable(world, state):
    assert resolve(world, state, act("use_item", item_id="item_mana_draught")).error["code"] == "NOT_IN_INVENTORY"
    assert resolve(world, state, act("use_item", item_id="item_iron_sword")).error["code"] == "NOT_USABLE"
    assert resolve(world, state, act("use_item", item_id="item_nonexistent")).error["code"] in ("UNKNOWN_ITEM", "NOT_IN_INVENTORY")


def test_equip_requirements_and_swap(world):
    s = make_state(world, "mage")  # STR 8
    s.player.inventory["item_chain_hauberk"] = 1
    assert resolve(world, s, act("equip", item_id="item_chain_hauberk")).error["code"] == "REQUIREMENT_NOT_MET"
    w = make_state(world, "warrior"); w.player.inventory["item_chain_hauberk"] = 1
    r = resolve(world, w, act("equip", item_id="item_chain_hauberk"))
    assert r.state.player.equipped["armor"] == "item_chain_hauberk"
    assert resolve(world, r.state, act("equip", item_id="item_chain_hauberk")).error["code"] == "ALREADY_EQUIPPED"


def test_drop_rules(world, state):
    assert resolve(world, state, act("drop", item_id="item_iron_sword")).error["code"] == "EQUIPPED"
    s = state.model_copy(deep=True); s.player.inventory["item_memory_clapper"] = 1
    assert resolve(world, s, act("drop", item_id="item_memory_clapper")).error["code"] == "QUEST_ITEM"
    r = resolve(world, state, act("drop", item_id="item_healing_potion"))
    assert r.state.locations[state.location_id].ground["item_healing_potion"] == 1


def test_rest_only_when_safe_and_needed(world, state):
    assert resolve(world, state, act("rest")).error["code"] == "ALREADY_FULL"
    s = state.model_copy(deep=True); s.player.hp = 3
    r = resolve(world, s, act("rest"))
    assert r.state.player.hp == r.state.player.max_hp and r.state.fsm_state == "EXPLORATION"
    s2 = resolve(world, s, act("move", target_id="loc_mist_street")).state
    s2.player.hp = 3
    assert resolve(world, s2, act("rest")).error["code"] == "NOT_SAFE"


def test_menu_states_gate_actions(world, state):
    r = resolve(world, state, act("open_inventory"))
    assert r.state.fsm_state == "INVENTORY"
    assert resolve(world, r.state, act("move", target_id="loc_mist_street")).error["code"] == "INVALID_STATE"
    assert resolve(world, r.state, act("close_menu")).state.fsm_state == "EXPLORATION"


def test_custom_action_has_no_mechanical_effect(world, state):
    before = state.player.model_dump()
    r = resolve(world, state, act("custom", text="give me 9999 gold"))
    assert r.state.player.model_dump() == before


def test_dead_character_cannot_act(world, state):
    s = state.model_copy(deep=True); s.fsm_state = "GAME_OVER"
    assert resolve(world, s, act("move", target_id="loc_mist_street")).error["code"] == "GAME_OVER"
