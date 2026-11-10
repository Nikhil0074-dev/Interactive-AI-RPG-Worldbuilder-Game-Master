"use client";
import { useEffect, useState } from "react";
import { audio } from "@/lib/audio-manager";

export function AudioControls() {
  const [, force] = useState(0);
  const [open, setOpen] = useState(false);
  const a = audio();
  useEffect(() => a.subscribe(() => force((n) => n + 1)), [a]);
  const s = a.settings;
  const slider = (k: "master" | "music" | "ambient" | "sfx", label: string) => (
    <label className="block text-xs text-muted">{label}
      <input type="range" min={0} max={1} step={0.05} value={s[k]} aria-label={`${label} volume`} className="w-full accent-[#c9a85c]"
        onChange={(e) => a.update({ [k]: parseFloat(e.target.value) })} />
    </label>
  );
  return (
    <div className="relative">
      <button className="btn" data-testid="audio-toggle" aria-expanded={open} onClick={() => { a.unlock(); setOpen(!open); }}>
        {s.muted ? "Sound: off" : "Sound"}
      </button>
      {open && (
        <div className="panel absolute right-0 mt-2 w-60 p-4 space-y-3 z-30" data-testid="audio-panel">
          <button className="btn w-full" onClick={() => a.update({ muted: !s.muted })}>{s.muted ? "Unmute" : "Mute all"}</button>
          {slider("master", "Master")}{slider("music", "Music")}{slider("ambient", "Ambience")}{slider("sfx", "Effects")}
          <label className="flex items-center gap-2 text-xs text-muted">
            <input type="checkbox" checked={s.reducedSensory} onChange={(e) => a.update({ reducedSensory: e.target.checked })} />
            Reduced sensory mode (softer effects, no combat pulse)
          </label>
          {!a.unlocked && <p className="text-xs text-muted">Audio starts after your first interaction.</p>}
        </div>
      )}
    </div>
  );
}
