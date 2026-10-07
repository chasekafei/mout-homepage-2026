import { useEffect, useRef, useState } from "react";

type Item = { id: string; section: string; n: string; title: string };
type Meta = { slug: string; vol: number; title: string; subtitle: string; date: string; range: string; items: Item[]; words: number };
type Issue = Meta & { html: string };
type Poster = { src: string; w: number; h: number };

const cache = new Map<string, unknown>();
async function getJSON<T>(url: string): Promise<T> {
  if (!cache.has(url)) cache.set(url, fetch(url).then((r) => { if (!r.ok) throw new Error(url); return r.json(); }));
  return cache.get(url) as Promise<T>;
}

export function WritingPanel({ slug, go }: { slug: string; go: (rest: string) => void }) {
  return slug ? <Reader slug={slug} go={go} /> : <Index go={go} />;
}

function Index({ go }: { go: (rest: string) => void }) {
  const [list, setList] = useState<Meta[] | null>(null);
  const [posters, setPosters] = useState<Poster[]>([]);
  useEffect(() => {
    getJSON<Meta[]>("/content/newsletter/index.json").then(setList).catch(() => setList([]));
    getJSON<Poster[]>("/media/newsletter/vol-24/index.json").then(setPosters).catch(() => {});
  }, []);

  return (
    <div className="writing">
      <p className="lede">
        写作是我逼自己思考的方式。这里会放文章、Newsletter 和还没想完的短想法。
        现在先收录 2022 年写的 24 期《社思现场》：每周整理熟人社交产品的动态，每条消息我都会去核实源头。
      </p>

      <section className="block">
        <div className="block-head"><h3>社思现场</h3><span className="meta">社交产品周报 · 2022.01–2022.08 · {list?.length ?? "…"} 期</span></div>
        <ol className="issue-list">
          {(list ?? []).map((m) => (
            <li key={m.slug}>
              <a href={`/create/writing/${m.slug}`} onClick={(e) => { e.preventDefault(); go(m.slug); }}>
                <span className="issue-vol">VOL.{String(m.vol).padStart(2, "0")}</span>
                <span className="issue-main">
                  <span className="issue-title">{m.items[0]?.title ?? m.title}</span>
                  <span className="issue-sub">{m.date}{m.subtitle ? ` · ${m.subtitle}` : ""} · {m.items.length} 条</span>
                </span>
              </a>
            </li>
          ))}
          {!list && <li className="loading-row">正在翻报纸…</li>}
        </ol>
      </section>

      {posters.length > 0 && (
        <section className="block">
          <div className="block-head"><h3>图片版</h3><span className="meta">为即刻做的 Figma 单页海报 · VOL.24</span></div>
          <div className="poster-strip" tabIndex={0} aria-label="VOL.24 图片版海报，可横向滚动">
            {posters.map((p, i) => (
              <a key={p.src} href={p.src} target="_blank" rel="noreferrer" className="poster">
                <img src={p.src} width={p.w} height={p.h} loading="lazy" alt={i === 0 ? "VOL.24 目录页" : `VOL.24 第 ${i} 页`} />
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Reader({ slug, go }: { slug: string; go: (rest: string) => void }) {
  const [issue, setIssue] = useState<Issue | null>(null);
  const [error, setError] = useState(false);
  const top = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setIssue(null);
    setError(false);
    getJSON<Issue>(`/content/newsletter/${slug}.json`).then(setIssue).catch(() => setError(true));
    top.current?.closest(".sheet-body")?.scrollTo({ top: 0 });
  }, [slug]);
  const [list, setList] = useState<Meta[]>([]);
  useEffect(() => { getJSON<Meta[]>("/content/newsletter/index.json").then(setList).catch(() => {}); }, []);
  const i = list.findIndex((m) => m.slug === slug);
  const newer = i > 0 ? list[i - 1] : undefined;
  const older = i >= 0 && i < list.length - 1 ? list[i + 1] : undefined;

  if (error) return <p className="lede">这一期没找到。<button className="link" onClick={() => go("")}>回到目录</button></p>;
  if (!issue) return <div ref={top} className="loading-row">正在展开这一期…</div>;

  return (
    <article className="reader" ref={top}>
      <header className="reader-head">
        <span className="reader-mast">社思现场</span>
        <h1>VOL.{String(issue.vol).padStart(2, "0")}{issue.subtitle ? <small> {issue.subtitle}</small> : null}</h1>
        <p className="meta">MouT.me · {issue.date} · 约 {Math.round(issue.words / 100) * 100} 字</p>
      </header>
      {issue.items.length > 0 && (
        <nav className="reader-toc" aria-label="本期目录">
          {issue.items.map((it) => (
            <a key={it.id} href={`#${it.id}`} onClick={(e) => { e.preventDefault(); document.getElementById(it.id)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>
              {it.n && <span className="nl-num">{it.n}</span>}{it.title}
            </a>
          ))}
        </nav>
      )}
      <div className="nl" dangerouslySetInnerHTML={{ __html: issue.html }} />
      <footer className="reader-foot">
        {older ? <button className="pager" onClick={() => go(older.slug)}>← VOL.{String(older.vol).padStart(2, "0")}</button> : <span />}
        <button className="pager" onClick={() => go("")}>全部 {list.length} 期</button>
        {newer ? <button className="pager" onClick={() => go(newer.slug)}>VOL.{String(newer.vol).padStart(2, "0")} →</button> : <span />}
      </footer>
    </article>
  );
}
