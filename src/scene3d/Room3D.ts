import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
// must match the gltfpack version in tools/content/build-assets.mjs (three bundles an older decoder)
import { MeshoptDecoder } from "meshoptimizer/decoder";

export type Variant = "desktop" | "mobile";
type V3 = [number, number, number];
type CamMeta = { pos: V3; fwd: V3; up: V3; vfov: number; aspect: number; pivot: number; yaw: number; pitch: number };
export type Meta = {
  scene: string;
  atlas: number;
  encodeK: number;
  lut: { n: number; lo: number; hi: number };
  /** Mirrors the Blender compositor of this scene. */
  grade: { bloom: number; tint: V3; gain: V3; lift: V3 };
  /** Heights of the glossy horizontal planes: floor and work surface (glTF Y-up, metres). */
  planes: [number, number];
  /** Encoded radiance standing in for the culled ceiling in the plane reflections. */
  mirrorClear: V3;
  cameras: Record<Variant, CamMeta>;
  hotspots: Record<string, { min: V3; max: V3; anchor: V3 }>;
  ids: string[];
  markers: Record<string, V3>;
  backdrop?: { pos: V3; fwd: V3; up: V3; right: V3; hfov: number; aspect: number; dist?: number };
};
export type Rect = { x: number; y: number; w: number; h: number };

export const sceneBase = (id: string) => `/scene/${id}/3d`;
/** Where the design frame is anchored when the viewport crops it (frame uv). */
const FOCUS: Record<Variant, [number, number]> = { desktop: [0.47, 0.56], mobile: [0.56, 0.5] };
const BACKDROP_DIST = 40;
const GLARE_SIZE = 0.7;
/** Blur levels for the floor reflection (from 1/4 res); the planks are fairly rough. */
const REFL_LEVELS = 3;
/** Seconds for a scene change; reduced motion gets a short crossfade instead of the block wipe. */
const FADE = { blocks: 1.1, plain: 0.25 };
/** GPU-resident rooms (current, outgoing, one preloaded). */
const RESIDENT = 3;
const DEG = Math.PI / 180;

const FULLSCREEN_VS = `precision highp float;
in vec3 position;
out vec2 vUv;
void main() {
  vUv = position.xy * 0.5 + 0.5;
  gl_Position = vec4(position.xy, 0.0, 1.0);
}`;

const SCENE_VS = `precision highp float;
uniform mat4 modelMatrix;
uniform mat4 modelViewMatrix;
uniform mat4 projectionMatrix;
in vec3 position;
in vec4 color;
#ifdef USE_UV
in vec2 uv;
out vec2 vUv;
#endif
out vec3 vCol;
out vec3 vWorld;
flat out float vId;
uniform float uId;
void main() {
#ifdef USE_UV
  vUv = uv;
#endif
  vCol = color.rgb;
  vId = uId >= 0.0 ? uId : floor(color.a * 255.0 + 0.5);
  vWorld = (modelMatrix * vec4(position, 1.0)).xyz;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

// Radiance is stored encoded (sqrt(x / (x + K))) everywhere up to the final pass.
// Alpha carries the floor's Fresnel weight for the planar reflection.
const SCENE_FS = `precision highp float;
#ifdef USE_UV
uniform sampler2D uMap;
in vec2 vUv;
#endif
in vec3 vCol;
in vec3 vWorld;
flat in float vId;
uniform float uIdPass;
uniform float uMirror;
uniform float uMirrorY;
uniform vec2 uPlanes;
uniform vec3 cameraPosition;
out vec4 fragColor;
void main() {
  // mirrored pass: only what is above the reflecting plane may reflect
  if (uMirror > 0.5 && vWorld.y > uMirrorY + 0.001) discard;
  if (uIdPass > 0.5) { fragColor = vec4(vId / 255.0, 0.0, 0.0, 1.0); return; }
#ifdef USE_UV
  vec3 rgb = texture(uMap, vUv).rgb;
#else
  vec3 rgb = vCol;
#endif
  // alpha: floor -> F / 2, desk -> 0.5 + F / 2, anything else 0
  float gloss = 0.0;
  float plane = abs(vWorld.y - uPlanes.x) < 0.0015 ? 0.0 : abs(vWorld.y - uPlanes.y) < 0.0015 ? 1.0 : -1.0;
  if (uMirror < 0.5 && plane >= 0.0) {
    vec3 n = normalize(cross(dFdx(vWorld), dFdy(vWorld)));
    if (abs(n.y) > 0.97) {
      float c = clamp(normalize(cameraPosition - vWorld).y, 0.0, 1.0);
      gloss = plane * 0.5 + 0.5 * (0.04 + 0.96 * pow(1.0 - c, 5.0));
    }
  }
  fragColor = vec4(rgb, gloss);
}`;

const COMMON = `
uniform float uK;
vec3 decodeRad(vec3 e) { vec3 y = min(e * e, vec3(0.9995)); return uK * y / (1.0 - y); }
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
`;

// Mirrored view -> linear, 4-tap average into the first blur level.
const DECODE_FS = `precision highp float;
${COMMON}
uniform sampler2D uSrc;
uniform vec2 uTexel;
in vec2 vUv;
out vec4 fragColor;
void main() {
  vec3 c = decodeRad(texture(uSrc, vUv + vec2(-1.0, -1.0) * uTexel).rgb) + decodeRad(texture(uSrc, vUv + vec2(1.0, -1.0) * uTexel).rgb)
         + decodeRad(texture(uSrc, vUv + vec2(-1.0, 1.0) * uTexel).rgb) + decodeRad(texture(uSrc, vUv + vec2(1.0, 1.0) * uTexel).rgb);
  fragColor = vec4(c * 0.25, 1.0);
}`;

const BRIGHT_FS = `precision highp float;
${COMMON}
uniform sampler2D uSrc;
uniform vec2 uTexel;
uniform float uThreshold;
in vec2 vUv;
out vec4 fragColor;
void main() {
  vec3 acc = vec3(0.0);
  for (int i = 0; i < 4; i++) {
    vec2 o = vec2(i == 0 || i == 2 ? -1.0 : 1.0, i < 2 ? -1.0 : 1.0) * uTexel;
    vec3 x = decodeRad(texture(uSrc, vUv + o).rgb);
    float l = luma(x);
    float knee = 0.6 * uThreshold;
    float s = clamp(l - uThreshold + knee, 0.0, 2.0 * knee);
    acc += x * max(s * s / (4.0 * knee), l - uThreshold) / max(l, 1e-4);
  }
  fragColor = vec4(acc * 0.25, 1.0);
}`;

const DOWN_FS = `precision highp float;
uniform sampler2D uSrc;
uniform vec2 uTexel;
in vec2 vUv;
out vec4 fragColor;
void main() {
  vec3 c = texture(uSrc, vUv).rgb * 0.5;
  c += (texture(uSrc, vUv + vec2(-1.0, -1.0) * uTexel).rgb + texture(uSrc, vUv + vec2(1.0, -1.0) * uTexel).rgb
      + texture(uSrc, vUv + vec2(-1.0, 1.0) * uTexel).rgb + texture(uSrc, vUv + vec2(1.0, 1.0) * uTexel).rgb) * 0.125;
  fragColor = vec4(c, 1.0);
}`;

// Upsample with a 3x3 tent and add the level below it, like Blender's bloom chain.
const UP_FS = `precision highp float;
uniform sampler2D uSrc;
uniform sampler2D uAdd;
uniform vec2 uTexel;
in vec2 vUv;
out vec4 fragColor;
void main() {
  vec3 c = texture(uSrc, vUv).rgb * 4.0;
  c += (texture(uSrc, vUv + vec2(uTexel.x, 0.0)).rgb + texture(uSrc, vUv - vec2(uTexel.x, 0.0)).rgb
      + texture(uSrc, vUv + vec2(0.0, uTexel.y)).rgb + texture(uSrc, vUv - vec2(0.0, uTexel.y)).rgb) * 2.0;
  c += texture(uSrc, vUv + uTexel).rgb + texture(uSrc, vUv - uTexel).rgb
     + texture(uSrc, vUv + vec2(uTexel.x, -uTexel.y)).rgb + texture(uSrc, vUv + vec2(-uTexel.x, uTexel.y)).rgb;
  fragColor = vec4(c / 16.0 + texture(uAdd, vUv).rgb, 1.0);
}`;

const FINAL_FS = `precision highp float;
precision highp sampler3D;
${COMMON}
uniform sampler2D uMain;
uniform sampler2D uGlare;
uniform float uGlareNorm;
uniform sampler2D uRefl0;
uniform sampler2D uRefl1;
uniform float uReflNorm;
uniform float uDebugView;
uniform sampler2D uIds;
uniform sampler3D uLut;
uniform vec3 uLutRange;
uniform float uBloom;
uniform vec3 uTint;
uniform vec3 uGain;
uniform vec3 uLift;
uniform vec2 uView;
uniform vec2 uIdTexel;
uniform float uHover;
uniform float uHoverAmt;
uniform float uOpen;
uniform float uDim;
uniform float uTime;
uniform float uDust;
uniform float uReveal;
uniform vec2 uDrift;
uniform sampler2D uPrev;
uniform float uFade;
uniform float uBlocks;
uniform vec2 uFocus;
in vec2 vUv;
out vec4 fragColor;

float idAt(vec2 uv) { return floor(texture(uIds, uv).r * 255.0 + 0.5) - 1.0; }

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float motes(vec2 uv, float aspect) {
  float acc = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float cells = 26.0 + fi * 22.0;
    vec2 p = (uv + uDrift * (0.6 + fi * 0.25)) * vec2(aspect, 1.0) * cells;
    p += vec2(uTime * (0.05 + fi * 0.03), -uTime * (0.08 + fi * 0.02));
    vec2 c = floor(p);
    vec2 f = fract(p);
    float h = hash(c + fi * 17.0);
    if (h < 0.82) continue;
    vec2 pos = 0.5 + 0.32 * vec2(sin(uTime * 0.4 + h * 40.0), cos(uTime * 0.31 + h * 23.0));
    float r = mix(0.05, 0.11, fract(h * 7.3)) * (1.0 - fi * 0.18);
    float tw = 0.55 + 0.45 * sin(uTime * (1.2 + h * 2.0) + h * 30.0);
    acc += smoothstep(r, 0.0, length(f - pos)) * tw * (1.0 - fi * 0.25);
  }
  return acc;
}

vec3 toSrgb(vec3 c) { return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c)); }
vec3 fromSrgb(vec3 c) { return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(0.04045, c)); }

void main() {
  vec4 m = texture(uMain, vUv);
  float desk = step(0.5, m.a);
  float fres = (m.a - 0.5 * desk) * 2.0;
  vec3 refl = mix(texture(uRefl0, vUv).rgb, texture(uRefl1, vUv).rgb, desk) * uReflNorm;
  vec3 x = decodeRad(m.rgb) + refl * fres;
  if (uDebugView > 0.5) { fragColor = vec4(uDebugView < 1.5 ? vec3(fres * 4.0, desk, 0.0) : refl * 0.3, 1.0); return; }
  vec3 b = texture(uGlare, vUv).rgb * uGlareNorm;
  b = mix(vec3(luma(b)), b, 1.1);
  x += b * uBloom * uTint;
  // Blender colour balance (lift / gain), applied like the beauty compositor did
  vec3 s = toSrgb(max(x, 0.0));
  s = ((s - 1.0) * (2.0 - uLift) + 1.0) * uGain;
  x = fromSrgb(max(s, 0.0));
  vec3 l = clamp((log2(max(x, vec3(1e-6))) - uLutRange.x) / (uLutRange.y - uLutRange.x), 0.0, 1.0);
  vec3 col = texture(uLut, l * (uLutRange.z - 1.0) / uLutRange.z + 0.5 / uLutRange.z).rgb;

  float id = idAt(vUv);
  float lum = dot(col, vec3(0.299, 0.587, 0.114));
  if (uHover >= 0.0 && uHoverAmt > 0.001) {
    float inside = id == uHover ? 1.0 : 0.0;
    float hits = 0.0;
    for (int k = 0; k < 12; k++) {
      float a = float(k) * 0.5236;
      hits += idAt(vUv + vec2(cos(a), sin(a)) * uIdTexel * 3.0) == uHover ? 1.0 : 0.0;
    }
    float rim = (1.0 - inside) * smoothstep(0.0, 0.5, hits / 12.0);
    float pulse = 0.85 + 0.15 * sin(uTime * 3.0);
    col = mix(col, col * 1.1 + vec3(0.035, 0.03, 0.015), inside * uHoverAmt);
    col = mix(col, vec3(1.0, 0.97, 0.9), rim * 0.75 * uHoverAmt * pulse);
  }
  if (uDim > 0.001) {
    float keep = id == uOpen ? 1.0 : 0.0;
    vec3 muted = mix(col, vec3(lum), 0.22) * 0.55;
    col = mix(col, muted, uDim * (1.0 - keep * 0.85));
  }
  if (uDust > 0.0) {
    float beam = smoothstep(0.6, 0.92, lum) * (1.0 - uDim * 0.7);
    col += motes(vec2(vUv.x, 1.0 - vUv.y), uView.x / uView.y) * beam * vec3(1.0, 0.93, 0.8) * 0.32 * uDust;
  }
  col += (hash(vUv * uView + fract(uTime)) - 0.5) / 255.0;
  // Scene change: the outgoing room gives way block by block from the frame edges in toward the
  // character, who is identical in both rooms and so never visibly changes.
  if (uFade < 1.0) {
    vec3 prev = texture(uPrev, vUv).rgb;
    float k = uFade;
    if (uBlocks > 0.5) {
      float cell = max(12.0, uView.y / 30.0);
      vec2 c = floor(vUv * uView / cell);
      vec2 cc = (c + 0.5) * cell / uView;
      float d = length((cc - uFocus) * vec2(uView.x / uView.y, 1.0));
      float t = (1.0 - smoothstep(0.0, 1.15, d)) * 0.72 + hash(c * 0.37 + 3.1) * 0.28;
      k = smoothstep(t * 0.78, t * 0.78 + 0.22, uFade);
      col = mix(prev, col, k) + k * (1.0 - k) * 0.24 * vec3(1.0, 0.96, 0.86);
    } else {
      col = mix(prev, col, k);
    }
  }
  fragColor = vec4(col * uReveal, 1.0);
}`;

async function bitmap(url: string, flip = false) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return createImageBitmap(await res.blob(), {
    colorSpaceConversion: "none", premultiplyAlpha: "none", imageOrientation: flip ? "flipY" : "from-image",
  });
}

async function image(stem: string) {
  try { return await bitmap(`${stem}.avif`); } catch { return bitmap(`${stem}.webp`); }
}

function v3(a: V3) { return new THREE.Vector3(a[0], a[1], a[2]); }

export type DrawParams = {
  hover: number; hoverAmt: number; open: number; dim: number; time: number; dust: number; reveal: number;
};

/** One navigable room on the GPU: baked geometry, radiance atlas, window backdrop and display LUT. */
type Room = {
  id: string;
  meta: Meta;
  scene: THREE.Scene;
  /** Everything renderable; mirrored about each glossy plane for the reflection passes. */
  world: THREE.Group;
  backdrop: THREE.Mesh | null;
  mats: THREE.RawShaderMaterial[];
  lut: THREE.Data3DTexture;
  textures: THREE.Texture[];
  mirrorClear: THREE.Color;
};

export class Room3D {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera = new THREE.PerspectiveCamera(50, 1, 0.03, 200);
  variant: Variant = "desktop";
  /** Current and target orbit angles in degrees; shared by every room, like the camera itself. */
  readonly orbit = { yaw: 0, pitch: 0, ty: 0, tp: 0, lookX: 0, lookY: 0 };
  /** Loaded or loading rooms, least recently shown first. */
  private rooms = new Map<string, Promise<Room>>();
  private cur: Room | null = null;
  private prev: Room | null = null;
  private wanted = "";
  private disposed = false;
  private fade = 1;
  private fadeDur = FADE.blocks;
  private blocks = true;
  private main!: THREE.WebGLRenderTarget;
  private ids!: THREE.WebGLRenderTarget;
  /** The outgoing room's final image while a scene change runs. */
  private out!: THREE.WebGLRenderTarget;
  private down: THREE.WebGLRenderTarget[] = [];
  private up: THREE.WebGLRenderTarget[] = [];
  /** Per reflecting plane: the mirrored view and its blur chain. */
  private refl: { mirror: THREE.WebGLRenderTarget; down: THREE.WebGLRenderTarget[]; up: THREE.WebGLRenderTarget[] }[] = [];
  private quad: THREE.Mesh;
  private quadScene = new THREE.Scene();
  private ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  private bright: THREE.RawShaderMaterial;
  private downMat: THREE.RawShaderMaterial;
  private upMat: THREE.RawShaderMaterial;
  private decodeMat: THREE.RawShaderMaterial;
  private final: THREE.RawShaderMaterial;
  private size = { w: 1, h: 1, pr: 1 };
  private px = new Uint8Array(4);

  constructor(readonly canvas: HTMLCanvasElement) {
    const r = new THREE.WebGLRenderer({ canvas, antialias: false, alpha: false, powerPreference: "high-performance", stencil: false });
    r.autoClear = true;
    r.setClearColor(0x000000, 1);
    this.renderer = r;
    const tri = new THREE.BufferGeometry();
    tri.setAttribute("position", new THREE.BufferAttribute(new Float32Array([-1, -1, 0, 3, -1, 0, -1, 3, 0]), 3));
    const mk = (fs: string, uniforms: Record<string, THREE.IUniform>) =>
      new THREE.RawShaderMaterial({ vertexShader: FULLSCREEN_VS, fragmentShader: fs, uniforms, glslVersion: THREE.GLSL3, depthTest: false, depthWrite: false });
    this.bright = mk(BRIGHT_FS, { uSrc: { value: null }, uTexel: { value: new THREE.Vector2() }, uThreshold: { value: 1.2 }, uK: { value: 0.6 } });
    this.downMat = mk(DOWN_FS, { uSrc: { value: null }, uTexel: { value: new THREE.Vector2() } });
    this.upMat = mk(UP_FS, { uSrc: { value: null }, uAdd: { value: null }, uTexel: { value: new THREE.Vector2() } });
    this.decodeMat = mk(DECODE_FS, { uSrc: { value: null }, uTexel: { value: new THREE.Vector2() }, uK: { value: 0.6 } });
    this.final = mk(FINAL_FS, {
      uMain: { value: null }, uGlare: { value: null }, uGlareNorm: { value: 1 }, uRefl0: { value: null }, uRefl1: { value: null }, uReflNorm: { value: 1 },
      uDebugView: { value: Number(new URLSearchParams(location.search).get("debugView") ?? 0) },
      uIds: { value: null }, uLut: { value: null },
      uLutRange: { value: new THREE.Vector3() }, uK: { value: 0.6 }, uBloom: { value: 0.45 },
      uTint: { value: new THREE.Vector3() }, uGain: { value: new THREE.Vector3() }, uLift: { value: new THREE.Vector3() },
      uView: { value: new THREE.Vector2() }, uIdTexel: { value: new THREE.Vector2() },
      uHover: { value: -1 }, uHoverAmt: { value: 0 }, uOpen: { value: -1 }, uDim: { value: 0 }, uTime: { value: 0 },
      uDust: { value: 1 }, uReveal: { value: 0 }, uDrift: { value: new THREE.Vector2() },
      uPrev: { value: null }, uFade: { value: 1 }, uBlocks: { value: 1 }, uFocus: { value: new THREE.Vector2(0.5, 0.5) },
    });
    this.quad = new THREE.Mesh(tri, this.final);
    this.quad.frustumCulled = false;
    this.quadScene.add(this.quad);
  }

  /** Metadata of the room on screen (camera, hotspots, markers). */
  get meta() { return this.cur!.meta; }
  get current() { return this.cur?.id ?? ""; }
  get transitioning() { return this.prev !== null; }

  /** Fetch, decode and upload a room without showing it. */
  preload(id: string) { return this.room(id).then(() => undefined); }

  /**
   * Put a room on screen; with a room already showing, the change runs as a transition.
   * Resolves false when a later call superseded this one before its room finished loading.
   */
  async show(id: string, opts: { instant?: boolean; still?: boolean } = {}) {
    this.wanted = id;
    const room = await this.room(id);
    if (this.wanted !== id) return false;
    const p = this.rooms.get(id)!;
    this.rooms.delete(id);
    this.rooms.set(id, p);
    if (this.cur === room) return true;
    if (!this.cur || opts.instant) {
      this.prev = null;
      this.fade = 1;
    } else {
      this.prev = this.cur;
      this.fade = 0;
      this.blocks = !opts.still;
      this.fadeDur = opts.still ? FADE.plain : FADE.blocks;
    }
    this.cur = room;
    this.evict();
    this.updateCamera();
    return true;
  }

  private room(id: string) {
    let p = this.rooms.get(id);
    if (!p) {
      p = this.build(id);
      this.rooms.set(id, p);
      p.catch(() => this.rooms.delete(id));
    }
    return p;
  }

  private evict() {
    const keep = new Set([this.cur?.id, this.prev?.id]);
    for (const id of [...this.rooms.keys()]) {
      if (this.rooms.size <= RESIDENT) break;
      if (keep.has(id)) continue;
      const p = this.rooms.get(id)!;
      this.rooms.delete(id);
      p.then((r) => this.free(r), () => {});
    }
  }

  private async build(id: string): Promise<Room> {
    const r = this.renderer;
    const base = sceneBase(id);
    const res = await fetch(`${base}/scene.json`);
    if (!res.ok) throw new Error(`${base}/scene.json: ${res.status}`);
    const meta: Meta = await res.json();
    const big = Math.max(screen.width, screen.height) * Math.min(devicePixelRatio, 2) > 1600 && r.capabilities.maxTextureSize >= 4096;
    const loader = new GLTFLoader().setMeshoptDecoder(MeshoptDecoder);
    const [gltf, atlasBmp, lutBmp, backBmp] = await Promise.all([
      loader.loadAsync(`${base}/room.glb`),
      image(`${base}/atlas_${big ? 4096 : 2048}`),
      bitmap(`${base}/lut.png`),
      meta.backdrop ? image(`${base}/backdrop_${big ? 2560 : 1600}`).catch(() => null) : Promise.resolve(null),
    ]);
    if (this.disposed) throw new Error("Room3D disposed");

    const scene = new THREE.Scene();
    const world = new THREE.Group();
    scene.add(world);
    const mats: THREE.RawShaderMaterial[] = [];
    const textures = [this.texture(atlasBmp)];
    const planes = new THREE.Vector2(...meta.planes);
    const mat = (uv: boolean, map: THREE.Texture | null, hs = -1) => {
      const m = new THREE.RawShaderMaterial({
        vertexShader: SCENE_VS, fragmentShader: SCENE_FS, glslVersion: THREE.GLSL3,
        defines: uv ? { USE_UV: "" } : {},
        uniforms: {
          uMap: { value: map }, uIdPass: { value: 0 }, uId: { value: hs },
          uMirror: { value: 0 }, uMirrorY: { value: 0 }, uPlanes: { value: planes },
        },
      });
      mats.push(m);
      return m;
    };
    gltf.scene.traverse((o) => {
      const mesh = o as THREE.Mesh;
      if (!mesh.isMesh) return;
      const uv = !!mesh.geometry.getAttribute("uv");
      mesh.material = mat(uv, uv ? textures[0] : null);
      mesh.frustumCulled = false;
    });
    world.add(gltf.scene);

    let backdrop: THREE.Mesh | null = null;
    if (backBmp && meta.backdrop) {
      const b = meta.backdrop;
      const fwd = v3(b.fwd), up = v3(b.up), right = v3(b.right);
      const dist = b.dist ?? BACKDROP_DIST;
      const c = v3(b.pos).addScaledVector(fwd, dist);
      const hw = dist * Math.tan((b.hfov / 2) * DEG), hh = hw / b.aspect;
      const corner = (sx: number, sy: number) => c.clone().addScaledVector(right, sx * hw).addScaledVector(up, sy * hh);
      const p = [corner(-1, 1), corner(1, 1), corner(-1, -1), corner(1, -1)];
      const g = new THREE.BufferGeometry();
      g.setAttribute("position", new THREE.BufferAttribute(new Float32Array(p.flatMap((v) => [v.x, v.y, v.z])), 3));
      g.setAttribute("uv", new THREE.BufferAttribute(new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), 2));
      g.setAttribute("color", new THREE.BufferAttribute(new Uint8Array(16).fill(255), 4, true));
      g.setIndex([0, 2, 1, 1, 2, 3]);
      const tex = this.texture(backBmp);
      textures.push(tex);
      backdrop = new THREE.Mesh(g, mat(true, tex, meta.ids.indexOf("window") + 1));
      backdrop.frustumCulled = false;
      world.add(backdrop);
    }

    const lut = this.lut(lutBmp, meta.lut.n);
    // upload now so neither the first frame nor a scene change stalls
    for (const t of [...textures, lut]) r.initTexture(t);
    r.compile(scene, this.camera);
    const mc = meta.mirrorClear;
    return {
      id, meta, scene, world, backdrop, mats, lut, textures,
      mirrorClear: new THREE.Color().setRGB(mc[0], mc[1], mc[2], THREE.LinearSRGBColorSpace),
    };
  }

  private free(room: Room) {
    room.scene.traverse((o) => { if ((o as THREE.Mesh).isMesh) (o as THREE.Mesh).geometry.dispose(); });
    for (const m of room.mats) m.dispose();
    for (const t of room.textures) t.dispose();
    room.lut.dispose();
  }

  private texture(bmp: ImageBitmap) {
    const t = new THREE.Texture(bmp as unknown as HTMLImageElement);
    t.flipY = false;
    t.colorSpace = THREE.NoColorSpace;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.magFilter = THREE.LinearFilter;
    t.anisotropy = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    t.needsUpdate = true;
    return t;
  }

  /** The LUT strip is (b * N + r, g) with g growing upwards. */
  private lut(bmp: ImageBitmap, n: number) {
    const c = new OffscreenCanvas(bmp.width, bmp.height);
    const ctx = c.getContext("2d", { willReadFrequently: true })!;
    ctx.drawImage(bmp, 0, 0);
    const src = ctx.getImageData(0, 0, bmp.width, bmp.height).data;
    const data = new Uint8Array(n * n * n * 4);
    for (let b = 0; b < n; b++) for (let g = 0; g < n; g++) for (let r = 0; r < n; r++) {
      const si = ((n - 1 - g) * bmp.width + b * n + r) * 4;
      const di = ((b * n + g) * n + r) * 4;
      data[di] = src[si]; data[di + 1] = src[si + 1]; data[di + 2] = src[si + 2]; data[di + 3] = 255;
    }
    const t = new THREE.Data3DTexture(data, n, n, n);
    t.format = THREE.RGBAFormat;
    t.type = THREE.UnsignedByteType;
    t.minFilter = t.magFilter = THREE.LinearFilter;
    t.wrapS = t.wrapT = t.wrapR = THREE.ClampToEdgeWrapping;
    t.unpackAlignment = 1;
    t.needsUpdate = true;
    return t;
  }

  setView(variant: Variant, w: number, h: number, pixelRatio: number) {
    this.variant = variant;
    const r = this.renderer;
    r.setPixelRatio(pixelRatio);
    r.setSize(w, h, false);
    this.size = { w, h, pr: pixelRatio };
    const W = Math.round(w * pixelRatio), H = Math.round(h * pixelRatio);
    const hf = r.extensions.has("EXT_color_buffer_float") || r.extensions.has("EXT_color_buffer_half_float");
    this.main?.dispose();
    this.ids?.dispose();
    this.out?.dispose();
    this.disposeChain();
    this.main = new THREE.WebGLRenderTarget(W, H, { samples: 4, type: THREE.UnsignedByteType, depthBuffer: true });
    this.ids = new THREE.WebGLRenderTarget(Math.ceil(W / 2), Math.ceil(H / 2), { type: THREE.UnsignedByteType, depthBuffer: true, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
    this.out = new THREE.WebGLRenderTarget(W, H, { type: THREE.UnsignedByteType, depthBuffer: false, minFilter: THREE.NearestFilter, magFilter: THREE.NearestFilter });
    const bt = { type: hf ? THREE.HalfFloatType : THREE.UnsignedByteType, depthBuffer: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter };
    // Blender's bloom "Size" is relative to the image: 0.7 spreads glow across most of the frame.
    const levels = Math.max(2, Math.floor(Math.log2(GLARE_SIZE * Math.max(W, H))));
    for (let i = 0, w = W, h = H; i < levels && (w > 1 || h > 1); i++) {
      w = Math.max(1, Math.ceil(w / 2)); h = Math.max(1, Math.ceil(h / 2));
      this.down.push(new THREE.WebGLRenderTarget(w, h, bt));
      this.up.push(new THREE.WebGLRenderTarget(w, h, bt));
    }
    this.refl = [0, 1].map(() => {
      const mirror = new THREE.WebGLRenderTarget(Math.ceil(W / 2), Math.ceil(H / 2), { type: THREE.UnsignedByteType, depthBuffer: true });
      const down: THREE.WebGLRenderTarget[] = [], up: THREE.WebGLRenderTarget[] = [];
      for (let i = 0; i < REFL_LEVELS; i++) {
        const d = 4 << i;
        down.push(new THREE.WebGLRenderTarget(Math.max(1, Math.ceil(W / d)), Math.max(1, Math.ceil(H / d)), bt));
        if (i < REFL_LEVELS - 1) up.push(new THREE.WebGLRenderTarget(down[i].width, down[i].height, bt));
      }
      return { mirror, down, up };
    });
    this.updateCamera();
  }

  /** Nudge the orbit by a pointer delta (px); angles clamp to the configured range. */
  drag(dx: number, dy: number) {
    const c = this.meta.cameras[this.variant];
    const k = 0.11;
    this.orbit.ty = Math.max(-c.yaw, Math.min(c.yaw, this.orbit.ty - dx * k));
    this.orbit.tp = Math.max(-c.pitch, Math.min(c.pitch, this.orbit.tp - dy * k));
  }

  /** Small look-around from the hover position, in [-1, 1]. */
  look(x: number, y: number) {
    this.orbit.lookX = x;
    this.orbit.lookY = y;
  }

  step(dt: number, still: boolean) {
    const o = this.orbit;
    const k = still ? 1 : 1 - Math.exp(-dt * 7);
    const ty = o.ty - o.lookX * (still ? 0 : 1.6), tp = o.tp - o.lookY * (still ? 0 : 0.9);
    o.yaw += (ty - o.yaw) * k;
    o.pitch += (tp - o.pitch) * k;
    if (this.prev) {
      this.fade = Math.min(1, this.fade + dt / this.fadeDur);
      if (this.fade >= 1) this.prev = null;
    }
    this.updateCamera();
  }

  private updateCamera() {
    if (!this.cur) return;
    const c = this.meta.cameras[this.variant];
    const fwd0 = v3(c.fwd), up0 = v3(c.up);
    const right0 = fwd0.clone().cross(up0).normalize();
    const pivot = v3(c.pos).addScaledVector(fwd0, c.pivot);
    const q = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), this.orbit.yaw * DEG)
      .multiply(new THREE.Quaternion().setFromAxisAngle(right0, this.orbit.pitch * DEG));
    const fwd = fwd0.applyQuaternion(q), up = up0.applyQuaternion(q);
    const cam = this.camera;
    cam.position.copy(pivot).addScaledVector(fwd, -c.pivot);
    cam.up.copy(up);
    cam.lookAt(cam.position.clone().add(fwd));
    const { w, h } = this.size;
    const FH = Math.max(h, w / c.aspect), FW = FH * c.aspect;
    const f = FOCUS[this.variant];
    const ox = Math.min(FW - w, Math.max(0, f[0] * FW - w / 2));
    const oy = Math.min(FH - h, Math.max(0, f[1] * FH - h / 2));
    cam.fov = c.vfov;
    cam.aspect = c.aspect;
    cam.setViewOffset(FW, FH, ox, oy, w, h);
    cam.updateProjectionMatrix();
    cam.updateMatrixWorld();
  }

  /** Hotspot index under a CSS-pixel position (from the last rendered id buffer), or -1. */
  pick(x: number, y: number) {
    if (!this.ids || this.prev) return -1;
    const { w, h } = this.size;
    const px = Math.floor((x / w) * this.ids.width), py = Math.floor((1 - y / h) * this.ids.height);
    if (px < 0 || py < 0 || px >= this.ids.width || py >= this.ids.height) return -1;
    this.renderer.readRenderTargetPixels(this.ids, px, py, 1, 1, this.px);
    return this.px[0] - 1;
  }

  project(p: V3 | THREE.Vector3): [number, number, boolean] {
    const v = Array.isArray(p) ? v3(p) : p.clone();
    const inFront = v.clone().sub(this.camera.position).dot(this.camera.getWorldDirection(new THREE.Vector3())) > 0;
    v.project(this.camera);
    return [(v.x + 1) / 2 * this.size.w, (1 - v.y) / 2 * this.size.h, inFront];
  }

  hotspotRect(name: string): Rect | null {
    const hs = this.cur?.meta.hotspots[name];
    if (!hs) return null;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (let i = 0; i < 8; i++) {
      const p: V3 = [i & 1 ? hs.max[0] : hs.min[0], i & 2 ? hs.max[1] : hs.min[1], i & 4 ? hs.max[2] : hs.min[2]];
      const [x, y, front] = this.project(p);
      if (!front) continue;
      x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y);
    }
    if (!isFinite(x0)) return null;
    const { w, h } = this.size;
    x0 = Math.max(0, x0); y0 = Math.max(0, y0); x1 = Math.min(w, x1); y1 = Math.min(h, y1);
    return { x: x0, y: y0, w: Math.max(1, x1 - x0), h: Math.max(1, y1 - y0) };
  }

  /** World-space right vector of the current camera (for screen-aligned overlays). */
  cameraRight() {
    return new THREE.Vector3().setFromMatrixColumn(this.camera.matrixWorld, 0);
  }

  draw(p: DrawParams) {
    const cur = this.cur;
    if (!cur) return;
    const me = cur.meta.hotspots.me?.anchor;
    if (me) {
      const [x, y] = this.project(me);
      this.final.uniforms.uFocus.value.set(x / this.size.w, 1 - y / this.size.h);
    }
    if (this.prev) {
      this.renderRoom(this.prev, { ...p, hover: -1, hoverAmt: 0, open: -1, dim: 0, reveal: 1 }, this.out, false, null);
      this.renderRoom(cur, p, null, true, this.out.texture);
    } else {
      this.renderRoom(cur, p, null, true, null);
    }
  }

  private renderRoom(room: Room, p: DrawParams, target: THREE.WebGLRenderTarget | null, idPass: boolean, prev: THREE.Texture | null) {
    const r = this.renderer;
    const { scene, world, mats, meta } = room;
    r.setRenderTarget(this.main);
    r.render(scene, this.camera);
    if (idPass) {
      for (const m of mats) m.uniforms.uIdPass.value = 1;
      r.setRenderTarget(this.ids);
      r.render(scene, this.camera);
      for (const m of mats) m.uniforms.uIdPass.value = 0;
    }
    const texel = (t: THREE.WebGLRenderTarget, s = 1) => new THREE.Vector2(s / t.width, s / t.height);

    // Planar reflections: the same camera looking at the room mirrored about each glossy plane.
    // The bake culled the ceiling (never seen directly), so mirrors clear to a ceiling-like
    // radiance instead of letting the sky backdrop show through.
    const reflected = meta.planes.map((h, i) => {
      const { mirror, down: rd, up: ru } = this.refl[i];
      world.scale.y = -1;
      world.position.y = 2 * h;
      world.updateMatrixWorld(true);
      for (const m of mats) { m.uniforms.uMirror.value = 1; m.uniforms.uMirrorY.value = h; }
      if (room.backdrop) room.backdrop.visible = false;
      r.setClearColor(room.mirrorClear, 1);
      r.setRenderTarget(mirror);
      r.render(scene, this.camera);
      this.pass(this.decodeMat, rd[0], { uSrc: mirror.texture, uTexel: texel(mirror, 0.5), uK: meta.encodeK });
      for (let k = 1; k < rd.length; k++) this.pass(this.downMat, rd[k], { uSrc: rd[k - 1].texture, uTexel: texel(rd[k - 1]) });
      let src = rd[rd.length - 1];
      for (let k = rd.length - 2; k >= 0; k--) {
        this.pass(this.upMat, ru[k], { uSrc: src.texture, uAdd: rd[k].texture, uTexel: texel(src) });
        src = ru[k];
      }
      return src.texture;
    });
    r.setClearColor(0x000000, 1);
    if (room.backdrop) room.backdrop.visible = true;
    for (const m of mats) m.uniforms.uMirror.value = 0;
    world.scale.y = 1;
    world.position.y = 0;
    world.updateMatrixWorld(true);

    const { down, up } = this;
    const n = down.length;
    this.pass(this.bright, down[0], { uSrc: this.main.texture, uTexel: texel(this.main, 0.5), uK: meta.encodeK });
    for (let k = 1; k < n; k++) this.pass(this.downMat, down[k], { uSrc: down[k - 1].texture, uTexel: texel(down[k - 1]) });
    let src = down[n - 1];
    for (let k = n - 2; k >= 0; k--) {
      this.pass(this.upMat, up[k], { uSrc: src.texture, uAdd: down[k].texture, uTexel: texel(src) });
      src = up[k];
    }

    const u = this.final.uniforms;
    const g = meta.grade;
    u.uLut.value = room.lut;
    u.uLutRange.value.set(meta.lut.lo, meta.lut.hi, meta.lut.n);
    u.uK.value = meta.encodeK;
    u.uBloom.value = g.bloom;
    u.uTint.value.set(...g.tint);
    u.uGain.value.set(...g.gain);
    u.uLift.value.set(...g.lift);
    u.uMain.value = this.main.texture;
    u.uGlare.value = up[0].texture;
    u.uGlareNorm.value = 1 / n;
    u.uRefl0.value = reflected[0];
    u.uRefl1.value = reflected[1];
    u.uReflNorm.value = 1 / REFL_LEVELS;
    u.uIds.value = this.ids.texture;
    u.uView.value.set(this.size.w, this.size.h);
    u.uIdTexel.value.set(1 / this.size.w, 1 / this.size.h);
    u.uHover.value = p.hover; u.uHoverAmt.value = p.hoverAmt; u.uOpen.value = p.open; u.uDim.value = p.dim;
    u.uTime.value = p.time; u.uDust.value = p.dust; u.uReveal.value = p.reveal;
    u.uDrift.value.set(this.orbit.yaw * 0.012, -this.orbit.pitch * 0.012);
    // never sample the target being written: the outgoing pass gets an unrelated texture
    u.uPrev.value = prev ?? this.ids.texture;
    u.uFade.value = prev ? this.fade : 1;
    u.uBlocks.value = this.blocks ? 1 : 0;
    this.quad.material = this.final;
    r.setRenderTarget(target);
    r.render(this.quadScene, this.ortho);
  }

  private pass(m: THREE.RawShaderMaterial, target: THREE.WebGLRenderTarget, uniforms: Record<string, unknown>) {
    for (const [k, v] of Object.entries(uniforms)) m.uniforms[k].value = v;
    this.quad.material = m;
    this.renderer.setRenderTarget(target);
    this.renderer.render(this.quadScene, this.ortho);
  }

  private disposeChain() {
    for (const t of [...this.down, ...this.up, ...this.refl.flatMap((p) => [p.mirror, ...p.down, ...p.up])]) t.dispose();
    this.down = [];
    this.up = [];
    this.refl = [];
  }

  dispose() {
    this.disposed = true;
    for (const p of this.rooms.values()) p.then((r) => this.free(r), () => {});
    this.rooms.clear();
    this.cur = this.prev = null;
    this.main?.dispose();
    this.ids?.dispose();
    this.out?.dispose();
    this.disposeChain();
    this.renderer.dispose();
  }
}

