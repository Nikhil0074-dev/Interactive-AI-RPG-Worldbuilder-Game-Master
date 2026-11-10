"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CampaignSummary, Meta } from "@/lib/types";

export default function Home() {
  const [campaigns, setCampaigns] = useState<CampaignSummary[] | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reduce, setReduce] = useState(false);

  const refresh = () => api.listCampaigns().then(setCampaigns).catch((e) => setError(e.message));
  useEffect(() => {
    void refresh();
    api.meta().then(setMeta).catch(() => {});
    setReduce(localStorage.getItem("rpg_reduce_motion") === "true");
  }, []);
  const toggleMotion = (v: boolean) => { setReduce(v); localStorage.setItem("rpg_reduce_motion", String(v)); document.documentElement.dataset.reduceMotion = String(v); };
  const remove = async (id: string, name: string) => { if (confirm(`Delete "${name}" permanently?`)) { await api.remove(id); void refresh(); } };
  const resumable = (campaigns || []).filter((c) => c.character);
  const latest = resumable[0];

  return (
    <main className="max-w-3xl mx-auto px-5 py-12">
      <header className="text-center mb-10">
        <p className="text-xs tracking-[0.4em] text-goldDim uppercase">AI-narrated · rules-driven</p>
        <h1 className="text-4xl sm:text-5xl text-gold mt-2" data-testid="title">Interactive AI RPG</h1>
        <p className="font-title text-xl text-parchment mt-1">Worldbuilder &amp; Game Master</p>
        <p className="text-muted mt-4 max-w-xl mx-auto">Explore a procedurally generated world where every choice is remembered. The Game Master tells the story; a deterministic engine keeps the rules honest.</p>
      </header>
      <div className="flex flex-wrap gap-3 justify-center mb-10">
        <Link href="/campaigns/new" className="btn btn-gold px-6 py-3" data-testid="new-campaign">Create New World</Link>
        {latest && <Link href={`/campaigns/${latest.id}`} className="btn px-6 py-3" data-testid="continue-campaign">Continue: {latest.name}</Link>}
      </div>
      {error && <p className="panel p-3 text-blood text-sm mb-4" role="alert">{error}</p>}
      <section aria-label="Saved campaigns">
        <h2 className="text-xl text-gold mb-3">Saved campaigns</h2>
        {campaigns === null && !error && <p className="text-muted">Loading...</p>}
        {campaigns?.length === 0 && <p className="text-muted">No campaigns yet. Create your first world.</p>}
        <ul className="space-y-2">
          {(campaigns || []).map((c) => (
            <li key={c.id} className="panel p-4 flex items-center justify-between gap-3" data-testid="campaign-item">
              <div>
                <p className="font-serif text-lg">{c.name}</p>
                <p className="text-xs text-muted">{c.character ? `${c.character.name} · Level ${c.character.level} ${c.character.class} · ${c.character.hp}/${c.character.max_hp} HP` : "Setup in progress"} · {new Date(c.updated_at).toLocaleString()}</p>
              </div>
              <div className="flex gap-2">
                <Link className="btn" href={c.character ? `/campaigns/${c.id}` : "/campaigns/new"}>{c.character ? "Play" : "Setup"}</Link>
                <button className="btn" onClick={() => void remove(c.id, c.name)} aria-label={`Delete ${c.name}`}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      </section>
      <section className="panel p-4 mt-8" aria-label="Settings and help">
        <h2 className="text-lg text-gold mb-2">Settings &amp; help</h2>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={reduce} onChange={(e) => toggleMotion(e.target.checked)} /> Reduce motion and animation</label>
        <p className="text-xs text-muted mt-2">Type your own actions during exploration, or tap the suggested buttons. Audio starts after your first click and can be muted in-game.</p>
        {meta && <p className="text-xs text-muted mt-2">Game Master: <b>{meta.providers.llm}</b>{meta.providers.llm_message ? ` - ${meta.providers.llm_message}` : ""} · Artwork: <b>{meta.providers.image}</b></p>}
        <p className="text-xs text-muted mt-1">Privacy: when an LLM provider is configured, scene context and your typed actions are sent to it. Campaigns can be deleted at any time.</p>
      </section>
    </main>
  );
}
