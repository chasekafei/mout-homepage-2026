import { useState } from "react";
import { PLAY, WEDDING_GAME, type PlayId } from "../content/site";

type Go = (path: string) => void;

export function PlayPanel({ id, go }: { id: PlayId; go: Go }) {
  const p = PLAY[id];
  return (
    <div className="play-panel">
      <p className="lede">{p.lede}</p>
      <p className="meta">{p.meta}</p>
      {id === "gba" && <WeddingGame />}
      {p.body.map((t) => <p key={t}>{t}</p>)}
      {p.next && (
        <div className="row-actions">
          <button type="button" className="cta" onClick={() => go(p.next!.to)}>{p.next.label}</button>
        </div>
      )}
    </div>
  );
}

function WeddingGame() {
  const [on, setOn] = useState(false);
  if (on && WEDDING_GAME.src) {
    return (
      <div className="gba-frame">
        <iframe src={WEDDING_GAME.src} title="婚礼请柬小游戏" allow="autoplay; fullscreen" />
      </div>
    );
  }
  return (
    <figure className="gba-preview">
      <img src={WEDDING_GAME.preview} width={240} height={160} alt="GBA 屏幕上的婚礼现场" className="pixel" />
      {WEDDING_GAME.src
        ? <button type="button" className="cta" onClick={() => setOn(true)}>开始玩</button>
        : <figcaption className="meta">可以玩的版本正在整理，很快放上来。</figcaption>}
    </figure>
  );
}
