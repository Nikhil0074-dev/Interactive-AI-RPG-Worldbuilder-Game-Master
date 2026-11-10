"""Build image prompts from approved structured attributes (never from free narrative text)."""
from __future__ import annotations

import hashlib

ART_STYLES = {
    "painterly_fantasy": "Painterly dark fantasy, cinematic lighting, muted colors, detailed fabric and metalwork.",
    "ink_sketch": "Ink and wash illustration, high contrast linework, parchment tones.",
    "storybook": "Warm storybook illustration, soft gradients, gentle shapes.",
}


def style_text(art_style: str) -> str:
    return ART_STYLES.get(art_style, ART_STYLES["painterly_fantasy"])


def character_prompt(npc: dict, art_style: str, setting: str = "") -> str:
    return (f"Create a fantasy RPG character portrait.\nCharacter: {npc['name']}\nRole: {npc['role']}\n"
            f"Age presentation: Adult\nAppearance: {npc['appearance']}\nPersonality: {npc['personality']}\n"
            f"Setting: {setting or 'a ruined fantasy city'}\nArt direction: {style_text(art_style)}\n"
            "Composition: Waist-up portrait, centered subject, consistent visual framing.")


def location_prompt(loc: dict, time_of_day: str, art_style: str) -> str:
    feats = ", ".join(loc.get("visual_features", []))
    return (f"Create a fantasy RPG environment illustration.\nLocation: {loc['name']}\nBiome: {loc['biome']}\n"
            f"Time of day: {time_of_day}\nWeather: {loc['weather']}\nMood: {loc['mood']}\nVisual features: {feats}\n"
            f"Art direction: {style_text(art_style)}\nComposition: Wide cinematic establishing shot, 16:9, no text, no characters.")


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode()).hexdigest()[:32]
