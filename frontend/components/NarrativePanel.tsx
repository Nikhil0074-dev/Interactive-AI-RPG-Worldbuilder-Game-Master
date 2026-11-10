"use client";
import { useEffect, useRef } from "react";
import { useGame } from "@/lib/store";

export function NarrativePanel() {
  const log = useGame((s) => s.log);
  const busy = useGame((s) => s.busy);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ block: "end" }); }, [log.length, busy]);
  return (
    <div className="panel p-4 h-[19rem] overflow-y-auto space-y-3" data-testid="narrative" role="log" aria-live="polite" aria-label="Story">
      {log.length === 0 && <p className="text-muted italic">The story begins...</p>}
      {log.map((e) => (
        <div key={e.id} className="fade-in">
          {e.kind === "player" && <p className="text-gold text-sm">&gt; {e.text}</p>}
          {e.kind === "system" && <p className="text-blood text-sm italic" data-testid="system-msg">{e.text}</p>}
          {e.kind === "narration" && (
            <div>
              <p className="font-serif text-[1.05rem] leading-relaxed" data-testid="narration">{e.text}</p>
              {e.mechanics && e.mechanics.length > 0 && (
                <ul className="mt-2 text-xs text-muted border-l-2 border-goldDim pl-3 space-y-0.5" data-testid="mechanics">
                  {e.mechanics.map((m, i) => <li key={i}>{m}</li>)}
                </ul>
              )}
            </div>
          )}
        </div>
      ))}
      {busy && <p className="text-muted italic animate-pulse">The Game Master considers...</p>}
      <div ref={end} />
    </div>
  );
}
