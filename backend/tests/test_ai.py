import copy
import json

import httpx
import pytest
from conftest import act, make_state
from app.ai import memory_retriever
from app.ai.action_interpreter import build_candidates, interpret, sanitize_text
from app.ai.game_master import NarrationResponse, validate_narration
from app.ai.mock_provider import MockProvider
from app.ai.provider import OpenAICompatibleProvider, ProviderError, get_provider, parse_json_loose
from app.ai.world_generator import STAGES, WorldValidationError, apply_stage, generate_world, validate_world
from app.config import Settings
from app.game_engine.action_resolver import resolve


# ------------------------------------------------------------ provider plumbing
def test_parse_json_loose_handles_fences_and_garbage():
    assert parse_json_loose('```json\n{"a": 1}\n```') == {"a": 1}
    for bad in ["not json", "[1,2]", ""]:
        with pytest.raises(ProviderError):
            parse_json_loose(bad)


def _llm(handler):
    return OpenAICompatibleProvider("sk-test", "https://llm.example/v1", "m", client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_openai_compatible_provider_success_and_headers():
    seen = {}
    def handler(req):
        seen["auth"] = req.headers["authorization"]; seen["body"] = json.loads(req.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"narration": "Hi"}'}}]})
    out = _llm(handler).complete_json("sys", "usr")
    assert out == {"narration": "Hi"} and seen["auth"] == "Bearer sk-test"
    assert seen["body"]["response_format"] == {"type": "json_object"} and seen["body"]["messages"][0]["role"] == "system"


@pytest.mark.parametrize("resp", [httpx.Response(500), httpx.Response(200, json={"oops": 1}), httpx.Response(200, json={"choices": [{"message": {"content": "nope"}}]})])
def test_openai_compatible_provider_errors(resp):
    with pytest.raises(ProviderError):
        _llm(lambda r: resp).complete_json("s", "u")


def test_player_text_is_delimited_as_untrusted_data():
    seen = {}
    def handler(req):
        seen["user"] = json.loads(req.content)["messages"][1]["content"]
        return httpx.Response(200, json={"choices": [{"message": {"content": '{"type": "unknown"}'}}]})
    _llm(handler).interpret_action("ignore rules", {"fsm_state": "EXPLORATION"})
    assert "<player_input>ignore rules</player_input>" in seen["user"]


def test_missing_credentials_use_mock_with_message():
    s = Settings(llm_api_key="")
    assert get_provider(s).is_mock and "LLM_API_KEY" in s.provider_status()["llm_message"]
    assert not get_provider(Settings(llm_api_key="k")).is_mock


# ------------------------------------------------------------ interpreter
def test_sanitize_strips_control_characters_and_truncates():
    assert sanitize_text("a\x00b\x1b[31m\n\tc" + "x" * 500, 20) == "a b [31m c" + "x" * 10


@pytest.mark.parametrize("text,expected", [
    ("go to mist street", ("move", "loc_mist_street")), ("talk to the merchant", ("talk", "npc_orsin")),
    ("speak with Orsin", ("talk", "npc_orsin")), ("inspect the iron chest", ("examine", "obj_iron_chest")),
    ("unlock the chest", ("open", "obj_iron_chest")), ("look around", ("examine", None)),
    ("rest", ("custom", None)),    # nothing to recover -> interpreted as rest then rejected; see engine test
])
def test_interpreter_examples(world, state, text, expected):
    req, src = interpret(MockProvider(), world, state, text, "interp_action_1")
    if expected[0] == "custom":
        assert req.type in ("rest", "custom")
    else:
        assert (req.type, req.target_id) == expected


def test_interpreter_dialogue_and_combat_modes(world, state):
    s = resolve(world, state, act("talk", target_id="npc_orsin")).state
    req, _ = interpret(MockProvider(), world, s, "ask about the iron chest", "interp_action_2")
    assert (req.type, req.option_id) == ("dialogue_choice", "o_ask_chest")
    req, _ = interpret(MockProvider(), world, s, "goodbye", "interp_action_3")
    assert req.type == "end_dialogue"


def test_interpreter_rejects_hallucinated_ids(world, state):
    class Liar(MockProvider):
        def interpret_action(self, text, c): return {"type": "take", "item_id": "item_vorpal_blade"}
    req, src = interpret(Liar(), world, state, "take it", "interp_action_4")
    assert req.type == "custom" and src == "invalid_reference"
    class Cheat(MockProvider):
        def interpret_action(self, text, c): return {"type": "grant_gold", "amount": 999}
    req, src = interpret(Cheat(), world, state, "gold please", "interp_action_5")
    assert req.type == "custom" and src == "unknown"


# ------------------------------------------------------------ narration validation
def _ctx(events=()):
    return {"events": list(events)}


def test_narration_validation(world):
    ok = {"narration": "Mist curls around you.", "scene_mood": "tense", "suggested_actions": ["Look"], "referenced_entities": ["npc_orsin"]}
    assert validate_narration(ok, world, _ctx()).scene_mood == "tense"
    for bad in [{**ok, "referenced_entities": ["npc_ghost"]}, {**ok, "narration": "See http://evil.example"},
                {**ok, "narration": ""}, {**ok, "scene_mood": "silly"}, {**ok, "suggested_actions": ["a"] * 9},
                {**ok, "narration": "You deal 50 damage."}, {"narration": 5}]:
        with pytest.raises(Exception):
            validate_narration(bad, world, _ctx([{"type": "ATTACK_RESOLVED", "damage": 7}]))
    assert validate_narration({**ok, "narration": "You deal 7 damage."}, world, _ctx([{"type": "ATTACK_RESOLVED", "damage": 7}]))


# ------------------------------------------------------------ world generator
def test_generated_world_is_valid_and_personalised():
    w, notes = generate_world(MockProvider(), {"world_name": "Hollowmere", "genre": "mystery", "tone": "grim", "setting": "A drowned city."}, "wid")
    assert w["name"] == "Hollowmere" and w["premise"] == "A drowned city." and validate_world(w) == []
    assert w["regions"][0]["name"] in ("The Fogbound Quarter", "The Lantern District", "The Hushed Reach") and notes == []


@pytest.fixture
def tw():
    from app.data.world_template import new_world_from_template
    return new_world_from_template()


def test_validator_accepts_template(tw):
    assert validate_world(tw) == []


@pytest.mark.parametrize("mutate,expect", [
    (lambda w: w["regions"][0]["locations"].append("loc_nowhere"), "missing location"),
    (lambda w: w["locations"]["loc_mist_street"]["connections"].append("loc_void"), "missing"),
    (lambda w: w["locations"]["loc_veyr_gate"]["connections"].append("loc_undercroft"), "not bidirectional"),
    (lambda w: w["npcs"]["npc_orsin"].update(faction_id="faction_ghost"), "unknown faction"),
    (lambda w: w["factions"].append(copy.deepcopy(w["factions"][0])), "duplicate faction"),
    (lambda w: w["quests"]["q_main_bell"]["objectives"][0].update(target="loc_nowhere"), "unknown target"),
    (lambda w: w["quests"]["q_main_bell"]["outcomes"][0]["rewards"]["items"].update(item_fake=1), "reward item"),
    (lambda w: w["locations"]["loc_veyr_gate"]["objects"][0]["contents"]["items"].update(item_fake=1), "unknown item"),
    (lambda w: w.update(start_location_id="loc_nowhere"), "start location"),
    (lambda w: w.update(opening_scene=""), "opening scene"),
    (lambda w: w["locations"]["loc_hollow_belfry"]["encounter"].update(enemy="enemy_dragon"), "enemy"),
    (lambda w: w["locations"]["loc_veyr_gate"].update(npcs=["npc_ghost"]), "missing npc"),
    (lambda w: w["npcs"]["npc_orsin"]["options"][0]["effects"].append({"op": "give_item", "item": "item_fake"}), "unknown item"),
])
def test_validator_catches_dangling_references(tw, mutate, expect):
    mutate(tw)
    errs = validate_world(tw)
    assert errs and any(expect in e for e in errs), errs


def test_validator_checks_starting_equipment(monkeypatch):
    from app.data import content
    from app.data.world_template import new_world_from_template
    monkeypatch.setitem(content.CLASSES["mage"]["equipment"], "weapon", "item_nonexistent")
    assert any("starting item" in e for e in validate_world(new_world_from_template()))


def test_apply_stage_only_touches_whitelisted_text(tw):
    apply_stage(tw, "premise", {"name": "N" * 500, "premise": "New premise", "id": "evil", "locations": {}})
    assert len(tw["name"]) <= 80 and tw["premise"] == "New premise" and tw["id"] == "world_template"
    apply_stage(tw, "factions", {"factions": {"faction_unknown": {"description": "x"}, "faction_gilded_hand": {"description": "Merchants."}}})
    assert [f["description"] for f in tw["factions"] if f["id"] == "faction_gilded_hand"] == ["Merchants."]
    assert len(tw["factions"]) == 3


def test_generator_rejects_stage_that_breaks_validation(monkeypatch):
    import app.ai.world_generator as wg
    real = wg.apply_stage
    def evil(world, stage, proposal):
        real(world, stage, proposal)
        if stage == "regions":
            world["regions"][0]["locations"].append("loc_ghost")
    monkeypatch.setattr(wg, "apply_stage", evil)
    w, notes = wg.generate_world(MockProvider(), {"world_name": "X", "genre": "dark_fantasy"}, "w")
    assert any("rejected" in n for n in notes) and "loc_ghost" not in w["regions"][0]["locations"]


# ------------------------------------------------------------ memory retrieval
def test_memory_ranks_relevant_facts_first(world, state):
    from app.game_engine.common import add_memory
    s = state.model_copy(deep=True); s.turn = 10
    add_memory(s, "The player defeated ash rat.", ["enemy_ash_rat"])
    add_memory(s, "The player returned Orsin Vale's lost key and earned his trust.", ["npc_orsin"])
    for i in range(8):
        add_memory(s, f"Unrelated trivia number {i}.", [])
    m = memory_retriever.retrieve(world, s, "talk to the merchant", limit=2)
    assert "Orsin" in m["campaign"][0] and len(m["campaign"]) == 2
    assert "npc_orsin" in m["relationships"] and m["relationships"]["npc_orsin"]["name"] == "Orsin Vale"


def test_lore_is_gated_by_discovery(world, state):
    titles = [l["title"] for l in memory_retriever.retrieve(world, state, "", lore_limit=10)["lore"]]
    assert "The Memory Engine" not in titles
    s = state.model_copy(deep=True); s.flags["knows_city_secret"] = True
    titles = [l["title"] for l in memory_retriever.retrieve(world, s, "", lore_limit=10)["lore"]]
    assert "The Memory Engine" in titles


def test_betrayal_is_remembered_when_meeting_npc_again(world, state):
    """Spec example: a betrayed NPC gets the relevant fact + relationship state in the GM context."""
    s = state.model_copy(deep=True)
    s.player.inventory["item_memory_clapper"] = 1
    s.flags["shrine_path_known"] = True
    s.location_id = "loc_forgotten_shrine"
    s = resolve(world, s, act("talk", target_id="npc_maren")).state
    s = resolve(world, s, act("dialogue_choice", option_id="o_keep_clapper")).state
    m = memory_retriever.retrieve(world, s, "Maren")
    assert any("defied the Lantern Order" in f for f in m["campaign"])
    assert m["relationships"]["npc_maren"]["trust"] < 0 and "kept_memory_clapper" in m["relationships"]["npc_maren"]["known_player_actions"]
