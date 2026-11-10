from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..data.content import ABILITIES, ATTR_SHORT, CLASSES, ITEMS
from ..models.api import AssetIn, CampaignConfig, CharacterIn, InventoryActionIn, QuestActionIn, SaveIn
from ..models.state import ActionRequest
from ..service import GENRES, GameService
from .deps import PLAYER_ID, get_owner, get_service, get_session, limit

router = APIRouter(prefix="/api")


@router.get("/health")
def health(svc: GameService = Depends(get_service)):
    return {"status": "ok", "providers": svc.settings.provider_status()}


@router.get("/meta")
def meta(svc: GameService = Depends(get_service)):
    return {"classes": {k: {**v, "ability_details": [{"id": a, **ABILITIES[a]} for a in v["abilities"]],
                            "equipment_details": {s: ITEMS[i]["name"] for s, i in v["equipment"].items()}} for k, v in CLASSES.items()},
            "genres": GENRES, "attributes": ATTR_SHORT, "providers": svc.settings.provider_status()}


@router.post("/campaigns", status_code=201)
def create_campaign(cfg: CampaignConfig, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                    svc: GameService = Depends(get_service), _=Depends(limit("generate"))):
    camp = svc.create_campaign(s, owner, cfg.model_dump())
    return {"id": camp.id, "name": camp.name, "fsm_state": camp.current_state}


@router.get("/campaigns")
def list_campaigns(owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.list_campaigns(s, owner)


@router.get("/campaigns/{cid}")
def get_campaign(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.state_view(s, owner, cid)


@router.get("/campaigns/{cid}/state")
def get_state(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.state_view(s, owner, cid)


@router.delete("/campaigns/{cid}", status_code=204)
def delete_campaign(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    svc.delete_campaign(s, owner, cid)
    return Response(status_code=204)


@router.post("/campaigns/{cid}/world")
def generate_world(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                   svc: GameService = Depends(get_service), _=Depends(limit("generate"))):
    return svc.generate_world(s, owner, cid)


@router.post("/campaigns/{cid}/character")
def create_character(cid: str, body: CharacterIn, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                     svc: GameService = Depends(get_service)):
    return svc.create_character(s, owner, cid, body.model_dump())


@router.post("/campaigns/{cid}/actions")
def submit_action(cid: str, action: ActionRequest, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                  svc: GameService = Depends(get_service), _=Depends(limit("action"))):
    return svc.perform_action(s, owner, cid, action)


@router.get("/campaigns/{cid}/inventory")
def get_inventory(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.state_view(s, owner, cid).get("inventory")


@router.post("/campaigns/{cid}/inventory/actions")
def inventory_action(cid: str, body: InventoryActionIn, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                     svc: GameService = Depends(get_service), _=Depends(limit("action"))):
    t = {"use": "use_item", "equip": "equip", "unequip": "unequip", "drop": "drop"}[body.action]
    return svc.perform_action(s, owner, cid, ActionRequest(action_id=body.action_id, type=t, item_id=body.item_id))


@router.get("/campaigns/{cid}/quests")
def get_quests(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.state_view(s, owner, cid).get("quests")


@router.post("/campaigns/{cid}/quests/{qid}/actions")
def quest_action(cid: str, qid: str, body: QuestActionIn, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                 svc: GameService = Depends(get_service), _=Depends(limit("action"))):
    return svc.perform_action(s, owner, cid, ActionRequest(action_id=body.action_id, type="abandon_quest", target_id=qid))


@router.get("/campaigns/{cid}/codex")
def codex(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.codex(s, owner, cid)


@router.get("/campaigns/{cid}/history")
def history(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.history(s, owner, cid)


@router.get("/campaigns/{cid}/export")
def export(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return Response(svc.export_markdown(s, owner, cid), media_type="text/markdown")


@router.post("/campaigns/{cid}/save", status_code=201)
def save(cid: str, body: SaveIn, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.save_checkpoint(s, owner, cid, body.label)


@router.get("/campaigns/{cid}/saves")
def saves(cid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.list_saves(s, owner, cid)


@router.post("/campaigns/{cid}/saves/{sid}/restore")
def restore(cid: str, sid: str, owner: str = Depends(get_owner), s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    return svc.restore_checkpoint(s, owner, cid, sid)


@router.post("/campaigns/{cid}/assets")
def request_asset(cid: str, body: AssetIn, owner: str = Depends(get_owner), s: Session = Depends(get_session),
                  svc: GameService = Depends(get_service), _=Depends(limit("asset"))):
    return svc.request_asset(s, owner, cid, body.entity_id)


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str, player: str | None = Query(default=None), x_player_id: str | None = Header(default=None),
              s: Session = Depends(get_session), svc: GameService = Depends(get_service)):
    # <img> tags cannot send headers, so the player id may also be given as ?player= for asset fetches only.
    pid = x_player_id or player
    if not pid or not PLAYER_ID.match(pid):
        raise HTTPException(401, {"code": "MISSING_PLAYER_ID", "message": "A valid player id is required."})
    data, mime = svc.get_asset(s, pid, asset_id)
    return Response(data, media_type=mime, headers={"Cache-Control": "private, max-age=86400", "X-Content-Type-Options": "nosniff",
                                                    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"})
