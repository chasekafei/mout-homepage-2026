ALTER TABLE conversation_messages
  ADD COLUMN IF NOT EXISTS fact_sources JSONB NOT NULL DEFAULT '[]'::jsonb;
