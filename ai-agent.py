import asyncio
import aiohttp
import re
from datetime import datetime
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters, ConversationHandler
import logging
import json
from typing import Dict, List
import uuid

# ==========================================
# Настройка логирования
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

# ==========================================
# Конфигурация API
# ==========================================
DEEPSEEK_API_KEY = "sk-27b9a09568a04c95b84b8d44f55bab8a"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
YANDEX_GEOCODER_API_KEY = "fdc69334-3f89-4a96-b29a-499da1f7142a"
YANDEX_STATIC_MAPS_API_KEY = "1d34fe00-70f9-4f28-bba4-ff9ae1f1e969"

deepseek_client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    timeout=60.0,
    max_retries=3
)

# ==========================================
# Этапы диалога Telegram-бота
# ==========================================
(ASK_TIME, ASK_DURATION, ASK_TYPE, ASK_START_POINT, ASK_BUDGET,
 ASK_PREFERENCES, ASK_ACTIVITIES, ASK_FOOD, ASK_TRANSPORT, ASK_LIMITS) = range(10)

# Используем словарь для хранения данных пользователей
user_data_store = {}


# ==========================================
# Функции для работы с Яндекс API
# ==========================================
async def geocode_address(address: str) -> Dict:
    """Геокодирование адреса с помощью Яндекс API"""
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_GEOCODER_API_KEY,
        "geocode": address,
        "format": "json",
        "results": 1
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()

                if response.status == 200 and data.get('response', {}).get('GeoObjectCollection', {}).get(
                        'featureMember'):
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
        logging.error(f"Ошибка геокодирования: {e}")
        return None


async def generate_map_image(points: List[Dict]) -> str:
    """Генерация изображения карты с маршрутом"""
    if not points or len(points) < 2:
        return None

    # Формируем параметры для запроса к Static API
    points_str = "~".join([f"{point['lon']},{point['lat']},pm2rdl{i + 1}" for i, point in enumerate(points)])

    url = "https://static-maps.yandex.ru/v1"
    params = {
        "apikey": YANDEX_STATIC_MAPS_API_KEY,
        "size": "650,450",
        "z": "13",
        "l": "map",
        "pt": points_str,
        "pl": f"c:8822DDC0,w:5,{','.join([f'{point['lon']},{point['lat']}' for point in points])}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    filename = f"map_{uuid.uuid4().hex}.png"
                    with open(filename, "wb") as f:
                        f.write(await response.read())
                    return filename
        return None
    except Exception as e:
        logging.error(f"Ошибка генерации карты: {e}")
        return None


def generate_yandex_maps_url(points: List[Dict]) -> str:
    """Генерирует URL для открытия маршрута в Яндекс.Картах"""
    if not points or len(points) < 2:
        return None

    # Формируем параметры для URL
    points_str = "~".join([f"{point['lat']},{point['lon']}" for point in points])

    url = f"https://yandex.ru/maps/?pt={points_str}&z=13&l=map"
    return url


# ==========================================
# Улучшенные функции диалога с поддержкой многопользовательности
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    user_data_store[user_id] = {
        "user_name": update.message.from_user.first_name,
        "created_at": datetime.now().isoformat(),
        "conversation_lock": asyncio.Lock()
    }

    await update.message.reply_text(
        f"Привет, {update.message.from_user.first_name}! 👋\n"
        "Я твой персональный гид по Москве! 🏛️\n\n"
        "Давай вместе создадим идеальный маршрут, который точно подойдет именно тебе!\n\n"
        "Для начала расскажи, во сколько ты планируешь начать прогулку?\n"
        "⏰ (например: 10:00, после обеда, вечером)"
    )
    return ASK_TIME


async def ask_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['time'] = update.message.text

    await update.message.reply_text(
        "Отлично! ⏳\n"
        "Сколько времени ты хочешь посвятить прогулке?\n\n"
        "🕒 Например:\n"
        "• 2-3 часа для короткой прогулки\n"
        "• 4-5 часов для полноценной экскурсии\n"
        "• Целый день для максимального погружения"
    )
    return ASK_DURATION


async def ask_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['duration'] = update.message.text

    await update.message.reply_text(
        "Какой тип прогулки тебе ближе? 🎯\n\n"
        "1. 🎨 Культурная (музеи, галереи, выставки)\n"
        "2. 🏛️ Историческая (Кремль, Красная площадь, старинные усадьбы)\n"
        "3. 🎪 Развлекательная (парки, аттракционы, шоу)\n"
        "4. 💖 Романтическая (уютные уголки, красивые виды)\n"
        "5. 👨‍👩‍👧‍👦 Семейная (интересно и детям, и взрослым)\n"
        "6. 🏃‍♂️ Спортивная/активная (велопрогулки, пробежки)\n"
        "7. 🍽️ Гастрономическая (рестораны, кафе, фуд-корты)\n"
        "8. 🛍️ Шопинг (торговые центры, бутики, рынки)\n"
        "9. 🎭 Другое (опиши своими словами)"
    )
    return ASK_TYPE


async def ask_start_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['type'] = update.message.text

    await update.message.reply_text(
        "Откуда тебе удобно начать маршрут? 🗺️\n\n"
        "Укажи конкретное место:\n"
        "• Метро (например: Китай-город, Охотный ряд)\n"
        "• Улица и дом (например: ул. Арбат, 45)\n"
        "• Достопримечательность (например: Красная площадь)\n"
        "• Район (например: от Замоскворечья)"
    )
    return ASK_START_POINT


async def ask_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['start_point'] = update.message.text

    await update.message.reply_text(
        "Какой бюджет ты планируешь на прогулку? 💰\n\n"
        "1. 🎗️ Эконом (бесплатные мероприятия, пикник)\n"
        "2. 💵 Средний (недорогие музеи, кафе, общественный транспорт)\n"
        "3. 💎 Премиум (рестораны, такси, VIP-экскурсии)\n"
        "4. 🚀 Не ограничен (лучшие места города)"
    )
    return ASK_BUDGET


async def ask_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['budget'] = update.message.text

    await update.message.reply_text(
        "Есть ли конкретные места, которые ты хотел бы посетить? 📍\n\n"
        "Можешь перечислить:\n"
        "• Достопримечательности (Кремль, ВДНХ, Останкинская башня)\n"
        "• Районы (Арбат, Замоскворечье, Хамовники)\n"
        "• Парки (Парк Горького, Сокольники, Коломенское)\n"
        "• Музеи (Третьяковка, Пушкинский, Исторический)\n\n"
        "Или просто напиши 'нет', если у тебя нет предпочтений"
    )
    return ASK_PREFERENCES


async def ask_activities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['preferences'] = update.message.text

    await update.message.reply_text(
        "Какие активности тебе интересны? 🎭\n\n"
        "Выбери несколько вариантов:\n"
        "• 🖼️ Посещение музеев и выставок\n"
        "• 🏛️ Осмотр архитектуры и памятников\n"
        "• 🌳 Прогулки по паркам и набережным\n"
        "• 🛍️ Шопинг в торговых центрах\n"
        "• 📸 Фотосессии в красивых местах\n"
        "• 🍽️ Посещение кафе и ресторанов\n"
        "• 🎡 Развлечения и аттракционы\n"
        "• 🎭 Театры и концерты\n"
        "• 🚶‍♂️ Просто прогуляться без цели"
    )
    return ASK_ACTIVITIES


async def ask_food(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['activities'] = update.message.text

    await update.message.reply_text(
        "Как насчет питания во время прогулки? 🍽️\n\n"
        "1. 🍔 Бюджетные варианты (столовые, фудкорты)\n"
        "2. 🍕 Средний уровень (кафе, бистро)\n"
        "3. 🍷 Премиум-заведения (рестораны, бары)\n"
        "4. 🚫 Не нужно, поем дома\n"
        "5. 🥗 Особые предпочтения (вегетарианское, безглютеновое и т.д.)"
    )
    return ASK_FOOD


async def ask_transport(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['food'] = update.message.text

    await update.message.reply_text(
        "Как ты планируешь перемещаться по городу? 🚗\n\n"
        "1. 🚶‍♂️ Пешком (для небольших расстояний)\n"
        "2. 🚇 На общественном транспорте (метро, автобусы)\n"
        "3. 🚕 На такси/каршеринге (максимум комфорта)\n"
        "4. 🚲 На велосипеде/самокате (активный вариант)\n"
        "5. 🔀 Смешанный вариант (что-то пешком, что-то на транспорте)"
    )
    return ASK_TRANSPORT


async def ask_limits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['transport'] = update.message.text

    await update.message.reply_text(
        "Последний вопрос! Есть ли особые пожелания или ограничения? 🚧\n\n"
        "Например:\n"
        "• ♿ Доступная среда (для людей с ограниченной подвижностью)\n"
        "👶 С детьми (укажи возраст)\n"
        "• 🚷 Избегать толп/очередей\n"
        "• 🏛️ Предпочтение крытым/уличным мероприятиям\n"
        "• 🐕 С домашними животными\n"
        "• 🚭 Некурящие зоны\n"
        "• 🚫 Никаких ограничений"
    )
    return ASK_LIMITS


async def finalize(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id

    # Проверяем, есть ли данные пользователя
    if user_id not in user_data_store:
        await update.message.reply_text("⚠️ Сессия устарела. Пожалуйста, начните заново с /start")
        return ConversationHandler.END

    async with user_data_store[user_id]["conversation_lock"]:
        user_data_store[user_id]['limits'] = update.message.text

    # Показываем анимацию процесса
    progress_message = await update.message.reply_text("🔄 Начинаю генерацию маршрута... 0%")

    # Обновляем прогресс
    for percent in range(10, 101, 10):
        try:
            await context.bot.edit_message_text(
                chat_id=update.message.chat_id,
                message_id=progress_message.message_id,
                text=f"🔄 Генерирую ваш персональный маршрут... {percent}%"
            )
            await asyncio.sleep(0.3)
        except:
            pass

    # Получаем координаты начальной точки
    start_point = user_data_store[user_id].get('start_point', '')
    start_coords = await geocode_address(f"Москва, {start_point}") if start_point else None

    # Формируем детальный промпт с учетом всех данных
    prompt = f"""
Создай подробный персонализированный маршрут прогулки по Москве для пользователя {user_data_store[user_id].get('user_name', '')}.

УЧТИ СЛЕДУЮЩИЕ ПРЕДПОЧТЕНИЯ:
1. Время начала: {user_data_store[user_id].get('time', 'не указано')}
2. Продолжительность: {user_data_store[user_id].get('duration', 'не указана')}
3. Тип прогулки: {user_data_store[user_id].get('type', 'не указан')}
4. Начальная точка: {user_data_store[user_id].get('start_point', 'не указана')} {f'(координаты: {start_coords['lat']}, {start_coords['lon']})' if start_coords else ''}
5. Бюджет: {user_data_store[user_id].get('budget', 'не указан')}
6. Предпочтения по местам: {user_data_store[user_id].get('preferences', 'не указаны')}
7. Активности: {user_data_store[user_id].get('activities', 'не указаны')}
8. Питание: {user_data_store[user_id].get('food', 'не указано')}
9. Транспорт: {user_data_store[user_id].get('transport', 'не указан')}
10. Ограничения: {user_data_store[user_id].get('limits', 'не указаны')}

ВАЖНЫЕ ТРЕБОВАНИЯ:
1. Используй актуальную информацию на 2024 год (цены, режим работы, доступность мест)
2. Создай логически связанный маршрут, где точки находятся близко друг к другу
3. Не используй звездочки (*) для форматирования
4. Используй формат: 🕔 16:30 – 17:30 | Прогулка по парку «Тропарёво»
5. Указывай точные адреса для каждого места
6. Рассчитай время с учетом перемещения между точками
7. Учитывай выбранный тип транспорта
8. Предложи альтернативные варианты на случай непогоды или других обстоятельств
9. Укажи примерные цены на входные билеты и питание

СОЗДАЙ СТРУКТУРИРОВАННЫЙ МАРШРУТ С:
- Точными адресами и координатами всех рекомендуемых мест
- Временными интервалами для каждого этапа
- Способами перемещения между точками
- Примерной стоимостью (где применимо)
- Персональными рекомендациями, основанными на предпочтениях
- Интересными фактами о местах
- Учетом ограничений и особых пожеланий

ПРЕДСТАВЬ ОТВЕТ В ВИДЕ:
1. Название маршрута и общее описание
2. Детальный пошаговый план с временем и адресами
3. Примерный бюджет на день
4. Рекомендации по транспорту
5. Варианты питания по маршруту
6. Советы и лайфхаки для лучшего опыта

ИСПОЛЬЗУЙ ТОЛЬКО РЕАЛЬНЫЕ СУЩЕСТВУЮЩИЕ МЕСТА С АДРЕСАМИ В МОСКВЕ.
"""

    try:
        # Генерируем маршрут через DeepSeek API
        route_description = await generate_route_with_retry(prompt)

        # Извлекаем адреса из описания маршрута для построения карты
        addresses = extract_addresses(route_description)
        points = []

        # Добавляем начальную точку
        if start_coords:
            points.append(start_coords)

        # Геокодируем извлеченные адреса
        for address in addresses[:7]:  # Ограничиваем количество точек на карте
            if address != start_point:  # Не добавляем начальную точку повторно
                coords = await geocode_address(f"Москва, {address}")
                if coords:
                    points.append(coords)

        # Генерируем карту
        map_filename = await generate_map_image(points) if len(points) > 1 else None

        # Создаем ссылку на Яндекс.Карты с маршрутом
        yandex_maps_url = generate_yandex_maps_url(points) if len(points) > 1 else None

    except Exception as e:
        route_description = f"⚠️ Произошла ошибка при генерации маршрута: {str(e)}"
        map_filename = None
        yandex_maps_url = None

    # Завершаем анимацию прогресса
    try:
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=progress_message.message_id,
            text="✅ Персональный маршрут успешно создан!"
        )
    except:
        pass

    # Отправляем карту, если она сгенерирована
    if map_filename:
        try:
            with open(map_filename, 'rb') as map_file:
                await update.message.reply_photo(
                    photo=map_file,
                    caption="🗺️ Вот карта вашего маршрута с отмеченными точками"
                )
        except Exception as e:
            logging.error(f"Ошибка отправки карты: {e}")

    # Отправляем ссылку на Яндекс.Карты
    if yandex_maps_url:
        await update.message.reply_text(
            f"📍 Открыть маршрут в Яндекс.Картах:\n{yandex_maps_url}"
        )

    # Отправляем текстовый маршрут
    if len(route_description) > 4000:
        parts = [route_description[i:i + 4000] for i in range(0, len(route_description), 4000)]
        for i, part in enumerate(parts):
            await update.message.reply_text(f"📝 Часть {i + 1}/{len(parts)}:\n\n{part}")
            await asyncio.sleep(1)
    else:
        await update.message.reply_text(route_description)

    # Добавляем заключительное сообщение
    await update.message.reply_text(
        "✨ Ваш персональный маршрут готов! ✨\n\n"
        "Если хочешь создать новый маршрут, просто введи /start\n\n"
        "Приятной прогулки по Москве! 🏛️"
    )

    # Очищаем данные пользователя
    if user_id in user_data_store:
        del user_data_store[user_id]

    return ConversationHandler.END


def extract_addresses(text: str) -> list:
    """Извлекает адреса из текста маршрута"""
    # Ищем упоминания адресов (улицы, проспекты, площади и т.д.)
    address_patterns = [
        r'(ул\.|улица|проспект|пр\.|переулок|пер\.|площадь|пл\.|набережная|наб\.|бульвар|б-р|метро|м\.)\s+[А-Яа-яёЁ\-\s]+[,\s]\s*д?\.?\s*\d+',
        r'м\.\s*[А-Яа-яёЁ\s]+',
        r'[А-Яа-яёЁ\s]+,\s*[А-Яа-яёЁ\s]*\d+',
        r'[А-Яа-яёЁ]+\s+[А-Яа-яёЁ]+\s*,\s*[дД]\.\s*\d+',
    ]

    addresses = []
    for pattern in address_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        addresses.extend(matches)

    return list(set(addresses))  # Удаляем дубликаты


async def generate_route_with_retry(prompt, retries=5):
    for attempt in range(retries):
        try:
            response = await deepseek_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": """Ты эксперт по планированию персонализированных маршрутов по Москве. 
                    Составляй подробные, практичные и интересные маршруты с точными адресами и координатами. 
                    Используй актуальную информацию на 2024 год. 
                    Форматируй время в виде: 🕔 16:30 – 17:30 | Прогулка по парку «Тропарёво»
                    Не используй звездочки (*) для форматирования.
                    Убедись, что точки маршрута логически связаны и находятся близко друг к другу.
                    Учитывай время на перемещение между точками.
                    Предоставляй точные адреса для каждого места.
                    Указывай примерные цены на входные билеты и питание.
                    """},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000,
                timeout=60.0
            )

            # Убираем звездочки из текста
            result = response.choices[0].message.content
            result = result.replace("**", "").replace("*", "•")

            return result

        except asyncio.TimeoutError:
            if attempt == retries - 1:
                raise Exception("Таймаут при подключении к API. Попробуйте позже.")
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            if attempt == retries - 1:
                if "401" in str(e):
                    raise Exception("Ошибка аутентификации. Проверьте API-ключ DeepSeek.")
                elif "429" in str(e):
                    raise Exception("Превышен лимит запросов. Попробуйте позже.")
                elif "500" in str(e) or "502" in str(e) or "503" in str(e):
                    raise Exception("Временные проблемы с сервером DeepSeek. Попробуйте позже.")
                else:
                    raise e
            await asyncio.sleep(2 ** attempt)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.from_user.id
    if user_id in user_data_store:
        del user_data_store[user_id]

    await update.message.reply_text(
        "Прогулка отменена. Если передумаешь, просто введи /start 🎯\n"
        "Жду тебя для новых приключений по Москве! 🏛️"
    )
    return ConversationHandler.END


# ==========================================
# Основная функция
# ==========================================
def main():
    TELEGRAM_TOKEN = "7977871622:AAGgXPGY4JN68E_wzKMu18n4Jkw7G-9ljoM"

    # Создаем application с увеличенными таймаутами
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # Добавляем обработчик ошибок
    app.add_error_handler(error_handler)

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            ASK_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_duration)],
            ASK_DURATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_type)],
            ASK_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_start_point)],
            ASK_START_POINT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_budget)],
            ASK_BUDGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_preferences)],
            ASK_PREFERENCES: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_activities)],
            ASK_ACTIVITIES: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_food)],
            ASK_FOOD: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_transport)],
            ASK_TRANSPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_limits)],
            ASK_LIMITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
    print("Бот запущен...")
    app.run_polling()


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик ошибок для телеграм бота"""
    logging.error("Exception while handling an update:", exc_info=context.error)

    if update and update.message:
        try:
            await update.message.reply_text(
                "⚠️ Произошла непредвиденная ошибка. Пожалуйста, попробуйте еще раз позже.\n"
                "Если проблема повторяется, введи /start для начала заново."
            )
        except:
            pass


if __name__ == '__main__':
    main()