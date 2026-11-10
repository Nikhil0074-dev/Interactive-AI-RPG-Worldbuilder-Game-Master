"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Meta, WorldOverview } from "@/lib/types";

const GENRES = [["dark_fantasy", "Dark fantasy"], ["high_fantasy", "High fantasy"], ["mystery", "Mystery"]];
const TONES = ["mysterious", "heroic", "grim", "whimsical"];
const ARTS = [["painterly_fantasy", "Painterly fantasy"], ["ink_sketch", "Ink sketch"], ["storybook", "Storybook"]];
const DEFAULT_SETTING = "An ancient kingdom where magic is powered by memories, abandoned cities float above a poisonous ocean, and dragons have become extinct.";

export default function NewCampaign() {
  const router = useRouter();
  const [step, setStep] = useState<"world" | "overview" | "character">("world");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cid, setCid] = useState<string | null>(null);
  const [overview, setOverview] = useState<WorldOverview | null>(null);
  const [cfg, setCfg] = useState({ world_name: "The Shattered Crown", genre: "dark_fantasy", setting: DEFAULT_SETTING, tone: "mysterious",
    difficulty: "normal", combat_enabled: true, magic_level: "high", party_size: "solo", art_style: "painterly_fantasy" });
  const [ch, setCh] = useState({ name: "", char_class: "warrior", background: "", appearance: "", bonus_attribute: "" });
  useEffect(() => { api.meta().then(setMeta).catch((e) => setError(e.message)); }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setError(null);
    try { await fn(); } catch (e) { setError(e instanceof ApiError ? e.message : "Something went wrong."); } finally { setBusy(false); }
  };
  const generate = () => run(async () => {
    const id = cid ?? (await api.createCampaign(cfg)).id;
    setCid(id);
    const r = await api.generateWorld(id);
    setOverview(r.world); setStep("overview");
  });
  const begin = () => run(async () => {
    const body: Record<string, unknown> = { ...ch };
    if (!ch.bonus_attribute) delete body.bonus_attribute;
    await api.createCharacter(cid!, body);
    router.push(`/campaigns/${cid}`);
  });
  const cls = meta?.classes[ch.char_class];

  return (
    <main className="max-w-3xl mx-auto px-5 py-10">
      <button className="text-xs text-muted hover:text-gold" onClick={() => router.push("/")}>← Home</button>
      <h1 className="text-3xl text-gold mb-1">{step === "character" ? "Create your character" : "Create a new world"}</h1>
      <ol className="flex gap-2 text-xs text-muted mb-6" aria-label="Progress">
        {["world", "overview", "character"].map((s, i) => <li key={s} className={step === s ? "text-gold" : ""}>{i + 1}. {s === "world" ? "World" : s === "overview" ? "Overview" : "Character"}</li>)}
      </ol>
      {error && <p role="alert" className="panel border-blood text-blood p-3 mb-4 text-sm" data-testid="form-error">{error}</p>}

      {step === "world" && (
        <form className="panel p-5 space-y-4" onSubmit={(e) => { e.preventDefault(); void generate(); }} data-testid="world-form">
          <div><label className="label" htmlFor="wn">World name</label><input id="wn" className="input" maxLength={60} required value={cfg.world_name} onChange={(e) => setCfg({ ...cfg, world_name: e.target.value })} /></div>
          <div><label className="label" htmlFor="st">Setting description</label><textarea id="st" className="input h-24" maxLength={500} value={cfg.setting} onChange={(e) => setCfg({ ...cfg, setting: e.target.value })} /></div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div><label className="label" htmlFor="ge">Genre</label><select id="ge" className="input" value={cfg.genre} onChange={(e) => setCfg({ ...cfg, genre: e.target.value })}>{GENRES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div><label className="label" htmlFor="to">Narrative tone</label><select id="to" className="input" value={cfg.tone} onChange={(e) => setCfg({ ...cfg, tone: e.target.value })}>{TONES.map((t) => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label" htmlFor="di">Difficulty</label><select id="di" className="input" value={cfg.difficulty} onChange={(e) => setCfg({ ...cfg, difficulty: e.target.value })}>{["easy", "normal", "hard"].map((t) => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label" htmlFor="ml">Magic level</label><select id="ml" className="input" value={cfg.magic_level} onChange={(e) => setCfg({ ...cfg, magic_level: e.target.value })}>{["low", "medium", "high"].map((t) => <option key={t}>{t}</option>)}</select></div>
            <div><label className="label" htmlFor="ar">Visual art style</label><select id="ar" className="input" value={cfg.art_style} onChange={(e) => setCfg({ ...cfg, art_style: e.target.value })}>{ARTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
            <div><label className="label" htmlFor="pa">Party</label><select id="pa" className="input" disabled><option>Solo adventure</option></select></div>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={cfg.combat_enabled} onChange={(e) => setCfg({ ...cfg, combat_enabled: e.target.checked })} /> Enable combat encounters</label>
          <button className="btn btn-gold w-full py-3" disabled={busy || !cfg.world_name.trim()} data-testid="generate-world">{busy ? "Generating world..." : "Generate World"}</button>
        </form>
      )}

      {step === "overview" && overview && (
        <section className="panel p-5 space-y-4" data-testid="world-overview">
          <h2 className="text-2xl">{overview.name}</h2>
          <p className="font-serif italic text-muted">{overview.premise}</p>
          <p><b className="text-gold">Central conflict:</b> {overview.central_conflict}</p>
          <div><b className="text-gold">Factions</b><ul className="text-sm mt-1 space-y-1">{overview.factions.map((f) => <li key={f.id}><b>{f.name}</b> - <span className="text-muted">{f.goal}</span></li>)}</ul></div>
          <div><b className="text-gold">Region</b><p className="text-sm text-muted">{overview.regions.map((r) => `${r.name}: ${r.description}`).join(" ")}</p></div>
          <blockquote className="border-l-2 border-gold pl-3 font-serif">{overview.opening_scene}</blockquote>
          <button className="btn btn-gold w-full py-3" onClick={() => setStep("character")} data-testid="to-character">Create your character</button>
        </section>
      )}

      {step === "character" && meta && cls && (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void begin(); }} data-testid="character-form">
          <div className="panel p-5 space-y-4">
            <div><label className="label" htmlFor="cn">Character name</label><input id="cn" className="input" maxLength={40} required value={ch.name} onChange={(e) => setCh({ ...ch, name: e.target.value })} data-testid="char-name" /></div>
            <div><span className="label">Class</span>
              <div className="grid sm:grid-cols-2 gap-2">{Object.entries(meta.classes).map(([k, c]) => (
                <button type="button" key={k} onClick={() => setCh({ ...ch, char_class: k })} aria-pressed={ch.char_class === k} data-testid={`class-${k}`}
                  className={`text-left border rounded-md p-3 transition-colors ${ch.char_class === k ? "border-gold bg-panel2" : "border-edge hover:border-goldDim"}`}>
                  <b className="font-serif">{c.name}</b><span className="block text-xs text-muted">{c.specialty}</span>
                  <span className="block text-xs text-gold mt-1">{c.ability_details.map((a) => a.name).join(", ")}</span></button>))}</div></div>
            <div className="grid sm:grid-cols-2 gap-4">
              <div><label className="label" htmlFor="bg">Background</label><input id="bg" className="input" maxLength={200} value={ch.background} onChange={(e) => setCh({ ...ch, background: e.target.value })} placeholder="Exiled cartographer..." /></div>
              <div><label className="label" htmlFor="ap">Appearance</label><input id="ap" className="input" maxLength={200} value={ch.appearance} onChange={(e) => setCh({ ...ch, appearance: e.target.value })} placeholder="Silver hair, travel cloak..." /></div>
              <div><label className="label" htmlFor="ba">Bonus attribute (+2)</label>
                <select id="ba" className="input" value={ch.bonus_attribute} onChange={(e) => setCh({ ...ch, bonus_attribute: e.target.value })}><option value="">None</option>
                  {Object.keys(meta.attributes).map((a) => <option key={a} value={a}>{a}</option>)}</select></div>
            </div>
          </div>
          <div className="panel p-5" data-testid="char-summary">
            <h3 className="text-gold mb-2">{ch.name || "Your hero"} - {cls.name}</h3>
            <div className="grid grid-cols-3 gap-2 text-center">{Object.entries(cls.attributes).map(([a, v]) => {
              const total = v + (ch.bonus_attribute === a ? 2 : 0);
              return <div key={a} className="bg-panel2 border border-edge rounded p-2"><div className="text-[10px] uppercase text-muted">{meta.attributes[a]}</div><div className="text-lg">{total}</div></div>; })}</div>
            <p className="text-sm text-muted mt-3">Starting gear: {Object.values(cls.equipment_details).join(", ")}. Ability: {cls.ability_details.map((a) => `${a.name} (${a.mana} mana)`).join(", ")}.</p>
          </div>
          <button className="btn btn-gold w-full py-3" disabled={busy || !ch.name.trim()} data-testid="begin-adventure">{busy ? "Entering the world..." : "Begin Adventure"}</button>
        </form>
      )}
    </main>
  );
}
