# AI design

Three questions, three owners:

| Question | Owner |
|---|---|
| What is the player trying to do? | `ai/action_interpreter.py` (provider-assisted, strictly validated) |
| Is it valid and what happens mechanically? | `game_engine/` (deterministic) |
| How is the outcome described? | `ai/game_master.py` (provider-assisted, validated, with template fallback) |

## Providers (`ai/provider.py`)
`LLMProvider` exposes `interpret_action`, `narrate`, `generate_world_stage` on top of one abstract `complete_json`.
* `MockProvider` - offline, deterministic (rule-based intent parsing, template narration/world stages). Default.
* `OpenAICompatibleProvider` - any `/chat/completions` endpoint with JSON mode. Enabled by `LLM_API_KEY`.
Missing credentials never crash the app; `/api/health` and the home page show a clear message.

## Defences
* **Prompt injection** - fixed system prompts; player text is length-capped, control-character-stripped and wrapped in `<player_input>` tags
  that the prompt declares untrusted; the model can only emit an allow-listed action *type* with ids that must exist in the current scene
  (otherwise the action becomes a no-op); the model has no tools, no database access and no way to emit state changes.
* **Output validation** - Pydantic schema, referenced entity ids must exist, no URLs/markup/prompt-leak phrases, damage numbers must equal engine values.
* **Fallback** - any provider error, timeout or invalid output yields deterministic template narration built from the engine's events. The
  committed action is never rolled back.

## Memory (`ai/memory_retriever.py`)
1. Immediate - last three narrations. 2. Campaign - structured `MemoryFact`s (from flags, defeats, quest outcomes), ranked by overlap with the
current location/NPCs/player text and recency. 3. World lore - entries unlocked by flags, ranked by keyword overlap. Present NPCs' relationship
records (including `known_player_actions`) are always included, so a betrayed NPC reacts consistently without relying on model memory.

## World generation (`ai/world_generator.py`)
Stages: premise → regions → factions → npcs → lore. Each stage proposes **text only** for existing ids; `apply_stage` whitelists fields and truncates;
the candidate world is then re-validated (`validate_world`: dangling references, duplicate ids, bidirectional exits, quest targets, reward items, starting
equipment, encounters, effects). A stage that breaks validation is discarded and the previous valid world is kept.
Honest scope: the playable graph (locations, links, quests, rules) is hand-authored in `data/world_template.py`; generation personalises names, premise
and descriptive text. Generating whole new graphs with an LLM is possible by extending the stages, because validation already exists.

## Artwork
`assets/prompt_builder.py` builds prompts from structured attributes (never raw narrative). Assets are cached by prompt hash, record provider/model/prompt,
are only available for discovered entities, and failures are stored as `status=failed` without affecting gameplay. Default provider: procedural SVG
(instant, offline). Optional: FLUX via the Hugging Face inference router.
