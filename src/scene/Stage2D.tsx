import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { HOTSPOTS } from "../content/site";
import { player } from "../lib/audio";
import { Compositor, coverFit, type Fit } from "./compositor";
import {
  SCENE, beautyUrl, depthAt, idAt, loadBeauty, loadPasses, parallaxShift, pickVariant,
  type Lookup, type Region, type Variant,
} from "./sceneData";

export type ScreenRect = { x: number; y: number; w: number; h: number };

type Props = {
  openId: number;
  onOpen: (id: number, origin: ScreenRect) => void;
  onBackground: () => void;
  onReady?: () => void;
};

const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
const coarse = () => matchMedia("(pointer: coarse)").matches;

export function Stage2D({ openId, onOpen, onBackground, onReady }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const waveCanvas = useRef<HTMLCanvasElement>(null);
  const comp = useRef<Compositor | null>(null);

  const [size, setSize] = useState({ w: innerWidth, h: innerHeight });
  const variant: Variant = pickVariant(size.w, size.h);
  const [lookup, setLookup] = useState<Lookup | null>(null);
  const [lookupVariant, setLookupVariant] = useState<Variant | null>(null);
  const [beautyReady, setBeautyReady] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [fallbackSrc, setFallbackSrc] = useState("");
  const [passesFailed, setPassesFailed] = useState(false);
  const [hover, setHover] = useState(-1);

  const live = useRef({
    pointer: [0, 0] as [number, number],
    parallax: [0, 0] as [number, number],
    hover: -1, hoverAmt: 0, lastHover: -1,
    dim: 0, reveal: 0, open: -1, t0: performance.now(),
  });

  const fit: Fit = useMemo(() => {
    const iw = variant === "desktop" ? 1600 : 900;
    const ih = iw / SCENE.aspect[variant];
    return coverFit(size.w, size.h, iw, ih, SCENE.focus[variant]);
  }, [size, variant]);

  useLayoutEffect(() => {
    const ro = new ResizeObserver(([e]) => setSize({ w: e.contentRect.width, h: e.contentRect.height }));
    ro.observe(host.current!);
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    if (fallback || !canvas.current || comp.current) return;
    try { comp.current = new Compositor(canvas.current); } catch { setFallback(true); }
  }, [fallback]);

  useEffect(() => {
    let cancelled = false;
    setBeautyReady(false);
    live.current.reveal = 0;
    const stem = beautyUrl(variant, size.w, size.h, devicePixelRatio);
    loadPasses(variant).then(({ mask, depth, lookup }) => {
      if (cancelled) return;
      comp.current?.setTexture("mask", mask);
      comp.current?.setTexture("depth", depth);
      setLookup(lookup);
      setLookupVariant(variant);
    }).catch(() => { if (!cancelled) { setPassesFailed(true); setFallback(true); } });
    if (fallback) { setFallbackSrc(`${stem}.webp`); return () => { cancelled = true; }; }
    loadBeauty(stem).then((bmp) => {
      if (cancelled) return;
      comp.current?.setTexture("beauty", bmp);
      setBeautyReady(true);
    }).catch(() => { if (!cancelled) setFallback(true); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [variant, fallback]);

  useEffect(() => {
    if (beautyReady && (lookupVariant === variant || passesFailed)) onReady?.();
  }, [beautyReady, lookupVariant, variant, passesFailed, onReady]);

  useEffect(() => { live.current.open = openId; }, [openId]);

  const toImage = useCallback((sx: number, sy: number): [number, number] => {
    return [(sx + fit.offX) / fit.imgW, (sy + fit.offY) / fit.imgH];
  }, [fit]);

  const regionRect = useCallback((r: Region): ScreenRect => ({
    x: r.bx0 * fit.imgW - fit.offX, y: r.by0 * fit.imgH - fit.offY,
    w: (r.bx1 - r.bx0) * fit.imgW, h: (r.by1 - r.by0) * fit.imgH,
  }), [fit]);

  const pick = useCallback((sx: number, sy: number) => {
    if (!lookup) return -1;
    const [u, v] = toImage(sx, sy);
    const d = depthAt(lookup, u, v);
    const [dx, dy] = parallaxShift(d, live.current.parallax);
    return idAt(lookup, u + dx, v + dy);
  }, [lookup, toImage]);

  const setHoverId = useCallback((id: number) => {
    live.current.hover = id;
    if (id >= 0) live.current.lastHover = id;
    setHover(id);
  }, []);

  const onMove = (e: React.PointerEvent) => {
    if (e.pointerType === "touch") return;
    const r = host.current!.getBoundingClientRect();
    const sx = e.clientX - r.left, sy = e.clientY - r.top;
    live.current.pointer = [(sx / r.width) * 2 - 1, (sy / r.height) * 2 - 1];
    const id = pick(sx, sy);
    if (id !== live.current.hover) setHoverId(id);
  };

  const onClick = (e: React.MouseEvent) => {
    const r = host.current!.getBoundingClientRect();
    const id = pick(e.clientX - r.left, e.clientY - r.top);
    if (id < 0 || !lookup) { onBackground(); return; }
    onOpen(id, regionRect(lookup.regions[id]));
  };

  useEffect(() => {
    const dpr = Math.min(devicePixelRatio, 2);
    const c = canvas.current;
    if (c && !fallback) { c.width = Math.round(size.w * dpr); c.height = Math.round(size.h * dpr); }
    const wc = waveCanvas.current;
    if (wc) { wc.width = Math.round(size.w * dpr); wc.height = Math.round(size.h * dpr); }
  }, [size, fallback]);

  useEffect(() => {
    let raf = 0;
    const L = live.current;
    const still = reducedMotion();
    const levels = new Float32Array(28);
    const smooth = new Float32Array(28);
    let last = performance.now();

    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      const t = (now - L.t0) / 1000;
      const k = 1 - Math.exp(-dt * 6);
      const amp = still ? 0 : 0.006;
      L.parallax[0] += (-L.pointer[0] * amp * fit.scale[0] - L.parallax[0]) * k;
      L.parallax[1] += (-L.pointer[1] * amp * 0.6 * fit.scale[1] - L.parallax[1]) * k;
      L.hoverAmt += ((L.hover >= 0 ? 1 : 0) - L.hoverAmt) * (1 - Math.exp(-dt * 10));
      L.dim += ((L.open >= 0 ? 1 : 0) - L.dim) * (1 - Math.exp(-dt * 7));
      if (beautyReady && lookupVariant === variant) L.reveal += (1 - L.reveal) * (1 - Math.exp(-dt * (still ? 30 : 4)));

      const cmp = comp.current;
      if (cmp?.ready && !fallback) {
        cmp.draw({
          fit, viewPx: [size.w, size.h], parallax: L.parallax,
          hover: L.hoverAmt > 0.01 ? (L.hover >= 0 ? L.hover : L.lastHover) : -1,
          hoverAmt: L.hoverAmt, open: L.open, dim: L.dim, time: still ? 0 : t, dust: still ? 0 : 1, reveal: L.reveal,
        });
      }

      const wc = waveCanvas.current;
      if (wc && lookup) {
        const ctx = wc.getContext("2d")!;
        const dpr = wc.width / size.w;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, size.w, size.h);
        const cfg = SCENE.wave[variant];
        const shift = parallaxShift(0.33, L.parallax);
        const x0 = (cfg.x0 - shift[0]) * fit.imgW - fit.offX;
        const yc = (cfg.y - shift[1]) * fit.imgH - fit.offY;
        const W = (cfg.x1 - cfg.x0) * fit.imgW, H = cfg.h * fit.imgH;
        const playing = player.levels(levels);
        const focus = L.hover === 1 || L.open === 1;
        const n = levels.length;
        for (let i = 0; i < n; i++) {
          const env = Math.sin((i / (n - 1)) * Math.PI) ** 0.7;
          const idle = 0.18 + 0.14 * Math.sin(t * 2.1 + i * 0.7) + 0.08 * Math.sin(t * 5.3 + i * 1.9);
          const target = playing ? 0.12 + levels[i] * 1.1 : still ? 0.25 : idle * (focus ? 2.1 : 1);
          smooth[i] += (target * env - smooth[i]) * (1 - Math.exp(-dt * 14));
        }
        const alpha = (0.55 + (focus || playing ? 0.4 : 0)) * L.reveal * (1 - L.dim * (L.open === 1 ? 0 : 0.6));
        ctx.globalCompositeOperation = "lighter";
        ctx.shadowColor = "rgba(64, 232, 205, 0.9)";
        ctx.shadowBlur = 8;
        ctx.fillStyle = `rgba(110, 245, 220, ${alpha})`;
        const step = W / n, bw = Math.max(1.2, step * 0.42);
        for (let i = 0; i < n; i++) {
          const h = Math.max(1.5, smooth[i] * H);
          const x = x0 + i * step;
          ctx.beginPath();
          ctx.roundRect(x, yc - h / 2, bw, h, bw / 2);
          ctx.fill();
        }
        ctx.globalCompositeOperation = "source-over";
        ctx.shadowBlur = 0;
      }
    };
    raf = requestAnimationFrame(frame);
    const vis = () => { if (document.hidden) cancelAnimationFrame(raf); else { last = performance.now(); raf = requestAnimationFrame(frame); } };
    document.addEventListener("visibilitychange", vis);
    return () => { cancelAnimationFrame(raf); document.removeEventListener("visibilitychange", vis); };
  }, [fit, size, beautyReady, lookup, lookupVariant, variant, fallback, regionRect]);

  const regions = lookupVariant === variant ? lookup?.regions ?? [] : [];
  const hovered = hover >= 0 ? regions[hover] : undefined;
  const label = hovered && openId < 0 ? labelPos(labelRect(hovered, regionRect(hovered), fit), size) : null;
  const touch = coarse();
  const lqip = `${SCENE.base}/beauty_${variant}_lqip.webp`;

  return (
    <div
      ref={host}
      className={`stage ${hover >= 0 ? "is-pointing" : ""}`}
      style={{ backgroundImage: `url(${lqip})`, backgroundSize: `${fit.imgW}px ${fit.imgH}px`, backgroundPosition: `${-fit.offX}px ${-fit.offY}px` }}
      onPointerMove={onMove}
      onPointerLeave={() => { live.current.pointer = [0, 0]; setHoverId(-1); }}
      onClick={onClick}
    >
      {fallback ? (
        fallbackSrc && <img className="stage-img" src={fallbackSrc} alt="" onLoad={() => setBeautyReady(true)} style={{ width: fit.imgW, height: fit.imgH, left: -fit.offX, top: -fit.offY }} />
      ) : (
        <canvas ref={canvas} className="stage-canvas" aria-hidden />
      )}
      <canvas ref={waveCanvas} className="stage-wave" aria-hidden />

      <div className="beacons">
        {regions.map((r) => {
          if (r.area < 0.0004) return null;
          const h = HOTSPOTS[r.id];
          const rect = regionRect(r);
          const [bx, by] = beaconPoint(r, fit);
          if (bx < 8 || by < 60 || bx > size.w - 8 || by > size.h - 8) return null;
          const active = openId === r.id;
          return (
            <button
              key={h.id}
              type="button"
              className={`beacon ${active ? "is-open" : ""} ${hover === r.id ? "is-hover" : ""} ${openId >= 0 && !active ? "is-muted" : ""}`}
              style={{ left: bx, top: by }}
              aria-label={`${h.label}：${h.hint}`}
              aria-expanded={active}
              onFocus={() => setHoverId(r.id)}
              onBlur={() => setHoverId(-1)}
              onPointerEnter={() => setHoverId(r.id)}
              onClick={(e) => { e.stopPropagation(); onOpen(r.id, rect); }}
            >
              <span />
            </button>
          );
        })}
      </div>

      {label && hovered && !touch && (
        <div className="hover-label" style={{ left: label.x, top: label.y }} data-below={label.below || undefined} role="presentation">
          <span className="hover-kind">{HOTSPOTS[hovered.id].kind}</span>
          <strong>{HOTSPOTS[hovered.id].label}</strong>
          <span className="hover-hint">{HOTSPOTS[hovered.id].hint}</span>
        </div>
      )}
    </div>
  );
}

function beaconPoint(r: Region, fit: Fit): [number, number] {
  return [r.cx * fit.imgW - fit.offX, r.cy * fit.imgH - fit.offY];
}

function labelRect(r: Region, rect: ScreenRect, fit: Fit): ScreenRect {
  if (r.area < 0.04 && rect.w < fit.imgW * 0.3) return rect;
  const [x, y] = beaconPoint(r, fit);
  return { x: x - 20, y: y - 16, w: 40, h: 32 };
}

function labelPos(rect: ScreenRect, view: { w: number; h: number }) {
  const W = 260;
  const x = Math.min(view.w - W / 2 - 16, Math.max(W / 2 + 16, rect.x + rect.w / 2));
  const above = rect.y - 14;
  if (above > 150) return { x, y: above, below: false };
  return { x, y: Math.min(view.h - 110, rect.y + rect.h + 14), below: true };
}
