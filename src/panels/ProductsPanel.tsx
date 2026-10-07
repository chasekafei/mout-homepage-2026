import { PRODUCTS } from "../content/site";

export function ProductsPanel({ id, go }: { id: string; go: (rest: string) => void }) {
  const open = PRODUCTS.find((p) => p.id === id);
  return (
    <div className="products">
      <p className="lede">
        桌角这台原型仓里插着我离职后用 AI web coding 做的几个产品。每个模块都可以单独拔出来看；最右边的空插槽留给下一个。
        CrossPod 串台在左边的麦克风里。
      </p>
      <div className="dock" role="list">
        {PRODUCTS.map((p) => {
          const active = p.id === open?.id;
          return (
            <article key={p.id} role="listitem" className={`cart cart-${p.slot} ${active ? "is-out" : ""}`}>
              <button type="button" className="cart-head" aria-expanded={active} onClick={() => go(active ? "" : p.id)}>
                <span className="cart-led" aria-hidden />
                <span className="cart-name">{p.name}<small>{p.zh}</small></span>
                <span className="cart-status">{p.status}</span>
              </button>
              <p className="cart-one">{p.oneLine}</p>
              {active && (
                <div className="cart-more">
                  <h4>为什么做</h4>
                  <p>{p.why}</p>
                  <ul>{p.notes.map((n) => <li key={n}>{n}</li>)}</ul>
                  {p.url && <a className="cta" href={p.url} target="_blank" rel="noreferrer">打开 {p.name} ↗</a>}
                </div>
              )}
            </article>
          );
        })}
        <div className="cart cart-empty" role="listitem" aria-label="空插槽">
          <span className="cart-led" aria-hidden />
          <span className="cart-name">空插槽<small>下一个原型</small></span>
        </div>
      </div>
    </div>
  );
}
