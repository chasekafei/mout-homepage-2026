import { useEffect, useRef, useState } from "react";
import { ABOUT, BOOKS, CATS, PRODUCTS, SCENES, type SceneId } from "../content/site";

type Go = (path: string) => void;

export function LegacyPanel() {
  return (
    <div className="legacy">
      <p className="lede">
        大学学 CSS3 时写的个人首页。没有一张切图，鼠标移到不同的 tab 上，方块会像魔方一样翻到对应的那一面。
        从那之后，它就一直没更新过，直到这个网站。
      </p>
      <ScaledFrame src="/legacy/index.html" title="旧个人首页：叫我小T" w={1000} h={720} />
      <p className="meta">当年的名字叫“叫我小T”，副标题是“给生活打个草稿……”。外链已经失效，页面原样保留。</p>
      <a className="cta" href="/legacy/index.html" target="_blank" rel="noreferrer">在新窗口打开 ↗</a>
    </div>
  );
}

function ScaledFrame({ src, title, w, h }: { src: string; title: string; w: number; h: number }) {
  const box = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(0.5);
  useEffect(() => {
    const ro = new ResizeObserver(([e]) => setK(e.contentRect.width / w));
    ro.observe(box.current!);
    return () => ro.disconnect();
  }, [w]);
  return (
    <div className="crt">
      <div ref={box} className="crt-screen" style={{ aspectRatio: `${w} / ${h}` }}>
        <iframe src={src} title={title} loading="lazy" style={{ width: w, height: h, transform: `scale(${k})` }} />
      </div>
    </div>
  );
}

type Photo = { cat: string; src: string; thumb: string; w: number; h: number };

export function CatsPanel({ who, scene, go }: { who: "shaojiu" | "xiaoba"; scene: SceneId; go: Go }) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [big, setBig] = useState<Photo | null>(null);
  useEffect(() => { fetch("/media/cats/index.json").then((r) => r.json()).then(setPhotos).catch(() => {}); }, []);
  const cat = CATS[who];
  const other = who === "shaojiu" ? "xiaoba" : "shaojiu";
  const list = photos.filter((p) => p.cat === who || p.cat === "both");

  return (
    <div className="cats">
      <div className="cat-card">
        <div>
          <span className="meta">{cat.breed} · {cat.spot[scene]}</span>
          {cat.lines.map((l) => <p key={l}>{l}</p>)}
        </div>
        <button type="button" className="chip" onClick={() => go(`/${scene}/cats/${other}`)}>看看{CATS[other].name} →</button>
      </div>
      {big ? (
        <figure className="cat-big">
          <img src={big.src} width={big.w} height={big.h} alt={`${cat.name}的照片`} />
          <button type="button" className="chip" onClick={() => setBig(null)}>← 返回相册</button>
        </figure>
      ) : (
        <div className="cat-grid">
          {list.map((p, i) => (
            <button type="button" key={p.src} className="cat-thumb" onClick={() => setBig(p)} aria-label={`放大第 ${i + 1} 张`}>
              <img src={p.thumb} width={480} height={480} loading="lazy" alt="" />
              {p.cat === "both" && <span className="tag">合照</span>}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function AboutPanel({ go }: { go: Go }) {
  return (
    <div className="about">
      <div className="about-id">
        <img src="/media/me/avatar-pixel.png" width={96} height={96} alt="MouT.me 的像素头像" className="pixel" />
        <div>
          <p className="about-lead">{ABOUT.lead}</p>
          <div className="words">{ABOUT.words.map((w) => <span key={w}>{w}</span>)}</div>
        </div>
      </div>
      <p>{ABOUT.chain}</p>
      <section className="block">
        <div className="block-head"><h3>一些时间点</h3></div>
        <ol className="timeline">
          {ABOUT.timeline.map((x) => <li key={x.t}><span>{x.t}</span><p>{x.d}</p></li>)}
        </ol>
      </section>
      <section className="block">
        <div className="block-head"><h3>场外</h3></div>
        <p>{ABOUT.life}</p>
      </section>
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/chat")}>和我的分身聊聊</button>
        {ABOUT.contact.map((c) => <a key={c.href} className="chip" href={c.href} target="_blank" rel="noreferrer">{c.label}</a>)}
      </div>
    </div>
  );
}

export function BooksPanel({ go }: { go: Go }) {
  const target = ["/create/writing", "/create/podcast", "/create/products", "/create/me"];
  return (
    <div className="books">
      <p className="lede">桌上立着的四本书，是我做东西时的四个动作。</p>
      <ol className="book-list">
        {BOOKS.map((b, i) => (
          <li key={b.spine} className={`book book-${i}`}>
            <button type="button" onClick={() => go(target[i])}>
              <span className="spine">{b.spine}</span>
              <span className="book-main"><strong>{b.zh}</strong><span>{b.d}</span></span>
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function WindowPanel({ go }: { go: Go }) {
  const places = ["新疆 · 北疆大环线", "格鲁吉亚 · 巴统", "日本 · 福冈 / 北海道 / 名古屋", "卡塔尔 · 多哈", "香港 · 澳门", "成都 · 重庆 · 大连 · 长沙"];
  return (
    <div className="window">
      <p className="lede">
        远程工作的那几年，我大部分时间在家办公，也常常带着电脑出发。很多次出门，是为了去现场看王楚钦和孙颖莎的比赛。
      </p>
      <ul className="places">{places.map((p) => <li key={p}>{p}</li>)}</ul>
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/depart")}>去「出发」：坐进驾驶座</button>
      </div>
    </div>
  );
}

const FAQ = [
  { q: "你现在在做什么？", a: `离职后在休息，同时用 AI web coding 做自己的产品：CrossPod 串台、${PRODUCTS.map((p) => p.name).join("、")}，还有这个网站。` },
  { q: "你是做什么的？", a: "产品经理出身，做过电子政务、品牌营销小游戏、游戏创业、熟人社交，最近几年专注 AI 和 AI Agent。也会设计，会写代码。" },
  { q: "为什么做 CrossPod？", a: "因为看到一篇文章时，我更想听听身边某个人的看法。串台让你用朋友的分身开一期节目，它不一定最好，但一定最像你们。" },
  { q: "那两只猫叫什么？", a: "烧酒是狸花猫，小八是英短蓝白。在这个房间里，一个在桌角卷成一团，一个摊在麦克风旁边。" },
];

export function ChatPanel() {
  const [asked, setAsked] = useState<number[]>([]);
  return (
    <div className="chat">
      <p className="lede">
        几年前我用 Dify 做过一个“个人 AI 分身”，面试和认识新朋友时会把链接发过去：“如果我不在，你可以先和我的分身聊。”
        新的分身正在用这个网站里的资料重新训练。在它上线之前，先回答几个常被问到的问题。
      </p>
      <div className="chat-log" aria-live="polite">
        {asked.map((i) => (
          <div key={i} className="qa">
            <p className="bubble bubble-q">{FAQ[i].q}</p>
            <p className="bubble bubble-a">{FAQ[i].a}</p>
          </div>
        ))}
      </div>
      <div className="chat-chips">
        {FAQ.map((f, i) => !asked.includes(i) && (
          <button type="button" key={f.q} className="chip" onClick={() => setAsked([...asked, i])}>{f.q}</button>
        ))}
      </div>
    </div>
  );
}

export function IndexPanel({ scene, go }: { scene: SceneId; go: Go }) {
  return (
    <div className="index">
      <p className="lede">不想在场景里找东西的话，这里是{SCENES[scene].label}场景里全部的内容。</p>
      <ul className="index-list">
        {SCENES[scene].hotspots.map((h) => (
          <li key={h.id}>
            <a href={`/${scene}/${h.route}`} onClick={(e) => { e.preventDefault(); go(`/${scene}/${h.route}`); }}>
              <span className="hover-kind">{h.kind}</span>
              <strong>{h.label}</strong>
              <span>{h.hint}</span>
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
