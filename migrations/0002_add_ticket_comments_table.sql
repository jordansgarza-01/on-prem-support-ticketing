-- Creates the ticket_comments table so posted comments/replies (and likes) persist
-- across sessions instead of only living in Streamlit's in-memory session state.
-- Run this in the Supabase SQL editor (or via `supabase db execute`) against the
-- project referenced by SUPABASE_URL before using the app's Comments feature.
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
