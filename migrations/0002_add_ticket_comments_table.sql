-- Creates the ticket_comments table so posted comments/replies (and likes) persist
-- across sessions instead of only living in Streamlit's in-memory session state.
--
-- HOW TO RUN (one-time, in your Supabase project — this repo has no Supabase
-- credentials and cannot run this for you):
--   1. Open https://supabase.com/dashboard -> your project -> SQL Editor.
--   2. Paste this entire file's contents and click "Run".
--   3. If the app still reports "Could not find the table 'public.ticket_comments'"
--      afterward, PostgREST's schema cache didn't pick up the change yet — go to
--      Project Settings -> API and click "Reload schema", or just re-run this file
--      (its NOTIFY line at the bottom forces the same reload).
CREATE TABLE IF NOT EXISTS ticket_comments (
    id text PRIMARY KEY,
    parent_id text REFERENCES ticket_comments (id) ON DELETE CASCADE,
    ticket_id text NOT NULL,
    username text NOT NULL DEFAULT '',
    comment text NOT NULL DEFAULT '',
    timestamp text NOT NULL DEFAULT '',
    likes text[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS ticket_comments_ticket_id_idx ON ticket_comments (ticket_id);
CREATE INDEX IF NOT EXISTS ticket_comments_parent_id_idx ON ticket_comments (parent_id);

-- PostgREST (Supabase's API layer) caches the schema and won't see the new table
-- until it reloads — this normally happens automatically, but force it immediately
-- so the app doesn't need to wait for the next auto-reload.
NOTIFY pgrst, 'reload schema';
