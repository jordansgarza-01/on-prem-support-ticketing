-- Creates the app_users table that backs individual account sign-in: one row per
-- Owens & Minor e-mail address, holding a salted scrypt password hash (never the password),
-- the failed-attempt counter / lockout expiry, and a hashed single-use reset token.
--
-- HOW TO RUN (one-time, in your Supabase project — this repo has no Supabase
-- credentials and cannot run this for you):
--   1. Open https://supabase.com/dashboard -> your project -> SQL Editor.
--   2. Paste this entire file's contents and click "Run".
CREATE TABLE IF NOT EXISTS app_users (
    email text PRIMARY KEY,
    password_hash text,
    failed_attempts integer NOT NULL DEFAULT 0,
    locked_until timestamptz,
    reset_token_hash text,
    reset_token_expires timestamptz
);

-- The app connects with the service-role key (which bypasses RLS). Enabling RLS with no
-- policies makes sure the public anon key can never read password hashes.
ALTER TABLE app_users ENABLE ROW LEVEL SECURITY;

NOTIFY pgrst, 'reload schema';
