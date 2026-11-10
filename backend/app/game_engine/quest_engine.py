"""Quest state machine: LOCKED -> AVAILABLE -> ACTIVE -> COMPLETED / FAILED / ABANDONED."""
from __future__ import annotations

from ..models.events import event_key, make_event
from ..models.state import GameState, QuestProgress
from .common import ActionRejected, add_memory, check_requires, set_flag
from . import inventory_engine as inv
from . import progression_engine as prog


def ensure_quests(world: dict, state: GameState) -> None:
    for qid in world["quests"]:
        state.quests.setdefault(qid, QuestProgress())


def refresh_availability(world: dict, state: GameState, events: list) -> None:
    """Promote LOCKED quests whose prerequisites are met; auto-start hidden quests."""
    ensure_quests(world, state)
    for qid, q in world["quests"].items():
        prog_ = state.quests[qid]
        if prog_.status == "LOCKED" and check_requires(world, state, q.get("prerequisites")):
            prog_.status = "AVAILABLE"
            events.append(make_event("QUEST_AVAILABLE", quest_id=qid))
            if q.get("auto_start"):
                start_quest(world, state, qid, events)


def start_quest(world: dict, state: GameState, quest_id: str, events: list) -> None:
    ensure_quests(world, state)
    if quest_id not in world["quests"]:
        raise ActionRejected("UNKNOWN_QUEST", f"Quest '{quest_id}' does not exist.")
    q = state.quests[quest_id]
    if q.status != "AVAILABLE":
        raise ActionRejected("QUEST_NOT_AVAILABLE", f"Quest cannot be started (status {q.status}).")
    q.status = "ACTIVE"
    q.started_turn = state.turn
    events.append(make_event("QUEST_STARTED", quest_id=quest_id))
    # The world remembers: objectives already satisfied earlier count retroactively.
    for obj in world["quests"][quest_id]["objectives"]:
        key = f'{obj["event"]}:{obj["target"]}'
        if key in state.seen_events and obj["id"] not in q.completed_objectives:
            q.completed_objectives.append(obj["id"])
            events.append(make_event("QUEST_OBJECTIVE_COMPLETED", quest_id=quest_id, objective_id=obj["id"]))
    _maybe_complete(world, state, quest_id, events)


def abandon_quest(world: dict, state: GameState, quest_id: str, events: list) -> None:
    ensure_quests(world, state)
    q = state.quests.get(quest_id)
    if q is None or q.status != "ACTIVE":
        raise ActionRejected("QUEST_NOT_ACTIVE", "Only active quests can be abandoned.")
    if world["quests"][quest_id].get("category") == "main":
        raise ActionRejected("MAIN_QUEST", "The main quest cannot be abandoned.")
    q.status = "ABANDONED"
    events.append(make_event("QUEST_ABANDONED", quest_id=quest_id))


def on_event(world: dict, state: GameState, ev: dict, events: list) -> None:
    key = event_key(ev)
    if key is None:
        return
    for qid, q in world["quests"].items():
        prog_ = state.quests.get(qid)
        if not prog_ or prog_.status != "ACTIVE":
            continue
        for obj in q["objectives"]:
            if obj["id"] in prog_.completed_objectives:
                continue
            if f'{obj["event"]}:{obj["target"]}' == key:
                prog_.completed_objectives.append(obj["id"])
                events.append(make_event("QUEST_OBJECTIVE_COMPLETED", quest_id=qid, objective_id=obj["id"]))
        _maybe_complete(world, state, qid, events)


def _maybe_complete(world: dict, state: GameState, qid: str, events: list) -> None:
    q = world["quests"][qid]
    prog_ = state.quests[qid]
    if prog_.status != "ACTIVE":
        return
    required = [o["id"] for o in q["objectives"] if not o.get("optional")]
    if not all(r in prog_.completed_objectives for r in required):
        return
    # Mark complete first so rewards can never be granted twice.
    prog_.status = "COMPLETED"
    prog_.completed_turn = state.turn
    outcome = None
    rewards = [q.get("rewards", {})]
    for o in q.get("outcomes", []):
        if state.flags.get(o["flag"]):
            outcome = o["id"]
            rewards.append(o.get("rewards", {}))
            add_memory(state, f'Quest "{q["title"]}" ended: {o["text"]}', [qid])
            break
    prog_.outcome = outcome
    events.append(make_event("QUEST_COMPLETED", quest_id=qid, outcome=outcome or "default"))
    if not outcome:
        add_memory(state, f'The player completed the quest "{q["title"]}".', [qid])
    for r in rewards:
        grant_rewards(world, state, r, events)


def grant_rewards(world: dict, state: GameState, r: dict, events: list) -> None:
    if r.get("xp"):
        prog.award_xp(state, r["xp"], events)
    if r.get("gold"):
        inv.change_gold(state, r["gold"], events)
    for item, qty in r.get("items", {}).items():
        inv.give_item(state, item, qty, "quest_reward", events)
    for flag, val in r.get("flags", {}).items():
        set_flag(world, state, flag, val, events)
