# TennisGo — сайт школы тенниса и Telegram‑шлюз

Этот репозиторий содержит статический сайт (лендинг и страницы услуг) и простой бэкенд‑шлюз на FastAPI для отправки заявок из форм в Telegram.

— Для быстрого деплоя фронтенда используется vps (папка `scr`).
— Для безопасной отправки заявок в Telegram используется Python‑API (`server.py`) с CORS и простой заголовочной авторизацией.


## Что сделано

- Многостраничный адаптивный сайт: `index.html`, `groups.html`, `adults.html`, `about.html`, `contacts.html`.
- Единый скрипт отправки форм в Telegram: `scr/js/telegram.js`.
  - Поддерживаются 2 режима:
    1) Через собственный шлюз (рекомендовано, безопаснее): POST на `/tg/send` вашего бэкенда.
    2) Напрямую в Bot API (для отладки; для продакшена не использовать, т.к. токен окажется во фронтенде).
- Бэкенд‑шлюз на FastAPI: `server.py` с эндпоинтами `/health` и `/tg/send`.
- Dockerfile для продакшен‑запуска API.
- DEPLOY.md с подробным сценарием развёртывания (VPS/Docker, прокси с HTTPS, Netlify).


## Технологии

- Frontend: HTML, Tailwind CSS (CDN), Google Fonts, Vanilla JS.
- Backend: Python 3.11, FastAPI, Uvicorn, Pydantic, Requests.
- Хостинг: vps THE HOST (фронтенд), любой VPS/PAAS + Docker (бэкенд).


## Структура проекта

- `scr/` — статический сайт (страницы, стили, изображения),
  - `scr/js/telegram.js` — отправка форм в Telegram.
- `server.py` — FastAPI‑шлюз (принимает JSON, отправляет сообщение в Telegram).
- `requirements.txt` — зависимости Python.
- `Dockerfile` — образ для продакшен‑запуска API.
- `netlify.toml` — конфигурация публикации фронтенда.
- `DEPLOY.md` — пошаговый гид по деплою.


## Быстрый старт (локально)

1) Бэкенд (рекомендуется для разработки и продакшена)
- Требуется Python 3.11+.
- Установите зависимости и запустите сервер:
  - Windows PowerShell: `py -m venv .venv && .venv\Scripts\Activate.ps1 && pip install -r requirements.txt && uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
  - Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && uvicorn server:app --host 0.0.0.0 --port 8000 --reload`
- Настройте переменные окружения (см. раздел ниже или файл `.env.example`).

2) Фронтенд
- Откройте `scr/index.html` в браузере (или запустите любой статический сервер).
- Убедитесь, что на странице задан адрес шлюза: мета‑тег `<meta name="tg-gateway" content="https://api.example.com/tg/send">` или установите `window.TG_GATEWAY` до подключения `telegram.js`.


## Переменные окружения (бэкенд)

Создайте файл `.env` рядом с `server.py` (см. пример `.env.example`) и задайте:

- `TG_BOT_TOKEN` — токен бота (получить у @BotFather).
- `TG_CHAT_ID` — ID чата/канала для приёма заявок (см. FAQ в `DEPLOY.md`).
- `TG_INBOUND_SECRET` — длинный случайный секрет для заголовка `X-Auth` (опционально, но рекомендуется).
- `ALLOW_ORIGINS` — список доменов, которым разрешены запросы CORS (через запятую): например, `https://<ваш‑сайт>.netlify.app,https://example.ru`.
- `PORT` — порт сервера (по умолчанию 8000).


## API

- `GET /health` — проверка доступности: возвращает `{ "ok": true }`.
- `POST /tg/send` — принимает JSON и отправляет сообщение в Telegram.
  - Тело запроса: свободная схема, типовые поля: `name`, `phone`, `email`, `level`, `topic`, `message`, `location`, `page`, `form_id`.
  - Заголовок авторизации (если включён): `X-Auth: <TG_INBOUND_SECRET>`.
  - Ответ: `{ "ok": true, "telegram": {...} }` при успехе.

Пример тела запроса:
`{"name":"Иван","phone":"+7 900 000 00 00","page":"/","message":"Хочу на пробное"}`


## Отправка форм из фронтенда

Скрипт `scr/js/telegram.js`:

- Режим 1 (рекомендуется): отправка через шлюз. Установите `<meta name="tg-gateway" content="https://api.example.com/tg/send">` или `window.TG_GATEWAY = '...'`. При наличии `window.TG_INBOUND_SECRET` он будет добавлен в заголовок `X-Auth`.
- Режим 2 (для отладки): отправка напрямую в Bot API. Для продакшена не используйте — токен окажется публичным.

Важно: в `telegram.js` есть значения по умолчанию для `TOKEN` и `CHAT_ID` — замените/удалите их перед публикацией и переключитесь на режим через шлюз.


## Деплой

- Подробная инструкция: см. `DEPLOY.md` (Docker, reverse‑proxy с HTTPS, Netlify).
- Быстрые команды Docker (пример):
  - `docker build -t tennisgo-api .`
  - `docker run -d --name tennisgo-api --restart unless-stopped --env-file .env -p 8000:8000 tennisgo-api`


## Безопасность и рекомендации

- Никогда не храните токен бота во фронтенде. Используйте бэкенд‑шлюз и секрет `X-Auth`.
- Ограничьте CORS доменами вашего сайта через `ALLOW_ORIGINS`.
- Не коммитьте `.env` и любые ключи/токены.


## Лицензия (кратко)

Материалы предоставляются для личного и учебного некоммерческого использования при обязательном упоминании первоисточника (ссылка на этот репозиторий/автора). Коммерческое использование запрещено без отдельного письменного разрешения. Идеи и подходы (структура, архитектура, приёмы) можно использовать свободно. Полный текст — в файле `LICENSE`.


## Контакты

- Вопросы и идеи: создайте Issue в репозитории или напишите автору в Telegram: `@ILYIDLI` (замените на актуальный контакт).

