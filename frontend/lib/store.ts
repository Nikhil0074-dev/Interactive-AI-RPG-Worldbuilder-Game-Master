import { create } from "zustand";
import { api, ApiError } from "./api";
import { audio, sfxForEvents } from "./audio-manager";
import type { ActionResponse, GameView, LogEntry } from "./types";

/** The server is the source of truth. This store mirrors the last authoritative view plus UI-only state. */
export interface GameStore {
  view: GameView | null; log: LogEntry[]; busy: boolean; error: string | null;
  load: (id: string) => Promise<void>;
  perform: (body: Record<string, unknown>, label?: string) => Promise<ActionResponse | null>;
  inventoryAction: (action: string, itemId: string, label: string) => Promise<void>;
  abandonQuest: (qid: string) => Promise<void>;
  applyResponse: (r: ActionResponse, label?: string) => void;
  setView: (v: GameView) => void;
  addLog: (e: Omit<LogEntry, "id">) => void;
  setAsset: (entity: string, assetId: string) => void;
  clearError: () => void;
  reset: () => void;
}

let seq = 0;
const mk = (e: Omit<LogEntry, "id">): LogEntry => ({ ...e, id: `l${++seq}` });
const msg = (e: unknown) => (e instanceof ApiError ? e.message : "Something went wrong.");

export const useGame = create<GameStore>((set, get) => ({
  view: null, log: [], busy: false, error: null,
  setView: (v) => set({ view: v }),
  addLog: (e) => set((s) => ({ log: [...s.log, mk(e)].slice(-200) })),
  setAsset: (entity, id) => set((s) => (s.view ? { view: { ...s.view, assets: { ...(s.view.assets || {}), [entity]: id } } } : s)),
  clearError: () => set({ error: null }),
  reset: () => set({ view: null, log: [], busy: false, error: null }),

  applyResponse(r, label) {
    if (label) get().addLog({ kind: "player", text: label });
    if (r.status === "rejected" && r.error) {
      audio().sfx("error");
      get().addLog({ kind: "system", text: r.error.message });
    } else {
      if (r.interpreted_as && r.interpreted_as.type === "custom") {
        get().addLog({ kind: "system", text: "The Game Master could not turn that into an action you can take here." });
      }
      if (r.narration) {
        get().addLog({ kind: "narration", text: r.narration.narration, mechanics: r.narration.mechanics, mood: r.narration.scene_mood,
                       suggestions: r.narration.suggested_actions, source: r.narration.source });
        audio().sfx(sfxForEvents(r.events.map((e) => e.type)) ?? "click");
      }
    }
    set({ view: r.state });
  },

  async load(id) {
    set({ error: null });
    try {
      const [view, hist] = await Promise.all([api.getCampaign(id), api.history(id)]);
      set({ view, log: hist.narrative.slice(-12).map((n) => mk({ kind: "narration", text: n.text })) });
    } catch (e) { set({ error: msg(e) }); }
  },

  async perform(body, label) {
    const id = get().view?.campaign.id;
    if (!id || get().busy) return null;
    set({ busy: true, error: null });
    try {
      const r = await api.action(id, body);
      get().applyResponse(r, label);
      return r;
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) await get().load(id);
      set({ error: msg(e) });
      return null;
    } finally { set({ busy: false }); }
  },

  async inventoryAction(action, itemId, label) {
    const id = get().view?.campaign.id;
    if (!id || get().busy) return;
    set({ busy: true, error: null });
    try { get().applyResponse(await api.inventoryAction(id, action, itemId), label); }
    catch (e) { set({ error: msg(e) }); }
    finally { set({ busy: false }); }
  },

  async abandonQuest(qid) {
    const id = get().view?.campaign.id;
    if (!id) return;
    set({ busy: true });
    try { get().applyResponse(await api.abandonQuest(id, qid)); }
    catch (e) { set({ error: msg(e) }); }
    finally { set({ busy: false }); }
  },
}));
