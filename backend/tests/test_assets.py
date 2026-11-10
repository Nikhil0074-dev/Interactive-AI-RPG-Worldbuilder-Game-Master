import httpx
import pytest
from test_api import CFG, P1, P2, act, make_client, start
from app.assets import prompt_builder as pb
from app.assets.image_service import HuggingFaceFluxProvider, ImageError, PlaceholderImageProvider, get_image_provider
from app.assets.storage import AssetStorage
from app.config import Settings


def test_prompts_are_built_from_structured_fields(world):
    p = pb.character_prompt(world["npcs"]["npc_orsin"], "painterly_fantasy", "a ruined city")
    assert "Orsin Vale" in p and "Wandering merchant" in p and "Waist-up portrait" in p
    l = pb.location_prompt(world["locations"]["loc_forgotten_shrine"], "twilight", "ink_sketch")
    assert "broken stone pillars" in l and "Ink and wash" in l and "16:9" in l
    assert pb.prompt_hash(p) == pb.prompt_hash(p) != pb.prompt_hash(l)


def test_placeholder_art_is_valid_deterministic_svg():
    pr = PlaceholderImageProvider()
    a = pr.generate("p", "location", {"biome": "ruined_tower", "weather": "rain"})
    assert a.startswith(b"<svg") and a.endswith(b"</svg>") and a == pr.generate("p", "location", {"biome": "ruined_tower", "weather": "rain"})
    import xml.dom.minidom as md
    md.parseString(a); md.parseString(pr.generate("q", "character", {"appearance": "silver hair"}))


def test_flux_provider_success_and_failures():
    png = b"\x89PNG" + b"0" * 200
    ok = HuggingFaceFluxProvider("t", "black-forest-labs/FLUX.1-schnell", httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, content=png, headers={"content-type": "image/png"}))))
    assert ok.generate("p", "location", {}) == png
    for resp in [httpx.Response(503), httpx.Response(200, content=b"{}", headers={"content-type": "application/json"})]:
        bad = HuggingFaceFluxProvider("t", "m", httpx.Client(transport=httpx.MockTransport(lambda r, resp=resp: resp)))
        with pytest.raises(ImageError):
            bad.generate("p", "location", {})


def test_missing_hf_token_falls_back_to_placeholder():
    s = Settings(image_provider="huggingface", hf_token="")
    assert isinstance(get_image_provider(s), PlaceholderImageProvider) and "HF_TOKEN" in s.provider_status()["image_message"]


def test_storage_blocks_path_traversal(tmp_path):
    st = AssetStorage(str(tmp_path))
    with pytest.raises(ValueError):
        st.path("../../etc/passwd")
    with pytest.raises(ValueError):
        st.save("not-a-uuid", b"x", "png")


def test_asset_generation_caching_and_authorization(tmp_path):
    c = make_client(tmp_path)
    cid, _ = start(c)
    a = c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "loc_veyr_gate"}, headers=P1).json()
    assert a["status"] == "ready" and a["cached"] is False and a["provider"] == "placeholder"
    b = c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "loc_veyr_gate"}, headers=P1).json()
    assert b["cached"] is True and b["id"] == a["id"]                                       # no regeneration
    img = c.get(a["url"], headers=P1)
    assert img.status_code == 200 and img.headers["content-type"] == "image/svg+xml" and img.headers["x-content-type-options"] == "nosniff"
    assert c.get(a["url"] + "?player=" + P1["X-Player-Id"]).status_code == 200            # <img> tag usage
    assert c.get(a["url"], headers=P2).status_code == 404 and c.get(a["url"]).status_code == 401
    assert c.get(f"/api/campaigns/{cid}", headers=P1).json()["assets"]["loc_veyr_gate"] == a["id"]


def test_assets_only_for_discovered_entities(tmp_path):
    c = make_client(tmp_path)
    cid, _ = start(c)
    assert c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "loc_undercroft"}, headers=P1).status_code == 403
    assert c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "npc_orsin"}, headers=P1).status_code == 403
    act(c, cid, type="talk", target_id="npc_orsin")
    assert c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "npc_orsin"}, headers=P1).json()["status"] == "ready"
    assert c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "item_iron_sword"}, headers=P1).status_code == 404


def test_failed_generation_never_blocks_gameplay(tmp_path):
    class Broken(PlaceholderImageProvider):
        def generate(self, *a, **k): raise ImageError("provider down")
    from app.main import create_app
    from fastapi.testclient import TestClient
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/t.db", asset_dir=str(tmp_path / "a")), image_provider=Broken())
    c = TestClient(app)
    cid, _ = start(c)
    a = c.post(f"/api/campaigns/{cid}/assets", json={"entity_id": "loc_veyr_gate"}, headers=P1).json()
    assert a["status"] == "failed" and a["url"] is None and "provider down" in a["error"]
    assert act(c, cid, type="move", target_id="loc_mist_street").json()["status"] == "completed"
