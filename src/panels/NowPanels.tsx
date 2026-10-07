import { NOW } from "../content/site";

type Go = (path: string) => void;

export function ProjectPanel({ go }: { go: Go }) {
  const p = NOW.project;
  return (
    <div className="now-project">
      <p className="lede">{p.oneLine}</p>
      <p className="meta"><span className="now-dot" aria-hidden />{p.status}</p>
      <section className="block">
        <div className="block-head"><h3>它是怎么做的</h3></div>
        <ul className="now-notes">{p.notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </section>
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/create")}>去创作场景看看</button>
        <button type="button" className="chip" onClick={() => go("/create/products")}>其他独立产品</button>
      </div>
    </div>
  );
}

export function ThoughtPanel({ go }: { go: Go }) {
  const t = NOW.thought;
  return (
    <div className="now-thought">
      <blockquote className="now-q">{t.q}</blockquote>
      {t.body.map((l) => <p key={l}>{l}</p>)}
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/chat")}>和我的分身聊聊这个</button>
        <button type="button" className="chip" onClick={() => go("/create/writing")}>更多写作</button>
      </div>
    </div>
  );
}
