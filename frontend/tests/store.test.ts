import { beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";
import { useGame } from "@/lib/store";
import type { ActionResponse, GameView } from "@/lib/types";

const view = (v: number, extra: Partial<GameView> = {}): GameView => ({ campaign: { id: "c1", name: "T", version: v, fsm_state: "EXPLORATION", config: {} }, ...extra });
const resp = (over: Partial<ActionResponse> = {}): ActionResponse => ({ action_id: "a", status: "completed", error: null, events: [], duplicate: false, interpreted_as: null,
  narration: { narration: "Mist curls.", scene_mood: "calm", suggested_actions: [], referenced_entities: [], source: "mock", warning: null, mechanics: ["+1 XP"] }, state: view(2), ...over });

beforeEach(() => { useGame.getState().reset(); vi.restoreAllMocks(); useGame.setState({ view: view(1) }); });

describe("game store", () => {
  it("replaces the view with the authoritative server state and logs narration", async () => {
    vi.spyOn(api, "action").mockResolvedValue(resp());
    await useGame.getState().perform({ type: "rest" }, "Rest");
    const s = useGame.getState();
    expect(s.view?.campaign.version).toBe(2);
    expect(s.log.map((l) => l.kind)).toEqual(["player", "narration"]);
    expect(s.log[1].mechanics).toEqual(["+1 XP"]); expect(s.busy).toBe(false);
  });
  it("shows rejection messages as system entries and still adopts server state", async () => {
    vi.spyOn(api, "action").mockResolvedValue(resp({ status: "rejected", error: { code: "LOCKED", message: "It is locked." }, narration: null, state: view(1) }));
    await useGame.getState().perform({ type: "open" }, "Open");
    expect(useGame.getState().log.at(-1)).toMatchObject({ kind: "system", text: "It is locked." });
  });
  it("ignores overlapping submissions while busy (no double-apply)", async () => {
    let resolve!: (r: ActionResponse) => void;
    const spy = vi.spyOn(api, "action").mockImplementation(() => new Promise((r) => { resolve = r; }));
    const p1 = useGame.getState().perform({ type: "rest" });
    const p2 = await useGame.getState().perform({ type: "rest" });
    expect(p2).toBeNull(); expect(spy).toHaveBeenCalledTimes(1);
    resolve(resp()); await p1;
  });
  it("reloads authoritative state after a version conflict", async () => {
    vi.spyOn(api, "action").mockRejectedValue(new ApiError(409, "VERSION_CONFLICT", "Modified elsewhere."));
    const load = vi.spyOn(api, "getCampaign").mockResolvedValue(view(5));
    vi.spyOn(api, "history").mockResolvedValue({ narrative: [], events: [] });
    await useGame.getState().perform({ type: "rest" });
    expect(load).toHaveBeenCalled(); expect(useGame.getState().view?.campaign.version).toBe(5);
  });
  it("reports network errors without crashing", async () => {
    vi.spyOn(api, "action").mockRejectedValue(new ApiError(0, "NETWORK", "Cannot reach the game server."));
    await useGame.getState().perform({ type: "rest" });
    expect(useGame.getState().error).toBe("Cannot reach the game server."); expect(useGame.getState().busy).toBe(false);
  });
  it("rebuilds recent story from history on load", async () => {
    vi.spyOn(api, "getCampaign").mockResolvedValue(view(3));
    vi.spyOn(api, "history").mockResolvedValue({ narrative: [{ id: 1, text: "Earlier.", action: "", location_id: "x" }], events: [] });
    await useGame.getState().load("c1");
    expect(useGame.getState().log[0].text).toBe("Earlier.");
  });
  it("notes when free text could not become an action", async () => {
    vi.spyOn(api, "action").mockResolvedValue(resp({ interpreted_as: { source: "unknown", type: "custom" } }));
    await useGame.getState().perform({ type: "custom", text: "dance" }, "dance");
    expect(useGame.getState().log.some((l) => l.kind === "system")).toBe(true);
  });
  it("stores generated asset ids per entity", () => {
    useGame.getState().setAsset("loc_a", "asset1");
    expect(useGame.getState().view?.assets).toEqual({ loc_a: "asset1" });
  });
});
