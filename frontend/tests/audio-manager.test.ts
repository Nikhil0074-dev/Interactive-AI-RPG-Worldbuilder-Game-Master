import { beforeEach, describe, expect, it, vi } from "vitest";
import { AudioManager, describeLayers, sfxForEvents } from "@/lib/audio-manager";
import { FakeContext } from "./fake-audio";

const forest = { profile: "shrine_mist_ominous", mood: "ominous", weather: "mist", time_of_day: "night", location_type: "mountain_forest" };
const rain = { profile: "ruined_city_rain", mood: "mysterious", weather: "rain", time_of_day: "night", location_type: "ruined_city" };
let ctx: FakeContext, created: number;
const make = () => { created = 0; ctx = new FakeContext(); return new AudioManager(() => { created++; return ctx as unknown as AudioContext; }); };

beforeEach(() => { localStorage.clear(); vi.useFakeTimers(); });

describe("describeLayers", () => {
  it("maps scene metadata to layers", () => {
    expect(describeLayers(rain).map((l) => l.type)).toEqual(["drone", "rain"]);
    expect(describeLayers(forest).map((l) => l.type)).toEqual(["drone", "wind"]);
    expect(describeLayers({ ...forest, location_type: "underground_temple", weather: "still" }).map((l) => l.type)).toContain("echo");
  });
  it("adds a combat pulse unless reduced sensory mode is on", () => {
    const c = { ...rain, profile: "combat", mood: "tense" };
    expect(describeLayers(c).some((l) => l.type === "pulse")).toBe(true);
    expect(describeLayers(c, true).some((l) => l.type === "pulse")).toBe(false);
  });
});

describe("AudioManager", () => {
  it("does not create an AudioContext until unlocked by a user gesture", () => {
    const m = make();
    m.setProfile(rain); m.sfx("click");
    expect(created).toBe(0); expect(m.unlocked).toBe(false); expect(m.ambienceStarts).toBe(0);
  });
  it("starts the queued ambience on unlock and resumes a suspended context", () => {
    const m = make();
    m.setProfile(rain); m.unlock();
    expect(created).toBe(1); expect(ctx.resumed).toBe(1); expect(m.ambienceStarts).toBe(1);
    expect(ctx.sources().length).toBeGreaterThan(0);
  });
  it("never duplicates ambience when the same profile is requested repeatedly", () => {
    const m = make(); m.unlock();
    m.setProfile(rain); const n = ctx.sources().length;
    for (let i = 0; i < 5; i++) { m.setProfile({ ...rain }); m.unlock(); }
    expect(m.ambienceStarts).toBe(1); expect(ctx.sources().length).toBe(n); expect(created).toBe(1);
  });
  it("crossfades and stops the previous ambience when the profile changes", () => {
    const m = make(); m.unlock(); m.setProfile(rain);
    const before = ctx.sources();
    m.setProfile(forest);
    expect(m.ambienceStarts).toBe(2);
    expect(before.every((s) => s.stopped === 0)).toBe(true);   // still fading
    vi.advanceTimersByTime(2000);
    expect(before.every((s) => s.stopped >= 1)).toBe(true);   // old layers stopped after the fade
  });
  it("applies mute and clamps and persists volumes", () => {
    const m = make(); m.unlock();
    m.update({ muted: true });
    expect((m as any).master.gain.value).toBe(0); // eslint-disable-line @typescript-eslint/no-explicit-any
    m.update({ muted: false, master: 5, music: -2 });
    expect(m.settings.master).toBe(1); expect(m.settings.music).toBe(0);
    expect(JSON.parse(localStorage.getItem("rpg_audio")!).master).toBe(1);
    expect(new AudioManager(() => null).settings.master).toBe(1);   // restored from storage
  });
  it("does not play sound effects while muted", () => {
    const m = make(); m.unlock(); const n = ctx.sources().length;
    m.update({ muted: true }); m.sfx("hit");
    expect(ctx.sources().length).toBe(n);
    m.update({ muted: false }); m.sfx("hit");
    expect(ctx.sources().length).toBeGreaterThan(n);
  });
  it("survives environments without Web Audio", () => {
    const m = new AudioManager(() => null);
    expect(() => { m.unlock(); m.setProfile(rain); m.sfx("click"); }).not.toThrow();
    expect(m.unlocked).toBe(false);
  });
  it("dispose stops everything", () => {
    const m = make(); m.unlock(); m.setProfile(rain); m.dispose();
    expect(ctx.sources().every((s) => s.stopped >= 1)).toBe(true); expect(ctx.closed).toBe(true);
  });
});

describe("sfxForEvents", () => {
  it("prioritises the most significant event", () => {
    expect(sfxForEvents(["ATTACK_RESOLVED", "LEVEL_UP"])).toBe("levelup");
    expect(sfxForEvents(["ATTACK_RESOLVED"])).toBe("hit");
    expect(sfxForEvents(["PLAYER_ENTERED_LOCATION"])).toBe("travel");
    expect(sfxForEvents(["FLAG_SET"])).toBeNull();
  });
});
