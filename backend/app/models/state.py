"""Authoritative, JSON-serialisable game state (Pydantic models).

The *world* (static content: locations, NPCs, quests...) lives in a separate dict
persisted in the ``worlds`` table.  The *state* below holds everything that changes.
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1

FSM_STATES = [
    "MAIN_MENU", "WORLD_CREATION", "CHARACTER_CREATION", "EXPLORATION", "DIALOGUE",
    "COMBAT", "INVENTORY", "QUEST_LOG", "TRAVEL", "RESTING", "GAME_OVER",
]
EQUIP_SLOTS = ["weapon", "armor", "trinket"]
ATTRIBUTES = ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]

ActionType = Literal[
    "move", "examine", "take", "open", "search", "talk", "dialogue_choice", "end_dialogue",
    "attack", "ability", "flee", "use_item", "equip", "unequip", "drop", "rest",
    "open_inventory", "open_quest_log", "close_menu", "abandon_quest", "custom",
]


class ActionRequest(BaseModel):
    """A player action as submitted to the API (untrusted input)."""
    model_config = ConfigDict(extra="forbid")
    action_id: str = Field(min_length=4, max_length=80, pattern=r"^[A-Za-z0-9_\-:.]+$")
    type: ActionType
    target_id: Optional[str] = Field(default=None, max_length=80)
    item_id: Optional[str] = Field(default=None, max_length=80)
    option_id: Optional[str] = Field(default=None, max_length=80)
    ability_id: Optional[str] = Field(default=None, max_length=80)
    text: Optional[str] = Field(default=None, max_length=300)


class Player(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    char_class: str
    background: str = ""
    appearance: str = ""
    level: int = 1
    xp: int = 0
    hp: int
    max_hp: int
    mana: int
    max_mana: int
    attributes: dict[str, int]
    abilities: list[str] = Field(default_factory=list)
    inventory: dict[str, int] = Field(default_factory=dict)
    equipped: dict[str, Optional[str]] = Field(default_factory=lambda: {s: None for s in EQUIP_SLOTS})
    gold: int = 0
    statuses: dict[str, dict[str, int]] = Field(default_factory=dict)  # name -> {value, turns}


class QuestProgress(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["LOCKED", "AVAILABLE", "ACTIVE", "COMPLETED", "FAILED", "ABANDONED"] = "LOCKED"
    completed_objectives: list[str] = Field(default_factory=list)
    outcome: Optional[str] = None
    started_turn: Optional[int] = None
    completed_turn: Optional[int] = None


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    score: int = 0
    trust: int = 0
    fear: int = 0
    respect: int = 0
    known_player_actions: list[str] = Field(default_factory=list)


class ObjectState(BaseModel):
    locked: bool = False
    opened: bool = False


class LocationState(BaseModel):
    discovered: bool = False
    visited: bool = False
    ground: dict[str, int] = Field(default_factory=dict)
    found_hidden: list[str] = Field(default_factory=list)
    objects: dict[str, ObjectState] = Field(default_factory=dict)
    encounter_done: bool = False


class CombatState(BaseModel):
    enemy_id: str
    enemy_hp: int
    enemy_max_hp: int
    enemy_statuses: dict[str, dict[str, int]] = Field(default_factory=dict)
    round: int = 1
    player_first: bool = True


class MemoryFact(BaseModel):
    turn: int
    text: str
    entities: list[str] = Field(default_factory=list)


class GameState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = SCHEMA_VERSION
    fsm_state: str = "MAIN_MENU"
    turn: int = 0
    clock: int = 0
    rng_seed: int = 0
    rng_counter: int = 0
    difficulty: str = "normal"
    combat_enabled: bool = True
    player: Optional[Player] = None
    location_id: Optional[str] = None
    previous_location_id: Optional[str] = None
    locations: dict[str, LocationState] = Field(default_factory=dict)
    quests: dict[str, QuestProgress] = Field(default_factory=dict)
    flags: dict[str, Any] = Field(default_factory=dict)
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    faction_rep: dict[str, int] = Field(default_factory=dict)
    combat: Optional[CombatState] = None
    dialogue_npc: Optional[str] = None
    seen_events: list[str] = Field(default_factory=list)
    memory: list[MemoryFact] = Field(default_factory=list)
    defeated_enemies: list[str] = Field(default_factory=list)
    met_npcs: list[str] = Field(default_factory=list)
    seen_items: list[str] = Field(default_factory=list)
