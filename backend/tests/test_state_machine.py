import pytest
from app.game_engine import state_machine as fsm
from app.models.state import FSM_STATES, GameState


def test_all_states_have_transition_entries():
    assert set(fsm.TRANSITIONS) == set(FSM_STATES)


def test_game_over_to_combat_rejected():
    s = GameState(fsm_state="GAME_OVER")
    with pytest.raises(fsm.InvalidTransition):
        fsm.transition(s, "COMBAT")


def test_valid_transition_chain():
    s = GameState(fsm_state="MAIN_MENU")
    for dst in ["WORLD_CREATION", "CHARACTER_CREATION", "EXPLORATION", "DIALOGUE", "EXPLORATION", "COMBAT", "EXPLORATION"]:
        fsm.transition(s, dst)
    assert s.fsm_state == "EXPLORATION"


def test_main_menu_cannot_jump_to_exploration():
    assert not fsm.can_transition("MAIN_MENU", "EXPLORATION")


def test_actions_gated_by_state():
    s = GameState(fsm_state="COMBAT")
    assert fsm.action_allowed(s, "attack") and not fsm.action_allowed(s, "move")
    s.fsm_state = "DIALOGUE"
    assert not fsm.action_allowed(s, "attack")
