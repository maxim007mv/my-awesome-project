import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Bring in the same OpenAI client the bot uses
from openai import AsyncOpenAI
import aiohttp

# === Keys (reused from ai-agent.py) ===
DEEPSEEK_API_KEY = "sk-27b9a09568a04c95b84b8d44f55bab8a"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
YANDEX_GEOCODER_API_KEY = "fdc69334-3f89-4a96-b29a-499da1f7142a"

deepseek_client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    timeout=60.0,
    max_retries=3
)


log = logging.getLogger("uvicorn.error")

app = FastAPI(title="yanqwip API", version="0.1.0")

# Allow local files and localhost
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RouteRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    message: str


class Stop(BaseModel):
    name: str
    address: str
    time: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None


class FeedbackRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    subject: Optional[str] = None
    message: str


@app.get("/api/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


def detect_city(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ["spb", "питер", "санкт", "petersburg"]):
        return "Санкт-Петербург"
    if any(k in t for k in ["moscow", "москва", "msk"]):
        return "Москва"
    return "Москва"


def build_prompt(message: str, city: str) -> str:
    return (
        "Сгенерируй персональный маршрут прогулки по городу с акцентом на интересы пользователя.\n"
        f"Город: {city}.\n"
        f"Описание от пользователя: {message}\n\n"
        "Формат ответа — только валидный JSON (без комментариев, без пояснений), c ключами: \n"
        "{\n"
        "  \"city\": \"<город>\",\n"
        "  \"stops\": [\n"
        "    { \"time\": \"HH:MM – HH:MM\", \"name\": \"<название>\", \"address\": \"<адрес>\" },\n"
        "    ... (5-7 пунктов)\n"
        "  ]\n"
        "}\n\n"
        "Требования: указывай точные адреса (улица, дом, район). Делай логичную последовательность точек, близких друг к другу."
    )


async def ask_deepseek_for_route(message: str, city: str) -> Dict[str, Any]:
    prompt = build_prompt(message, city)
    # Try to request JSON. If provider doesn't support response_format, still ask in-system prompt
    try:
        resp = await deepseek_client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "Ты эксперт по городским прогулкам и маршрутам. Отвечай ТОЛЬКО валидным JSON."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=1200,
        )
        text = resp.choices[0].message.content
        data = json.loads(text)
        return data
    except Exception as e:
        # If JSON parsing fails, fallback to simple heuristic list extraction
        log.warning(f"JSON parse failed, fallback parse: {e}")
        try:
            raw = resp.choices[0].message.content  # type: ignore
        except Exception:
            raw = ""
        # naive parse: lines containing address-like commas
        lines = [ln.strip("- •\t ") for ln in raw.splitlines() if "," in ln]
        stops: List[Dict[str, str]] = []
        for ln in lines[:6]:
            m = re.match(r"(?:(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2})\s*\|\s*)?(.*?)[,\-\|]+(.*)$", ln)
            if m:
                time, name, addr = m.groups()
                stops.append({"time": (time or ""), "name": name.strip(), "address": addr.strip()})
        return {"city": city, "stops": stops}


async def geocode_address(address: str) -> Optional[Dict[str, Any]]:
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_GEOCODER_API_KEY,
        "geocode": address,
        "format": "json",
        "results": 1,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                if response.status == 200 and data.get('response', {}).get('GeoObjectCollection', {}).get('featureMember'):
                    feature = data['response']['GeoObjectCollection']['featureMember'][0]['GeoObject']
                    point = feature['Point']['pos'].split()
                    return {
                        "lat": float(point[1]),
                        "lon": float(point[0]),
                        "address": feature['metaDataProperty']['GeocoderMetaData']['text'],
                        "precision": feature['metaDataProperty']['GeocoderMetaData']['precision']
                    }
        return None
    except Exception as e:
        log.error(f"Geo error: {e}")
        return None


async def geocode_stops(city: str, stops: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for st in stops:
        addr = st.get("address")
        full = f"{city}, {addr}" if city not in addr else addr
        info = await geocode_address(full)
        if info:
            st = {**st, "lat": info["lat"], "lon": info["lon"], "address": info["address"]}
        out.append(st)
        # small polite delay to avoid rate limits
        await asyncio.sleep(0.05)
    return out


def generate_yandex_maps_url(points: List[Dict[str, Any]]) -> Optional[str]:
    if not points or len(points) < 2:
        return None
    pts = "~".join([f"{p['lat']},{p['lon']}" for p in points])
    return f"https://yandex.ru/maps/?pt={pts}&z=13&l=map"


@app.post("/api/route")
async def generate_route(req: RouteRequest) -> Dict[str, Any]:
    city = detect_city(req.message or "")
    try:
        data = await ask_deepseek_for_route(req.message, city)
        city_out = data.get("city") or city
        stops = data.get("stops") or []
        if not isinstance(stops, list) or not stops:
            raise ValueError("Модель вернула пустой список точек")
        # Geocode
        geocoded = await geocode_stops(city_out, stops)
        points = [
            {"lat": s.get("lat"), "lon": s.get("lon")}
            for s in geocoded if s.get("lat") and s.get("lon")
        ]
        map_url = generate_yandex_maps_url(points) if len(points) >= 2 else None
        return {
            "city": city_out,
            "stops": geocoded,
            "map_url": map_url,
        }
    except Exception as e:
        log.exception("Route generation failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/feedback")
async def feedback(req: FeedbackRequest) -> Dict[str, Any]:
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    try:
        rec = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "name": req.name,
            "email": req.email,
            "subject": req.subject,
            "message": req.message,
        }
        with open("feedback.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return {"status": "ok"}
    except Exception as e:
        log.exception("Feedback save failed")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
