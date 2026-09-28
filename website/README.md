# Website Deployment

The web dashboard is a React/Vite single-page app served by Flask. It shares the bot's `.env` and `data/storage.db`; run the bot and website from the repository root so both processes resolve the same data directory.

## Discord OAuth

1. Set `WEBSITE_BASE_URL` to the full site origin, for example `http://127.0.0.1:9090` locally or `https://dashboard.example.com` for public hosting. The app derives the callback as `{WEBSITE_BASE_URL}/auth/discord/callback`.
2. In the Discord Developer Portal, register that exact derived callback URL as an OAuth2 redirect URI.
3. Set `DISCORD_OAUTH_CLIENT_ID`, `DISCORD_OAUTH_CLIENT_SECRET`, and a stable `WEBSITE_SECRET_KEY` in `.env`. The OAuth client ID can fall back to `DISCORD_CLIENT_ID`.
4. Generate the website key with `py -c "import secrets; print(secrets.token_urlsafe(48))"` on Windows or `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'` on Linux/macOS; do not rotate it without forcing active users to sign in again.
5. For public hosting, set `WEBSITE_BASE_URL` to the public HTTPS origin and terminate TLS at a reverse proxy. Keep the Flask/Waitress listener behind that proxy.

The website uses Discord OAuth `identify` and `guilds` scopes. OAuth access and refresh credentials are encrypted with `WEBSITE_SECRET_KEY` before being stored in SQLite. Sessions use an HttpOnly, SameSite=Lax cookie containing only a random server-side session identifier and expire after 90 days of inactivity. Refresh tokens renew the login and refresh the membership/permission snapshot.

## Build and Run

```powershell
py -m pip install -r requirements.txt
website\scripts\build-frontend.bat
website\scripts\run-website.bat
```

The regular run scripts use Flask's development server for local use. For production, install `requirements.txt` and run `website\scripts\run-website-prod.bat` (Waitress); put it behind a TLS reverse proxy. On Linux/macOS, run `sh website/scripts/build-frontend.sh` then `sh website/scripts/run-website.sh` for local development. For Linux/macOS production, use `sh website/scripts/run-website-prod.sh` behind a TLS reverse proxy. The shell scripts prefer `python3`, fall back to `python`, and honor `PYTHON` when explicitly set.

The logged-out page contains no server counts, individual statistics, update text, or guild names. After login, users see only servers they own/administer or configured teams they captain. The total tracked-user count is restricted to the `OWNER_ID` account.

## Website Actions

Team creation, owner settings changes, team preferences, schedule sends, activities, and team deletion are written to `website_actions` in `data/storage.db`. The bot's `WebsiteQueueCog` processes one request at a time and checks live Discord membership and permissions immediately before acting. The website displays the status and result for actions submitted by the signed-in user. Pending requests remain queued while the bot is offline.

Changing Vite source requires rebuilding the frontend. The built files are under `website/static/dist/` and are generated output.