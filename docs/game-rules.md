# Game rules (all implemented in `backend/app/game_engine`, none decided by the LLM)

**Attributes** STR, DEX, CON, INT, WIS, CHA. Modifier = `(score − 10) // 2`.
**Checks** `d20 + modifier (+ bonus) ≥ DC`; natural 20 always succeeds, natural 1 always fails.
**Classes** (7): Warrior, Mage, Rogue, Ranger, Cleric, Bard, Engineer, each with attributes, starting kit and one ability
(`data/content.py`). `HP = 20 + hit_die + 2·CON_mod`; `Mana = class_mana + 2·primary_mod`. Optional +2 bonus attribute at creation.

**Combat** Initiative `d20 + DEX` vs `d20 + enemy initiative`. Player attacks hit unless natural 1; natural 20 doubles damage.
`Damage = max(1, base + attack_bonus − defense)`. Enemies hit if `d20 + accuracy ≥ 8 + DEX_mod + armor` (nat 1 miss / nat 20 crit);
enemy base damage scales with difficulty (×0.75 / ×1 / ×1.25). Abilities cost mana and may heal, ignore defense, force a crit or apply
statuses (`defense_down`, `attack_up`, `stunned`) that tick down each round. Flee = DEX check DC 12. Defeat → `GAME_OVER`.

**Inventory** Capacity `20 + 2·STR`. Slots: weapon, armor, trinket. Equipment may have attribute requirements. Quest items cannot be
dropped. Consumables are only consumed when they can have an effect (no wasted potions). Rewards that do not fit are left on the ground.

**Progression** XP to reach level *L*: `100·L·(L−1)/2` (max level 10). Level-up: `+hit_die/2+1+CON_mod` HP, `+2+primary_mod` mana, +1 primary
attribute. XP: quests, first visit of a location (15), enemies, examining discoveries.

**Quests** `LOCKED → AVAILABLE → ACTIVE → COMPLETED / FAILED / ABANDONED`. Objectives are matched against typed events
(`ITEM_ACQUIRED:item_x`, `ENEMY_DEFEATED:enemy_y`, …). Objectives satisfied *before* a quest starts count retroactively
(the world remembers). A quest is marked `COMPLETED` before rewards are granted, so rewards can never duplicate. Outcome-specific rewards
depend on flags set by choices. Main quests cannot be abandoned.

**Relationships & factions** Per-NPC `score, trust, fear, respect, known_player_actions`; faction reputation. Trust gives merchant
discounts (up to 30%), `rel_min` unlocks dialogue (e.g. Maren's blessing). Notable flags create *campaign memory facts* and tag the NPCs
that witnessed them.

**Sample campaign** "The Shattered Crown": 5 locations, 2 NPCs, 3 factions, 3 quests (one main with three mutually exclusive endings, one side quest,
one hidden auto-starting quest), 2 enemies, 18 items. Three independent ways to reach the shrine: persuade Orsin (CHA 12), search Mist Street (WIS 14),
or help Orsin.
