# Architecture

```
Browser (Next.js, Zustand, Web Audio)
   │  /api/*  (Next rewrites to FastAPI - no CORS, no secrets in the client)
   ▼
FastAPI  ── api/routes.py (validation, auth by X-Player-Id, rate limits)
   ▼
service.py  (GameService: transactions, idempotency, optimistic locking, narration orchestration)
   ├── game_engine/   deterministic rules (pure functions: (world, state, action) -> new state + typed events)
   │     state_machine · action_resolver · inventory · combat · quest · progression · effects · event_processor · scene (read models)
   ├── ai/            action_interpreter · game_master · memory_retriever · world_generator · providers (mock / OpenAI-compatible)
   ├── assets/        prompt_builder · image providers (procedural SVG / FLUX) · storage
   └── db/            SQLAlchemy models (SQLite default, PostgreSQL-ready)
```

## The central rule: AI narrates, the engine decides

```
Player action ──► (free text only) Interpreter ──► ActionRequest   (AI proposes, strict allow-list validates ids)
                                         │
                                         ▼
                  FSM guard ► rules validation ► dice (seeded, engine-side) ► state copy mutated ► typed events
                                         │                                         (rejections never mutate state)
                                         ▼
                     one DB transaction: ActionLog (unique action_id) + events + state (version check)
                                         │   ◄── committed here; nothing after this can roll it back
                                         ▼
               Game Master: context (scene, events, memory, relationships) ► provider ► schema + consistency validation
                                         │  invalid / error / timeout ► deterministic template narration
                                         ▼
                                  narration + mechanics log
```

* The engine works on a **deep copy** of the state; a rejected action returns the original state untouched.
* Dice use `random.Random(f"{seed}:{counter}")`, so the same seed and the same actions always give the same result
  (this is what makes tests, fuzzing and idempotent retries reliable).
* The LLM sees events *after* they happened. `validate_narration` rejects unknown entity ids, URLs/markup, schema violations
  and damage numbers that differ from the engine's.

## Data model

| Table | Purpose |
|---|---|
| `users` | Owner ids (created on first use of an `X-Player-Id`) |
| `campaigns` | Config, FSM state, location, `version` (optimistic lock), `state_json` (mutable authoritative state) |
| `worlds` | Validated static world graph (locations, NPCs, quests, lore) - separated from mutable state |
| `action_log` | One row per `action_id` (unique per campaign): idempotency + cached response |
| `campaign_events` | Typed event stream (audit/history/codex) |
| `narrative_history` | Narration text for "immediate memory" and the story log |
| `assets` | Generated image metadata: provider, model, prompt, prompt hash, storage key, status |
| `saves` | Checkpoints (full state snapshot + schema version) |

Mutable state is one JSON document per campaign, but it is small, validated by Pydantic (`extra="forbid"`), versioned
(`schema_version` + `migrate_state`) and written only through a version-checked `UPDATE`. Events, narrative and assets
are relational. Moving inventory/quests to their own tables is a mechanical next step if multi-user querying is needed.

## Finite state machine

States: `MAIN_MENU, WORLD_CREATION, CHARACTER_CREATION, EXPLORATION, DIALOGUE, COMBAT, INVENTORY, QUEST_LOG, TRAVEL, RESTING, GAME_OVER`.
`state_machine.TRANSITIONS` is the single transition table; `ALLOWED_ACTIONS` lists which actions each state accepts.
`TRAVEL` and `RESTING` are transient (entered and left inside one action), and `TRAVEL → COMBAT` models ambushes on arrival.

## Concurrency, idempotency, recovery

* Duplicate `action_id` → cached response is returned with `duplicate: true`; nothing is applied twice.
* Competing writers → `UPDATE ... WHERE version = :v`; loser gets `409 VERSION_CONFLICT` (the UI reloads).
* A per-campaign lock serialises actions inside one process. For multiple workers rely on the version check (or add Redis locks).
* Narration/provider failures degrade to template narration; image failures leave a placeholder; neither blocks play.
* Saves newer than the running schema return `SAVE_TOO_NEW`; corrupt saves return `SAVE_INVALID`.
