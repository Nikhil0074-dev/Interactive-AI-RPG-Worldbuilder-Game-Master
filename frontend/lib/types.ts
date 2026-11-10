export type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

export interface CampaignSummary {
  id: string; name: string; fsm_state: string; updated_at: string; genre: string;
  character: { name: string; class: string; level: number; hp: number; max_hp: number } | null;
}
export interface GameAction {
  id: string; label: string; category: string; enabled?: boolean;
  action: { type: string; target_id?: string; item_id?: string; option_id?: string; ability_id?: string };
}
export interface Exit { id: string; name: string; locked: boolean; reason: string | null; visited: boolean }
export interface Npc { id: string; name: string; role: string; relationship: Json | null }
export interface Audio { profile: string; mood: string; weather: string; time_of_day: string; location_type: string }
export interface Scene {
  fsm_state: string; turn: number; time_of_day: string;
  location: { id: string; name: string; description: string; biome: string; weather: string; mood: string; safe: boolean; visual_features: string[] };
  exits: Exit[]; npcs: Npc[];
  objects: { id: string; name: string; kind: string; locked: boolean; opened: boolean }[];
  ground_items: { id: string; name: string; quantity: number }[];
  dialogue: { npc_id: string; npc_name: string; role: string; greeting: string; options: { id: string; text: string }[] } | null;
  combat: { enemy_id: string; name: string; description: string; hp: number; max_hp: number; statuses: Json; round: number } | null;
  available_actions: GameAction[]; audio: Audio;
}
export interface Item {
  id: string; name: string; category: string; rarity: string; weight: number; description: string;
  properties: Json; quantity: number; equipped: boolean; actions: ("use" | "equip" | "unequip" | "drop")[];
}
export interface InventoryView { items: Item[]; gold: number; weight: number; capacity: number; equipped: Record<string, string | null> }
export interface Objective { id: string; text: string; done: boolean; optional: boolean }
export interface Quest {
  id: string; title: string; description: string; category: string; status: string;
  objectives: Objective[]; outcome: string | null; outcome_text: string | null; rewards: Json;
}
export interface Player {
  name: string; char_class: string; class_name: string; background: string; appearance: string;
  level: number; xp: number; xp_next: number; xp_current_level: number;
  hp: number; max_hp: number; mana: number; max_mana: number; gold: number;
  attributes: Record<string, number>; attribute_mods: Record<string, number>;
  armor_class: number; defense: number; capacity: number; weight: number;
  statuses: Json; ability_details: { id: string; name: string; mana: number; desc: string }[];
  equipment_details: Record<string, Item | null>;
}
export interface GameView {
  campaign: { id: string; name: string; version: number; fsm_state: string; config: Json };
  world?: { name: string; premise: string } | null;
  player?: Player; scene?: Scene; inventory?: InventoryView; quests?: Quest[];
  assets?: Record<string, string>; game_over?: boolean; faction_rep?: Record<string, number>;
}
export interface Narration {
  narration: string; scene_mood: string; suggested_actions: string[]; referenced_entities: string[];
  source: string; warning: string | null; mechanics: string[];
}
export interface ActionResponse {
  action_id: string; status: "completed" | "rejected"; error: { code: string; message: string } | null;
  events: { type: string; [k: string]: any }[]; narration: Narration | null; // eslint-disable-line @typescript-eslint/no-explicit-any
  interpreted_as: { source: string; type: string; target_id?: string } | null; duplicate: boolean; state: GameView;
}
export interface ClassInfo {
  name: string; specialty: string; primary: string; attributes: Record<string, number>; mana: number;
  ability_details: { id: string; name: string; mana: number; desc: string }[]; equipment_details: Record<string, string>;
}
export interface Meta { classes: Record<string, ClassInfo>; genres: string[]; attributes: Record<string, string>; providers: { llm: string; llm_message: string | null; image: string; image_message: string | null } }
export interface LogEntry { id: string; kind: "narration" | "player" | "system"; text: string; mechanics?: string[]; mood?: string; suggestions?: string[]; source?: string }
export interface WorldOverview { name: string; genre: string; premise: string; central_conflict: string; regions: Json[]; factions: { id: string; name: string; goal: string }[]; opening_scene: string }
