"""Randomised play: whatever happens, the authoritative state must stay consistent."""
import random
import pytest
from conftest import act, make_state
from app.data.content import CLASSES
from app.game_engine.action_resolver import resolve
from app.game_engine.invariants import check_invariants
from app.game_engine.scene import available_actions
from app.models.state import ActionRequest, GameState

JUNK = [dict(type="move", target_id="loc_undercroft"), dict(type="take", item_id="item_memory_clapper"), dict(type="open", target_id="x"),
        dict(type="use_item", item_id="item_healing_potion"), dict(type="equip", item_id="item_chain_hauberk"), dict(type="drop", item_id="item_iron_sword"),
        dict(type="ability", ability_id="arcane_bolt"), dict(type="dialogue_choice", option_id="o_sell_clapper"), dict(type="attack"), dict(type="flee"),
        dict(type="rest"), dict(type="abandon_quest", target_id="q_main_bell"), dict(type="open_inventory"), dict(type="close_menu")]


@pytest.mark.parametrize("seed", range(14))
def test_random_play_keeps_state_consistent(world, seed):
    rng = random.Random(seed)
    s = make_state(world, list(CLASSES)[seed % 7], seed=seed)
    for i in range(200):
        acts = available_actions(world, s)
        kw = rng.choice(acts)["action"] if acts and rng.random() < 0.75 else rng.choice(JUNK)
        before = s.model_dump()
        r = resolve(world, s, ActionRequest(action_id=f"fz_{seed}_{i}", **kw))
        if r.status == "rejected":
            assert r.state.model_dump() == before, f"rejected action mutated state: {kw}"
        assert check_invariants(world, r.state) == [], (seed, i, kw)
        assert GameState.model_validate_json(r.state.model_dump_json()) == r.state
        s = r.state
        if s.fsm_state == "GAME_OVER":
            break


def test_invariant_checker_detects_corruption(world, state):
    bad = state.model_copy(deep=True)
    bad.player.hp = bad.player.max_hp + 5
    bad.player.inventory["item_iron_sword"] = 0
    bad.flags["clapper_sold"] = bad.flags["clapper_kept"] = True
    errs = check_invariants(world, bad)
    assert len(errs) >= 3
