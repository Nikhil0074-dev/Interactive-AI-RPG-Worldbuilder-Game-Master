import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, assetUrl, newActionId, playerId } from "@/lib/api";

const ok = (body: unknown, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } }));
beforeEach(() => localStorage.clear());
afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("creates a stable player id and sends it as a header", async () => {
    const id = playerId();
    expect(id).toMatch(/^p-/); expect(playerId()).toBe(id);
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(() => ok([]));
    await api.listCampaigns();
    const [url, init] = spy.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/campaigns"); expect((init.headers as Record<string, string>)["X-Player-Id"]).toBe(id);
    expect(assetUrl("abc")).toBe(`/api/assets/abc?player=${encodeURIComponent(id)}`);
  });
  it("generates unique, schema-valid action ids", () => {
    const ids = new Set(Array.from({ length: 200 }, newActionId));
    expect(ids.size).toBe(200);
    ids.forEach((i) => expect(i).toMatch(/^[A-Za-z0-9_\-:.]{4,80}$/));
  });
  it("surfaces structured server errors", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(() => ok({ detail: { code: "CAMPAIGN_NOT_FOUND", message: "Campaign not found." } }, 404));
    await expect(api.getCampaign("x")).rejects.toMatchObject({ status: 404, code: "CAMPAIGN_NOT_FOUND", message: "Campaign not found." });
  });
  it("reports unreachable servers clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    const e = await api.meta().catch((x) => x);
    expect(e).toBeInstanceOf(ApiError); expect(e.code).toBe("NETWORK");
  });
  it("posts actions with a fresh action_id", async () => {
    const spy = vi.spyOn(globalThis, "fetch").mockImplementation(() => ok({ status: "completed" }));
    await api.action("c1", { type: "rest" });
    const body = JSON.parse((spy.mock.calls[0][1] as RequestInit).body as string);
    expect(body.type).toBe("rest"); expect(body.action_id).toMatch(/^a_/);
  });
});
