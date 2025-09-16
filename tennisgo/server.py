import os
import requests
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


# Telegram credentials (must be provided via env vars)
TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.getenv("TG_CHAT_ID", "")

# Optional simple auth for incoming requests (set TG_INBOUND_SECRET env if needed)
TG_INBOUND_SECRET = os.getenv("TG_INBOUND_SECRET", "")


app = FastAPI(title="TennisGo Telegram Gateway", version="1.0.0")

# CORS (set ALLOW_ORIGINS env as comma-separated list or leave * for dev)
allow_origins = os.getenv("ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in allow_origins if o.strip()],
    allow_credentials=False,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


class LeadPayload(BaseModel):
    # Common fields from forms
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    topic: str | None = None
    message: str | None = None
    # Extra/optional
    level: str | None = None
    location: str | None = None
    loc: str | None = None
    page: str | None = None
    form_id: str | None = None


def build_message(p: LeadPayload) -> str:
    rows: list[str] = ["<b>📝 Новая заявка с сайта</b>"]
    if p.page:
        rows.append(f"Страница: {p.page}")
    if p.form_id:
        rows.append(f"Форма: #{p.form_id}")

    def add(label: str, value: str | None):
        if value:
            rows.append(f"<b>{label}:</b> {value}")

    add("Имя", p.name)
    add("Телефон", p.phone)
    add("E‑mail", p.email)
    add("Уровень", p.level)
    add("Тема", p.topic)
    add("Локация", p.location or p.loc)
    add("Сообщение", p.message)

    return "\n".join(rows)


def tg_send_message(text: str) -> dict:
    if not TG_BOT_TOKEN:
        raise RuntimeError("TG_BOT_TOKEN is not configured")
    if not TG_CHAT_ID:
        raise RuntimeError("TG_CHAT_ID is not configured")
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": TG_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
    }, timeout=10)
    if not resp.ok:
        raise RuntimeError(f"Telegram error {resp.status_code}: {resp.text}")
    return resp.json()


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/tg/send")
def tg_send(payload: LeadPayload, x_auth: str | None = Header(default=None, alias="X-Auth")):
    # Optional simple auth
    if TG_INBOUND_SECRET and x_auth != TG_INBOUND_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

    text = build_message(payload)
    data = tg_send_message(text)
    return {"ok": True, "telegram": data}


# For local debug: `python server.py`
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)
