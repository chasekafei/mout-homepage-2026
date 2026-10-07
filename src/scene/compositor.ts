const VERT = `#version 300 es
in vec2 aPos;
out vec2 vScreen;
void main() {
  vScreen = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5);
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const FRAG = `#version 300 es
precision highp float;
in vec2 vScreen;
out vec4 outColor;

uniform sampler2D uBeauty;
uniform sampler2D uMask;
uniform sampler2D uDepth;
uniform vec2 uScale;
uniform vec2 uOffset;
uniform vec2 uViewPx;
uniform vec2 uParallax;
uniform float uHover;
uniform float uHoverAmt;
uniform float uOpen;
uniform float uDim;
uniform float uTime;
uniform float uDust;
uniform float uReveal;

float maskId(vec2 uv) {
  float r = texture(uMask, uv).r * 255.0;
  return floor(r / 16.0 + 0.5) - 1.0;
}

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

vec2 parallax(vec2 uv) {
  float d = texture(uDepth, uv).r;
  return uv + uParallax * (1.0 - smoothstep(0.0, 0.85, d)) * 0.9;
}

float motes(vec2 uv, float aspect) {
  float acc = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float cells = 26.0 + fi * 22.0;
    vec2 p = uv * vec2(aspect, 1.0) * cells;
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

void main() {
  vec2 uv0 = uOffset + vScreen * uScale;
  vec2 uv = parallax(uv0);
  vec3 col = texture(uBeauty, uv).rgb;
  float id = maskId(uv);

  float lum = dot(col, vec3(0.299, 0.587, 0.114));

  if (uHover >= 0.0 && uHoverAmt > 0.001) {
    vec2 px = 1.0 / uViewPx * uScale;
    float inside = id == uHover ? 1.0 : 0.0;
    float hits = 0.0;
    for (int k = 0; k < 12; k++) {
      float a = float(k) * 0.5236;
      vec2 o = vec2(cos(a), sin(a)) * px * 3.0;
      hits += maskId(uv + o) == uHover ? 1.0 : 0.0;
    }
    float frac = hits / 12.0;
    float rim = (1.0 - inside) * smoothstep(0.0, 0.5, frac);
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
    float aspect = uViewPx.x / uViewPx.y;
    col += motes(uv0, aspect) * beam * vec3(1.0, 0.93, 0.8) * 0.32 * uDust;
  }

  col += (hash(vScreen * uViewPx + fract(uTime)) - 0.5) / 255.0;
  outColor = vec4(col * uReveal, 1.0);
}`;

export type Fit = { scale: [number, number]; offset: [number, number]; imgW: number; imgH: number; offX: number; offY: number };

/** Cover-fit an image into the viewport while keeping `focus` (image uv) as central as possible. */
export function coverFit(vw: number, vh: number, iw: number, ih: number, focus: [number, number], overscan = 1.03): Fit {
  const s = Math.max(vw / iw, vh / ih) * overscan;
  const imgW = iw * s;
  const imgH = ih * s;
  const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
  const offX = clamp(focus[0] * imgW - vw / 2, 0, imgW - vw);
  const offY = clamp(focus[1] * imgH - vh / 2, 0, imgH - vh);
  return { scale: [vw / imgW, vh / imgH], offset: [offX / imgW, offY / imgH], imgW, imgH, offX, offY };
}

type Uniforms = Record<string, WebGLUniformLocation | null>;

export class Compositor {
  readonly gl: WebGL2RenderingContext;
  private prog: WebGLProgram;
  private u: Uniforms = {};
  private tex: Record<"beauty" | "mask" | "depth", WebGLTexture | null> = { beauty: null, mask: null, depth: null };

  constructor(readonly canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl2", { antialias: false, alpha: false, premultipliedAlpha: false, powerPreference: "high-performance" });
    if (!gl) throw new Error("webgl2 unavailable");
    this.gl = gl;
    this.prog = this.link(VERT, FRAG);
    gl.useProgram(this.prog);
    for (const n of ["uBeauty", "uMask", "uDepth", "uScale", "uOffset", "uViewPx", "uParallax", "uHover", "uHoverAmt", "uOpen", "uDim", "uTime", "uDust", "uReveal"]) {
      this.u[n] = gl.getUniformLocation(this.prog, n);
    }
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(this.prog, "aPos");
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
    gl.uniform1i(this.u.uBeauty, 0);
    gl.uniform1i(this.u.uMask, 1);
    gl.uniform1i(this.u.uDepth, 2);
  }

  private link(vs: string, fs: string) {
    const gl = this.gl;
    const compile = (type: number, src: string) => {
      const s = gl.createShader(type)!;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s) ?? "shader");
      return s;
    };
    const p = gl.createProgram()!;
    gl.attachShader(p, compile(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, compile(gl.FRAGMENT_SHADER, fs));
    gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p) ?? "link");
    return p;
  }

  setTexture(slot: "beauty" | "mask" | "depth", img: TexImageSource) {
    const gl = this.gl;
    const unit = { beauty: 0, mask: 1, depth: 2 }[slot];
    if (this.tex[slot]) gl.deleteTexture(this.tex[slot]);
    const t = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0 + unit);
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, img);
    const nearest = slot === "mask";
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, nearest ? gl.NEAREST : gl.LINEAR);
    if (slot === "beauty") {
      gl.generateMipmap(gl.TEXTURE_2D);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
    } else {
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, nearest ? gl.NEAREST : gl.LINEAR);
    }
    this.tex[slot] = t;
  }

  get ready() { return !!(this.tex.beauty && this.tex.mask && this.tex.depth); }

  draw(p: {
    fit: Fit; viewPx: [number, number]; parallax: [number, number];
    hover: number; hoverAmt: number; open: number; dim: number; time: number; dust: number; reveal: number;
  }) {
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.useProgram(this.prog);
    (["beauty", "mask", "depth"] as const).forEach((k, i) => { gl.activeTexture(gl.TEXTURE0 + i); gl.bindTexture(gl.TEXTURE_2D, this.tex[k]); });
    gl.uniform2f(this.u.uScale, p.fit.scale[0], p.fit.scale[1]);
    gl.uniform2f(this.u.uOffset, p.fit.offset[0], p.fit.offset[1]);
    gl.uniform2f(this.u.uViewPx, p.viewPx[0], p.viewPx[1]);
    gl.uniform2f(this.u.uParallax, p.parallax[0], p.parallax[1]);
    gl.uniform1f(this.u.uHover, p.hover);
    gl.uniform1f(this.u.uHoverAmt, p.hoverAmt);
    gl.uniform1f(this.u.uOpen, p.open);
    gl.uniform1f(this.u.uDim, p.dim);
    gl.uniform1f(this.u.uTime, p.time);
    gl.uniform1f(this.u.uDust, p.dust);
    gl.uniform1f(this.u.uReveal, p.reveal);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }

  dispose() {
    const gl = this.gl;
    Object.values(this.tex).forEach((t) => t && gl.deleteTexture(t));
    gl.deleteProgram(this.prog);
  }
}
