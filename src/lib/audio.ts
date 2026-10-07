import { useSyncExternalStore } from "react";

type State = { src: string; playing: boolean; time: number; duration: number };

let el: HTMLAudioElement | null = null;
let ctx: AudioContext | null = null;
let analyser: AnalyserNode | null = null;
let state: State = { src: "", playing: false, time: 0, duration: 0 };
const listeners = new Set<() => void>();
const set = (p: Partial<State>) => { state = { ...state, ...p }; listeners.forEach((l) => l()); };

function audio() {
  if (el) return el;
  el = new Audio();
  el.preload = "metadata";
  el.crossOrigin = "anonymous";
  el.addEventListener("play", () => set({ playing: true }));
  el.addEventListener("pause", () => set({ playing: false }));
  el.addEventListener("ended", () => set({ playing: false }));
  el.addEventListener("timeupdate", () => set({ time: el!.currentTime }));
  el.addEventListener("loadedmetadata", () => set({ duration: el!.duration }));
  el.addEventListener("durationchange", () => set({ duration: el!.duration }));
  return el;
}

function ensureGraph() {
  if (ctx || typeof AudioContext === "undefined") return;
  ctx = new AudioContext();
  const node = ctx.createMediaElementSource(audio());
  analyser = ctx.createAnalyser();
  analyser.fftSize = 256;
  analyser.smoothingTimeConstant = 0.78;
  node.connect(analyser);
  analyser.connect(ctx.destination);
}

export const player = {
  load(src: string) {
    const a = audio();
    if (state.src !== src) { a.src = src; set({ src, time: 0, duration: 0 }); }
  },
  async toggle(src: string) {
    this.load(src);
    ensureGraph();
    await ctx?.resume();
    const a = audio();
    if (a.paused) await a.play(); else a.pause();
  },
  seek(t: number) { const a = audio(); a.currentTime = Math.max(0, Math.min(t, a.duration || t)); set({ time: a.currentTime }); },
  skip(dt: number) { this.seek(audio().currentTime + dt); },
  /** Fills `out` with 0..1 band levels, or returns false when nothing is playing. */
  levels(out: Float32Array): boolean {
    if (!analyser || !state.playing) return false;
    const bins = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(bins);
    const usable = Math.floor(bins.length * 0.7);
    for (let i = 0; i < out.length; i++) {
      const a = Math.floor((i / out.length) ** 1.4 * usable);
      const b = Math.max(a + 1, Math.floor(((i + 1) / out.length) ** 1.4 * usable));
      let s = 0;
      for (let k = a; k < b; k++) s += bins[k];
      out[i] = s / (b - a) / 255;
    }
    return true;
  },
};

export function usePlayer() {
  return useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, () => state);
}
