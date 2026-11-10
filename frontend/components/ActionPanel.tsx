"use client";
import { useState } from "react";
import { audio } from "@/lib/audio-manager";
import { useGame } from "@/lib/store";
import type { GameAction } from "@/lib/types";

const CAT_ORDER = ["dialogue", "combat", "talk", "interact", "travel", "examine", "take", "search", "rest"];

export function ActionPanel() {
  const scene = useGame((s) => s.view?.scene);
  const busy = useGame((s) => s.busy);
  const perform = useGame((s) => s.perform);
  const view = useGame((s) => s.view);
  const [text, setText] = useState("");
  if (!scene || !view) return null;
  const dead = view.game_over;
  const run = (a: GameAction) => { audio().unlock(); void perform(a.action, a.label); };
  const sorted = [...scene.available_actions].sort((a, b) => CAT_ORDER.indexOf(a.category) - CAT_ORDER.indexOf(b.category));
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    audio().unlock();
    setText("");
    await perform({ type: "custom", text: t }, t);
  };
  return (
    <div className="space-y-3" data-testid="action-panel">
      {dead ? (
        <div className="panel p-4 border-blood text-center" data-testid="game-over">
          <h3 className="text-2xl text-blood">You have fallen</h3>
          <p className="text-muted text-sm mt-1">Open the menu to load a saved checkpoint, or return home to begin a new campaign.</p>
        </div>
      ) : (
        <div className="flex flex-wrap gap-2" aria-label="Available actions">
          {sorted.map((a) => (
            <button key={a.id} className="btn" disabled={busy || a.enabled === false} onClick={() => run(a)} data-testid={`action-${a.id}`}>{a.label}</button>
          ))}
        </div>
      )}
      {!dead && scene.fsm_state === "EXPLORATION" && (
        <form onSubmit={submit} className="flex gap-2">
          <input className="input" value={text} maxLength={300} onChange={(e) => setText(e.target.value)} data-testid="custom-action-input"
            placeholder="Or describe your own action, e.g. “I search the rubble for a key”" aria-label="Custom action" disabled={busy} />
          <button className="btn btn-gold" disabled={busy || !text.trim()} data-testid="custom-action-submit">Act</button>
        </form>
      )}
      {!dead && scene.fsm_state !== "EXPLORATION" && <p className="text-xs text-muted">Free-text actions are available while exploring.</p>}
    </div>
  );
}
