CREATE TABLE IF NOT EXISTS conversations (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL DEFAULT '新的对话',
  source TEXT NOT NULL DEFAULT 'im' CHECK (source IN ('im', 'homepage')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_activity_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  label TEXT NOT NULL DEFAULT 'none' CHECK (label IN ('none', 'job', 'collaboration', 'other')),
  review_status TEXT NOT NULL DEFAULT 'unreviewed' CHECK (review_status IN ('unreviewed', 'reviewing', 'reviewed')),
  quality TEXT NOT NULL DEFAULT 'unrated' CHECK (quality IN ('unrated', 'good', 'needs_improvement')),
  notes TEXT NOT NULL DEFAULT '',
  potential_contact BOOLEAN NOT NULL DEFAULT FALSE
);

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS quality TEXT NOT NULL DEFAULT 'unrated';

CREATE TABLE IF NOT EXISTS conversation_messages (
  id BIGSERIAL PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'complete' CHECK (status IN ('pending', 'complete', 'error')),
  model TEXT,
  provider TEXT,
  citations JSONB NOT NULL DEFAULT '[]'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS conversations_activity_idx ON conversations (last_activity_at DESC);
CREATE INDEX IF NOT EXISTS conversations_review_idx ON conversations (review_status, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS conversations_potential_contact_idx ON conversations (potential_contact, last_activity_at DESC);
CREATE INDEX IF NOT EXISTS conversation_messages_conversation_idx ON conversation_messages (conversation_id, id);
