"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Json } from "@/lib/types";

type Tab = "locations" | "characters" | "factions" | "creatures" | "artifacts" | "lore" | "memory" | "history";

export function CodexPanel({ campaignId }: { campaignId: string }) {
  const [codex, setCodex] = useState<Json | null>(null);
  const [hist, setHist] = useState<Json | null>(null);
  const [tab, setTab] = useState<Tab>("locations");
  const [q, setQ] = useState("");
  useEffect(() => { void api.codex(campaignId).then(setCodex).catch(() => {}); void api.history(campaignId).then(setHist).catch(() => {}); }, [campaignId]);
  if (!codex) return <p className="text-muted">Loading codex...</p>;
  const tabs: Tab[] = ["locations", "characters", "factions", "creatures", "artifacts", "lore", "memory", "history"];
  const match = (o: Json) => !q || JSON.stringify(o).toLowerCase().includes(q.toLowerCase());
  const rows: Json[] = tab === "memory" ? codex.campaign_memory : tab === "history" ? (hist?.narrative || []).slice().reverse() : codex[tab];
  return (
    <div data-testid="codex-panel" className="space-y-3">
      <input className="input" placeholder="Search the codex..." aria-label="Search codex" value={q} onChange={(e) => setQ(e.target.value)} />
      <div className="flex flex-wrap gap-1" role="tablist">
        {tabs.map((t) => <button key={t} role="tab" aria-selected={tab === t} className={`btn text-xs py-1 capitalize ${tab === t ? "border-gold text-gold" : ""}`} onClick={() => setTab(t)}>{t}</button>)}
      </div>
      <ul className="space-y-2">
        {(rows || []).filter(match).map((r, i) => (
          <li key={r.id ?? i} className="border border-edge rounded-md p-3 bg-panel2 text-sm">
            <b className="font-serif">{r.name || r.title || (tab === "memory" ? `Turn ${r.turn}` : r.action)}</b>
            <p className="text-muted mt-1">{r.text || r.description || r.appearance || ""}</p>
            {r.relationship && <p className="text-xs text-goldDim mt-1">Trust {r.relationship.trust} · Respect {r.relationship.respect} · Fear {r.relationship.fear}
              {r.relationship.known_player_actions.length ? ` · Remembers: ${r.relationship.known_player_actions.join(", ").replace(/_/g, " ")}` : ""}</p>}
            {r.reputation !== undefined && <p className="text-xs text-goldDim mt-1">Reputation {r.reputation}</p>}
          </li>
        ))}
        {(rows || []).filter(match).length === 0 && <li className="text-muted text-sm">Nothing discovered yet.</li>}
      </ul>
    </div>
  );
}
