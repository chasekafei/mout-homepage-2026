import { useEffect, useRef } from "react";
import { PODCAST } from "../content/site";
import { player, usePlayer } from "../lib/audio";

const fmt = (s: number) => (Number.isFinite(s) ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "--:--");

export function PodcastPanel() {
  const st = usePlayer();
  const ep = PODCAST.episode;
  const mine = st.src === ep.src;
  const playing = mine && st.playing;
  const pct = mine && st.duration ? (st.time / st.duration) * 100 : 0;

  useEffect(() => { player.load(ep.src); }, [ep.src]);

  return (
    <div className="podcast">
      <p className="lede"><strong>{PODCAST.slogan}</strong> 不用约时间，不用凑档期。</p>

      <section className="track" aria-label={`试听：${ep.title}`}>
        <button type="button" className={`play ${playing ? "is-on" : ""}`} onClick={() => player.toggle(ep.src)} aria-label={playing ? "暂停" : "播放"}>
          <span aria-hidden>{playing ? "❚❚" : "▶"}</span>
        </button>
        <div className="track-main">
          <div className="track-title"><strong>{ep.title}</strong><span className="meta">{fmt(mine ? st.time : 0)} / {fmt(st.duration)}</span></div>
          <Scrubber pct={pct} duration={st.duration} />
          <div className="track-tools">
            <button type="button" onClick={() => player.skip(-15)}>−15s</button>
            <button type="button" onClick={() => player.skip(30)}>+30s</button>
          </div>
        </div>
      </section>
      <p className="meta track-note">{ep.note}播放的时候，桌上麦克风旁的波形会跟着声音动。关掉面板也会继续播放。</p>

      <section className="block">
        <div className="block-head"><h3>为什么做串台</h3></div>
        {PODCAST.pitch.map((p) => <p key={p}>{p}</p>)}
      </section>
    </div>
  );
}

function Scrubber({ pct, duration }: { pct: number; duration: number }) {
  const bar = useRef<HTMLDivElement>(null);
  const seekTo = (clientX: number) => {
    const r = bar.current!.getBoundingClientRect();
    player.seek(((clientX - r.left) / r.width) * duration);
  };
  return (
    <div
      ref={bar}
      className="scrub"
      role="slider"
      tabIndex={0}
      aria-label="播放进度"
      aria-valuemin={0}
      aria-valuemax={Math.round(duration || 0)}
      aria-valuenow={Math.round((pct / 100) * (duration || 0))}
      onPointerDown={(e) => { if (duration) { (e.target as HTMLElement).setPointerCapture(e.pointerId); seekTo(e.clientX); } }}
      onPointerMove={(e) => { if (e.buttons && duration) seekTo(e.clientX); }}
      onKeyDown={(e) => { if (e.key === "ArrowRight") player.skip(5); if (e.key === "ArrowLeft") player.skip(-5); }}
    >
      <div className="scrub-fill" style={{ width: `${pct}%` }} />
    </div>
  );
}
