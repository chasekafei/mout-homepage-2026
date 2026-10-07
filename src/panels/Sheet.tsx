import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import type { ScreenRect } from "../scene/SceneStage";

type Props = {
  side: "left" | "right" | "bottom";
  origin: ScreenRect | null;
  kind: string;
  title: string;
  wide?: boolean;
  onClose: () => void;
  onBack?: () => void;
  children: ReactNode;
};

export function Sheet({ side, origin, kind, title, wide, onClose, onBack, children }: Props) {
  const el = useRef<HTMLElement>(null);

  useLayoutEffect(() => {
    const node = el.current;
    if (!node || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = node.getBoundingClientRect();
    let from: Keyframe;
    if (origin && side !== "bottom") {
      const sx = Math.max(0.08, origin.w / r.width), sy = Math.max(0.08, origin.h / r.height);
      from = { transform: `translate(${origin.x - r.left}px, ${origin.y - r.top}px) scale(${sx}, ${sy})`, opacity: 0, borderRadius: "24px" };
    } else {
      from = { transform: side === "bottom" ? "translateY(40px)" : `translateX(${side === "left" ? -32 : 32}px)`, opacity: 0 };
    }
    node.animate([from, { transform: "none", opacity: 1 }], { duration: 520, easing: "cubic-bezier(.2,.8,.2,1)" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    el.current?.focus({ preventScroll: true });
  }, [title]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    addEventListener("keydown", key);
    return () => removeEventListener("keydown", key);
  }, [onClose]);

  return (
    <aside ref={el} className={`sheet sheet-${side} ${wide ? "sheet-wide" : ""}`} role="dialog" aria-label={title} tabIndex={-1}>
      <header className="sheet-head">
        {onBack ? (
          <button type="button" className="sheet-btn" onClick={onBack} aria-label="返回上一层"><span aria-hidden>←</span></button>
        ) : <span className="sheet-dot" aria-hidden />}
        <div className="sheet-title">
          <span className="sheet-kind">{kind}</span>
          <h2>{title}</h2>
        </div>
        <button type="button" className="sheet-btn" onClick={onClose} aria-label="关闭，回到场景（Esc）"><span aria-hidden>✕</span></button>
      </header>
      <div className="sheet-body">{children}</div>
    </aside>
  );
}
