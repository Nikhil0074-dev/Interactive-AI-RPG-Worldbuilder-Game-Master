from conftest import act, make_state
from app.game_engine.action_resolver import resolve, visible_options
from app.game_engine.progression_engine import award_xp, xp_for_level
from app.game_engine import effects


def do(world, s, t, **kw):
    r = resolve(world, s, act(t, **kw))
    assert r.status == "completed", r.error
    return r.state


def talk_choose(world, s, npc, *opts):
    s = do(world, s, "talk", target_id=npc)
    for o in opts:
        s = do(world, s, "dialogue_choice", option_id=o)
    if s.fsm_state == "DIALOGUE":
        s = do(world, s, "end_dialogue")
    return s


def beat_ringer(world, s):
    s = s.model_copy(deep=True)
    s.player.max_hp = s.player.hp = 900
    s = do(world, s, "move", target_id="loc_mist_street")
    s = do(world, s, "move", target_id="loc_hollow_belfry")
    for _ in range(60):
        if s.fsm_state != "COMBAT":
            break
        s = do(world, s, "attack")
    assert s.fsm_state == "EXPLORATION"
    return do(world, s, "move", target_id="loc_mist_street")


def test_quest_locked_until_prerequisite(world, state):
    assert state.quests["q_main_bell"].status == "LOCKED"
    s = talk_choose(world, state, "npc_orsin", "o_ask_bell")
    assert s.quests["q_main_bell"].status == "AVAILABLE"
    ids = [o["id"] for o in visible_options(world, s, "npc_orsin")]
    assert "o_accept_bell" in ids and "o_decline_bell" in ids


def test_accept_and_decline(world, state):
    s = talk_choose(world, state, "npc_orsin", "o_ask_bell", "o_decline_bell")
    assert s.quests["q_main_bell"].status == "AVAILABLE" and s.flags["declined_bell"]
    s = talk_choose(world, s, "npc_orsin", "o_accept_bell")
    assert s.quests["q_main_bell"].status == "ACTIVE"


def test_cannot_start_quest_unavailable(world, state):
    s = do(world, state, "talk", target_id="npc_orsin")
    r = resolve(world, s, act("dialogue_choice", option_id="o_accept_bell"))
    assert r.error["code"] == "OPTION_UNAVAILABLE"


def test_retroactive_objectives_world_remembers(world, state):
    s = beat_ringer(world, state)     # clapper obtained BEFORE accepting the quest
    s = do(world, s, "move", target_id="loc_veyr_gate")
    s = talk_choose(world, s, "npc_orsin", "o_ask_bell", "o_accept_bell")
    done = s.quests["q_main_bell"].completed_objectives
    assert {"reach_belfry", "defeat_ringer", "take_clapper"} <= set(done)
    assert s.quests["q_main_bell"].status == "ACTIVE"


def test_branch_sell_clapper(world, state):
    s = beat_ringer(world, state)
    s = do(world, s, "move", target_id="loc_veyr_gate")
    s = talk_choose(world, s, "npc_orsin", "o_ask_bell", "o_accept_bell")
    gold = s.player.gold
    s = talk_choose(world, s, "npc_orsin", "o_sell_clapper")
    q = s.quests["q_main_bell"]
    assert q.status == "COMPLETED" and q.outcome == "sold"
    assert s.player.gold == gold + 120 + 60 and "item_memory_clapper" not in s.player.inventory
    assert s.relationships["npc_maren"].score == -15
    assert "sold_memory_clapper" in s.relationships["npc_maren"].known_player_actions
    assert any("sold the Memory Clapper" in m.text for m in s.memory)
    assert s.faction_rep["faction_lantern_order"] == -15


def test_branch_return_clapper_via_shrine(world, state):
    s = beat_ringer(world, state)
    s = do(world, s, "move", target_id="loc_veyr_gate")
    s = talk_choose(world, s, "npc_orsin", "o_ask_bell", "o_accept_bell")
    s.flags["shrine_path_known"] = True
    s = do(world, s, "move", target_id="loc_mist_street")
    s = do(world, s, "move", target_id="loc_forgotten_shrine")
    s = talk_choose(world, s, "npc_maren", "o_return_order")
    q = s.quests["q_main_bell"]
    assert q.outcome == "returned" and "item_lanternward_charm" in s.player.inventory
    s = talk_choose(world, s, "npc_maren")
    # relationship unlocks a blessing option
    assert "o_blessing" in [o["id"] for o in visible_options(world, do(world, s, "talk", target_id="npc_maren"), "npc_maren")]


def test_branch_keep_clapper(world, state):
    s = beat_ringer(world, state)
    s = do(world, s, "move", target_id="loc_veyr_gate")
    s = talk_choose(world, s, "npc_orsin", "o_ask_bell", "o_accept_bell")
    s.flags["shrine_path_known"] = True
    s = do(world, s, "move", target_id="loc_mist_street")
    s = do(world, s, "move", target_id="loc_forgotten_shrine")
    s = talk_choose(world, s, "npc_maren", "o_keep_clapper")
    assert s.quests["q_main_bell"].outcome == "kept" and s.flags["clapper_power"]
    assert "item_memory_clapper" in s.player.inventory
    # the decision is final: cannot also sell it
    ids = [o["id"] for o in visible_options(world, do(world, s, "move", target_id="loc_mist_street") and s, "npc_orsin")]
    assert "o_sell_clapper" not in ids


def test_rewards_cannot_be_claimed_twice(world, state):
    s = beat_ringer(world, state)
    s = do(world, s, "move", target_id="loc_veyr_gate")
    s = talk_choose(world, s, "npc_orsin", "o_ask_bell", "o_accept_bell", "o_sell_clapper")
    xp = s.player.xp
    r = resolve(world, s, act("talk", target_id="npc_orsin"))
    r = resolve(world, r.state, act("dialogue_choice", option_id="o_sell_clapper"))
    assert r.error["code"] == "OPTION_UNAVAILABLE"
    assert s.player.xp == xp


def test_orsin_key_quest_unlocks_secret_route(world, state):
    s = talk_choose(world, state, "npc_orsin", "o_ask_chest", "o_accept_key")
    assert s.quests["q_orsin_key"].status == "ACTIVE"
    s = do(world, s, "move", target_id="loc_mist_street")
    for _ in range(15):
        if "hid_key" in s.locations["loc_mist_street"].found_hidden:
            break
        r = resolve(world, s, act("search"))
        s = r.state
    s = do(world, s, "take", item_id="item_orsin_key")
    assert "find_key" in s.quests["q_orsin_key"].completed_objectives
    s = do(world, s, "move", target_id="loc_veyr_gate")
    xp = s.player.xp
    s = talk_choose(world, s, "npc_orsin", "o_give_key")
    assert s.quests["q_orsin_key"].status == "COMPLETED" and s.flags["merchant_helped"]
    assert s.player.xp >= xp + 80
    assert s.quests["q_echoes"].status == "ACTIVE"          # hidden quest auto-started
    assert not s.locations["loc_veyr_gate"].objects["obj_iron_chest"].locked
    assert "item_orsin_key" not in s.player.inventory
    s = do(world, s, "move", target_id="loc_mist_street")
    s = do(world, s, "move", target_id="loc_forgotten_shrine")      # reachable thanks to the memory of helping Orsin


def test_persuasion_uses_engine_dice_and_is_one_shot(world):
    results = set()
    for seed in range(1, 12):
        s = make_state(world, "bard", seed=seed)
        s = talk_choose(world, s, "npc_orsin", "o_persuade_shrine")
        results.add(bool(s.flags.get("shrine_path_known")))
        assert bool(s.flags.get("shrine_path_known")) != bool(s.flags.get("orsin_refused"))
        ids = [o["id"] for o in visible_options(world, s, "npc_orsin")]
        assert "o_persuade_shrine" not in ids
    assert results == {True, False}


def test_abandon_rules(world, state):
    s = talk_choose(world, state, "npc_orsin", "o_ask_chest", "o_accept_key")
    s = do(world, s, "abandon_quest", target_id="q_orsin_key")
    assert s.quests["q_orsin_key"].status == "ABANDONED"
    assert resolve(world, s, act("abandon_quest", target_id="q_orsin_key")).error["code"] == "QUEST_NOT_ACTIVE"


def test_levelling_is_engine_computed(world, state):
    s = state.model_copy(deep=True); ev = []
    hp0 = s.player.max_hp
    award_xp(s, xp_for_level(3), ev)
    assert s.player.level == 3 and s.player.max_hp > hp0
    assert [e for e in ev if e["type"] == "LEVEL_UP"].__len__() == 2


def test_merchant_discount_from_relationship(world, state):
    s = state.model_copy(deep=True)
    base = effects.buy_price(s, 15, "npc_orsin")
    s.relationships["npc_orsin"] = type(s.relationships.get("npc_orsin") or __import__("app.models.state", fromlist=["Relationship"]).Relationship())(trust=60)
    assert effects.buy_price(s, 15, "npc_orsin") < base == 15


def test_buying_requires_gold(world, state):
    s = state.model_copy(deep=True); s.player.gold = 5
    s = do(world, s, "talk", target_id="npc_orsin")
    ids = [o["id"] for o in visible_options(world, s, "npc_orsin")]
    assert "o_buy_potion" not in ids
