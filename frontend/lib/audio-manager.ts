/**
 * Central audio manager built on the Web Audio API.
 * - One instance owns all playback, so screens can never start duplicate ambience.
 * - Nothing plays until unlock() is called from a user gesture (browser autoplay policy).
 * - Ambience is procedural (filtered noise + drones); licensed audio files can be mixed in via `assets/audio`.
 */
import type { Audio } from "./types";

export type LayerType = "drone" | "wind" | "rain" | "echo" | "pulse";
export interface Layer { type: LayerType; freq?: number; gain: number }
export type SfxName = "click" | "travel" | "hit" | "magic" | "quest" | "levelup" | "error";
export interface AudioSettings { master: number; music: number; ambient: number; sfx: number; muted: boolean; reducedSensory: boolean }

export const DEFAULT_SETTINGS: AudioSettings = { master: 0.7, music: 0.5, ambient: 0.6, sfx: 0.7, muted: false, reducedSensory: false };
const FADE = 1.2;

/** Pure mapping from scene metadata to ambience layers (unit-tested). */
export function describeLayers(a: Pick<Audio, "weather" | "mood" | "location_type" | "time_of_day" | "profile">, reduced = false): Layer[] {
  const layers: Layer[] = [];
  const droneBase: Record<string, number> = { tense: 73.4, ominous: 49, mysterious: 55, uneasy: 61.7, calm: 82.4, hopeful: 98 };
  layers.push({ type: "drone", freq: droneBase[a.mood] ?? 55, gain: a.time_of_day === "night" ? 0.5 : 0.35 });
  if (a.weather === "rain" || a.weather === "storm") layers.push({ type: "rain", gain: a.weather === "storm" ? 0.55 : 0.4 });
  if (["mist", "fog", "still"].includes(a.weather) || a.location_type === "mountain_forest") layers.push({ type: "wind", gain: 0.3 });
  if (a.location_type === "underground_temple") layers.push({ type: "echo", gain: 0.35 });
  if (a.profile === "combat" && !reduced) layers.push({ type: "pulse", freq: 1.6, gain: 0.5 });
  return layers;
}

interface Running { key: string; gain: GainNode; stops: (() => void)[] }

export class AudioManager {
  private ctx: AudioContext | null = null;
  private master!: GainNode; private bus!: { music: GainNode; ambient: GainNode; sfx: GainNode };
  private current: Running | null = null;
  private pendingProfile: Audio | null = null;
  settings: AudioSettings = { ...DEFAULT_SETTINGS };
  private listeners = new Set<() => void>();
  ambienceStarts = 0; // exposed for tests / diagnostics

  constructor(private factory: () => AudioContext | null = () => (typeof window !== "undefined" && (window.AudioContext || (window as any).webkitAudioContext)) // eslint-disable-line @typescript-eslint/no-explicit-any
    ? new (window.AudioContext || (window as any).webkitAudioContext)() : null) { // eslint-disable-line @typescript-eslint/no-explicit-any
    if (typeof window !== "undefined") {
      try { const raw = window.localStorage.getItem("rpg_audio"); if (raw) this.settings = { ...DEFAULT_SETTINGS, ...JSON.parse(raw) }; } catch { /* ignore */ }
    }
  }

  get unlocked() { return this.ctx !== null; }
  subscribe(fn: () => void) { this.listeners.add(fn); return () => { this.listeners.delete(fn); }; }
  private emit() { this.listeners.forEach((f) => f()); }

  /** Must be called from a click/keypress handler. Safe to call repeatedly. */
  unlock() {
    if (!this.ctx) {
      const ctx = this.factory();
      if (!ctx) return;
      this.ctx = ctx;
      this.master = ctx.createGain(); this.master.connect(ctx.destination);
      this.bus = { music: ctx.createGain(), ambient: ctx.createGain(), sfx: ctx.createGain() };
      Object.values(this.bus).forEach((b) => b.connect(this.master));
      this.applyVolumes();
    }
    if (this.ctx.state === "suspended") void this.ctx.resume();
    if (this.pendingProfile) { const p = this.pendingProfile; this.pendingProfile = null; this.setProfile(p); }
    this.emit();
  }

  private clamp(v: number) { return Math.max(0, Math.min(1, Number.isFinite(v) ? v : 0)); }

  update(partial: Partial<AudioSettings>) {
    const s = { ...this.settings, ...partial };
    (["master", "music", "ambient", "sfx"] as const).forEach((k) => (s[k] = this.clamp(s[k])));
    this.settings = s;
    try { window.localStorage.setItem("rpg_audio", JSON.stringify(s)); } catch { /* ignore */ }
    this.applyVolumes();
    this.emit();
  }

  private applyVolumes() {
    if (!this.ctx) return;
    const t = this.ctx.currentTime, s = this.settings;
    this.master.gain.setTargetAtTime(s.muted ? 0 : s.master, t, 0.05);
    this.bus.music.gain.setTargetAtTime(s.music, t, 0.05);
    this.bus.ambient.gain.setTargetAtTime(s.ambient, t, 0.05);
    this.bus.sfx.gain.setTargetAtTime(s.reducedSensory ? s.sfx * 0.4 : s.sfx, t, 0.05);
  }

  /** Switch ambience. Re-requesting the active profile is a no-op, so duplicates are impossible. */
  setProfile(a: Audio) {
    if (!this.ctx) { this.pendingProfile = a; return; }
    const reduced = this.settings.reducedSensory || (typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
    const layers = describeLayers(a, reduced);
    const key = `${a.profile}|${a.mood}|${a.weather}|${a.time_of_day}|${reduced}`;
    if (this.current?.key === key) return;
    const ctx = this.ctx, t = ctx.currentTime;
    const prev = this.current;
    if (prev) {
      prev.gain.gain.cancelScheduledValues(t);
      prev.gain.gain.setTargetAtTime(0, t, FADE / 3);
      setTimeout(() => prev.stops.forEach((s) => s()), FADE * 1000 + 200);
    }
    const g = ctx.createGain(); g.gain.value = 0; g.connect(this.bus.ambient);
    g.gain.setTargetAtTime(1, t, FADE / 3);
    const stops: (() => void)[] = [];
    layers.forEach((l) => stops.push(this.buildLayer(l, g)));
    this.current = { key, gain: g, stops: [...stops, () => g.disconnect()] };
    this.ambienceStarts++;
  }

  private noise(): AudioBufferSourceNode {
    const ctx = this.ctx!, len = ctx.sampleRate * 2, buf = ctx.createBuffer(1, len, ctx.sampleRate), d = buf.getChannelData(0);
    for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1;
    const src = ctx.createBufferSource(); src.buffer = buf; src.loop = true; return src;
  }

  private buildLayer(l: Layer, out: GainNode): () => void {
    const ctx = this.ctx!, g = ctx.createGain(); g.gain.value = l.gain * 0.35; g.connect(out);
    const nodes: AudioScheduledSourceNode[] = [];
    if (l.type === "drone") {
      [1, 1.5, 2.005].forEach((m, i) => {
        const o = ctx.createOscillator(); o.type = i === 0 ? "sawtooth" : "sine"; o.frequency.value = (l.freq ?? 55) * m;
        const f = ctx.createBiquadFilter(); f.type = "lowpass"; f.frequency.value = 280;
        const og = ctx.createGain(); og.gain.value = i === 0 ? 0.5 : 0.25;
        o.connect(f); f.connect(og); og.connect(g); o.start(); nodes.push(o);
      });
    } else if (l.type === "wind" || l.type === "rain" || l.type === "echo") {
      const n = this.noise(), f = ctx.createBiquadFilter();
      f.type = l.type === "rain" ? "highpass" : "bandpass"; f.frequency.value = l.type === "rain" ? 1800 : l.type === "wind" ? 420 : 240; f.Q.value = 0.7;
      n.connect(f); f.connect(g); n.start(); nodes.push(n);
      if (l.type === "wind") { // slow gust LFO
        const lfo = ctx.createOscillator(); lfo.frequency.value = 0.11; const lg = ctx.createGain(); lg.gain.value = 180;
        lfo.connect(lg); lg.connect(f.frequency); lfo.start(); nodes.push(lfo);
      }
    } else if (l.type === "pulse") {
      const o = ctx.createOscillator(); o.type = "sine"; o.frequency.value = 48;
      const pg = ctx.createGain(); pg.gain.value = 0.3; const lfo = ctx.createOscillator(); lfo.frequency.value = l.freq ?? 1.6;
      const lg = ctx.createGain(); lg.gain.value = 0.3; lfo.connect(lg); lg.connect(pg.gain); o.connect(pg); pg.connect(g); o.start(); lfo.start(); nodes.push(o, lfo);
    }
    return () => { nodes.forEach((n) => { try { n.stop(); } catch { /* already stopped */ } }); g.disconnect(); };
  }

  /** Short procedural UI/combat sounds. */
  sfx(name: SfxName) {
    if (!this.ctx || this.settings.muted) return;
    const ctx = this.ctx, t = ctx.currentTime;
    const tone = (freq: number, dur: number, type: OscillatorType = "sine", vol = 0.25, slide = 0, delay = 0) => {
      const o = ctx.createOscillator(), g = ctx.createGain();
      o.type = type; o.frequency.setValueAtTime(freq, t + delay);
      if (slide) o.frequency.linearRampToValueAtTime(freq + slide, t + delay + dur);
      g.gain.setValueAtTime(0.0001, t + delay); g.gain.linearRampToValueAtTime(vol, t + delay + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, t + delay + dur);
      o.connect(g); g.connect(this.bus.sfx); o.start(t + delay); o.stop(t + delay + dur + 0.05);
    };
    switch (name) {
      case "click": tone(520, 0.06, "triangle", 0.12); break;
      case "travel": tone(180, 0.35, "sine", 0.18, -60); break;
      case "hit": tone(110, 0.18, "square", 0.22, -70); break;
      case "magic": tone(660, 0.4, "sine", 0.18, 440); tone(990, 0.4, "triangle", 0.1, 300, 0.05); break;
      case "quest": [523, 659, 784].forEach((f, i) => tone(f, 0.3, "triangle", 0.18, 0, i * 0.12)); break;
      case "levelup": [392, 523, 659, 784].forEach((f, i) => tone(f, 0.35, "sine", 0.2, 0, i * 0.1)); break;
      case "error": tone(160, 0.15, "sawtooth", 0.1); break;
    }
  }

  dispose() { this.current?.stops.forEach((s) => s()); this.current = null; if (this.ctx) void this.ctx.close?.(); this.ctx = null; }
}

let singleton: AudioManager | null = null;
export function audio(): AudioManager { return (singleton ??= new AudioManager()); }
export function sfxForEvents(types: string[]): SfxName | null {
  if (types.includes("LEVEL_UP")) return "levelup";
  if (types.includes("QUEST_COMPLETED")) return "quest";
  if (types.includes("ABILITY_USED")) return "magic";
  if (types.includes("ATTACK_RESOLVED")) return "hit";
  if (types.includes("PLAYER_ENTERED_LOCATION")) return "travel";
  return null;
}
