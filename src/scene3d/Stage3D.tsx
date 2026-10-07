import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { HOTSPOTS } from "../content/site";
import { player } from "../lib/audio";
import type { ScreenRect } from "../scene/Stage2D";
import { Room3D, type Variant } from "./Room3D";

type Props = {
  openId: number;
  onOpen: (id: number, origin: ScreenRect) => void;
  onBackground: () => void;
  onReady?: () => void;
  onFail: () => void;
};

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const coarse = () => matchMedia("(pointer: coarse)").matches;
const LQIP: Record<Variant, string> = { desktop: "/scene/create/beauty_desktop_lqip.webp", mobile: "/scene/create/beauty_mobile_lqip.webp" };
const FRAME: Record<Variant, { aspect: number; focus: [number, number] }> = {
  desktop: { aspect: 16 / 9, focus: [0.47, 0.56] },
  mobile: { aspect: 9 / 16, focus: [0.56, 0.5] },
};

export function Stage3D({ openId, onOpen, onBackground, onReady, onFail }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const waveCanvas = useRef<HTMLCanvasElement>(null);
  const labelEl = useRef<HTMLDivElement>(null);
  const beaconEls = useRef<(HTMLButtonElement | null)[]>([]);
  const room = useRef<Room3D | null>(null);
  const [size, setSize] = useState({ w: innerWidth, h: innerHeight });
  const variant: Variant = size.w / size.h < 0.9 ? "mobile" : "desktop";
  const [loaded, setLoaded] = useState(false);
  const [hover, setHover] = useState(-1);
  const [dragging, setDragging] = useState(false);

  const live = useRef({
    hover: -1, hoverAmt: 0, lastHover: -1, dim: 0, reveal: 0, open: -1, t0: performance.now(),
    down: null as null | { x: number; y: number; lx: number; ly: number; moved: boolean; id: number },
  });

  useLayoutEffect(() => {
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(host.current!);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    let r: Room3D;
    try { r = new Room3D(canvas.current!); } catch { onFail(); return; }
    room.current = r;
    let cancelled = false;
    r.load().then(() => {
      if (cancelled) return;
      const s = host.current!.getBoundingClientRect();
      r.setView(s.width / s.height < 0.9 ? "mobile" : "desktop", s.width, s.height, pixelRatio());
      setLoaded(true);
    }).catch((e) => { console.error(e); if (!cancelled) onFail(); });
    return () => { cancelled = true; r.dispose(); room.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (loaded) room.current?.setView(variant, size.w, size.h, pixelRatio());
    const wc = waveCanvas.current;
    if (wc) { const d = Math.min(devicePixelRatio, 2); wc.width = Math.round(size.w * d); wc.height = Math.round(size.h * d); }
  }, [loaded, variant, size]);

  useEffect(() => { live.current.open = openId; }, [openId]);

  const setHoverId = (id: number) => {
    const L = live.current;
    if (id === L.hover) return;
    L.hover = id;
    if (id >= 0) L.lastHover = id;
    setHover(id);
  };

  const local = (e: React.PointerEvent) => {
    const r = host.current!.getBoundingClientRect();
    return [e.clientX - r.left, e.clientY - r.top] as const;
  };

  const onDown = (e: React.PointerEvent) => {
    if (e.button !== 0 || !room.current) return;
    const [x, y] = local(e);
    live.current.down = { x, y, lx: x, ly: y, moved: false, id: e.pointerId };
    host.current!.setPointerCapture(e.pointerId);
  };

  const onMove = (e: React.PointerEvent) => {
    const r = room.current;
    if (!r || !loaded) return;
    const [x, y] = local(e);
    const d = live.current.down;
    if (d && d.id === e.pointerId) {
      if (!d.moved && Math.hypot(x - d.x, y - d.y) > 6) { d.moved = true; setDragging(true); setHoverId(-1); }
      if (d.moved) r.drag(x - d.lx, y - d.ly);
      d.lx = x; d.ly = y;
      return;
    }
    if (e.pointerType === "touch") return;
    r.look((x / size.w) * 2 - 1, (y / size.h) * 2 - 1);
    setHoverId(r.pick(x, y));
  };

  const onUp = (e: React.PointerEvent) => {
    const d = live.current.down;
    live.current.down = null;
    if (host.current!.hasPointerCapture(e.pointerId)) host.current!.releasePointerCapture(e.pointerId);
    setDragging(false);
    const r = room.current;
    if (!d || d.moved || !r || !loaded) return;
    const [x, y] = local(e);
    const id = r.pick(x, y);
    if (id < 0) { onBackground(); return; }
    onOpen(id, r.hotspotRect(HOTSPOTS[id].id) ?? { x, y, w: 1, h: 1 });
  };

  useEffect(() => {
    if (!loaded) return;
    let raf = 0;
    const L = live.current;
    const still = reducedMotion();
    const levels = new Float32Array(28);
    const smooth = new Float32Array(28);
    let last = performance.now();
    let readySent = false;

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const r = room.current;
      if (!r) return;
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = (now - L.t0) / 1000;
      L.hoverAmt += ((L.hover >= 0 ? 1 : 0) - L.hoverAmt) * (1 - Math.exp(-dt * 10));
      L.dim += ((L.open >= 0 ? 1 : 0) - L.dim) * (1 - Math.exp(-dt * 7));
      L.reveal += (1 - L.reveal) * (1 - Math.exp(-dt * (still ? 30 : 4)));
      r.step(dt, still);
      r.draw({
        hover: L.hoverAmt > 0.01 ? (L.hover >= 0 ? L.hover : L.lastHover) : -1,
        hoverAmt: L.hoverAmt, open: L.open, dim: L.dim, time: still ? 0 : t, dust: still ? 0 : 1, reveal: L.reveal,
      });
      if (!readySent) { readySent = true; onReady?.(); }

      const { w, h } = size;
      HOTSPOTS.forEach((hs, i) => {
        const el = beaconEls.current[i];
        const a = r.meta.hotspots[hs.id]?.anchor;
        if (!el || !a) return;
        const [bx, by, front] = r.project(a);
        const show = front && bx > 8 && by > 60 && bx < w - 8 && by < h - 8;
        el.style.visibility = show ? "" : "hidden";
        el.style.transform = `translate3d(${bx}px, ${by}px, 0)`;
      });
      const lab = labelEl.current;
      if (lab && L.hover >= 0) {
        const rect = r.hotspotRect(HOTSPOTS[L.hover].id);
        const a = r.meta.hotspots[HOTSPOTS[L.hover].id]?.anchor;
        if (rect && a) {
          const [ax, ay] = r.project(a);
          const small = rect.w < w * 0.3 && rect.h < h * 0.35;
          const p = labelPos(small ? rect : { x: ax - 20, y: ay - 16, w: 40, h: 32 }, size);
          lab.style.left = `${p.x}px`;
          lab.style.top = `${p.y}px`;
          if (p.below) lab.dataset.below = ""; else delete lab.dataset.below;
        }
      }

      const wc = waveCanvas.current;
      const mic = r.meta.mic;
      if (wc && mic) {
        const ctx = wc.getContext("2d")!;
        const dpr = wc.width / w;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        const right = r.cameraRight();
        const at = (k: number) => r.project([mic[0] + right.x * k, mic[1] + right.y * k, mic[2] + right.z * k]);
        const [x0, yc, front] = at(0.06);
        const [x1] = at(0.15);
        const W = x1 - x0, H = W * 0.55;
        const playing = player.levels(levels);
        const focus = L.hover === 1 || L.open === 1;
        const n = levels.length;
        for (let i = 0; i < n; i++) {
          const env = Math.sin((i / (n - 1)) * Math.PI) ** 0.7;
          const idle = 0.18 + 0.14 * Math.sin(t * 2.1 + i * 0.7) + 0.08 * Math.sin(t * 5.3 + i * 1.9);
          const target = playing ? 0.12 + levels[i] * 1.1 : still ? 0.25 : idle * (focus ? 2.1 : 1);
          smooth[i] += (target * env - smooth[i]) * (1 - Math.exp(-dt * 14));
        }
        if (front && W > 4) {
          const alpha = (0.55 + (focus || playing ? 0.4 : 0)) * L.reveal * (1 - L.dim * (L.open === 1 ? 0 : 0.6));
          ctx.globalCompositeOperation = "lighter";
          ctx.shadowColor = "rgba(64, 232, 205, 0.9)";
          ctx.shadowBlur = 8;
          ctx.fillStyle = `rgba(110, 245, 220, ${alpha})`;
          const step = W / n, bw = Math.max(1.2, step * 0.42);
          for (let i = 0; i < n; i++) {
            const bh = Math.max(1.5, smooth[i] * H);
            ctx.beginPath();
            ctx.roundRect(x0 + i * step, yc - bh / 2, bw, bh, bw / 2);
            ctx.fill();
          }
          ctx.globalCompositeOperation = "source-over";
          ctx.shadowBlur = 0;
        }
      }
    };
    raf = requestAnimationFrame(frame);
    const vis = () => { if (document.hidden) cancelAnimationFrame(raf); else { last = performance.now(); raf = requestAnimationFrame(frame); } };
    document.addEventListener("visibilitychange", vis);
    return () => { cancelAnimationFrame(raf); document.removeEventListener("visibilitychange", vis); };
  }, [loaded, size, onReady]);

  const touch = coarse();
  const f = FRAME[variant];
  const FH = Math.max(size.h, size.w / f.aspect), FW = FH * f.aspect;
  const offX = Math.min(FW - size.w, Math.max(0, f.focus[0] * FW - size.w / 2));
  const offY = Math.min(FH - size.h, Math.max(0, f.focus[1] * FH - size.h / 2));
  const hovered = hover >= 0 && openId < 0 && !touch ? HOTSPOTS[hover] : null;

  return (
    <div
      ref={host}
      className={`stage stage-3d ${hover >= 0 ? "is-pointing" : ""} ${dragging ? "is-dragging" : ""}`}
      style={{ backgroundImage: `url(${LQIP[variant]})`, backgroundSize: `${FW}px ${FH}px`, backgroundPosition: `${-offX}px ${-offY}px` }}
      onPointerDown={onDown}
      onPointerMove={onMove}
      onPointerUp={onUp}
      onPointerCancel={onUp}
      onPointerLeave={(e) => { if (e.pointerType !== "touch") { room.current?.look(0, 0); setHoverId(-1); } }}
    >
      <canvas ref={canvas} className="stage-canvas" aria-hidden />
      <canvas ref={waveCanvas} className="stage-wave" aria-hidden />
      <div className="beacons">
        {HOTSPOTS.map((h, i) => {
          const active = openId === i;
          return (
            <button
              key={h.id}
              ref={(el) => { beaconEls.current[i] = el; }}
              type="button"
              className={`beacon ${active ? "is-open" : ""} ${hover === i ? "is-hover" : ""} ${openId >= 0 && !active ? "is-muted" : ""}`}
              style={{ left: 0, top: 0, visibility: "hidden" }}
              aria-label={`${h.label}：${h.hint}`}
              aria-expanded={active}
              onPointerDown={(e) => e.stopPropagation()}
              onPointerUp={(e) => e.stopPropagation()}
              onFocus={() => setHoverId(i)}
              onBlur={() => setHoverId(-1)}
              onPointerEnter={() => setHoverId(i)}
              onClick={(e) => {
                e.stopPropagation();
                const r = room.current?.hotspotRect(h.id);
                const b = e.currentTarget.getBoundingClientRect();
                onOpen(i, r ?? { x: b.x, y: b.y, w: b.width, h: b.height });
              }}
            >
              <span />
            </button>
          );
        })}
      </div>
      {hovered && (
        <div ref={labelEl} className="hover-label" role="presentation">
          <span className="hover-kind">{hovered.kind}</span>
          <strong>{hovered.label}</strong>
          <span className="hover-hint">{hovered.hint}</span>
        </div>
      )}
    </div>
  );
}

function pixelRatio() {
  return Math.min(devicePixelRatio || 1, 2);
}

function labelPos(rect: ScreenRect, view: { w: number; h: number }) {
  const W = 260;
  const x = Math.min(view.w - W / 2 - 16, Math.max(W / 2 + 16, rect.x + rect.w / 2));
  const above = rect.y - 14;
  if (above > 150) return { x, y: above, below: false };
  return { x, y: Math.min(view.h - 110, rect.y + rect.h + 14), below: true };
}
