Backend (Telegram API) on your server, frontend on Netlify. Follow these steps.

1) Prepare the backend (server)
- Choose hosting: VPS (Ubuntu) or any PaaS.
- Install dependencies:
  - System: `sudo apt update && sudo apt install -y docker.io docker-compose-plugin` (or use Python directly).
  - Domain + HTTPS: point `api.your-domain` DNS to the server; later use Nginx/Caddy for TLS.

Option A — with Docker (recommended)
- Put `.env` next to `Dockerfile` (copy from `.env.example` and fill values):
  - `TG_BOT_TOKEN=...`
  - `TG_CHAT_ID=...`
  - `TG_INBOUND_SECRET=long-random-secret`
  - `ALLOW_ORIGINS=https://<your-netlify-app>.netlify.app`
- Build and run:
  - `docker build -t tennisgo-api .`
  - `docker run -d --name tennisgo-api --restart unless-stopped --env-file .env -p 8000:8000 tennisgo-api`
- (Optional) Put a reverse proxy with HTTPS in front (example Nginx below).

Option B — without Docker (system Python)
- `python -m venv .venv && source .venv/bin/activate`
- `pip install -r requirements.txt`
- Export env vars (or use a `.env` loader in your process manager):
  - `export TG_BOT_TOKEN=...`
  - `export TG_CHAT_ID=...`
  - `export TG_INBOUND_SECRET=...`
  - `export ALLOW_ORIGINS=https://<your-netlify-app>.netlify.app`
- Run: `uvicorn server:app --host 0.0.0.0 --port 8000`
- Use `systemd` or `pm2` to keep it alive in production.

Health check
- `curl http://localhost:8000/health` -> `{"ok": true}`

2) Configure reverse proxy (HTTPS)
Example Nginx (replace domain):

```
server {
    listen 80;
    server_name api.tennisgo.ru;
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then issue a certificate (e.g., `certbot --nginx -d api.tennisgo.ru`).

3) Deploy the frontend to Netlify
- Repo contains static site in `scr/`.
- Netlify settings:
  - New site from Git (or drop folder).
  - Build command: empty (static).
  - Publish directory: `scr` (already in `netlify.toml`).
- Take the Netlify URL (e.g., `https://tennisgo.netlify.app`).

4) Wire frontend to backend
- In your frontend JS (`scr/js/telegram.js`) set the API URL to your domain:
  - `const API_URL = 'https://api.tennisgo.ru/tg/send';`
- Include auth header if you set `TG_INBOUND_SECRET`:
  - `headers: { 'Content-Type': 'application/json', 'X-Auth': '<your-secret>' }`

5) Configure CORS on backend
- Set `ALLOW_ORIGINS=https://tennisgo.netlify.app` (and any additional domains separated by commas).

6) Test end-to-end
- From your laptop:
  - `curl -X POST https://api.tennisgo.ru/tg/send \`
    `-H "Content-Type: application/json" -H "X-Auth: <your-secret>" \`
    `-d '{"name":"Test","phone":"+7 900 000 00 00","page":"/","message":"hello"}'`
- You should receive a message in your Telegram chat/channel.

7) Production tips
- Do NOT commit secrets. Use `.env` on the server or managed secrets.
- Keep `TG_INBOUND_SECRET` long and random to prevent spam.
- Monitor logs: `docker logs -f tennisgo-api` or your process manager.
- Backup your `.env` and Nginx config.

FAQ
- Where to get `TG_CHAT_ID`? Send a message to your bot, then use a helper like @userinfobot or log `resp.json()` once to see `chat.id`. For channels, add the bot as admin and use the channel ID (often negative, like `-100...`).
- Webhooks needed? Not for this gateway; it only sends messages to Telegram.

