import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Pool, type PoolClient } from "pg";
import { config } from "./config.js";

const pool = config.databaseUrl
  ? new Pool({
    connectionString: config.databaseUrl,
    max: 3,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 8_000,
    query_timeout: 8_000,
    statement_timeout: 8_000,
    allowExitOnIdle: true,
  })
  : null;

// Neon may suspend or rotate connections while they are idle. Let the pool discard them safely.
pool?.on("error", (error) => console.error("Archive idle connection error", error.name));

let schemaPromise: Promise<void> | null = null;

export type ArchiveTurn = {
  conversationId: string;
  userMessageId: string;
  assistantMessageId: string;
};

export type AdminConversationFilter = {
  limit: number;
  offset: number;
  query: string;
  label: "none" | "job" | "collaboration" | "other" | "";
  potentialContact?: boolean;
};

async function ensureSchema() {
  if (!pool) throw new Error("DATABASE_URL is not configured");
  if (!schemaPromise) {
    schemaPromise = (async () => {
      const currentDir = dirname(fileURLToPath(import.meta.url));
      const sql = await readFile(resolve(currentDir, "../sql/001_archive.sql"), "utf8");
      const client = await pool.connect();
      try {
        await client.query("BEGIN");
        // Multiple API replicas can warm up simultaneously; serialize the initial DDL.
        await client.query("SELECT pg_advisory_xact_lock(738511204)");
        await client.query(sql);
        await client.query("COMMIT");
      } catch (error) {
        await client.query("ROLLBACK").catch(() => undefined);
        throw error;
      } finally {
        client.release();
      }
    })().catch((error) => {
      schemaPromise = null;
      throw error;
    });
  }
  await schemaPromise;
}

export function archiveEnabled(): boolean {
  return pool !== null;
}

export async function warmArchive(): Promise<{ ok: true; archived: boolean }> {
  if (!pool) return { ok: true, archived: false };
  await ensureSchema();
  await pool.query("SELECT 1");
  return { ok: true, archived: true };
}

async function inTransaction<T>(fn: (client: PoolClient) => Promise<T>): Promise<T> {
  if (!pool) throw new Error("DATABASE_URL is not configured");
  await ensureSchema();
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    const result = await fn(client);
    await client.query("COMMIT");
    return result;
  } catch (error) {
    await client.query("ROLLBACK").catch(() => undefined);
    throw error;
  } finally {
    client.release();
  }
}

export async function beginArchiveTurn(args: {
  conversationId: string;
  source: "im" | "homepage";
  userMessage: string;
  title: string;
  potentialContact: boolean;
}): Promise<ArchiveTurn> {
  const { conversationId, source, userMessage, title, potentialContact } = args;
  return inTransaction(async (client) => {
    const conversation = await client.query<{ id: string }>(
      `INSERT INTO conversations (id, title, source, potential_contact)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (id) DO UPDATE SET
         last_activity_at = NOW(),
         review_status = 'unreviewed',
         potential_contact = conversations.potential_contact OR EXCLUDED.potential_contact
       RETURNING id`,
      [conversationId, title.slice(0, 120) || "新的对话", source, potentialContact],
    );
    const user = await client.query<{ id: string }>(
      `INSERT INTO conversation_messages (conversation_id, role, content, status)
       VALUES ($1, 'user', $2, 'complete') RETURNING id`,
      [conversation.rows[0].id, userMessage],
    );
    const assistant = await client.query<{ id: string }>(
      `INSERT INTO conversation_messages (conversation_id, role, content, status)
       VALUES ($1, 'assistant', '', 'pending') RETURNING id`,
      [conversation.rows[0].id],
    );
    return {
      conversationId: conversation.rows[0].id,
      userMessageId: user.rows[0].id,
      assistantMessageId: assistant.rows[0].id,
    };
  });
}

export async function completeArchiveTurn(args: {
  assistantMessageId: string;
  conversationId: string;
  content: string;
  status: "complete" | "error";
  model: string;
  provider: string;
  citations: Array<{ title: string; url: string }>;
}) {
  if (!pool) return;
  await ensureSchema();
  await pool.query(
    `UPDATE conversation_messages
       SET content = $1, status = $2, model = $3, provider = $4, citations = $5::jsonb
     WHERE id = $6 AND conversation_id = $7 AND role = 'assistant'`,
    [args.content, args.status, args.model, args.provider, JSON.stringify(args.citations), args.assistantMessageId, args.conversationId],
  );
  await pool.query("UPDATE conversations SET last_activity_at = NOW() WHERE id = $1", [args.conversationId]);
}

export async function listAdminConversations(filter: AdminConversationFilter) {
  if (!pool) throw new Error("Conversation archive is disabled");
  await ensureSchema();
  const q = filter.query.trim();
  const label = filter.label;
  const potentialContact = filter.potentialContact;
  const where = `WHERE ($1 = '' OR c.title ILIKE '%' || $1 || '%' OR EXISTS (
      SELECT 1 FROM conversation_messages search_message
      WHERE search_message.conversation_id = c.id AND search_message.content ILIKE '%' || $1 || '%'
    ))
    AND ($2 = '' OR c.label = $2)
    AND ($3::boolean IS NULL OR c.potential_contact = $3)`;
  const [items, count] = await Promise.all([
    pool.query(
      `SELECT c.id, c.title, c.source, c.created_at AS "createdAt",
         c.last_activity_at AS "lastActivityAt", c.label, c.review_status AS "reviewStatus",
         c.quality, c.potential_contact AS "potentialContact",
         (SELECT COUNT(*)::int FROM conversation_messages m WHERE m.conversation_id = c.id) AS "messageCount",
         (SELECT content FROM conversation_messages m WHERE m.conversation_id = c.id AND m.role = 'user' ORDER BY m.id LIMIT 1) AS preview
       FROM conversations c ${where}
       ORDER BY c.last_activity_at DESC
       LIMIT $4 OFFSET $5`,
      [q, label, potentialContact ?? null, filter.limit, filter.offset],
    ),
    pool.query<{ total: number }>(`SELECT COUNT(*)::int AS total FROM conversations c ${where}`, [q, label, potentialContact ?? null]),
  ]);
  return { items: items.rows, total: count.rows[0]?.total ?? 0 };
}

export async function getAdminConversation(id: string) {
  if (!pool) throw new Error("Conversation archive is disabled");
  await ensureSchema();
  const conversation = await pool.query(
    `SELECT c.id, c.title, c.source, c.created_at AS "createdAt", c.last_activity_at AS "lastActivityAt",
       c.label, c.review_status AS "reviewStatus", c.quality, c.notes, c.potential_contact AS "potentialContact",
       (SELECT COUNT(*)::int FROM conversation_messages m WHERE m.conversation_id = c.id) AS "messageCount"
     FROM conversations c WHERE c.id = $1`,
    [id],
  );
  if (!conversation.rowCount) return null;
  const messages = await pool.query(
    `SELECT id::text, role, content, status, model, provider, citations, created_at AS "createdAt"
     FROM conversation_messages WHERE conversation_id = $1 ORDER BY id ASC`,
    [id],
  );
  return { conversation: conversation.rows[0], messages: messages.rows };
}

export async function updateAdminConversation(id: string, patch: {
  label?: "none" | "job" | "collaboration" | "other";
  reviewStatus?: "unreviewed" | "reviewing" | "reviewed";
  quality?: "unrated" | "good" | "needs_improvement";
  notes?: string;
}) {
  if (!pool) throw new Error("Conversation archive is disabled");
  await ensureSchema();
  const result = await pool.query(
    `UPDATE conversations SET
       label = CASE WHEN $2::boolean THEN $3 ELSE label END,
       review_status = CASE WHEN $4::boolean THEN $5 ELSE review_status END,
       notes = CASE WHEN $6::boolean THEN $7 ELSE notes END,
       quality = CASE WHEN $8::boolean THEN $9 ELSE quality END
     WHERE id = $1
     RETURNING id, title, source, created_at AS "createdAt", last_activity_at AS "lastActivityAt",
       label, review_status AS "reviewStatus", quality, notes, potential_contact AS "potentialContact"`,
    [id, patch.label !== undefined, patch.label ?? "none", patch.reviewStatus !== undefined, patch.reviewStatus ?? "unreviewed", patch.notes !== undefined, patch.notes ?? "", patch.quality !== undefined, patch.quality ?? "unrated"],
  );
  return result.rows[0] ?? null;
}
