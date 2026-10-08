import { CINEMA, MATCHES, SCENES, STAMPS_ELSEWHERE, TRIPS, type DestId } from "../content/site";

type Go = (path: string) => void;

const hasWindow = (id: DestId) => SCENES.depart.views?.includes(id) ?? false;

/** The centre screen: every destination; picking one drives the car there. */
export function NavPanel({ current, go }: { current: string; go: Go }) {
  return (
    <div className="depart">
      <p className="lede">选一个目的地，车窗外就换成那里。</p>
      <ol className="dest-list">
        {TRIPS.map((t) => (
          <li key={t.id}>
            <button type="button" className={t.id === current ? "is-current" : ""} onClick={() => go(`/depart/nav/${t.id}`)}>
              <span className="hover-kind">{t.en}</span>
              <strong>{t.name}</strong>
              <span>{t.line || t.where}</span>
              {!hasWindow(t.id) && <em className="tag">窗外施工中</em>}
            </button>
          </li>
        ))}
      </ol>
    </div>
  );
}

export function TripPanel({ id, go }: { id: DestId; go: Go }) {
  const t = TRIPS.find((x) => x.id === id)!;
  const matches = MATCHES.filter((m) => m.trip === id);
  return (
    <div className="depart trip">
      <p className="meta">{t.en} · {t.where}{t.when && ` · ${t.when}`}</p>
      {t.body.length ? t.body.map((p) => <p key={p}>{p}</p>) : <p className="muted">这一站的时间、照片和文字还在整理。</p>}
      {t.also && <p className="meta">同一趟还去了：{t.also.join("、")}</p>}
      {t.photos.length > 0 && (
        <div className="trip-photos">
          {t.photos.map((p) => <img key={p.src} src={p.src} width={p.w} height={p.h} alt={p.alt} loading="lazy" />)}
        </div>
      )}
      {matches.length > 0 && (
        <ul className="matches">
          {matches.map((m) => (
            <li key={m.event}>
              <span className="meta">{m.when} · {m.what}</span>
              <strong>{m.event}</strong>
            </li>
          ))}
        </ul>
      )}
      <div className="row-actions">
        {t.guide && <a className="cta" href={t.guide} target="_blank" rel="noreferrer">读这一站的攻略</a>}
        {matches.length > 0 && <button type="button" className="chip" onClick={() => go("/depart/pingpong")}>观赛清单</button>}
        <button type="button" className="chip" onClick={() => go("/depart/nav")}>换一个目的地</button>
      </div>
    </div>
  );
}

export function PassportPanel({ go }: { go: Go }) {
  return (
    <div className="depart">
      <p className="lede">远程工作的那几年，我常常带着电脑出发。这些是盖过章的地方。</p>
      <div className="stamps">
        {TRIPS.map((t, i) => (
          <button type="button" key={t.id} className="stamp" style={{ rotate: `${((i * 37) % 11) - 5}deg` }} onClick={() => go(`/depart/nav/${t.id}`)}>
            <strong>{t.name}</strong>
            <span>{t.en}</span>
            <em>{t.when || t.where}</em>
          </button>
        ))}
        {STAMPS_ELSEWHERE.map((n, i) => (
          <span key={n} className="stamp is-plain" style={{ rotate: `${((i * 53) % 9) - 4}deg` }}><strong>{n}</strong></span>
        ))}
      </div>
    </div>
  );
}

export function PingpongPanel({ go }: { go: Go }) {
  return (
    <div className="depart">
      <p className="lede">很多次出发，是为了去现场看王楚钦和孙颖莎的比赛。</p>
      <ul className="matches">
        {MATCHES.map((m) => (
          <li key={m.event}>
            <span className="meta">{m.when} · {m.city} · {m.what}</span>
            <strong>{m.event}</strong>
            {m.note && <span>{m.note}</span>}
            {m.trip && <button type="button" className="chip" onClick={() => go(`/depart/nav/${m.trip}`)}>这一站 →</button>}
          </li>
        ))}
      </ul>
      <p className="meta">更完整的观赛清单正在整理。</p>
      <div className="row-actions">
        <button type="button" className="cta" onClick={() => go("/create/products/stphq")}>给莎头粉丝做的 stpHQ</button>
      </div>
    </div>
  );
}

export function CinemaPanel() {
  return (
    <div className="depart">
      <p className="lede">{CINEMA.lede}</p>
      {CINEMA.body.map((p) => <p key={p}>{p}</p>)}
    </div>
  );
}
