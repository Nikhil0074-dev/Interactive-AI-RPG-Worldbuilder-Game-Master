"use client";
import { useGame } from "@/lib/store";
import { Bar } from "./Modal";

export function InventoryPanel() {
  const inv = useGame((s) => s.view?.inventory);
  const busy = useGame((s) => s.busy);
  const act = useGame((s) => s.inventoryAction);
  if (!inv) return null;
  const label = { use: "Use", equip: "Equip", unequip: "Unequip", drop: "Drop" } as const;
  return (
    <div data-testid="inventory-panel" className="space-y-4">
      <Bar value={Math.round(inv.weight * 10) / 10} max={inv.capacity} color="#c9a85c" label="Carry weight" />
      <p className="text-sm text-muted">Gold: <span className="text-gold">{inv.gold}</span></p>
      <ul className="grid sm:grid-cols-2 gap-3">
        {inv.items.map((it) => (
          <li key={it.id} className={`border rounded-md p-3 bg-panel2 rarity-${it.rarity}`} data-testid={`item-${it.id}`}>
            <div className="flex justify-between gap-2">
              <h4 className="font-serif text-parchment">{it.name}{it.quantity > 1 ? ` ×${it.quantity}` : ""}</h4>
              <span className="text-[10px] uppercase tracking-wider">{it.rarity}</span>
            </div>
            <p className="text-xs text-muted mt-1">{it.description}</p>
            <p className="text-xs text-muted mt-1">{it.category} · wt {it.weight}
              {it.properties.damage ? ` · dmg ${it.properties.damage}` : ""}{it.properties.defense ? ` · def ${it.properties.defense}` : ""}
              {it.properties.heal ? ` · heals ${it.properties.heal}` : ""}{it.properties.mana ? ` · mana ${it.properties.mana}` : ""}
              {it.equipped ? " · equipped" : ""}</p>
            <div className="flex flex-wrap gap-2 mt-2">
              {it.actions.map((a) => (
                <button key={a} className="btn text-xs py-1" disabled={busy} data-testid={`item-${it.id}-${a}`}
                  onClick={() => void act(a, it.id, `${label[a]} ${it.name}`)}>{label[a]}</button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
