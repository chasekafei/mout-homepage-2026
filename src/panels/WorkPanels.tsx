import { WORK, type WorkId } from "../content/site";

type Go = (path: string) => void;

const NEXT: Partial<Record<WorkId, { label: string; to: string }>> = {
  social: { label: "读《社思现场》", to: "/create/writing" },
  agent: { label: "现在自己做的 Agent 和产品", to: "/create/products" },
};

export function WorkPanel({ id, go }: { id: WorkId; go: Go }) {
  const k = WORK.findIndex((w) => w.id === id);
  const w = WORK[k];
  const next = NEXT[id];
  return (
    <div className="work">
      <p className="lede">{w.oneLine}</p>
      <p className="meta">{w.where} · {w.role}</p>
      <ul className="work-items">
        {w.items.map((x) => <li key={x.t}><strong>{x.t}</strong><p>{x.d}</p></li>)}
      </ul>
      <p className="work-carry"><span>{k < WORK.length - 1 ? "带到下一站" : "现在相信的"}</span>{w.carry}</p>
      <section className="block">
        <div className="block-head"><h3>一根线串起来</h3><span className="meta">{k + 1} / {WORK.length}</span></div>
        <ol className="work-chain">
          {WORK.map((x) => (
            <li key={x.id} className={x.id === id ? "is-on" : ""}>
              <button type="button" aria-current={x.id === id ? "step" : undefined} onClick={() => go(`/work/${x.id}`)}>{x.name}</button>
            </li>
          ))}
        </ol>
      </section>
      {next && (
        <div className="row-actions">
          <button type="button" className="cta" onClick={() => go(next.to)}>{next.label}</button>
        </div>
      )}
    </div>
  );
}
