from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .state import ATTRIBUTES


class CampaignConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    world_name: str = Field(min_length=1, max_length=60)
    genre: Literal["dark_fantasy", "high_fantasy", "mystery"] = "dark_fantasy"
    setting: str = Field(default="", max_length=500)
    tone: Literal["mysterious", "heroic", "grim", "whimsical"] = "mysterious"
    difficulty: Literal["easy", "normal", "hard"] = "normal"
    combat_enabled: bool = True
    magic_level: Literal["low", "medium", "high"] = "high"
    party_size: Literal["solo"] = "solo"
    art_style: Literal["painterly_fantasy", "ink_sketch", "storybook"] = "painterly_fantasy"


class CharacterIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=40)
    char_class: str = Field(max_length=20)
    background: str = Field(default="", max_length=200)
    appearance: str = Field(default="", max_length=200)
    bonus_attribute: Optional[Literal[tuple(ATTRIBUTES)]] = None   # type: ignore[valid-type]


class InventoryActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str = Field(min_length=4, max_length=80, pattern=r"^[A-Za-z0-9_\-:.]+$")
    action: Literal["use", "equip", "unequip", "drop"]
    item_id: str = Field(max_length=80)


class QuestActionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_id: str = Field(min_length=4, max_length=80, pattern=r"^[A-Za-z0-9_\-:.]+$")
    action: Literal["abandon"]


class SaveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(default="Checkpoint", max_length=80)


class AssetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_id: str = Field(max_length=64)
