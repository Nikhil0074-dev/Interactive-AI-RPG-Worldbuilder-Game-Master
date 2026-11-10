/** Minimal AudioContext stand-in that records node creation so tests can assert on playback behaviour. */
export function fakeParam() {
  return { value: 0, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {}, setTargetAtTime(v: number) { this.value = v; }, cancelScheduledValues() {} };
}
export class FakeNode {
  gain = fakeParam(); frequency = fakeParam(); Q = fakeParam(); type = ""; buffer: unknown = null; loop = false;
  started = 0; stopped = 0; connected: FakeNode[] = [];
  constructor(public kind: string, public ctx: FakeContext) { ctx.nodes.push(this); }
  connect(n: FakeNode) { this.connected.push(n); return n; }
  disconnect() {}
  start() { this.started++; }
  stop() { this.stopped++; }
  getChannelData() { return new Float32Array(8); }
}
export class FakeContext {
  nodes: FakeNode[] = []; state = "suspended"; currentTime = 0; sampleRate = 8; destination = new FakeNode("dest", this); resumed = 0; closed = false;
  createGain() { return new FakeNode("gain", this); }
  createOscillator() { return new FakeNode("osc", this); }
  createBiquadFilter() { return new FakeNode("filter", this); }
  createBufferSource() { return new FakeNode("buffersource", this); }
  createBuffer() { return new FakeNode("buffer", this); }
  resume() { this.state = "running"; this.resumed++; return Promise.resolve(); }
  close() { this.closed = true; return Promise.resolve(); }
  sources() { return this.nodes.filter((n) => n.kind === "osc" || n.kind === "buffersource"); }
}
