"use client";
import { useGame } from "@/lib/store";

export function CharacterSheet() {
  const p = useGame((s) => s.view?.player);
  if (!p) return null;
  return (
    <div className="space-y-5" data-testid="character-sheet">
      <div><h3 className="text-xl">{p.name}</h3><p className="text-sm text-muted">Level {p.level} {p.class_name} · {p.xp} XP · AC {p.armor_class} · Defense {p.defense}</p>
        {p.background && <p className="text-sm mt-1 italic">{p.background}</p>}</div>
      <section><h4 className="text-gold mb-2">Attributes</h4>
        <div className="grid grid-cols-3 gap-2">{Object.entries(p.attributes).map(([k, v]) => (
          <div key={k} className="bg-panel2 border border-edge rounded p-2 text-center"><div className="text-[10px] uppercase text-muted">{k.slice(0, 3)}</div>
            <div className="text-lg">{v} <span className="text-xs text-gold">({p.attribute_mods[k] >= 0 ? "+" : ""}{p.attribute_mods[k]})</span></div></div>))}</div></section>
      <section><h4 className="text-gold mb-2">Abilities</h4>
        <ul className="space-y-1 text-sm">{p.ability_details.map((a) => <li key={a.id}><b>{a.name}</b> <span className="text-xs text-mana">({a.mana} mana)</span> <span className="text-muted">- {a.desc}</span></li>)}</ul></section>
      <section><h4 className="text-gold mb-2">Equipment</h4>
        <ul className="space-y-1 text-sm">{Object.entries(p.equipment_details).map(([slot, it]) => <li key={slot}><span className="text-muted capitalize">{slot}:</span> {it ? it.name : "—"}</li>)}</ul></section>
    </div>
  );
}
