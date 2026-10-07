import { useCallback, useEffect, useRef, useState } from "react";
import { HOTSPOTS, PODCAST, PRODUCTS, STATES, hotspotByRoute, type StateId } from "./content/site";
import { player, usePlayer } from "./lib/audio";
import { navigate, parsePath, usePath } from "./lib/router";
import { SceneStage, type ScreenRect } from "./scene/SceneStage";
import { Sheet } from "./panels/Sheet";
import { WritingPanel } from "./panels/WritingPanel";
import { PodcastPanel } from "./panels/PodcastPanel";
import { ProductsPanel } from "./panels/ProductsPanel";
import { AboutPanel, BooksPanel, CatsPanel, ChatPanel, IndexPanel, LegacyPanel, WindowPanel } from "./panels/MiscPanels";

type View = { key: string; kind: string; title: string; hotspot: number; back?: string; wide?: boolean; body: JSX.Element } | null;

export function App() {
  const path = usePath();
  const { state, rest } = parsePath(path);
  const [origin, setOrigin] = useState<ScreenRect | null>(null);
  const [toast, setToast] = useState<string>("");
  const [ready, setReady] = useState(false);
  const [vw, setVw] = useState(innerWidth);
  const toastTimer = useRef(0);
  const touch = matchMedia("(pointer: coarse)").matches;

  useEffect(() => {
    const r = () => setVw(innerWidth);
    addEventListener("resize", r);
    return () => removeEventListener("resize", r);
  }, []);

  const say = useCallback((msg: string) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToast(""), 5200);
  }, []);

  useEffect(() => {
    const s = STATES.find((x) => x.id === state);
    if (path === "/" || !s) { navigate("/create", { replace: true }); return; }
    if (!s.ready) { navigate("/create", { replace: true }); say(s.teaser); }
  }, [path, state, say]);

  const go = useCallback((to: string) => navigate(to), []);
  const close = useCallback(() => navigate("/create"), []);
  const onReady = useCallback(() => setReady(true), []);
  const view = resolveView(state as StateId, rest, go);

  useEffect(() => {
    document.title = view ? `${view.title} · MouT.me` : "MouT.me · 创作";
  }, [view?.title]);

  const onOpen = useCallback((id: number, rect: ScreenRect) => {
    setOrigin(rect);
    navigate(`/create/${HOTSPOTS[id].route}`);
  }, []);

  const onNav = (id: StateId) => {
    const s = STATES.find((x) => x.id === id)!;
    if (!s.ready) { say(s.teaser); return; }
    setOrigin(null);
    navigate(id === "create" ? "/create" : `/${id}`);
  };

  const center = origin ? origin.x + origin.w / 2 : vw;
  const side = vw < 760 ? "bottom" : view?.hotspot === 6 || view?.hotspot === -1 ? "right" : center > vw * 0.55 ? "left" : "right";
  const activeState: StateId = state === "chat" ? "chat" : "create";

  return (
    <div className={`app ${ready ? "is-ready" : ""}`}>
      <header className="topbar">
        <a className="brand" href="/create" onClick={(e) => { e.preventDefault(); onNav("create"); }}>
          <img src="/media/me/avatar-face.png" width={28} height={28} alt="" className="pixel" />
          <span>MouT<em>.me</em></span>
        </a>
        <nav className="states" aria-label="状态">
          {STATES.map((s) => (
            <button
              key={s.id}
              type="button"
              className={`state ${activeState === s.id ? "is-active" : ""} ${s.ready ? "" : "is-soon"} ${s.id === "chat" ? "state-chat" : ""}`}
              aria-current={activeState === s.id ? "page" : undefined}
              onClick={() => onNav(s.id)}
            >
              {s.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="scene" aria-label="创作场景：桌上的物件都可以打开">
        <SceneStage openId={view ? view.hotspot : -1} onOpen={onOpen} onBackground={() => view && close()} onReady={onReady} />
      </main>

      <footer className="caption" hidden={!!view && side !== "bottom"}>
        <p><strong>创作</strong>　写作、播客和独立产品。{touch ? "点一下桌上的东西打开。" : "移动鼠标看看桌上的东西，点一下打开。"}</p>
        <button type="button" className="chip" onClick={() => { setOrigin(null); navigate("/create/index"); }}>内容目录</button>
        <NowPlaying />
      </footer>

      {view && (
        <Sheet
          key={view.key}
          side={side}
          origin={origin}
          kind={view.kind}
          title={view.title}
          wide={view.wide}
          onClose={close}
          onBack={view.back !== undefined ? () => navigate(view.back!) : undefined}
        >
          {view.body}
        </Sheet>
      )}

      <div className={`toast ${toast ? "is-on" : ""}`} role="status" aria-live="polite">
        {toast && <><span className="toast-tag">施工中</span>{toast}</>}
      </div>

      <div className="loader" aria-hidden={ready}>
        <div className="loader-mark"><img src="/media/me/avatar-face.png" width={56} height={56} alt="" className="pixel" /><span>MouT<em>.me</em></span></div>
        <div className="loader-bar"><span /></div>
        <p>正在把房间搬进来…</p>
      </div>
    </div>
  );
}

function NowPlaying() {
  const st = usePlayer();
  if (!st.src || (!st.playing && st.time === 0)) return null;
  return (
    <button type="button" className="chip now-playing" onClick={() => player.toggle(st.src)} aria-label={st.playing ? "暂停播客" : "继续播放播客"}>
      <span className={`np-bars ${st.playing ? "is-on" : ""}`} aria-hidden><i /><i /><i /></span>
      {PODCAST.episode.title}
      <span aria-hidden>{st.playing ? "❚❚" : "▶"}</span>
    </button>
  );
}

function resolveView(state: StateId, rest: string, go: (to: string) => void): View {
  if (state === "chat") return { key: "chat", kind: "AI CLONE", title: "和我聊聊", hotspot: 6, body: <ChatPanel /> };
  if (state !== "create" || !rest) return null;
  const sub = (base: string) => (r: string) => go(r.startsWith("/") ? r : `/create/${base}${r ? `/${r}` : ""}`);

  if (rest === "index") return { key: "index", kind: "INDEX", title: "内容目录", hotspot: -1, body: <IndexPanel go={go} /> };

  const h = hotspotByRoute(rest);
  if (!h) return null;
  const id = HOTSPOTS.indexOf(h);
  const tail = rest.slice(h.route.length + 1);

  switch (h.id) {
    case "writing":
      return tail
        ? { key: "writing", kind: "社思现场", title: `VOL.${tail.replace("vol-", "")}`, hotspot: id, back: "/create/writing", wide: true, body: <WritingPanel slug={tail} go={sub("writing")} /> }
        : { key: "writing", kind: h.kind, title: "写作与 Newsletter", hotspot: id, body: <WritingPanel slug="" go={sub("writing")} /> };
    case "podcast":
      return { key: "podcast", kind: h.kind, title: "串台 CrossPod", hotspot: id, body: <PodcastPanel /> };
    case "products": {
      const p = PRODUCTS.find((x) => x.id === tail);
      return { key: "products", kind: h.kind, title: p ? p.name : "独立产品原型仓", hotspot: id, body: <ProductsPanel id={tail} go={sub("products")} /> };
    }
    case "rubik":
      return { key: "legacy", kind: h.kind, title: "旧首页 · 叫我小T", hotspot: id, body: <LegacyPanel /> };
    case "cat_shaojiu":
    case "cat_xiaoba": {
      const who = h.id === "cat_shaojiu" ? "shaojiu" : "xiaoba";
      return { key: "cats", kind: h.kind, title: h.label, hotspot: id, body: <CatsPanel who={who} go={go} /> };
    }
    case "me":
      return { key: "me", kind: h.kind, title: "关于 MouT.me", hotspot: id, body: <AboutPanel go={go} /> };
    case "books":
      return { key: "books", kind: h.kind, title: "四个动作", hotspot: id, body: <BooksPanel go={go} /> };
    case "window":
      return { key: "window", kind: h.kind, title: "窗外", hotspot: id, body: <WindowPanel /> };
  }
  return null;
}
