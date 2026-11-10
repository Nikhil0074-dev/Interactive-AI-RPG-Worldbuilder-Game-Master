# REST API

All endpoints except `/api/health`, `/api/meta` need an `X-Player-Id` header (8-64 chars `[A-Za-z0-9_-]`; the web client generates one). Campaigns
are owned by that id; other ids receive `404` (no existence leak). `GET /api/assets/{id}` also accepts `?player=` because `<img>` tags cannot send headers.
Errors: `{"detail": {"code": "...", "message": "..."}}`. Interactive docs: `http://localhost:8000/docs`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health`, `/api/meta` | Health + provider status; classes, abilities, genres |
| POST | `/api/campaigns` | Create campaign from config (rate-limited, per-user cap) |
| GET | `/api/campaigns` · `/{id}` · `/{id}/state` | List / full authoritative view |
| DELETE | `/api/campaigns/{id}` | Delete campaign, events, assets, saves |
| POST | `/api/campaigns/{id}/world` | Staged world generation → `CHARACTER_CREATION` |
| POST | `/api/campaigns/{id}/character` | Create character → `EXPLORATION`, opening narration |
| POST | `/api/campaigns/{id}/actions` | Submit an action (idempotent by `action_id`) |
| GET | `/api/campaigns/{id}/inventory` · POST `/inventory/actions` | Inventory view; use/equip/unequip/drop |
| GET | `/api/campaigns/{id}/quests` · POST `/quests/{qid}/actions` | Quest log; abandon |
| GET | `/api/campaigns/{id}/codex` · `/history` · `/export` | Discovered-only codex; events + narration; Markdown summary |
| POST/GET | `/api/campaigns/{id}/save` · `/saves` · POST `/saves/{sid}/restore` | Checkpoints |
| POST | `/api/campaigns/{id}/assets` | Request (cached) image for a discovered location/NPC |
| GET | `/api/assets/{asset_id}` | Fetch an authorised asset |

## Action request
```json
{ "action_id": "a_lq3x_9fk2", "type": "move", "target_id": "loc_mist_street" }
{ "action_id": "a_lq3x_9fl8", "type": "custom", "text": "I follow the sound of the bell" }
```
Types: `move examine take open search talk dialogue_choice end_dialogue attack ability flee use_item equip unequip drop rest open_inventory open_quest_log close_menu abandon_quest custom`.
Unknown fields are rejected (`422`) - the client cannot send state.

## Action response
```json
{ "action_id": "…", "status": "completed|rejected", "error": null,
  "events": [{"type": "PLAYER_ENTERED_LOCATION", "location_id": "loc_mist_street", "first_visit": true}],
  "narration": {"narration": "…", "scene_mood": "uneasy", "suggested_actions": [], "referenced_entities": [], "source": "mock|llm|fallback|engine", "warning": null, "mechanics": ["+15 XP"]},
  "interpreted_as": null, "duplicate": false, "state": { "…full authoritative view…" } }
```
Event types and required fields are defined in `backend/app/models/events.py` (`EVENT_SCHEMAS`).
