import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
from app.data.world_template import new_world_from_template
from app.game_engine.setup import create_initial_state, start_adventure
from app.models.state import ActionRequest

_n = {"i": 0}


def act(type_, **kw):
    _n["i"] += 1
    return ActionRequest(action_id=f"test_action_{_n['i']}", type=type_, **kw)


@pytest.fixture
def world():
    return new_world_from_template()


def make_state(world, cls="warrior", seed=1, **config):
    st = create_initial_state({"difficulty": "normal", **config}, seed=seed)
    st.fsm_state = "CHARACTER_CREATION"
    st, _ = start_adventure(world, st, "Tester", cls)
    return st


@pytest.fixture
def state(world):
    return make_state(world)
