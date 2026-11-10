"""Static game content: items, classes, abilities, enemies. All rules data, no prose generation."""
from __future__ import annotations

ATTR_SHORT = {"strength": "STR", "dexterity": "DEX", "constitution": "CON",
              "intelligence": "INT", "wisdom": "WIS", "charisma": "CHA"}


def _item(id, name, category, rarity, weight, desc, stackable=False, slot=None, requirements=None, **props):
    return {"id": id, "name": name, "category": category, "rarity": rarity, "weight": weight,
            "stackable": stackable, "slot": slot, "requirements": requirements or {},
            "properties": props, "description": desc}


ITEMS: dict[str, dict] = {i["id"]: i for i in [
    _item("item_iron_sword", "Iron Sword", "weapon", "common", 3, "A dependable sword forged from ordinary iron.", slot="weapon", damage=8, scaling="strength", durability=100),
    _item("item_rusty_dagger", "Rusty Dagger", "weapon", "common", 1, "Chipped, but still sharp where it counts.", slot="weapon", damage=6, scaling="dexterity", durability=80),
    _item("item_oak_staff", "Oak Staff", "weapon", "common", 2, "A knotted staff humming faintly with stored memory.", slot="weapon", damage=5, scaling="intelligence", durability=80),
    _item("item_short_bow", "Short Bow", "weapon", "common", 2, "A supple yew bow with a worn grip.", slot="weapon", damage=7, scaling="dexterity", durability=80),
    _item("item_pilgrim_mace", "Pilgrim's Mace", "weapon", "common", 4, "A blessed mace carried by roadside pilgrims.", slot="weapon", damage=7, scaling="wisdom", durability=100),
    _item("item_brass_lute", "Brass Lute", "weapon", "common", 2, "A sturdy instrument that doubles as a club.", slot="weapon", damage=4, scaling="charisma", durability=60),
    _item("item_spanner", "Heavy Spanner", "weapon", "common", 3, "Engineer's best friend, in more ways than one.", slot="weapon", damage=7, scaling="intelligence", durability=100),
    _item("item_leather_jerkin", "Leather Jerkin", "armor", "common", 4, "Boiled leather, patched in several places.", slot="armor", defense=2),
    _item("item_scholar_robe", "Scholar's Robe", "armor", "common", 2, "Ink-stained wool lined with warding thread.", slot="armor", defense=1),
    _item("item_chain_hauberk", "Chain Hauberk", "armor", "uncommon", 12, "Heavy riveted mail from a vanished garrison.", slot="armor", requirements={"strength": 13}, defense=4),
    _item("item_ember_charm", "Ember Charm", "magical", "rare", 0.5, "A warm charm that sharpens the wearer's resolve.", slot="trinket", attack_bonus=1),
    _item("item_lanternward_charm", "Lanternward Charm", "magical", "rare", 0.5, "A Lantern Order blessing, bright against the dark.", slot="trinket", attack_bonus=1, defense=1),
    _item("item_healing_potion", "Healing Potion", "consumable", "common", 1, "A ruby tonic that knits wounds.", stackable=True, heal=20),
    _item("item_mana_draught", "Mana Draught", "consumable", "common", 1, "A silver draught that steadies the mind.", stackable=True, mana=15),
    _item("item_lockpicks", "Lockpicks", "tool", "common", 0.5, "A slim roll of picks and tension wrenches.", bonus=2),
    _item("item_orsin_key", "Orsin's Brass Key", "key", "common", 0.2, "A small brass key stamped with a coin-and-hand crest.", quest=True, opens="obj_iron_chest"),
    _item("item_memory_clapper", "Memory Clapper", "quest", "legendary", 2, "A bell clapper that hums with trapped recollections.", quest=True),
    _item("item_torn_ledger", "Torn Ledger", "book", "uncommon", 0.5, "Pages of the Gilded Hand's old accounts, hinting at buried vaults."),
]}

CLASSES: dict[str, dict] = {
    "warrior": {"name": "Warrior", "specialty": "Melee combat", "primary": "strength", "hit_die": 10, "mana": 5,
                "attributes": {"strength": 15, "dexterity": 11, "constitution": 14, "intelligence": 8, "wisdom": 10, "charisma": 10},
                "abilities": ["shield_break"], "equipment": {"weapon": "item_iron_sword", "armor": "item_leather_jerkin"},
                "items": {"item_healing_potion": 2}},
    "mage": {"name": "Mage", "specialty": "Arcane magic", "primary": "intelligence", "hit_die": 6, "mana": 24,
             "attributes": {"strength": 8, "dexterity": 11, "constitution": 10, "intelligence": 15, "wisdom": 13, "charisma": 10},
             "abilities": ["arcane_bolt"], "equipment": {"weapon": "item_oak_staff", "armor": "item_scholar_robe"},
             "items": {"item_healing_potion": 1, "item_mana_draught": 2}},
    "rogue": {"name": "Rogue", "specialty": "Stealth and traps", "primary": "dexterity", "hit_die": 8, "mana": 10,
              "attributes": {"strength": 10, "dexterity": 15, "constitution": 11, "intelligence": 12, "wisdom": 11, "charisma": 12},
              "abilities": ["shadow_step"], "equipment": {"weapon": "item_rusty_dagger", "armor": "item_leather_jerkin"},
              "items": {"item_healing_potion": 2, "item_lockpicks": 1}},
    "ranger": {"name": "Ranger", "specialty": "Ranged combat and tracking", "primary": "dexterity", "hit_die": 8, "mana": 10,
               "attributes": {"strength": 11, "dexterity": 14, "constitution": 12, "intelligence": 10, "wisdom": 14, "charisma": 9},
               "abilities": ["marked_shot"], "equipment": {"weapon": "item_short_bow", "armor": "item_leather_jerkin"},
               "items": {"item_healing_potion": 2}},
    "cleric": {"name": "Cleric", "specialty": "Healing and protection", "primary": "wisdom", "hit_die": 8, "mana": 20,
               "attributes": {"strength": 11, "dexterity": 9, "constitution": 13, "intelligence": 10, "wisdom": 15, "charisma": 12},
               "abilities": ["healing_light"], "equipment": {"weapon": "item_pilgrim_mace", "armor": "item_leather_jerkin"},
               "items": {"item_healing_potion": 1}},
    "bard": {"name": "Bard", "specialty": "Dialogue and support", "primary": "charisma", "hit_die": 8, "mana": 16,
             "attributes": {"strength": 9, "dexterity": 12, "constitution": 11, "intelligence": 11, "wisdom": 10, "charisma": 15},
             "abilities": ["inspiring_song"], "equipment": {"weapon": "item_brass_lute", "armor": "item_leather_jerkin"},
             "items": {"item_healing_potion": 2}},
    "engineer": {"name": "Engineer", "specialty": "Devices and mechanisms", "primary": "intelligence", "hit_die": 8, "mana": 12,
                 "attributes": {"strength": 10, "dexterity": 12, "constitution": 12, "intelligence": 14, "wisdom": 11, "charisma": 9},
                 "abilities": ["mechanical_override"], "equipment": {"weapon": "item_spanner", "armor": "item_leather_jerkin"},
                 "items": {"item_healing_potion": 1, "item_lockpicks": 1}},
}

ABILITIES: dict[str, dict] = {
    "shield_break": {"name": "Shield Break", "mana": 3, "damage": 3, "uses_weapon": True, "scaling": "strength",
                     "status": {"name": "defense_down", "value": 3, "turns": 3}, "desc": "Smash the foe's guard, lowering its defense."},
    "arcane_bolt": {"name": "Arcane Bolt", "mana": 5, "damage": 10, "uses_weapon": False, "scaling": "intelligence",
                    "ignore_defense": True, "desc": "A bolt of force that ignores armor."},
    "shadow_step": {"name": "Shadow Step", "mana": 4, "damage": 6, "uses_weapon": True, "scaling": "dexterity",
                    "critical": True, "desc": "Slip behind the target for a guaranteed critical strike."},
    "marked_shot": {"name": "Marked Shot", "mana": 3, "damage": 4, "uses_weapon": True, "scaling": "dexterity",
                    "status": {"name": "defense_down", "value": 2, "turns": 2}, "desc": "A precise shot that exposes the target."},
    "healing_light": {"name": "Healing Light", "mana": 5, "heal": 15, "scaling": "wisdom", "desc": "Mend your wounds with holy light."},
    "inspiring_song": {"name": "Inspiring Song", "mana": 4, "self_status": {"name": "attack_up", "value": 3, "turns": 3},
                       "desc": "A rousing tune that raises your attack."},
    "mechanical_override": {"name": "Mechanical Override", "mana": 4, "damage": 2, "uses_weapon": False, "scaling": "intelligence",
                            "status": {"name": "stunned", "value": 1, "turns": 1}, "desc": "Jam the foe's movements, stunning it."},
}

ENEMIES: dict[str, dict] = {
    "enemy_bell_ringer": {"id": "enemy_bell_ringer", "name": "Hollow Bell-Ringer", "hp": 34, "attack": 8, "defense": 2,
                          "accuracy": 3, "initiative": 1, "xp": 120,
                          "loot": {"gold": 15, "items": {"item_memory_clapper": 1}},
                          "description": "A tall figure of brass and drifting mist, hauling an unseen rope.",
                          "attack_text": "swings a bronze-wrapped fist"},
    "enemy_ash_rat": {"id": "enemy_ash_rat", "name": "Ashen Rat", "hp": 14, "attack": 5, "defense": 0,
                      "accuracy": 2, "initiative": 2, "xp": 40,
                      "loot": {"gold": 6, "items": {}},
                      "description": "A rat the size of a hound, fur dusted with grey ash.",
                      "attack_text": "snaps with ash-stained teeth"},
}

XP_PER_LEVEL_STEP = 100
MAX_LEVEL = 10
DIFFICULTY_ENEMY_MULT = {"easy": 0.75, "normal": 1.0, "hard": 1.25}
TIMES_OF_DAY = ["dawn", "day", "dusk", "night"]
