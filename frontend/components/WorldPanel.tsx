"use client";
import { useGame } from "@/lib/store";
import { Portrait } from "./SceneArt";

export function WorldPanel() {
  const view = useGame((s) => s.view);
  const scene = view?.scene;
  if (!scene || !view) return null;
  const active = (view.quests || []).filter((q) => q.status === "ACTIVE" || q.status === "AVAILABLE");
  return (
    <aside className="space-y-4" data-testid="world-panel" aria-label="World">
      {scene.combat && (
        <section className="panel p-4 border-blood" data-testid="combat-panel">
          <h3 className="text-blood text-lg">{scene.combat.name}</h3>
          <p className="text-xs text-muted mb-2">{scene.combat.description}</p>
          <div className="bar"><div className="h-full bg-blood transition-all duration-500" style={{ width: `${(scene.combat.hp / scene.combat.max_hp) * 100}%` }} /></div>
          <p className="text-xs mt-1 text-muted" data-testid="enemy-hp">{scene.combat.hp}/{scene.combat.max_hp} HP · Round {scene.combat.round}</p>
        </section>
      )}
      <section className="panel p-4">
        <h3 className="text-gold mb-2">Objectives</h3>
        {active.length === 0 && <p className="text-xs text-muted">No active objectives. Speak with the people you meet.</p>}
        <ul className="space-y-3">
          {active.map((q) => (
            <li key={q.id} data-testid={`objective-${q.id}`}>
              <p className="text-sm">{q.title}{q.status === "AVAILABLE" && <span className="text-xs text-leaf"> (offered)</span>}</p>
              {q.status === "ACTIVE" && <ul className="text-xs text-muted mt-1 space-y-0.5">
                {q.objectives.map((o) => <li key={o.id} className={o.done ? "line-through opacity-60" : ""}>{o.done ? "☑" : "☐"} {o.text}</li>)}
              </ul>}
            </li>
          ))}
        </ul>
      </section>
      <section className="panel p-4">
        <h3 className="text-gold mb-2">Nearby</h3>
        {scene.npcs.length === 0 && scene.objects.length === 0 && scene.ground_items.length === 0 && <p className="text-xs text-muted">Nothing of note.</p>}
        <ul className="space-y-2">
          {scene.npcs.map((n) => (
            <li key={n.id} className="flex items-center gap-2" data-testid={`npc-${n.id}`}>
              {n.relationship && <Portrait entityId={n.id} name={n.name} size={40} />}
              <div className="text-sm"><div>{n.name}</div><div className="text-xs text-muted">{n.role}{n.relationship ? ` · trust ${n.relationship.trust}` : ""}</div></div>
            </li>
          ))}
          {scene.objects.map((o) => <li key={o.id} className="text-sm text-muted">{o.name}{o.kind === "chest" ? (o.opened ? " (open)" : o.locked ? " (locked)" : " (unlocked)") : ""}</li>)}
          {scene.ground_items.map((i) => <li key={i.id} className="text-sm text-leaf">{i.name}{i.quantity > 1 ? ` ×${i.quantity}` : ""}</li>)}
        </ul>
      </section>
      <section className="panel p-4">
        <h3 className="text-gold mb-2">Exits</h3>
        <ul className="space-y-1">
          {scene.exits.map((e) => (
            <li key={e.id} className="text-sm" data-testid={`exit-${e.id}`}>
              <span className={e.locked ? "text-muted" : ""}>{e.locked ? "🔒 " : "→ "}{e.name}</span>
              {e.locked && e.reason && <p className="text-xs text-muted pl-5">{e.reason}</p>}
            </li>
          ))}
        </ul>
      </section>
      <section className="panel p-4 text-sm space-y-1">
        <h3 className="text-gold mb-1">World status</h3>
        <p className="text-muted">Time: <span className="text-parchment">{scene.time_of_day}</span> · Weather: <span className="text-parchment">{scene.location.weather}</span></p>
        {Object.entries(view.faction_rep || {}).map(([f, v]) => <p key={f} className="text-muted">{f.replace("faction_", "").replace(/_/g, " ")}: <span className={v >= 0 ? "text-leaf" : "text-blood"}>{v > 0 ? "+" : ""}{v}</span></p>)}
      </section>
    </aside>
  );
}
