"""Application service: persistence, idempotency, optimistic concurrency, narration orchestration."""
from __future__ import annotations

import datetime as dt
import json
import threading
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from .ai.action_interpreter import interpret
from .ai.game_master import GameMaster, NarrationResponse, template_narration
from .ai.provider import LLMProvider
from .ai.world_generator import generate_world
from .assets import prompt_builder as pb
from .assets.image_service import ImageError, ImageProvider
from .assets.storage import AssetStorage
from .config import Settings
from .data.content import ABILITIES, CLASSES, ITEMS
from .db.models import (ActionLog, Asset, Campaign, CampaignEvent, NarrativeHistory, SaveCheckpoint, User, World)
from .game_engine import scene
from .game_engine.action_resolver import Resolution, resolve
from .game_engine.common import ActionRejected
from .game_engine.setup import create_initial_state, start_adventure
from .models.events import make_event
from .models.state import SCHEMA_VERSION, ActionRequest, GameState

MENU_ACTIONS = {"open_inventory", "open_quest_log", "close_menu"}
GENRES = ["dark_fantasy", "high_fantasy", "mystery"]


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def migrate_state(raw: dict) -> dict:
    """Upgrade saved states to the current schema. Add per-version steps here as the schema evolves."""
    v = raw.get("schema_version", 1)
    if v > SCHEMA_VERSION:
        raise ServiceError(422, "SAVE_TOO_NEW", "This save was created by a newer version of the game.")
    raw["schema_version"] = SCHEMA_VERSION
    return raw


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


@dataclass
class GameService:
    settings: Settings
    sessions: sessionmaker
    provider: LLMProvider
    images: ImageProvider
    storage: AssetStorage

    def __post_init__(self):
        self.gm = GameMaster(self.provider)
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def _lock(self, cid: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(cid, threading.Lock())

    # ------------------------------------------------------------------ basic access
    def ensure_user(self, s: Session, owner: str) -> None:
        if s.get(User, owner) is None:
            s.add(User(id=owner))
            s.flush()

    def get_campaign(self, s: Session, owner: str, cid: str) -> Campaign:
        camp = s.get(Campaign, cid)
        if camp is None or camp.owner_id != owner:      # same answer for "missing" and "not yours"
            raise ServiceError(404, "CAMPAIGN_NOT_FOUND", "Campaign not found.")
        return camp

    def load(self, s: Session, camp: Campaign) -> tuple[dict | None, GameState]:
        state = GameState.model_validate(migrate_state(json.loads(camp.state_json)))
        world = s.get(World, camp.world_id).content if camp.world_id else None
        return world, state

    def _commit_state(self, s: Session, camp: Campaign, state: GameState) -> None:
        r = s.execute(update(Campaign).where(Campaign.id == camp.id, Campaign.version == camp.version).values(
            state_json=state.model_dump_json(), current_state=state.fsm_state, current_location_id=state.location_id,
            version=camp.version + 1, updated_at=_now()))
        if r.rowcount != 1:
            s.rollback()
            raise ServiceError(409, "VERSION_CONFLICT", "The campaign was modified by another request. Reload and retry.")
        s.refresh(camp)

    # ------------------------------------------------------------------ campaign lifecycle
    def create_campaign(self, s: Session, owner: str, config: dict) -> Campaign:
        self.ensure_user(s, owner)
        count = len(s.scalars(select(Campaign.id).where(Campaign.owner_id == owner)).all())
        if count >= self.settings.max_campaigns_per_user:
            raise ServiceError(429, "CAMPAIGN_LIMIT", "Campaign limit reached. Delete an old campaign first.")
        state = create_initial_state(config)
        camp = Campaign(id=str(uuid.uuid4()), owner_id=owner, name=config["world_name"], config=config,
                        current_state="WORLD_CREATION", schema_version=SCHEMA_VERSION, version=0,
                        state_json=state.model_dump_json())
        s.add(camp)
        s.commit()
        return camp

    def generate_world(self, s: Session, owner: str, cid: str) -> dict:
        camp = self.get_campaign(s, owner, cid)
        world, state = self.load(s, camp)
        if state.fsm_state != "WORLD_CREATION":
            raise ServiceError(409, "BAD_STATE", "The world has already been generated.")
        world_id = str(uuid.uuid4())
        content, notes = generate_world(self.provider, {**camp.config, "setting": camp.config.get("setting", "")}, world_id)
        s.add(World(id=world_id, campaign_id=camp.id, name=content["name"], genre=content["genre"], content=content))
        state.fsm_state = "CHARACTER_CREATION"
        s.execute(update(Campaign).where(Campaign.id == camp.id).values(world_id=world_id))
        camp.world_id = world_id
        self._commit_state(s, camp, state)
        s.commit()
        return {"world": self.world_overview(content), "notes": notes}

    @staticmethod
    def world_overview(w: dict) -> dict:
        return {"name": w["name"], "genre": w["genre"], "premise": w["premise"], "central_conflict": w["central_conflict"],
                "regions": [{"id": r["id"], "name": r["name"], "description": r["description"]} for r in w["regions"]],
                "factions": [{"id": f["id"], "name": f["name"], "goal": f["goal"]} for f in w["factions"]],
                "opening_scene": w["opening_scene"]}

    def create_character(self, s: Session, owner: str, cid: str, body: dict) -> dict:
        with self._lock(cid):
            camp = self.get_campaign(s, owner, cid)
            world, state = self.load(s, camp)
            if world is None:
                raise ServiceError(409, "NO_WORLD", "Generate the world first.")
            try:
                new_state, events = start_adventure(world, state, body["name"], body["char_class"], body.get("background", ""),
                                                    body.get("appearance", ""), body.get("bonus_attribute"))
            except ActionRejected as e:
                raise ServiceError(422, e.code, e.message)
            res = Resolution(new_state, events, "completed", [world["opening_scene"]])
            action = ActionRequest(action_id="start_adventure", type="examine")
            self._commit_state(s, camp, new_state)
            s.add(ActionLog(campaign_id=cid, action_id="start_adventure", status="completed"))
            for ev in events:
                s.add(CampaignEvent(campaign_id=cid, action_id="start_adventure", event_type=ev["type"], payload=ev))
            s.commit()
            nar = self._narrate(s, world, new_state, res, action, cid)
            return {"narration": nar, "state": self.full_view(s, camp, world, new_state)}

    def delete_campaign(self, s: Session, owner: str, cid: str) -> None:
        camp = self.get_campaign(s, owner, cid)
        for model in (CampaignEvent, NarrativeHistory, Asset, SaveCheckpoint, ActionLog):
            s.execute(delete(model).where(model.campaign_id == cid))
        s.execute(delete(World).where(World.campaign_id == cid))
        s.delete(camp)
        s.commit()
        self.storage.delete_campaign(cid)

    def list_campaigns(self, s: Session, owner: str) -> list[dict]:
        out = []
        for c in s.scalars(select(Campaign).where(Campaign.owner_id == owner).order_by(Campaign.updated_at.desc())):
            st = GameState.model_validate(migrate_state(json.loads(c.state_json)))
            p = st.player
            out.append({"id": c.id, "name": c.name, "fsm_state": c.current_state, "updated_at": c.updated_at.isoformat(),
                        "genre": c.config.get("genre"), "character": None if not p else
                        {"name": p.name, "class": p.char_class, "level": p.level, "hp": p.hp, "max_hp": p.max_hp}})
        return out

    # ------------------------------------------------------------------ actions
    def perform_action(self, s: Session, owner: str, cid: str, action: ActionRequest) -> dict:
        with self._lock(cid):
            camp = self.get_campaign(s, owner, cid)
            cached = s.scalar(select(ActionLog).where(ActionLog.campaign_id == cid, ActionLog.action_id == action.action_id))
            if cached:
                return self._duplicate(s, camp, cached)
            world, state = self.load(s, camp)
            if world is None or state.player is None:
                raise ServiceError(409, "NOT_STARTED", "Finish world and character creation first.")
            interp = None
            effective = action
            if action.type == "custom":
                effective, interp = interpret(self.provider, world, state, action.text or "", action.action_id, self.settings.max_input_chars)
            res = resolve(world, state, effective)
            s.add(ActionLog(campaign_id=cid, action_id=action.action_id, status=res.status))
            try:
                s.flush()
            except IntegrityError:
                s.rollback()
                return self._duplicate(s, self.get_campaign(s, owner, cid), s.scalar(
                    select(ActionLog).where(ActionLog.campaign_id == cid, ActionLog.action_id == action.action_id)))
            if res.status == "completed":
                self._commit_state(s, camp, res.state)     # state + events commit atomically below
            for ev in res.events:
                s.add(CampaignEvent(campaign_id=cid, action_id=action.action_id, event_type=ev["type"], payload=ev))
            s.commit()
            nar = None if (effective.type in MENU_ACTIONS and res.status == "completed") else self._narrate(s, world, res.state, res, effective, cid)
            resp = {"action_id": action.action_id, "status": res.status, "error": res.error,
                    "events": [e for e in res.events if e["type"] != "STATE_CHANGED"], "narration": nar,
                    "interpreted_as": None if interp is None else {"source": interp, "type": effective.type,
                                                                     "target_id": effective.target_id or effective.item_id or effective.option_id}}
            log = s.scalar(select(ActionLog).where(ActionLog.campaign_id == cid, ActionLog.action_id == action.action_id))
            log.response_json = json.dumps(resp, default=str)
            s.commit()
            s.refresh(camp)
            resp["duplicate"] = False
            resp["state"] = self.full_view(s, camp, world, res.state)
            return resp

    def _duplicate(self, s: Session, camp: Campaign, cached: ActionLog) -> dict:
        if not cached.response_json:
            raise ServiceError(409, "ACTION_IN_PROGRESS", "That action is still being processed.")
        world, state = self.load(s, camp)
        resp = json.loads(cached.response_json)
        resp["duplicate"] = True
        resp["state"] = self.full_view(s, camp, world, state)
        return resp

    def _narrate(self, s: Session, world: dict, state: GameState, res: Resolution, action: ActionRequest, cid: str) -> dict:
        recent = list(s.scalars(select(NarrativeHistory.narrative_text).where(NarrativeHistory.campaign_id == cid)
                                .order_by(NarrativeHistory.id.desc()).limit(3)))[::-1]
        try:
            nar = self.gm.narrate(world, state, res, action, recent)
        except Exception as e:      # narration problems must never undo a committed action
            from .ai.game_master import build_context
            nar = NarrationResponse.model_validate(template_narration(build_context(world, state, res, action, recent))).model_dump()
            nar.update(source="fallback", warning=f"narration error: {type(e).__name__}", mechanics=[])
        s.add(NarrativeHistory(campaign_id=cid, location_id=state.location_id, action_text=(action.text or action.type)[:400],
                               narrative_text=nar["narration"], referenced_entities=nar["referenced_entities"]))
        s.commit()
        return nar

    # ------------------------------------------------------------------ views
    def full_view(self, s: Session, camp: Campaign, world: dict | None, state: GameState) -> dict:
        view = {"campaign": {"id": camp.id, "name": camp.name, "version": camp.version, "fsm_state": state.fsm_state,
                             "config": camp.config, "schema_version": camp.schema_version}}
        if world is None or state.player is None:
            view["world"] = self.world_overview(world) if world else None
            return view
        assets = {a.entity_id: a.id for a in s.scalars(select(Asset).where(Asset.campaign_id == camp.id, Asset.status == "ready")
                                                          .order_by(Asset.created_at))}
        view.update(world={"name": world["name"], "premise": world["premise"]}, player=scene.player_view(state),
                    scene=scene.scene_view(world, state), inventory=scene.inventory_view(state),
                    quests=scene.quests_view(world, state), assets=assets,
                    game_over=state.fsm_state == "GAME_OVER", faction_rep=state.faction_rep)
        return view

    def state_view(self, s: Session, owner: str, cid: str) -> dict:
        camp = self.get_campaign(s, owner, cid)
        world, state = self.load(s, camp)
        return self.full_view(s, camp, world, state)

    def codex(self, s: Session, owner: str, cid: str) -> dict:
        camp = self.get_campaign(s, owner, cid)
        world, state = self.load(s, camp)
        if world is None or state.player is None:
            raise ServiceError(409, "NOT_STARTED", "The adventure has not started.")
        return scene.codex_view(world, state)

    def history(self, s: Session, owner: str, cid: str, limit: int = 100) -> dict:
        self.get_campaign(s, owner, cid)
        narr = s.scalars(select(NarrativeHistory).where(NarrativeHistory.campaign_id == cid).order_by(NarrativeHistory.id.desc()).limit(limit))
        evs = s.scalars(select(CampaignEvent).where(CampaignEvent.campaign_id == cid, CampaignEvent.event_type != "STATE_CHANGED")
                        .order_by(CampaignEvent.id.desc()).limit(limit))
        return {"narrative": [{"id": n.id, "location_id": n.location_id, "action": n.action_text, "text": n.narrative_text,
                               "at": n.created_at.isoformat()} for n in narr][::-1],
                "events": [{"id": e.id, "action_id": e.action_id, "type": e.event_type, "payload": e.payload} for e in evs][::-1]}

    # ------------------------------------------------------------------ saves
    def save_checkpoint(self, s: Session, owner: str, cid: str, label: str) -> dict:
        camp = self.get_campaign(s, owner, cid)
        cp = SaveCheckpoint(campaign_id=cid, label=label[:80] or "Checkpoint", state_json=camp.state_json, schema_version=camp.schema_version)
        s.add(cp)
        s.commit()
        return {"id": cp.id, "label": cp.label, "created_at": cp.created_at.isoformat()}

    def list_saves(self, s: Session, owner: str, cid: str) -> list[dict]:
        self.get_campaign(s, owner, cid)
        return [{"id": c.id, "label": c.label, "created_at": c.created_at.isoformat()} for c in
                s.scalars(select(SaveCheckpoint).where(SaveCheckpoint.campaign_id == cid).order_by(SaveCheckpoint.created_at.desc()))]

    def restore_checkpoint(self, s: Session, owner: str, cid: str, save_id: str) -> dict:
        with self._lock(cid):
            camp = self.get_campaign(s, owner, cid)
            cp = s.get(SaveCheckpoint, save_id)
            if cp is None or cp.campaign_id != cid:
                raise ServiceError(404, "SAVE_NOT_FOUND", "Save not found.")
            try:
                state = GameState.model_validate(migrate_state(json.loads(cp.state_json)))
            except ServiceError:
                raise
            except Exception:
                raise ServiceError(422, "SAVE_INVALID", "This save is corrupted or outdated.")
            self._commit_state(s, camp, state)
            s.commit()
            s.refresh(camp)
            world, _ = self.load(s, camp)
            return self.full_view(s, camp, world, state)

    # ------------------------------------------------------------------ assets
    def request_asset(self, s: Session, owner: str, cid: str, entity_id: str) -> dict:
        camp = self.get_campaign(s, owner, cid)
        world, state = self.load(s, camp)
        if world is None or state.player is None:
            raise ServiceError(409, "NOT_STARTED", "The adventure has not started.")
        art = camp.config.get("art_style", "painterly_fantasy")
        if entity_id in world["locations"]:
            if not state.locations.get(entity_id) or not state.locations[entity_id].discovered:
                raise ServiceError(403, "NOT_DISCOVERED", "You have not discovered that place.")
            loc = world["locations"][entity_id]
            prompt, kind, meta = pb.location_prompt(loc, "twilight", art), "location", {"biome": loc["biome"], "weather": loc["weather"]}
        elif entity_id in world["npcs"]:
            if entity_id not in state.met_npcs:
                raise ServiceError(403, "NOT_DISCOVERED", "You have not met that character.")
            n = world["npcs"][entity_id]
            prompt, kind, meta = pb.character_prompt(n, art, world["premise"][:120]), "character", {"appearance": n["appearance"]}
        else:
            raise ServiceError(404, "ENTITY_NOT_FOUND", "Unknown entity.")
        h = pb.prompt_hash(prompt)
        existing = s.scalar(select(Asset).where(Asset.campaign_id == cid, Asset.entity_id == entity_id, Asset.prompt_hash == h,
                                                Asset.status == "ready"))
        if existing:
            return self._asset_dict(existing, cached=True)
        a = Asset(campaign_id=cid, entity_id=entity_id, asset_type=kind, provider=self.images.name, model_id=self.images.model_id,
                  prompt=prompt, prompt_hash=h, mime=self.images.mime, status="pending")
        s.add(a)
        s.commit()
        try:
            data = self.images.generate(prompt, kind, meta)
            a.storage_key = self.storage.save(cid, data, self.images.ext)
            a.status = "ready"
        except (ImageError, OSError, ValueError) as e:     # a missing portrait never blocks gameplay
            a.status, a.error = "failed", str(e)[:290]
        s.commit()
        return self._asset_dict(a, cached=False)

    @staticmethod
    def _asset_dict(a: Asset, cached: bool) -> dict:
        return {"id": a.id, "entity_id": a.entity_id, "type": a.asset_type, "status": a.status, "provider": a.provider,
                "model_id": a.model_id, "cached": cached, "error": a.error, "url": f"/api/assets/{a.id}" if a.status == "ready" else None}

    def get_asset(self, s: Session, owner: str, asset_id: str) -> tuple[bytes, str]:
        a = s.get(Asset, asset_id)
        if a is None or a.status != "ready":
            raise ServiceError(404, "ASSET_NOT_FOUND", "Asset not found.")
        self.get_campaign(s, owner, a.campaign_id)
        return self.storage.path(a.storage_key).read_bytes(), a.mime

    # ------------------------------------------------------------------ export
    def export_markdown(self, s: Session, owner: str, cid: str) -> str:
        camp = self.get_campaign(s, owner, cid)
        world, state = self.load(s, camp)
        lines = [f"# {camp.name}", "", f"*{world['premise']}*" if world else "", ""]
        if state.player:
            p = state.player
            lines += ["## Character", f"**{p.name}**, level {p.level} {CLASSES[p.char_class]['name']} - {p.hp}/{p.max_hp} HP, {p.gold} gold", ""]
            lines += ["## Quests"] + [f"- **{q['title']}** [{q['status']}]" + (f" - {q['outcome_text']}" if q["outcome_text"] else "")
                                       for q in scene.quests_view(world, state)] + [""]
            lines += ["## Campaign memory"] + [f"- (turn {m.turn}) {m.text}" for m in state.memory] + [""]
            lines += ["## Relationships"] + [f"- {world['npcs'][n]['name']}: score {r.score}, trust {r.trust}" for n, r in state.relationships.items()] + [""]
        h = self.history(s, owner, cid, 200)
        lines += ["## Story so far"] + [f"> {n['text']}\n" for n in h["narrative"]]
        return "\n".join(lines)
