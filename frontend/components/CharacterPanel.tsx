"use client";
import { useGame } from "@/lib/store";
import { Bar } from "./Modal";

const GLYPH: Record<string, string> = { warrior: "⚔", mage: "✦", rogue: "🗡", ranger: "➹", cleric: "✚", bard: "♪", engineer: "⚙" };

export function CharacterPanel({ onOpen }: { onOpen: (m: "inventory" | "quests" | "sheet" | "codex") => void }) {
  const p = useGame((s) => s.view?.player);
  const fsm = useGame((s) => s.view?.campaign.fsm_state);
  if (!p) return null;
  const canMenu = fsm === "EXPLORATION" || fsm === "INVENTORY" || fsm === "QUEST_LOG";
  const xpPct = p.xp - p.xp_current_level;
  return (
    <aside className="panel p-4 space-y-4" data-testid="character-panel" aria-label="Character">
      <div className="flex items-center gap-3">
        <div className="w-14 h-14 rounded-md border border-goldDim bg-panel2 flex items-center justify-center text-2xl text-gold" aria-hidden>{GLYPH[p.char_class] || "★"}</div>
        <div>
          <h2 className="text-lg leading-tight" data-testid="player-name">{p.name}</h2>
          <p className="text-xs text-muted">Level {p.level} {p.class_name}</p>
        </div>
      </div>
      <Bar value={p.hp} max={p.max_hp} color="#b4483c" label="Health" />
      <Bar value={p.mana} max={p.max_mana} color="#4a7bd0" label="Mana" />
      <Bar value={xpPct} max={p.xp_next - p.xp_current_level} color="#c9a85c" label={`XP (to level ${p.level + 1})`} />
      <div className="flex justify-between text-sm"><span className="text-muted">Gold</span><span className="text-gold" data-testid="gold">{p.gold}</span></div>
      {Object.keys(p.statuses).length > 0 && <p className="text-xs text-mana">Effects: {Object.keys(p.statuses).join(", ").replace(/_/g, " ")}</p>}
      <div className="grid grid-cols-2 gap-2">
        <button className="btn" disabled={!canMenu} onClick={() => onOpen("inventory")} data-testid="open-inventory">Inventory</button>
        <button className="btn" disabled={!canMenu} onClick={() => onOpen("quests")} data-testid="open-quests">Quests</button>
        <button className="btn" onClick={() => onOpen("sheet")} data-testid="open-sheet">Character</button>
        <button className="btn" onClick={() => onOpen("codex")} data-testid="open-codex">Codex</button>
      </div>
    </aside>
  );
}
