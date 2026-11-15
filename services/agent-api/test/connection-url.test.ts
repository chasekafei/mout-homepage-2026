import assert from "node:assert/strict";
import test from "node:test";
import { normalizeDatabaseConnectionString } from "../src/connection-url.js";

test("Neon require mode is made explicit without losing pooled TLS options", () => {
  const original = "postgresql://archive:p%40ss@ep-example-pooler.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require";
  const normalized = new URL(normalizeDatabaseConnectionString(original));

  assert.equal(normalized.searchParams.get("sslmode"), "verify-full");
  assert.equal(normalized.searchParams.get("channel_binding"), "require");
  assert.equal(normalized.username, "archive");
  assert.equal(normalized.password, "p%40ss");
  assert.match(normalized.hostname, /-pooler\./);
});

test("explicit certificate verification and malformed values are preserved", () => {
  const alreadyVerified = "postgres://archive:secret@db.example/neondb?sslmode=verify-full";
  const malformed = "not a postgres URL";
  assert.equal(normalizeDatabaseConnectionString(alreadyVerified), alreadyVerified);
  assert.equal(normalizeDatabaseConnectionString(malformed), malformed);
});
