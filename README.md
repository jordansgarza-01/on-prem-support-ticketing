# 🎫 Support tickets template

A simple Streamlit app showing an internal tool that lets you create, manage, and visualize support tickets. 

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://on-prem-support-ticketing.streamlit.app/)

### How to run it on your own machine

1. Install the requirements

   ```
   $ pip install -r requirements.txt
   ```

2. Run the app

   ```
   $ streamlit run streamlit_app.py
   ```

### Accounts, password reset and e-mail notifications

People sign in with their own Owens & Minor e-mail (`firstname.lastname@owens-minor.com`) and password.
First-time users (and anyone who forgot their password) use **First time or forgot password?** on the
login screen to get a single-use link that expires in 60 minutes. Three wrong passwords lock the account
for 15 minutes and e-mail a reset link. Passwords need 10+ characters with an uppercase letter, a lowercase
letter, a number and a symbol, and no character may be used twice. Only George Dixon, Deno Erickson and
Jordan Garza see **Service Overview** and **Performance Management**.

One-time setup:

1. Run `migrations/0003_add_app_users_table.sql` in the Supabase SQL editor (stores password hashes only).
2. Add these to the Streamlit secrets (alongside `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`):

   ```toml
   SMTP_HOST = "smtp.example.com"
   SMTP_PORT = 587              # 465 uses implicit TLS
   SMTP_USERNAME = "..."
   SMTP_PASSWORD = "..."
   SMTP_FROM = "support@owens-minor.com"
   APP_BASE_URL = "https://on-prem-support-ticketing.streamlit.app"
   ```

Until e-mail is configured (or to help someone directly), an administrator with the Supabase service key can
manage accounts from a terminal, with no e-mail needed:

```
$ python manage_accounts.py set-password jordan.garza@owens-minor.com   # prompts for the password
$ python manage_accounts.py reset-link   jordan.garza@owens-minor.com   # one-time link to hand over
$ python manage_accounts.py unlock       jordan.garza@owens-minor.com
$ python manage_accounts.py status       jordan.garza@owens-minor.com
```
