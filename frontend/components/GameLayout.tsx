"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { audio } from "@/lib/audio-manager";
import { useGame } from "@/lib/store";
import { ActionPanel } from "./ActionPanel";
import { AudioControls } from "./AudioControls";
import { CharacterPanel } from "./CharacterPanel";
import { CharacterSheet } from "./CharacterSheet";
import { CodexPanel } from "./CodexPanel";
import { InventoryPanel } from "./InventoryPanel";
import { Modal } from "./Modal";
import { NarrativePanel } from "./NarrativePanel";
import { QuestJournal } from "./QuestJournal";
import { SceneArt } from "./SceneArt";
import { WorldPanel } from "./WorldPanel";

type ModalName = "inventory" | "quests" | "sheet" | "codex" | "saves" | null;

export function GameLayout({ campaignId }: { campaignId: string }) {
  const { view, error, load, perform, clearError } = useGame();
  const [modal, setModal] = useState<ModalName>(null);
  const [tab, setTab] = useState<"story" | "character" | "world">("story");
  const [saves, setSaves] = useState<{ id: string; label: string; created_at: string }[]>([]);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => { void load(campaignId); return () => useGame.getState().reset(); }, [campaignId, load]);

  const audioProfile = view?.scene?.audio;
  useEffect(() => { if (audioProfile) audio().setProfile(audioProfile); }, [audioProfile?.profile, audioProfile?.mood, audioProfile?.weather, audioProfile?.time_of_day]); // eslint-disable-line react-hooks/exhaustive-deps

  // Resume into a menu state if the browser was closed while a menu was open.
  const fsm = view?.campaign.fsm_state;
  useEffect(() => { if (fsm === "INVENTORY") setModal("inventory"); if (fsm === "QUEST_LOG") setModal("quests"); }, [fsm]);

  const open = useCallback(async (m: Exclude<ModalName, null>) => {
    audio().unlock();
    if (m === "inventory" && fsm === "EXPLORATION") await perform({ type: "open_inventory" });
    if (m === "quests" && fsm === "EXPLORATION") await perform({ type: "open_quest_log" });
    if (m === "saves") setSaves(await api.saves(campaignId).catch(() => []));
    setModal(m);
  }, [fsm, perform, campaignId]);

  const close = useCallback(async () => {
    const f = useGame.getState().view?.campaign.fsm_state;
    setModal(null);
    if (f === "INVENTORY" || f === "QUEST_LOG") await perform({ type: "close_menu" });
  }, [perform]);

  const flash = (t: string) => { setToast(t); setTimeout(() => setToast(null), 2500); };
  const doSave = async () => { const s = await api.save(campaignId, `Turn ${view?.scene?.turn ?? 0} - ${view?.scene?.location.name ?? ""}`); flash(`Saved: ${s.label}`); };
  const doExport = async () => {
    const md = await api.exportMarkdown(campaignId);
    const url = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    const a = document.createElement("a"); a.href = url; a.download = `${view?.campaign.name ?? "campaign"}.md`; a.click(); URL.revokeObjectURL(url);
  };
  const restore = async (sid: string) => { const v = await api.restore(campaignId, sid); useGame.getState().setView(v); setModal(null); flash("Checkpoint restored"); };

  if (!view) return <main className="p-10 text-center text-muted">{error ? <p className="text-blood" role="alert">{error} <Link className="underline" href="/">Home</Link></p> : "Loading your campaign..."}</main>;
  if (!view.scene || !view.player) return <main className="p-10 text-center">This campaign has not started yet. <Link className="underline text-gold" href="/campaigns/new">Create a world</Link></main>;
  const { scene } = view;

  return (
    <div className="max-w-7xl mx-auto p-3 sm:p-5" onClick={() => audio().unlock()}>
      <header className="flex flex-wrap items-center justify-between gap-2 mb-4">
        <div><Link href="/" className="text-xs text-muted hover:text-gold">← Home</Link>
          <h1 className="text-2xl text-gold leading-tight" data-testid="campaign-title">{view.world?.name || view.campaign.name}</h1></div>
        <nav className="flex flex-wrap gap-2" aria-label="Game menu">
          <button className="btn" onClick={doSave} data-testid="save-btn">Save</button>
          <button className="btn" onClick={() => void open("saves")} data-testid="load-btn">Load</button>
          <button className="btn" onClick={doExport}>Export</button>
          <AudioControls />
        </nav>
      </header>
      {(error || toast) && <div role="status" className={`panel px-4 py-2 mb-3 text-sm ${error ? "border-blood text-blood" : "border-leaf text-leaf"}`}>{error || toast}
        {error && <button className="ml-3 underline" onClick={clearError}>dismiss</button>}</div>}

      <div className="lg:hidden flex gap-2 mb-3" role="tablist">
        {(["story", "character", "world"] as const).map((t) => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)} className={`btn flex-1 capitalize ${tab === t ? "border-gold text-gold" : ""}`}>{t}</button>)}
      </div>
      <div className="grid lg:grid-cols-[260px_minmax(0,1fr)_290px] gap-4">
        <div className={tab === "character" ? "" : "hidden lg:block"}><CharacterPanel onOpen={(m) => void open(m)} /></div>
        <main className={`space-y-3 min-w-0 ${tab === "story" ? "" : "hidden lg:block"}`}>
          <SceneArt entityId={scene.location.id} biome={scene.location.biome} name={scene.location.name} mood={scene.location.mood} />
          {scene.dialogue && (
            <div className="panel p-4 border-goldDim fade-in" data-testid="dialogue-box">
              <h3 className="text-gold">{scene.dialogue.npc_name} <span className="text-xs text-muted">· {scene.dialogue.role}</span></h3>
              <p className="font-serif italic mt-1">{scene.dialogue.greeting}</p>
            </div>
          )}
          <NarrativePanel />
          <ActionPanel />
        </main>
        <div className={tab === "world" ? "" : "hidden lg:block"}><WorldPanel /></div>
      </div>

      {modal === "inventory" && <Modal title="Inventory" onClose={() => void close()} testId="inventory-modal"><InventoryPanel /></Modal>}
      {modal === "quests" && <Modal title="Quest Journal" onClose={() => void close()} testId="quest-modal"><QuestJournal /></Modal>}
      {modal === "sheet" && <Modal title="Character Sheet" onClose={() => setModal(null)} testId="sheet-modal"><CharacterSheet /></Modal>}
      {modal === "codex" && <Modal title="World Codex" wide onClose={() => setModal(null)} testId="codex-modal"><CodexPanel campaignId={campaignId} /></Modal>}
      {modal === "saves" && <Modal title="Load Checkpoint" onClose={() => setModal(null)} testId="saves-modal">
        {saves.length === 0 ? <p className="text-muted">No checkpoints yet. Use Save during play.</p> :
          <ul className="space-y-2">{saves.map((s) => <li key={s.id} className="flex justify-between items-center border border-edge rounded p-3 bg-panel2">
            <span>{s.label}<span className="block text-xs text-muted">{new Date(s.created_at).toLocaleString()}</span></span>
            <button className="btn" onClick={() => void restore(s.id)}>Restore</button></li>)}</ul>}
      </Modal>}
    </div>
  );
}
