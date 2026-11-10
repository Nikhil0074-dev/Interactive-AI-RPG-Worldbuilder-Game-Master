"""Image providers. A missing or failed image must never block gameplay."""
from __future__ import annotations

import hashlib
import random
from abc import ABC, abstractmethod

import httpx


class ImageError(Exception):
    pass


class ImageProvider(ABC):
    name = "base"
    model_id = ""
    mime = "image/png"
    ext = "png"

    @abstractmethod
    def generate(self, prompt: str, kind: str, meta: dict) -> bytes: ...


PALETTES = {
    "ruined_city": ("#1b2430", "#3d5a6c", "#a9b8c4"), "ruined_tower": ("#1d1a26", "#4a3f63", "#b7a9d6"),
    "mountain_forest": ("#10201a", "#2f5d46", "#9ccfb0"), "underground_temple": ("#140f24", "#3b2d6e", "#e2b857"),
}


class PlaceholderImageProvider(ImageProvider):
    """Deterministic procedural SVG artwork - instant, free, offline."""
    name, model_id, mime, ext = "placeholder", "procedural-svg-v1", "image/svg+xml", "svg"

    def generate(self, prompt: str, kind: str, meta: dict) -> bytes:
        rnd = random.Random(int(hashlib.sha256(prompt.encode()).hexdigest(), 16))
        return (self._portrait(rnd, meta) if kind == "character" else self._scene(rnd, meta)).encode()

    def _scene(self, rnd: random.Random, meta: dict) -> str:
        top, mid, glow = PALETTES.get(meta.get("biome", ""), PALETTES["ruined_city"])
        w, h = 1024, 576
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid slice">',
               f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{mid}"/></linearGradient>'
               f'<radialGradient id="m"><stop offset="0" stop-color="{glow}" stop-opacity=".9"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient>'
               '<filter id="b"><feGaussianBlur stdDeviation="14"/></filter></defs>',
               f'<rect width="{w}" height="{h}" fill="url(#g)"/>']
        for _ in range(60):
            out.append(f'<circle cx="{rnd.randint(0, w)}" cy="{rnd.randint(0, h // 2)}" r="{rnd.random() * 1.4:.1f}" fill="#fff" opacity="{rnd.random() * .6:.2f}"/>')
        mx, my = rnd.randint(150, 870), rnd.randint(70, 150)
        out.append(f'<circle cx="{mx}" cy="{my}" r="120" fill="url(#m)"/><circle cx="{mx}" cy="{my}" r="34" fill="{glow}" opacity=".85"/>')
        underground = meta.get("biome") == "underground_temple"
        for layer, (col, base) in enumerate([("#0e1218", 400), ("#080b0f", 460)]):
            pts, x = [f"0,{h}"], 0
            while x <= w + 60:
                spike = rnd.choice([0, 0, 1, 2]) * (90 if meta.get("biome") in ("ruined_city", "ruined_tower") else 40)
                pts.append(f"{x},{base - rnd.randint(10, 70) - spike + layer * 30}")
                x += rnd.randint(30, 80)
            pts.append(f"{w},{h}")
            out.append(f'<polygon points="{" ".join(pts)}" fill="{col}" opacity="{.8 + layer * .2}"/>')
        if meta.get("biome") == "ruined_tower":
            out.append(f'<rect x="470" y="130" width="84" height="330" fill="#06080b"/><polygon points="460,130 512,70 564,130" fill="#06080b"/>'
                       f'<circle cx="512" cy="190" r="14" fill="{glow}" opacity=".8"/>')
        if underground:
            out.append(f'<ellipse cx="512" cy="470" rx="140" ry="28" fill="{glow}" opacity=".5" filter="url(#b)"/>')
        for _ in range(4):
            out.append(f'<ellipse cx="{rnd.randint(0, w)}" cy="{rnd.randint(380, 520)}" rx="{rnd.randint(200, 400)}" ry="34" fill="#cfd8e0" opacity=".10" filter="url(#b)"/>')
        if meta.get("weather") == "rain":
            for _ in range(140):
                x, y = rnd.randint(0, w), rnd.randint(0, h)
                out.append(f'<line x1="{x}" y1="{y}" x2="{x - 6}" y2="{y + 22}" stroke="#bcd" stroke-opacity=".25"/>')
        out.append("</svg>")
        return "".join(out)

    def _portrait(self, rnd: random.Random, meta: dict) -> str:
        a = meta.get("appearance", "").lower()
        hair = "#c9ced6" if "silver" in a or "grey" in a else rnd.choice(["#3b2a20", "#5a3b22", "#1e1e24"])
        cloth = rnd.choice(["#3d4f66", "#5a3340", "#34513f", "#4b4638"])
        glow = rnd.choice(["#e2b857", "#8fd0c0", "#c3a2ff"])
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 640"><defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
                f'<stop offset="0" stop-color="#151a22"/><stop offset="1" stop-color="#2a3340"/></linearGradient>'
                f'<radialGradient id="r"><stop offset="0" stop-color="{glow}" stop-opacity=".55"/><stop offset="1" stop-color="{glow}" stop-opacity="0"/></radialGradient></defs>'
                f'<rect width="512" height="640" fill="url(#g)"/><circle cx="256" cy="250" r="230" fill="url(#r)"/>'
                f'<path d="M60 640 C70 470 160 430 256 430 C352 430 442 470 452 640Z" fill="{cloth}"/>'
                f'<path d="M200 430 L256 520 L312 430 L290 410 L222 410Z" fill="#0d1015" opacity=".55"/>'
                f'<rect x="228" y="350" width="56" height="80" rx="20" fill="#c8a98c"/>'
                f'<ellipse cx="256" cy="270" rx="86" ry="108" fill="#d4b498"/>'
                f'<path d="M165 262 C160 150 352 150 347 262 C330 200 190 200 165 262Z" fill="{hair}"/>'
                f'<ellipse cx="226" cy="278" rx="9" ry="6" fill="#1a1d22"/><ellipse cx="286" cy="278" rx="9" ry="6" fill="#1a1d22"/>'
                f'<path d="M232 332 Q256 346 280 332" stroke="#7a5a48" stroke-width="4" fill="none" stroke-linecap="round"/>'
                f'<circle cx="256" cy="470" r="16" fill="{glow}" opacity=".9"/></svg>')


class HuggingFaceFluxProvider(ImageProvider):
    name = "huggingface-flux"

    def __init__(self, token: str, model: str, client: httpx.Client | None = None):
        self.token, self.model_id = token, model
        self.client = client or httpx.Client(timeout=90)

    def generate(self, prompt: str, kind: str, meta: dict) -> bytes:
        try:
            r = self.client.post(f"https://router.huggingface.co/hf-inference/models/{self.model_id}",
                                 headers={"Authorization": f"Bearer {self.token}"}, json={"inputs": prompt})
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise ImageError(f"image provider failed: {e}") from e
        if not r.headers.get("content-type", "").startswith("image/") or len(r.content) < 100:
            raise ImageError("image provider returned a non-image response")
        return r.content


def get_image_provider(settings) -> ImageProvider:
    if settings.image_provider == "huggingface" and settings.hf_token:
        return HuggingFaceFluxProvider(settings.hf_token, settings.flux_model)
    return PlaceholderImageProvider()
