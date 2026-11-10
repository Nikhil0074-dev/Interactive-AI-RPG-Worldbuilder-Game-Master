import type { ActionResponse, CampaignSummary, GameView, Json, Meta, Narration, WorldOverview } from "./types";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

export function playerId(): string {
  if (typeof window === "undefined") return "server-render-00";
  let id = window.localStorage.getItem("rpg_player_id");
  if (!id) {
    id = "p-" + (crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36));
    window.localStorage.setItem("rpg_player_id", id);
  }
  return id;
}

export function newActionId(): string {
  return `a_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;
}

export const assetUrl = (assetId: string) => `/api/assets/${assetId}?player=${encodeURIComponent(playerId())}`;

async function req<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", "X-Player-Id": playerId(), ...(init.headers || {}) },
    });
  } catch {
    throw new ApiError(0, "NETWORK", "Cannot reach the game server. Is the backend running?");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: any = null; // eslint-disable-line @typescript-eslint/no-explicit-any
  try { body = text ? JSON.parse(text) : null; } catch { /* non-JSON body */ }
  if (!res.ok) {
    const d = body?.detail;
    throw new ApiError(res.status, d?.code || "ERROR", d?.message || (typeof d === "string" ? d : `Request failed (${res.status})`));
  }
  return (body ?? text) as T;
}

const post = (b?: unknown): RequestInit => ({ method: "POST", body: b === undefined ? undefined : JSON.stringify(b) });

export const api = {
  meta: () => req<Meta>("/meta"),
  health: () => req<{ status: string; providers: Meta["providers"] }>("/health"),
  listCampaigns: () => req<CampaignSummary[]>("/campaigns"),
  createCampaign: (config: Json) => req<{ id: string }>("/campaigns", post(config)),
  generateWorld: (id: string) => req<{ world: WorldOverview; notes: string[] }>(`/campaigns/${id}/world`, post()),
  createCharacter: (id: string, body: Json) => req<{ narration: Narration; state: GameView }>(`/campaigns/${id}/character`, post(body)),
  getCampaign: (id: string) => req<GameView>(`/campaigns/${id}`),
  action: (id: string, body: Json) => req<ActionResponse>(`/campaigns/${id}/actions`, post({ action_id: newActionId(), ...body })),
  inventoryAction: (id: string, action: string, item_id: string) =>
    req<ActionResponse>(`/campaigns/${id}/inventory/actions`, post({ action_id: newActionId(), action, item_id })),
  abandonQuest: (id: string, qid: string) =>
    req<ActionResponse>(`/campaigns/${id}/quests/${qid}/actions`, post({ action_id: newActionId(), action: "abandon" })),
  codex: (id: string) => req<Json>(`/campaigns/${id}/codex`),
  history: (id: string) => req<{ narrative: { id: number; text: string; action: string; location_id: string }[]; events: Json[] }>(`/campaigns/${id}/history`),
  save: (id: string, label: string) => req<{ id: string; label: string }>(`/campaigns/${id}/save`, post({ label })),
  saves: (id: string) => req<{ id: string; label: string; created_at: string }[]>(`/campaigns/${id}/saves`),
  restore: (id: string, sid: string) => req<GameView>(`/campaigns/${id}/saves/${sid}/restore`, post()),
  requestAsset: (id: string, entity_id: string) => req<{ id: string; status: string }>(`/campaigns/${id}/assets`, post({ entity_id })),
  remove: (id: string) => req<void>(`/campaigns/${id}`, { method: "DELETE" }),
  exportMarkdown: (id: string) => req<string>(`/campaigns/${id}/export`),
};
