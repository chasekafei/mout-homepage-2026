import { createHmac, createHash, timingSafeEqual, randomBytes } from "node:crypto";
import type { IncomingMessage, ServerResponse } from "node:http";
import { config } from "./config.js";

const COOKIE = "mout_admin";
const SESSION_MS = 7 * 24 * 60 * 60 * 1_000;
const attempts = new Map<string, { count: number; resetAt: number }>();

export function adminConfigured(): boolean {
  return config.adminPassword.length > 0 && config.adminSessionSecret.length >= 32;
}

export function allowAdminLogin(key: string): boolean {
  const now = Date.now();
  const current = attempts.get(key);
  if (!current || current.resetAt <= now) {
    attempts.set(key, { count: 1, resetAt: now + 15 * 60 * 1_000 });
    return true;
  }
  current.count += 1;
  return current.count <= 8;
}

function digest(value: string): Buffer {
  return createHash("sha256").update(value).digest();
}

export function verifyAdminPassword(value: unknown): boolean {
  if (!adminConfigured() || typeof value !== "string") return false;
  return timingSafeEqual(digest(value), digest(config.adminPassword));
}

function sign(payload: string): string {
  return createHmac("sha256", config.adminSessionSecret).update(payload).digest("base64url");
}

function cookieValue(req: IncomingMessage): string | undefined {
  const cookie = req.headers.cookie;
  if (!cookie) return undefined;
  for (const item of cookie.split(";")) {
    const [name, ...rest] = item.trim().split("=");
    if (name === COOKIE) return rest.join("=");
  }
  return undefined;
}

export function isAdminRequest(req: IncomingMessage): boolean {
  if (!adminConfigured()) return false;
  const value = cookieValue(req);
  if (!value) return false;
  const [expiresAt, nonce, signature] = value.split(".");
  if (!expiresAt || !nonce || !signature || !/^\d+$/.test(expiresAt) || Number(expiresAt) <= Date.now()) return false;
  const expected = Buffer.from(sign(`${expiresAt}.${nonce}`));
  const actual = Buffer.from(signature);
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}

export function setAdminCookie(req: IncomingMessage, res: ServerResponse): void {
  const expiresAt = String(Date.now() + SESSION_MS);
  const nonce = randomBytes(18).toString("base64url");
  const value = `${expiresAt}.${nonce}.${sign(`${expiresAt}.${nonce}`)}`;
  const forwardedProto = req.headers["x-forwarded-proto"];
  const secure = process.env.NODE_ENV === "production" || forwardedProto === "https" ? "; Secure" : "";
  res.setHeader("Set-Cookie", `${COOKIE}=${value}; HttpOnly; SameSite=Strict; Path=/v1/admin; Max-Age=${Math.floor(SESSION_MS / 1_000)}${secure}`);
}

export function clearAdminCookie(req: IncomingMessage, res: ServerResponse): void {
  const forwardedProto = req.headers["x-forwarded-proto"];
  const secure = process.env.NODE_ENV === "production" || forwardedProto === "https" ? "; Secure" : "";
  res.setHeader("Set-Cookie", `${COOKIE}=; HttpOnly; SameSite=Strict; Path=/v1/admin; Max-Age=0${secure}`);
}
