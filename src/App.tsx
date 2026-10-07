import { useCallback, useEffect, useRef, useState } from "react";
import { PODCAST, PRODUCTS, SCENES, STATES, WORK, hotspotByRoute, isScene, type SceneId, type StateId } from "./content/site";
import { player, usePlayer } from "./lib/audio";
import { navigate, parsePath, usePath } from "./lib/router";
import { SceneStage, type ScreenRect } from "./scene/SceneStage";
import { Sheet } from "./panels/Sheet";
import { WritingPanel } from "./panels/WritingPanel";
import { PodcastPanel } from "./panels/PodcastPanel";
import { ProductsPanel } from "./panels/ProductsPanel";
import { ProjectPanel, ThoughtPanel } from "./panels/NowPanels";
import { WorkPanel } from "./panels/WorkPanels";
import { PlayPanel } from "./panels/PlayPanels";
import { AboutPanel, BooksPanel, CatsPanel, ChatPanel, IndexPanel, LegacyPanel, WindowPanel } from "./panels/MiscPanels";

type View = { key: string; kind: string; title: string; hotspot: number; side?: "right"; back?: string; wide?: boolean; body: JSX.Element } | null;

/** The landing scene: the first navigation state that has a finished room. */
const HOME: SceneId = STATES.find((s) => s.ready && isScene(s.id))!.id as SceneId;
const ready = (id: string) => STATES.some((s) => s.id === id && s.ready);

export function App() {
  const path = usePath();
  const { state, rest } = parsePath(path);
  // "和我聊聊" keeps whichever room was on screen behind the conversation.
  const lastScene = useRef<SceneId>(HOME);
  if (isScene(state) && ready(state)) lastScene.current = state;
  const scene = lastScene.current;
  const [origin, setOrigin] = useState<ScreenRect | null>(null);
  const [toast, setToast] = useState<string>("");
  const [loaded, setLoaded] = useState(false);
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
    if (path === "/" || !s) { navigate(`/${HOME}`, { replace: true }); return; }
    if (!s.ready) { navigate(`/${scene}`, { replace: true }); say(s.teaser); }
  }, [path, state, scene, say]);

  const go = useCallback((to: string) => navigate(to), []);
  const close = useCallback(() => navigate(`/${scene}`), [scene]);
  const onReady = useCallback(() => setLoaded(true), []);
  const view = resolveView(scene, state, rest, go);
  const def = SCENES[scene];

  useEffect(() => {
    document.title = view ? `${view.title} · MouT.me` : `MouT.me · ${def.label}`;
  }, [view?.title, def.label]);

  const onOpen = useCallback((id: number, rect: ScreenRect) => {
    setOrigin(rect);
    navigate(`/${scene}/${SCENES[scene].hotspots[id].route}`);
  }, [scene]);

  const onNav = (id: StateId) => {
    const s = STATES.find((x) => x.id === id)!;
    if (!s.ready) { say(s.teaser); return; }
    setOrigin(null);
    navigate(`/${id}`);
  };

  const center = origin ? origin.x + origin.w / 2 : vw;
  const side = vw < 760 ? "bottom" : view?.side ?? (center > vw * 0.55 ? "left" : "right");
  const activeState: StateId = state === "chat" ? "chat" : scene;
  const act = touch ? "点一下场景里的东西打开。" : "移动鼠标看看场景里的东西，点一下打开。";

  return (
    <div className={`app ${loaded ? "is-ready" : ""}`}>
      <header className="topbar">
        <a className="brand" href={`/${HOME}`} onClick={(e) => { e.preventDefault(); onNav(HOME); }}>
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

      <main className="scene" aria-label={`${def.label}场景：场景里的物件都可以打开`}>
        <SceneStage scene={scene} openId={view ? view.hotspot : -1} onOpen={onOpen} onBackground={() => view && close()} onReady={onReady} />
      </main>

      <footer className="caption" hidden={!!view && side !== "bottom"}>
        <p><strong>{def.label}</strong>　{def.caption.replace("{act}", act)}</p>
        <button type="button" className="chip" onClick={() => { setOrigin(null); navigate(`/${scene}/index`); }}>内容目录</button>
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

      <div className="loader" aria-hidden={loaded}>
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

function resolveView(scene: SceneId, state: string, rest: string, go: (to: string) => void): View {
  const list = SCENES[scene].hotspots;
  const me = list.findIndex((h) => h.id === "me");
  const chat: View = { key: "chat", kind: "AI CLONE", title: "和我聊聊", hotspot: me, side: "right", body: <ChatPanel /> };
  if (state === "chat") return chat;
  if (state !== scene || !rest) return null;
  const sub = (base: string) => (r: string) => go(r.startsWith("/") ? r : `/${scene}/${base}${r ? `/${r}` : ""}`);

  if (rest === "index") return { key: "index", kind: "INDEX", title: "内容目录", hotspot: -1, side: "right", body: <IndexPanel scene={scene} go={go} /> };

  const h = hotspotByRoute(scene, rest);
  if (!h) return null;
  const id = list.indexOf(h);
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
      return { key: "cats", kind: h.kind, title: h.label, hotspot: id, body: <CatsPanel who={who} scene={scene} go={go} /> };
    }
    case "me":
      return scene === "now"
        ? { ...chat, key: "me" }
        : { key: "me", kind: h.kind, title: "关于 MouT.me", hotspot: id, side: "right", body: <AboutPanel go={go} /> };
    case "books":
      return { key: "books", kind: h.kind, title: "四个动作", hotspot: id, body: <BooksPanel go={go} /> };
    case "window":
      return { key: "window", kind: h.kind, title: "窗外", hotspot: id, body: <WindowPanel /> };
    case "project":
      return { key: "project", kind: h.kind, title: "现在在做：MouT.me", hotspot: id, body: <ProjectPanel go={go} /> };
    case "thought":
      return { key: "thought", kind: h.kind, title: "最近在想", hotspot: id, body: <ThoughtPanel go={go} /> };
    case "agent":
    case "social":
    case "games":
    case "brand":
    case "gov": {
      const w = WORK.find((x) => x.id === h.id)!;
      return { key: "work", kind: h.kind, title: w.name, hotspot: id, body: <WorkPanel id={w.id} go={go} /> };
    }
    case "tv":
    case "gba":
    case "archive":
    case "handhelds":
    case "arcade":
      return { key: "play", kind: h.kind, title: h.label, hotspot: id, wide: h.id === "gba", body: <PlayPanel id={h.id} go={go} /> };
  }
  return null;
}
