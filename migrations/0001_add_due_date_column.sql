-- Adds the Due Date column used for SLA metrics (Overdue Tasks, On-Time Close %).
-- Run this in the Supabase SQL editor (or via `supabase db execute`) against the
-- project referenced by SUPABASE_URL before using the app's Due Date feature.
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS due_date text DEFAULT '';
