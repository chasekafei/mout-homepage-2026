import { lazy, Suspense, useState } from "react";
import { SCENES, STATES, isScene, type SceneId } from "../content/site";
import { Stage2D, type ScreenRect } from "./Stage2D";

export type { ScreenRect };

type Props = {
  scene: SceneId;
  openId: number;
  onOpen: (id: number, origin: ScreenRect) => void;
  onBackground: () => void;
  onReady?: () => void;
};

// three.js is most of the bundle; keep it out of the first paint.
const Stage3D = lazy(() =>
  import("../scene3d/Stage3D")
    .then((m) => ({ default: m.Stage3D }))
    .catch(() => ({ default: (p: Props & { onFail: () => void }) => <Stage2D {...p} /> })),
);

const ROOMS = STATES.filter((s) => s.ready && isScene(s.id)).map((s) => s.id as SceneId);

function supports3D() {
  if (new URLSearchParams(location.search).has("flat")) return false;
  try { return !!document.createElement("canvas").getContext("webgl2"); } catch { return false; }
}

const placeholder = (scene: SceneId) => (
  <div
    className="stage stage-3d"
    style={SCENES[scene].flat ? {
      backgroundImage: `url(/scene/${scene}/beauty_${innerWidth / innerHeight < 0.9 ? "mobile" : "desktop"}_lqip.webp)`,
      backgroundSize: "cover",
      backgroundPosition: "47% 56%",
    } : undefined}
  />
);

/** Realtime rooms when WebGL2 works; the pre-rendered 2.5D stage otherwise. */
export function SceneStage(props: Props) {
  const [mode, setMode] = useState<"3d" | "2d">(supports3D() ? "3d" : "2d");
  if (mode === "2d") return <Stage2D {...props} />;
  return (
    <Suspense fallback={placeholder(props.scene)}>
      <Stage3D {...props} preload={ROOMS.filter((id) => id !== props.scene)} onFail={() => setMode("2d")} />
    </Suspense>
  );
}
