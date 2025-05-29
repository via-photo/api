
import logging
import openai
from openai import AsyncOpenAI
from aiogram import Bot, Dispatcher, types
from aiogram.types import ContentType, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils import executor
from aiogram.dispatcher.filters import BoundFilter
from aiogram.dispatcher.filters import Command
from PIL import Image
import io
import os
from dotenv import load_dotenv
import base64
import random
import re
from unicodedata import normalize as uni_normalize
from datetime import datetime, timedelta, date, timezone
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean, Text, select, delete
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from collections import OrderedDict
from sqlalchemy import delete
from aiogram.dispatcher.filters import BoundFilter
from aiogram import types
# 🔧 Глобальный кэш: название продукта -> нутриенты на 100 г
from collections import OrderedDict
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

persistent_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton("🍽️ Добавить блюдо"), KeyboardButton("🍎 Итоги за день")],
        [KeyboardButton("⚙️ Профиль")]
    ],
    resize_keyboard=True,
    is_persistent=True
)

class LimitedCache(OrderedDict):
    def __init__(self, limit=2000):
        super().__init__()
        self.limit = limit

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        if len(self) > self.limit:
            self.popitem(last=False)

product_cache = LimitedCache(limit=2000)

# 📅 Отслеживание даты последнего фото от пользователя: user_id -> date
last_photo_date: dict[int, date] = {}



product_logger = logging.getLogger("product_logger")
product_logger.setLevel(logging.INFO)
if not product_logger.hasHandlers():
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    product_logger.addHandler(handler)









async def calculate_summary_text(user_id: str, date_str: str) -> str:
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        async with async_session() as session:
            result = await session.execute(
                select(History).where(
                    History.user_id == user_id,
                    History.date == target_date
                )
            )
            entries = result.scalars().all()

        if not entries:
            return "📭 В этот день не было добавлено ни одного блюда."

        total_kcal = total_prot = total_fat = total_carb = total_fiber = 0.0

        for entry in entries:
            match = re.search(r"(\d+(?:[.,]\d+)?) ккал, Белки: (\d+(?:[.,]\d+)?) г, Жиры: (\d+(?:[.,]\d+)?) г, Углеводы: (\d+(?:[.,]\d+)?) г, Клетчатка: (\d+(?:[.,]\d+)?) г", entry.response)
            if match:
                kcal, prot, fat, carb, fiber = map(lambda x: float(x.replace(",", ".")), match.groups())
                total_kcal += kcal
                total_prot += prot
                total_fat += fat
                total_carb += carb
                total_fiber += fiber

        total_kcal = round(total_kcal)
        total_prot = round(total_prot)
        total_fat = round(total_fat)
        total_carb = round(total_carb)
        total_fiber = round(total_fiber)

        return (
            f"📊 Итого: {total_kcal} ккал\n"
            f"Белки: {total_prot} г\n"
            f"Жиры: {total_fat} г\n"
            f"Углеводы: {total_carb} г\n"
            f"Клетчатка: {total_fiber} г"
        )
    except Exception as e:
        return f"❌ Ошибка при расчёте: {str(e)}"









def round_totals_to_int(text):
    def replacer(match):
        try:
            kcal, prot, fat, carb, fiber = [s.replace('~', '').replace('≈', '').strip() for s in match.groups()]
            return (
                f"📊 Итого: {round(float(kcal))} ккал, "
                f"Белки: {round(float(prot))} г, "
                f"Жиры: {round(float(fat))} г, "
                f"Углеводы: {round(float(carb))} г, "
                f"Клетчатка: {round(float(fiber), 1)} г"
            )
        except Exception as e:
            logging.error(f"Ошибка округления БЖУ: {e}")
            return match.group(0)

    return re.sub(
        r"📊 Итого:\s*([~≈]?\s*\d+\.?\d*)\s*ккал.*?"
        r"Белки[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г.*?"
        r"Жиры[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г.*?"
        r"Углеводы[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г.*?"
        r"Клетчатка[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г",
        lambda m: replacer(m),
        text,
        flags=re.IGNORECASE | re.DOTALL
    )

class FixModeFilter(BoundFilter):
    key = 'fix_mode'

    def __init__(self, fix_mode):
        self.fix_mode = fix_mode

    async def check(self, message: types.Message):
        user_id = str(message.from_user.id)
        data = await get_user_data(user_id)
        return bool(data.get("fix_mode")) == self.fix_mode

load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_KEYS = os.getenv("OPENAI_KEYS").split(",")
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

dp.filters_factory.bind(FixModeFilter)

# PostgreSQL setup
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class UserData(Base):
    __tablename__ = "user_data"
    user_id = Column(String, primary_key=True)
    data = Column(JSON)

class UserHistory(Base):
    __tablename__ = "user_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    prompt = Column(Text)
    response = Column(Text)
    timestamp = Column(DateTime)
    type = Column(String)
    data = Column(JSON)



class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    kcal = Column(Float)
    protein = Column(Float)
    fat = Column(Float)
    carb = Column(Float)
    fiber = Column(Float)

async def search_product_by_name(name: str) -> dict:
    async with async_session() as session:
        result = await session.execute(
            select(Product).where(Product.name.ilike(f"%{name}%")).limit(1)
        )
        product = result.scalar()
        if product:
            return {
                "name": product.name,
                "kcal": product.kcal,
                "protein": product.protein,
                "fat": product.fat,
                "carb": product.carb,
                "fiber": product.fiber,
            }
        return {}

function_definitions = [
    {
        "name": "search_product_by_name",
        "description": "Находит БЖУ по названию продукта из базы данных.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Название продукта (например: гречка варёная, курица жареная и т.п.)"
                }
            },
            "required": ["name"]
        }
    }
]

import unicodedata

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower()).replace("ё", "е")
    return "".join([c for c in text if not unicodedata.combining(c)]).strip()

async def get_batch_kbzu(names: list[str]) -> dict:
    results = []

    for name in names:
        product_data = await match_product_name_to_db(name)

        if product_data:
            logging.warning(f"[MATCHED ✅] '{name}' => '{product_data['matched_name']}' из базы")
            results.append({
                "matched_name": product_data["matched_name"],
                "source": "db",
                "kcal": product_data["kcal"],
                "protein": product_data["protein"],
                "fat": product_data["fat"],
                "carb": product_data["carb"],
                "fiber": product_data["fiber"]
            })
        else:
            logging.warning(f"[NOT FOUND ❌] '{name}' не найдено в базе — GPT должен придумать")
            results.append({
                "matched_name": name,
                "source": "gpt",
                "kcal": None,
                "protein": None,
                "fat": None,
                "carb": None,
                "fiber": None
            })

    all_from_db = all(r["source"] == "db" for r in results)

    if all_from_db:
        text_lines = ["🍽️ На фото:"]
        total_kcal = total_prot = total_fat = total_carb = total_fiber = 0

        for r in results:
            grams = 100
            kcal = round(r["kcal"] * grams / 100)
            prot = r["protein"] * grams / 100
            fat = r["fat"] * grams / 100
            carb = r["carb"] * grams / 100
            fiber = r["fiber"] * grams / 100

            total_kcal += kcal
            total_prot += prot
            total_fat += fat
            total_carb += carb
            total_fiber += fiber

            text_lines.append(f"• {r['matched_name']} – {grams} г (~{kcal} ккал)")

        text_lines.append(
            f"📊 Итого: {round(total_kcal)} ккал, Белки: {round(total_prot)} г, Жиры: {round(total_fat)} г, "
            f"Углеводы: {round(total_carb)} г, Клетчатка: {round(total_fiber, 1)} г"
        )

        return {
            "results": results,
            "prebuilt_text": "\n".join(text_lines)
        }

    return {
        "results": results,
        "prebuilt_text": None
    }

async def match_product_names_to_db(names: list[str]) -> list[str]:
    results = []
    for name in names:
        matched = await match_product_name_to_db(name)
        results.append(matched["matched_name"] if matched else name)
    return results


# Helper to convert datetime in user data to ISO string for JSON storage
def _convert_user_data(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _convert_user_data(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_user_data(v) for v in obj]
    return obj

async def get_user_data(user_id: str) -> dict:
    async with async_session() as session:
        result = await session.get(UserData, user_id)
        return result.data if result else {}

async def update_user_data(user_id: str, data: dict):
    # Convert datetime objects to ISO strings for JSON
    safe_data = _convert_user_data(data)
    async with async_session() as session:
        async with session.begin():
            obj = await session.get(UserData, user_id)
            if obj:
                obj.data = safe_data
            else:
                session.add(UserData(user_id=user_id, data=safe_data))

async def add_history_entry(user_id: str, entry: dict):
    async with async_session() as session:
        async with session.begin():
            session.add(UserHistory(user_id=user_id, **entry))

async def get_history(user_id: str) -> list:
    async with async_session() as session:
        result = await session.execute(select(UserHistory).where(UserHistory.user_id == user_id).order_by(UserHistory.timestamp))
        entries = result.scalars().all()
        history_list = []
        for e in entries:
            history_list.append({
                "prompt": e.prompt,
                "response": e.response,
                "timestamp": e.timestamp,
                "type": e.type
            })
        return history_list

# Custom filter for profile stage
class ProfileStageFilter(BoundFilter):
    key = 'profile_stage'
    def __init__(self, profile_stage):
        self.profile_stage = profile_stage
    async def check(self, message: types.Message):
        data = await get_user_data(str(message.from_user.id))
        return data.get("profile_stage") == self.profile_stage

dp.filters_factory.bind(ProfileStageFilter)

# In-memory storage for recent photos (for clarifications, not persisted)
recent_photos: dict = {}  # {user_id: {"image_bytes": ..., "time": datetime}}

async def send_morning_reminders():
    reminder_messages = [
        "Доброе утро!\nБережно пинаю: завтрак в голове — не считается 😄\nСкидывай, я всё посчитаю.",
        "Доброе утро!\nЗавтрак уже был? Кидай. Чем раньше внесёшь — тем меньше шансов сорваться на обед 😅",
        "Привет, с утречком!\nПросто напоминаю: если уже поела — скидывай, запишу и посчитаю)",
        "Доброе утро 💛\nЯ знаю, ты занята. Но 10 секунд — и завтрак не забудется.\nПиши. Я посчитаю",
        "☕ Доброе утро!\nСчитай это нежным пинком: не забудь про завтрак 😄",
        "📊 Доброе утро!\nФиксируем завтрак и спокойно идём покорять день.",
        "✨ Доброе утро, красотка!\nЕсли поела — закинь в бот. Я всё посчитаю, как всегда.",
        "🌞 Утро доброе, а завтрак где?\nБез меня калории не считаются :)",
        "С добрым утром!\nКаждый внесённый завтрак — минус одна «ой, я забыла» вечером 😉",
        "Это знак.\nЗнак добавить завтрак 😌\nДоброе утро!"
    ]

    while True:
        now_utc = datetime.utcnow()
        async with async_session() as session:
            result = await session.execute(select(UserData))
            users = result.scalars().all()

            for user in users:
                data = user.data
                offset = data.get("utc_offset", 0)
                local_time = now_utc + timedelta(hours=offset)

                if local_time.hour == 9 and 30 <= local_time.minute < 34 and not data.get("morning_reminded", False):
                    user_id = user.user_id

                    # Проверим, есть ли записи за сегодня
                    result = await session.execute(
                        select(UserHistory).where(
                            UserHistory.user_id == user_id,
                            UserHistory.timestamp >= datetime.combine(local_time.date(), datetime.min.time())
                        )
                    )
                    entries = result.scalars().all()

                    try:
                        reminder_index = data.get("morning_index", 0)
                        message = reminder_messages[reminder_index % len(reminder_messages)]

                        if not entries:
                            await bot.send_message(user_id, message)
                            data["morning_reminded"] = True

                        data["morning_index"] = reminder_index + 1
                        user.data = data
                        await session.commit()
                    except Exception as e:
                        logging.warning(f"Не удалось отправить утреннее сообщение {user_id}: {e}")

                elif local_time.hour >= 10:
                    # Сброс флага на следующий день
                    if data.get("morning_reminded"):
                        data["morning_reminded"] = False
                        user.data = data
                        await session.commit()

        await asyncio.sleep(300)  # каждые 5 минут


async def clean_old_photos():
    while True:
        await asyncio.sleep(3600)  # run every hour
        cutoff = datetime.now() - timedelta(hours=12)
        to_delete = [uid for uid, data in recent_photos.items() if data["time"] < cutoff]
        for uid in to_delete:
            del recent_photos[uid]






import json

async def get_kbzu_from_db(food_name: str):
    async with async_session() as session:
        result = await session.execute(select(Product.name))
        all_names = [row[0] for row in result.all()]

    match, score, _ = process.extractOne(food_name, all_names, scorer=fuzz.token_sort_ratio)

    if score > 90:
        async with async_session() as session:
            result = await session.execute(select(Product).where(Product.name == match))
            product = result.scalar()
            if product:
                return {
                    "matched_name": match,
                    "source": "db",
                    "kcal": product.kcal,
                    "protein": product.protein,
                    "fat": product.fat,
                    "carb": product.carb,
                    "fiber": product.fiber
                }

    # Продукт не найден → вернём заготовку и скажем GPT, что нужно додумать
    return {
        "matched_name": food_name,
        "source": "gpt",
        "kcal": None,
        "protein": None,
        "fat": None,
        "carb": None,
        "fiber": None
    }


from rapidfuzz import process, fuzz

COOKED_KEYWORDS = ["отвар", "варен", "варён", "жарен", "запеч", "гриль", "тушен"]
RAW_KEYWORDS = ["сырой", "сырое", "сырая", "сырые", "сухой", "сухая", "сухие", "неприготов"]

# Эти переменные нужно инициализировать один раз при старте
product_list = []
product_map = {}

async def load_products_from_db():
    global product_list, product_map
    async with async_session() as session:
        result = await session.execute(select(Product))
        products = result.scalars().all()

        product_list = []
        product_map = {}

        for p in products:
            norm_name = normalize(p.name)
            replaced_name = replace_similar_words(norm_name)

            product_list.append(replaced_name)
            product_map[replaced_name] = {
                "matched_name": p.name,
                "source": "db",
                "kcal": p.kcal,
                "protein": p.protein,
                "fat": p.fat,
                "carb": p.carb,
                "fiber": p.fiber
            }

SIMILAR_WORDS = {
    "вареные": "отварные",
    "варёные": "отварные",
    "отварные": "отварные",
    "жареные": "жаренные",
    "обжаренный": "жареный",
    "обжаренная": "жареная",
    "тушёные": "тушеные",
    "тушенные": "тушеные",
    "запечённые": "запеченные",
    "запеченые": "запеченные",
    "печеные": "запеченные",
    "вареная": "отварная",
    "варёная": "отварная",
    "отварная": "отварная",
    "жареная": "жаренная",
    "жарёная": "жаренная",
    "тушёная": "тушеная",
    "тушеная": "тушеная",
    "запечённая": "запеченная",
    "запеченая": "запеченная",
    "печеная": "запеченная",
    # и так далее — можно расширять при необходимости
}

def replace_similar_words(text: str) -> str:
    words = text.split()
    replaced = [SIMILAR_WORDS.get(word.lower(), word.lower()) for word in words]
    return " ".join(replaced)



openai_index = 0  # глобальный счётчик
def get_openai_client():
    global openai_index
    key = OPENAI_KEYS[openai_index % len(OPENAI_KEYS)]
    openai_index += 1
    return AsyncOpenAI(api_key=key)

functions = [
    {
        "name": "get_kbzu_from_db",
        "description": "Получает КБЖУ из базы продуктов по названию",
        "parameters": {
            "type": "object",
            "properties": {
                "food_name": {
                    "type": "string",
                    "description": "Название продукта (например, 'куриная грудка жареная')"
                }
            },
            "required": ["food_name"]
        }
    },
    {
        "name": "get_batch_kbzu",
        "description": "Возвращает КБЖУ по списку продуктов",
        "parameters": {
            "type": "object",
            "properties": {
                "names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Список названий продуктов (например: ['куриная грудка', 'гречка', 'брокколи'])"
                }
            },
            "required": ["names"]
        }
    }
]





@dp.message_handler(Command("webapp"))
async def send_webapp_button(message: types.Message):
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton(
            text="Открыть профиль",
            web_app=WebAppInfo(url="https://reliable-toffee-e14334.netlify.app/")
        )
    )
    await message.answer("Нажми кнопку, чтобы открыть профиль 👇", reply_markup=keyboard)



@dp.message_handler(content_types=[ContentType.VIDEO, ContentType.DOCUMENT, ContentType.STICKER])
async def handle_unsupported_content(message: types.Message):
    await message.reply(
        "❗️Я могу распознать только *фото еды*.\n\n"
        "Если хочешь — просто пришли фотографию своей тарелки. "
        "А если удобнее — можешь описать блюдо текстом ✍️ или голосом 🎤",
        parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data == "show_today_summary")
async def show_today_summary_callback(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    chat_id = callback_query.message.chat.id
    data = await get_user_data(user_id)
    user_offset = data.get("utc_offset", 0)
    target_date = datetime.utcnow().astimezone(timezone(timedelta(hours=user_offset))).date()
    history_list = await get_history(user_id)
    if not history_list or all(e["timestamp"].date() != target_date for e in history_list):
        # If no history at all or none for today
        if not history_list:
            await bot.send_message(chat_id, "Ты ещё не присылала фото еды 🍽️")
        else:
            await bot.send_message(chat_id, f"Нет данных на {target_date.strftime('%Y-%m-%d')} 📅")
        await callback_query.answer()
        return
    entries_today = [e for e in history_list if e["timestamp"].date() == target_date]
    # Calculate totals and send each entry summary with delete button
    total_kcal = total_prot = total_fat = total_carb = total_fiber = 0
    for i, entry in enumerate(entries_today, start=1):
        kcal = prot = fat = carb = fiber = 0


        match = re.search(
            r'Итого:\s*[~≈]?\s*(\d+\.?\d*)\s*ккал.*?'
            r'Белки[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
            r'Жиры[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
            r'Углеводы[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
            r'Клетчатка[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г',
            entry['response'], flags=re.IGNORECASE | re.DOTALL
        )

        if match:
            kcal, prot, fat, carb = map(lambda x: round(float(x)), match.groups()[:4])
            fiber = round(float(match.groups()[4]), 1)
            total_fiber += fiber
        total_kcal += kcal
        total_prot += prot
        total_fat += fat
        total_carb += carb
        lines = entry['response'].splitlines()
        food_lines = [line for line in lines if line.strip().startswith(("•", "-"))]
        short_desc = ", ".join([re.sub(r'^[•\-]\s*', '', line).split("–")[0].strip() for line in food_lines]) or "Без описания"
        text = f"{i}. {short_desc} – {kcal} ккал"
        kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton(f"❌ Удалить блюдо", callback_data=f"del_id:{entry['timestamp'].isoformat()}")
        )
        await bot.send_message(chat_id, text, reply_markup=kb)
    # Compute remaining macros against targets
    data = await get_user_data(user_id)
    target_kcal = int(data.get("target_kcal", 0))
    target_protein = int(data.get("target_protein", 0))
    target_fat = int(data.get("target_fat", 0))
    target_carb = int(data.get("target_carb", 0))
    target_fiber = int(data.get("target_fiber", 20))
    remaining_kcal = target_kcal - total_kcal
    remaining_prot = target_protein - total_prot
    remaining_fat = target_fat - total_fat
    remaining_carb = target_carb - total_carb
    fiber_message = (
        f"Клетчатка: осталось {round(target_fiber - total_fiber, 1)} г"
        if total_fiber < target_fiber else
        f"Клетчатка: добрана 👍"
    )
    warning_lines = []
    if remaining_kcal < 0:
        maintenance_kcal = int(target_kcal / 0.83) if target_kcal else 0
        if total_kcal <= maintenance_kcal and data.get("goal", 0) < data.get("weight", 0):
            warning_lines.append(
                f"⚖️ По калориям уже перебор для похудения, но ты всё ещё в рамках нормы для поддержания веса — до неё ещё {maintenance_kcal - total_kcal} ккал. Вес не прибавится, не переживай 😊"
            )
        else:
            warning_lines.append("🍩 Калорий вышло чуть больше нормы — не страшно, но завтра можно чуть аккуратнее 😉")
    if remaining_prot < 0:
        warning_lines.append("🥩 Белка получилось больше, чем нужно — это не страшно.")
    if remaining_fat < 0:
        warning_lines.append("🧈 Жиров вышло многовато — обрати внимание, может где-то масло лишнее.")
    if remaining_carb < 0:
        warning_lines.append("🍞 Углеводов перебор — может, сегодня было много сладкого?")
    warnings_text = "\n".join(warning_lines)
    fiber_line = f"Клетчатка: {total_fiber:.1f} г"

    remaining_fiber = target_fiber - total_fiber
    remaining_fiber_line = (
        f"Клетчатка: нужно добрать {round(remaining_fiber, 1)} г"
        if remaining_fiber > 0 else
        "Клетчатка: добрана 👍"
    )

    summary_text = (
        f"📊 Сумма за день:\n"
        f"Калории: {total_kcal} ккал\n"
        f"Белки: {total_prot} г\n"
        f"Жиры: {total_fat} г\n"
        f"Углеводы: {total_carb} г\n"
        f"{fiber_line}\n\n"
        f"🧮 Осталось на сегодня:\n"
        f"Калорий: {remaining_kcal if remaining_kcal > 0 else 0} ккал\n"
        f"Белков: {remaining_prot if remaining_prot > 0 else 0} г\n"
        f"Жиров: {remaining_fat if remaining_fat > 0 else 0} г\n"
        f"Углеводов: {remaining_carb if remaining_carb > 0 else 0} г\n"
        f"{remaining_fiber_line}\n\n"
        f"{warnings_text}"
    )
    sent_msg = await bot.send_message(chat_id, summary_text)
    # Store summary message ID for updates on deletion
    data["summary_message_id"] = sent_msg.message_id
    await update_user_data(user_id, data)
    await callback_query.answer()

@dp.message_handler(lambda message: message.text == "🍎 Итоги за день")
async def summary_button_handler(message: types.Message):
    # Фейковый callback_query для вызова уже существующей функции
    class FakeCallbackQuery:
        def __init__(self, message):
            self.from_user = message.from_user
            self.message = message
        async def answer(self):
            pass

    fake_cb = FakeCallbackQuery(message)
    await show_today_summary_callback(fake_cb)

@dp.callback_query_handler(lambda c: c.data.startswith("del_id:"))
async def delete_entry(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    entry_id = callback_query.data.split(":", 1)[1]
    history_list = await get_history(user_id)
    if not history_list or len(history_list) == 0:
        await callback_query.answer("История пуста.")
        return
    entry_to_remove = None
    for entry in history_list:
        if entry["timestamp"].isoformat() == entry_id:
            entry_to_remove = entry
            break
    if entry_to_remove:
        # Remove from database
        try:
            dt = entry_to_remove["timestamp"]
            async with async_session() as session:
                async with session.begin():
                    await session.execute(delete(UserHistory).where(UserHistory.user_id == user_id, UserHistory.timestamp == dt))
        except Exception as e:
            logging.error(f"Failed to delete entry: {e}")
        # Edit the message with the removed entry
        await callback_query.message.edit_text("❌ Блюдо удалено.")
        # Update summary message if exists
        data = await get_user_data(user_id)
        summary_message_id = data.get("summary_message_id")
        if summary_message_id:
            user_offset = data.get("utc_offset", 0)
            today = datetime.utcnow().astimezone(timezone(timedelta(hours=user_offset))).date()
            # Recompute todaаy's totals without the removed entry
            entries_today = [e for e in history_list if e["timestamp"].date() == today and e["timestamp"] != entry_to_remove["timestamp"]]
            total_kcal = total_prot = total_fat = total_carb = total_fiber = 0
            for e in entries_today:
                kcal = prot = fat = carb = fiber = 0

                match = re.search(
                    r'Итого:\s*[~≈]?\s*(\d+\.?\d*)\s*ккал.*?'
                    r'Белки[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
                    r'Жиры[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
                    r'Углеводы[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
                    r'Клетчатка[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г',
                    entry['response'], flags=re.IGNORECASE | re.DOTALL
                )

                if match:
                    kcal, prot, fat, carb = map(lambda x: round(float(x)), match.groups()[:4])
                    fiber = round(float(match.groups()[4]), 1)
                    total_fiber += fiber
                total_kcal += kcal
                total_prot += prot
                total_fat += fat
                total_carb += carb
            target_kcal = int(data.get("target_kcal", 0))
            target_protein = int(data.get("target_protein", 0))
            target_fat = int(data.get("target_fat", 0))
            target_carb = int(data.get("target_carb", 0))
            target_fiber = int(data.get("target_fiber", 20))
            remaining_kcal = target_kcal - total_kcal
            remaining_prot = target_protein - total_prot
            remaining_fat = target_fat - total_fat
            remaining_carb = target_carb - total_carb
            warnings = []
            if remaining_kcal < 0:
                maintenance_kcal = int(target_kcal / 0.83) if target_kcal else 0
                if total_kcal <= maintenance_kcal:
                    warnings.append(f"⚖️ Ещё в пределах нормы для поддержания — до неё {maintenance_kcal - total_kcal} ккал.")
                else:
                    warnings.append("🍩 Калорий больше нормы — завтра можно чуть аккуратнее.")
            if remaining_prot < 0:
                warnings.append("🥩 Белка больше нормы — это не критично.")
            if remaining_fat < 0:
                warnings.append("🧈 Жиров многовато — обрати внимание.")
            if remaining_carb < 0:
                warnings.append("🍞 Углеводов перебор — может, было много сладкого?")
            warnings_text = "\n".join(warnings)
            try:
                fiber_line = (
                    f"Клетчатка: {total_fiber:.1f} г"
                    if total_fiber < target_fiber else
                    f"Клетчатка: {total_fiber:.1f} г (добрана 👍)"
                )

                remaining_fiber = target_fiber - total_fiber
                remaining_fiber_line = (
                    f"Клетчатка: нужно добрать {round(remaining_fiber, 1)} г"
                    if remaining_fiber > 0 else
                    "Клетчатка: добрана 👍"
                )

                await bot.edit_message_text(
                    chat_id=callback_query.message.chat.id,
                    message_id=summary_message_id,
                    text=(
                        f"📊 Сумма за день:\n"
                        f"Калории: {total_kcal} ккал\n"
                        f"Белки: {total_prot} г\n"
                        f"Жиры: {total_fat} г\n"
                        f"Углеводы: {total_carb} г\n"
                        f"{fiber_line}\n\n"
                        f"🧮 Осталось на сегодня:\n"
                        f"Калорий: {remaining_kcal if remaining_kcal > 0 else 0} ккал\n"
                        f"Белков: {remaining_prot if remaining_prot > 0 else 0} г\n"
                        f"Жиров: {remaining_fat if remaining_fat > 0 else 0} г\n"
                        f"Углеводов: {remaining_carb if remaining_carb > 0 else 0} г\n"
                        f"{remaining_fiber_line}\n\n"
                        f"{warnings_text}"
                    )
                )
            except Exception as e:
                logging.error(f"Не удалось обновить сообщение с итогами: {e}")
        return
    await callback_query.answer("Блюдо не найдено.")

@dp.message_handler(commands=['история', 'history'])
async def show_history(message: types.Message):
    user_id = str(message.from_user.id)
    history_list = await get_history(user_id)
    if not history_list or len(history_list) == 0:
        await message.reply("История пуста. Сначала отправь фото еды 🍽️")
        return
    text = "🗂 *История последних 10 запросов:*\n\n"
    for i, entry in enumerate(history_list[-10:], start=1):
        prompt_preview = entry['prompt'][:60].strip()
        text += f"{i}. _{prompt_preview}_\n"
        text += f"{entry['response'][:500].strip()}\n\n"
    await message.reply(text, parse_mode="Markdown")

@dp.message_handler(commands=['start'])
async def start_profile(message: types.Message):
    user_id = str(message.from_user.id)
    data = await get_user_data(user_id)
    data["profile_stage"] = "gender"
    
    await update_user_data(user_id, data)
    kb = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Муж", callback_data="gender:муж"),
        InlineKeyboardButton("Жен", callback_data="gender:жен")
    )
    await message.reply(
        "Привет! Я бот, который считает калории по фото, тексту или голосовому 🍽\n\n"
        "Для начала рассчитаем твою суточную норму калорий.\n\n"
        "Выбери свой пол:", reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith("gender:"))
async def handle_gender(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    gender = callback_query.data.split(":")[1]
    data = await get_user_data(user_id)
    data["gender"] = gender
    data["profile_stage"] = "age"
    await update_user_data(user_id, data)
    # Remove the gender keyboard
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.error(f"Не удалось убрать кнопки пола: {e}")
    await bot.send_message(user_id, "Сколько тебе лет? Напиши цифрами.")
    await callback_query.answer()

@dp.message_handler(profile_stage="age")
async def set_age(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip()
    try:
        age = int(text)
        if age < 10 or age > 100:
            raise ValueError
    except:
        await message.reply("Пожалуйста, напиши возраст цифрами от 10 до 100.")
        return
    data = await get_user_data(user_id)
    data["age"] = int(text)
    data["profile_stage"] = "height"
    await update_user_data(user_id, data)
    await message.reply("Какой у тебя рост в см?")

@dp.message_handler(profile_stage="height")
async def set_height(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip()
    try:
        height = int(text)
        if height < 120 or height > 250:
            raise ValueError
    except:
        await message.reply("Напиши рост цифрами в сантиметрах (например, 165).")
        return
    data = await get_user_data(user_id)
    data["height"] = int(text)
    data["profile_stage"] = "weight"
    await update_user_data(user_id, data)
    await message.reply("Какой у тебя текущий вес в кг?")

@dp.message_handler(profile_stage="edit_weight")
async def handle_edit_weight(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip().replace(',', '.')
    try:
        weight = float(text)
        if weight < 30 or weight > 250:
            raise ValueError
    except:
        await message.reply("⚠️ Напиши вес цифрами, например: 67.5")
        return

    data = await get_user_data(user_id)
    data["weight"] = weight
    data["profile_stage"] = None

    # Пересчёт калоража
    gender = data.get("gender")
    age = data.get("age")
    height = data.get("height")
    goal = data.get("goal")
    activity = data.get("activity")
    pregnant = data.get("pregnant", False)

    if gender == "муж":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    multipliers = {"низкий": 1.2, "средний": 1.3, "высокий": 1.4}
    maintenance = bmr * multipliers.get(activity, 1.2)
    if pregnant:
        if goal == weight:
            target_calories = maintenance * 1.17
        elif goal < weight:
            target_calories = maintenance
        else:
            target_calories = maintenance * 1.34
    else:
        if goal == weight:
            target_calories = maintenance
        elif goal < weight:
            target_calories = maintenance * 0.83
        else:
            target_calories = maintenance * 1.17
    target_calories = max(1200, target_calories)
    protein_grams = int((target_calories * 0.3) / 4)
    fat_grams = int((target_calories * 0.3) / 9)
    carbs_grams = int((target_calories * 0.4) / 4)
    fiber_grams = max(20, round(target_calories * 0.014))

    data["target_kcal"] = int(target_calories)
    data["target_protein"] = protein_grams
    data["target_fat"] = fat_grams
    data["target_carb"] = carbs_grams
    data["target_fiber"] = fiber_grams

    await update_user_data(user_id, data)

    await message.reply(
        f"✅ Вес обновлён: *{weight} кг*.\n"
        f"📊 Новая норма калорий: *{int(target_calories)} ккал*.",
        parse_mode="Markdown"
    )


@dp.message_handler(profile_stage="weight")
async def set_weight(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip().replace(',', '.')
    try:
        weight = float(text)
        if weight < 30 or weight > 250:
            raise ValueError
    except:
        await message.reply("⚠️ Напиши вес цифрами, например: 67.5")
        return

    data = await get_user_data(user_id)
    data["weight"] = weight
    data["profile_stage"] = "goal"
    await update_user_data(user_id, data)
    await message.reply("Какой у тебя желаемый вес в кг?")


@dp.message_handler(profile_stage="goal")
async def set_goal_weight(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip().replace(',', '.')
    try:
        goal = float(text)
        if goal < 30 or goal > 250:
            raise ValueError
    except:
        await message.reply("Напиши желаемый вес цифрами, например 60 или 72.5.")
        return
    data = await get_user_data(user_id)
    data["goal"] = float(text)
    data["profile_stage"] = "activity"
    await update_user_data(user_id, data)
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("Минимальная", callback_data="activity:низкий"),
        InlineKeyboardButton("Средняя", callback_data="activity:средний"),
        InlineKeyboardButton("Высокая", callback_data="activity:высокий")
    )
    await message.reply(
        "Выбери уровень своей ежедневной активности:\n\n"
        "1️⃣ *Минимальная* — сидячая работа, почти нет движения в течение дня, нет тренировок.\n"
        "2️⃣ *Средняя* — немного двигаешься в течение дня (гуляешь, делаешь дела по дому), бывают лёгкие тренировки 1–2 раза в неделю.\n"
        "3️⃣ *Высокая* — активный образ жизни или регулярные тренировки 3–5 раз в неделю.",
        reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query_handler(lambda c: c.data.startswith("activity:"))
async def handle_activity(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    activity_level = callback_query.data.split(":")[1]
    data = await get_user_data(user_id)
    data["activity"] = activity_level
    # If female, ask pregnancy status; if male, calculate immediately
    if data.get("gender") == "жен":
        data["profile_stage"] = "pregnant"
        await update_user_data(user_id, data)
        kb = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("Да", callback_data="pregnancy:yes"),
            InlineKeyboardButton("Нет", callback_data="pregnancy:no")
        )
        # Remove activity buttons
        try:
            await callback_query.message.edit_reply_markup(reply_markup=None)
        except Exception as e:
            logging.error(f"Не удалось убрать кнопки активности: {e}")
        await bot.send_message(
            user_id,
            "Беременны или кормите грудью?\n\n"
            "💡 В беременность (со 2 триместра) и при грудном вскармливании калорийность нужно повышать.",
            reply_markup=kb
        )
        await callback_query.answer()
    else:
        # Male or not female: proceed to calculate targets
        data["profile_stage"] = "timezone"  # следующий шаг — часовой пояс
        await update_user_data(user_id, data)
        await bot.send_message(user_id, "Сколько сейчас времени? Напиши только час, без минут (число от 0 до 23)")
        await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data.startswith("pregnancy:"))
async def handle_pregnancy(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    answer = callback_query.data.split(":")[1]
    data = await get_user_data(user_id)
    data["pregnant"] = (answer == "yes")
    data["profile_stage"] = "timezone"  # следующий шаг — часовой пояс
    await update_user_data(user_id, data)
    await bot.send_message(user_id, "Сколько сейчас времени? Напиши только час, без минут (число от 0 до 23)")
    # Remove pregnancy buttons
    try:
        await callback_query.message.edit_reply_markup(reply_markup=None)
    except Exception as e:
        logging.error(f"Не удалось убрать кнопки: {e}")
    await callback_query.answer()

@dp.message_handler(profile_stage="timezone")
async def set_timezone(message: types.Message):
    user_id = str(message.from_user.id)
    text = message.text.strip()

    match = re.match(r"^\d{1,2}$", text)
    if not match:
        await message.reply("Сколько сейчас времени? Напиши только час, без минут (число от 0 до 23)")
        return

    hour = int(text)
    if hour < 0 or hour > 23:
        await message.reply("Час должен быть от 0 до 23. Например: 9 или 20.")
        return

    now_utc = datetime.utcnow()
    user_offset = hour - now_utc.hour
    if user_offset > 12:
        user_offset -= 24
    elif user_offset < -12:
        user_offset += 24

    data = await get_user_data(user_id)
    data["utc_offset"] = user_offset
    data["profile_stage"] = None
    await update_user_data(user_id, data)

    await calculate_and_send_targets(message.chat.id, user_id)

async def calculate_and_send_targets(chat_id, user_id: str):
    data = await get_user_data(user_id)
    gender = data.get("gender")
    age = data.get("age")
    height = data.get("height")
    weight = data.get("weight")
    goal = data.get("goal")
    activity = data.get("activity")
    pregnant = data.get("pregnant", False)
    # Calculate BMR (Mifflin-St Jeor)
    if gender == "муж":
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    multipliers = {"низкий": 1.2, "средний": 1.3, "высокий": 1.4}
    maintenance = bmr * multipliers.get(activity, 1.2)
    if pregnant:
        if goal == weight:
            target_calories = maintenance * 1.17
        elif goal < weight:
            target_calories = maintenance
        else:
            target_calories = maintenance * 1.34
    else:
        if goal == weight:
            target_calories = maintenance
        elif goal < weight:
            target_calories = maintenance * 0.83
        else:
            target_calories = maintenance * 1.17
    target_calories = max(1200, target_calories)
    protein_grams = int((target_calories * 0.3) / 4)
    fat_grams = int((target_calories * 0.3) / 9)
    carbs_grams = int((target_calories * 0.4) / 4)
    fiber_grams = max(20, round(target_calories * 0.014))
    # Update user data with target values
    data["target_kcal"] = int(target_calories)
    data["target_protein"] = protein_grams
    data["target_fat"] = fat_grams
    data["target_carb"] = carbs_grams
    data["target_fiber"] = fiber_grams
    data["profile_stage"] = None
    await update_user_data(user_id, data)

    # Создаём клавиатуру снизу
    persistent_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("🍽️ Добавить блюдо"), KeyboardButton("🍎 Итоги за день")],
            [KeyboardButton("⚙️ Профиль")]
        ],
        resize_keyboard=True,
        is_persistent=True
    )

    # Отправляем расчёт и инструкцию с клавиатурой
    await bot.send_message(
        chat_id,
        (
            f"📊 Твоя суточная норма:\n"
            f"— Для достижения твоей цели по весу: {int(target_calories)} ккал\n"
            f"— Белки: {protein_grams} г\n"
            f"— Жиры: {fat_grams} г\n"
            f"— Углеводы: {carbs_grams} г\n"
            f"— Клетчатка: {fiber_grams} г\n"
            f"— Для поддержания веса: {int(maintenance)} ккал\n\n"
            f"Теперь можешь присылать фото или описание еды — я всё посчитаю 🍽\n\n"
            f"Если хочешь более точный результат — к фото напиши короткое пояснение:\n"
            f"• что именно на тарелке (например: рис, салат со ст.л. оливкового масла)\n"
            f"• как приготовлено (варёное, жареное, запеченое)\n"
            f"• размеры (тарелка 25 см, кружка 300 мл, кусок с ладонь и т.п.)\n\n"
            f"Пример:\n"
            f"«Курица запечённая, картошка варёная, тарелка 26 см»\n\n"
            f"📩 Просто пришли фото, текст или аудио прямо в ответ на это сообщение — и я сразу всё рассчитаю!"
        ),
        reply_markup=persistent_keyboard
    )




@dp.message_handler(content_types=ContentType.PHOTO)
async def handle_photo(message: types.Message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    data = await get_user_data(user_id)
    usage_count = data.get("usage_count", 0)
    show_hint = usage_count < 2
    data["usage_count"] = usage_count + 1
    await update_user_data(user_id, data)

    last_time = data.get("last_photo_time")
    if last_time:
        if isinstance(last_time, str):
            try:
                last_time_dt = datetime.fromisoformat(last_time)
            except Exception:
                last_time_dt = None
        else:
            last_time_dt = last_time
        if last_time_dt and (now - last_time_dt).total_seconds() < 15:
            await message.reply("Подожди немного перед следующим фото 🙏 Я обрабатываю по одной за раз.")
            return

    history_list = await get_history(user_id)
    user_offset = data.get("utc_offset", 0)
    today = datetime.utcnow().astimezone(timezone(timedelta(hours=user_offset))).date()
    photo_entries_today = [e for e in history_list if e.get("type") == "photo" and e["timestamp"].date() == today]
    if len(photo_entries_today) >= 10:
        data["last_photo_time"] = now
        await update_user_data(user_id, data)
        await message.reply("⚠️ Сегодня уже загружено 10 фото. Новые будут доступны завтра.")
        return

    data["last_photo_time"] = now
    await update_user_data(user_id, data)
    await message.reply("Обрабатываю фото...", reply_markup=persistent_keyboard)

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file.file_path)
    image_bytes = file_bytes.getvalue()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    user_caption = message.caption.strip() if message.caption else None
    caption_block = (
        {"type": "text", "text": f"Пояснение от пользователя: {user_caption}. Используй это, только если помогает определить еду или вес еды на фото."}
        if user_caption else None
    )

    recent_photos[user_id] = {"image_bytes": image_bytes, "time": datetime.now()}
    data["last_prompt"] = user_caption or ""
    data["prompts"] = []
    await update_user_data(user_id, data)

    try:
        client = get_openai_client()
        messages = [
            {"role": "system", "content": (
                "Ты нутрициолог. Пользователь прислал фото еды.\n\n"
                "Определи, какие продукты на фото, примерный вес каждого (в граммах), и верни список в формате:\n\n"
                "[{\"name\": \"название продукта на русском языке\", \"grams\": число}]\n\n"
                "⚠️ ВАЖНО:\n"
                "Если блюдо сложное — распиши его по составу. Даже если оно кажется простым, всё равно укажи компоненты и их примерный вес.\n"
                "- Используй ТОЛЬКО готовые продукты — например: «гречка варёная», «куриная грудка жареная», «банан».\n"
                "- Оценивай вес по справочным данным и типичным порциям, характерным для российской кухни, и используй простые, распространённые в России продукты.\n"
                "- Игнорируй людей, руки, фон, посуду и всё, что не еда.\n"
                "- Если на упаковке чётко видно название бренда (например, «Йогурт Epica манго», «Almette сыр лёгкий») — установи \"branded\": true\n"
                "- В остальных случаях — установи \"branded\": false\n"
                "- Не оценивай КБЖУ сам — только определи название, вес и branded\n"
                "- Ответ строго в формате JSON без комментариев, пояснений и кода."
            )},
            {"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                *([caption_block] if caption_block else [])
            ]}
        ]
        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=700,
                temperature=0,
                functions=functions,
                function_call="auto"
            )
        except Exception as e:
            await message.reply("⚠️ Не удалось получить ответ от AI. Попробуй снова через минуту.")
            logging.error(f"[OpenAI ERROR in handle_photo]: {e}")
            return

        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        logging.warning(f"[GPT raw JSON] {content}")
        try:
            food_items = json.loads(content)
        except json.JSONDecodeError:
            await message.reply("⚠️ Не удалось обработать фото. Попробуй ещё раз.")
            return

        # Проверяем продукты через кэш и БД
        results = []
        not_found = []
        for item in food_items:
            name = item["name"]
            grams = item["grams"]
            is_branded = item.get("branded", False)  # 🟡 добавлено поле branded
            cached = product_cache.get(name.lower())
            if cached:
                nutr = cached
                matched_name = name
            else:
                if is_branded:
                    matched = await match_product_name_to_brand_table(name)  # 🟡 ищем в брендах
                else:
                    matched = await match_product_name_to_ready_table(name)  # 🟡 ищем в готовых

                if matched:
                    nutr = {
                        "kcal": matched["kcal"],
                        "protein": matched["protein"],
                        "fat": matched["fat"],
                        "carb": matched["carb"],
                        "fiber": matched["fiber"]
                    }
                    product_cache[name.lower()] = nutr
                    matched_name = matched["matched_name"]
                else:
                    nutr = None
                    matched_name = name

            if nutr:
                logging.info(f"[✅ Из БД] {matched_name} — {grams} г")
                results.append({
                    "name": matched_name,
                    "grams": grams,
                    "kcal": round(nutr["kcal"] * grams / 100),
                    "protein": round(nutr["protein"] * grams / 100, 1),
                    "fat": round(nutr["fat"] * grams / 100, 1),
                    "carb": round(nutr["carb"] * grams / 100, 1),
                    "fiber": round(nutr["fiber"] * grams / 100, 1)
                })
            else:
                logging.warning(f"[❌ GPT сам считает] {name} — {grams} г")
                not_found.append({"name": name, "grams": grams, "branded": is_branded})

        # Если есть ненайденные — отправляем второй запрос в GPT
        if not_found:
            desc = "\n".join([f"{item['name']} – {item['grams']} г" for item in not_found])
            second_prompt = [
                {"role": "system", "content": (
                    "Ты нутрициолог. Рассчитай КБЖУ для следующих продуктов с известным весом.\n\n"
                    "Формат ответа:\n"
                    "[{\"name\": \"название продукта на русском\", \"grams\": ..., \"kcal\": ..., \"protein\": ..., \"fat\": ..., \"carb\": ..., \"fiber\": ...}]\n\n"
                    "⚠️ Все названия продуктов пиши на русском языке.\n"
                    "⚠️ Ответ только JSON, без пояснений и лишнего текста."
                )},
                {"role": "user", "content": desc}
            ]

            try:
                second_response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=second_prompt,
                    temperature=0,
                    max_tokens=700
                )
            except Exception as e:
                await message.reply("⚠️ Ошибка при расчёте КБЖУ для некоторых продуктов. Попробуй снова.")
                logging.error(f"[OpenAI ERROR in handle_photo second call]: {e}")
                return

            second_content = second_response.choices[0].message.content.strip()
            if second_content.startswith("```"):
                second_content = second_content.replace("```json", "").replace("```", "").strip()
            gpt_items = json.loads(second_content)
            for item in gpt_items:
                logging.warning(f"[🧠 Придумано GPT] {item['name']} — {item['grams']} г")
                results.append({
                    "name": item["name"],
                    "grams": item["grams"],
                    "kcal": round(item["kcal"]),
                    "protein": round(item["protein"], 1),
                    "fat": round(item["fat"], 1),
                    "carb": round(item["carb"], 1),
                    "fiber": round(item["fiber"], 1)
                })

        # Собираем итоговое сообщение
        total_kcal = total_prot = total_fat = total_carb = total_fiber = 0
        text_lines = ["🍽️ На фото:"]
        not_found_names = {item["name"] for item in not_found if item.get("branded")}
        for r in results:
            total_kcal += r["kcal"]
            total_prot += r["protein"]
            total_fat += r["fat"]
            total_carb += r["carb"]
            total_fiber += r["fiber"]
            mark = " *" if r["name"] in not_found_names else ""
            text_lines.append(f"• {r['name']}{mark} – {r['grams']} г (~{r['kcal']} ккал)")
        text_lines.append(
            f"📊 Итого: {total_kcal} ккал, Белки: {total_prot} г, Жиры: {total_fat} г, "
            f"Углеводы: {total_carb} г, Клетчатка: {round(total_fiber, 1)} г"
        )
        if not_found_names:
            text_lines.append("🔸 * — точный состав не найден, возможна погрешность")

        int_user_id = int(user_id)
        if (int_user_id not in last_photo_date or last_photo_date[int_user_id] < today) and show_hint:
            text_lines.append("\n💡 Что-то не учёл? Нажми на кнопку «Исправить» и напиши уточнение или запиши голосом — я пересчитаю.\n")
            text_lines.append("Чтобы посмотреть итоги за день, нажми «🍎 Итоги за день» внизу. Если у тебя открыта клавиатура — нажми на кнопочку справа от поля ввода (похожа на 🎛), и появятся кнопки.")
            last_photo_date[int_user_id] = today

        answer = "\n".join(text_lines)
        parsed_ingredients = results

    except Exception as e:
        await message.reply(f"⚠️ Ошибка: {e}")
        return

    answer = round_totals_to_int(answer)

    entry = {
        "prompt": user_caption or "",
        "response": answer,
        "timestamp": now,
        "type": "photo",
        "data": parsed_ingredients
    }
    await add_history_entry(user_id, entry)

    buttons = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💬 Исправить", callback_data=f"start_fix:{entry['timestamp'].isoformat()}"),
        InlineKeyboardButton("❌ Удалить", callback_data=f"del_id:{entry['timestamp'].isoformat()}")
    )
    await message.reply(answer, reply_markup=buttons)




@dp.callback_query_handler(lambda c: c.data.startswith("cancel_fix:"))
async def cancel_fix_callback(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = await get_user_data(user_id)

    data["fix_mode"] = None
    await update_user_data(user_id, data)

    timestamp = callback_query.data.split("cancel_fix:")[1]
    original_text = callback_query.message.text or ""

    # Удаляем строку «✏️ В режиме исправления» из конца текста
    new_text = original_text.replace("\n\n✏️ Внеси уточнение текстом или голосом, я пересчитаю", "").strip()

    new_buttons = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💬 Исправить", callback_data=f"start_fix:{timestamp}"),
        InlineKeyboardButton("❌ Удалить", callback_data=f"del_id:{timestamp}")
    )

    await callback_query.message.edit_text(new_text, reply_markup=new_buttons)
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("start_fix:"))
async def start_fixing(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    timestamp_str = callback_query.data.split(":", 1)[1]

    data = await get_user_data(user_id)
    data["fix_mode"] = timestamp_str
    data["prompts"] = []
    await update_user_data(user_id, data)

    await callback_query.message.reply("✍️ Напиши, что изменить, или запиши голосом — я всё учту.")
    await callback_query.answer()

@dp.message_handler(lambda message: message.text == "🍽️ Добавить блюдо")
async def handle_add_food_reply_button(message: types.Message):
    await message.reply(
        "Просто пришли фото еды — я сам распознаю, что на тарелке, и посчитаю калории.\n\n"
        "Если нет фото — можешь написать описание блюда текстом ✍️ или надиктовать голосом 🎤\n\n"
        "💡 Главное — укажи примерный объём (например: «3 печенья типа “Мария” и чашка чая без сахара»). Тогда расчёт будет точнее.\n\n"
        "📷 Чтобы отправить фото — нажми на скрепку 📎 внизу.\n\n"
        "Кстати, в следующий раз можно не нажимать на кнопку, а просто сразу присылать фото, текст или голос 😉"
    )



from io import BytesIO


@dp.message_handler(content_types=[ContentType.VOICE, ContentType.AUDIO], fix_mode=False)
async def handle_voice_audio(message: types.Message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    data = await get_user_data(user_id)
    usage_count = data.get("usage_count", 0)
    show_hint = usage_count < 2
    data["usage_count"] = usage_count + 1
    await update_user_data(user_id, data)

    history_list = await get_history(user_id)
    user_offset = data.get("utc_offset", 0)
    today = datetime.utcnow().astimezone(timezone(timedelta(hours=user_offset))).date()
    text_entries_today = [e for e in history_list if e.get("type") == "text" and e["timestamp"].date() == today]
    if len(text_entries_today) >= 60:
        await message.reply("⚠️ Сегодня ты уже отправила 10 описаний еды. Новые можно будет отправить завтра.")
        return

    await message.reply("🎧 Распознаю аудио...")

    file_id = message.voice.file_id if message.voice else message.audio.file_id
    file = await bot.get_file(file_id)
    file_bytes = await bot.download_file(file.file_path)
    audio_file = BytesIO(file_bytes.getvalue())
    audio_file.name = "audio.ogg"

    try:
        client = get_openai_client()
        transcript_response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
            language="ru",
            prompt="Опиши, что ты съела — для расчёта калорий и БЖУ"
        )
        user_text = transcript_response.strip()
    except Exception as e:
        await message.reply(f"⚠️ Не удалось распознать голосовое сообщение. Попробуй сказать чуть медленнее или отправь описание текстом ✍️")
        return


    if len(user_text) < 5:
        await message.reply("✍️ Пожалуйста, проговори еду подробнее. Пример: «Булочка с корицей размером с ладонь и кофе с молоком 250 мл»")
        return

    await message.reply("Считаю калории...", reply_markup=persistent_keyboard)

    try:
        client = get_openai_client()
        messages = [
            {"role": "system", "content": (
                "Ты нутрициолог. Пользователь описал голосом, что он ел.\n\n"
                "Определи, какие продукты он упомянул и примерный вес каждого (в граммах).\n\n"
                "Формат ответа:\n"
                "[{\"name\": \"название продукта на русском языке\", \"grams\": число}]\n\n"
                "⚠️ Если в описании есть конкретное название бренда (например, «Йогурт Epica манго»), пометь его как branded: true\n"
                "⚠️ Если бренд не указан — branded: false\n"
                "⚠️ Не оценивай КБЖУ\n"
                "⚠️ Ответ строго в JSON без комментариев, пояснений и кода."
            )},
            {"role": "user", "content": user_text}
        ]


        try:
            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=700,
                temperature=0,
            )
        except Exception as e:
            await message.reply("⚠️ Не удалось обработать голосовое описание. Попробуй ещё раз через минуту.")
            logging.error(f"[OpenAI ERROR in handle_voice_audio]: {e}")
            return


        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        food_items = json.loads(content)
    except Exception as e:
        await message.reply(f"⚠️ Ошибка обработки текста: {e}")
        return

    results = []
    not_found = []

    for item in food_items:
        name = item["name"]
        grams = item["grams"]
        is_branded = item.get("branded", False)

        cached = product_cache.get(name.lower())
        if cached:
            nutr = cached
            matched_name = name
        else:
            matched = await match_product_name_to_brand_table(name) if is_branded else await match_product_name_to_ready_table(name)
            if matched:
                nutr = {
                    "kcal": matched["kcal"],
                    "protein": matched["protein"],
                    "fat": matched["fat"],
                    "carb": matched["carb"],
                    "fiber": matched["fiber"]
                }
                matched_name = matched["matched_name"]
                product_cache[name.lower()] = nutr
            else:
                nutr = None
                matched_name = name

        if nutr:
            results.append({
                "name": matched_name,
                "grams": grams,
                "kcal": round(nutr["kcal"] * grams / 100),
                "protein": round(nutr["protein"] * grams / 100, 1),
                "fat": round(nutr["fat"] * grams / 100, 1),
                "carb": round(nutr["carb"] * grams / 100, 1),
                "fiber": round(nutr["fiber"] * grams / 100, 1)
            })
        else:
            not_found.append({"name": name, "grams": grams, "branded": is_branded})


    if not_found:
        desc = "\n".join([f"{item['name']} – {item['grams']} г" for item in not_found])
        second_prompt = [
            {"role": "system", "content": (
                "Ты нутрициолог. Рассчитай КБЖУ для следующих продуктов с известным весом.\n\n"
                "Формат:\n"
                "[{\"name\": \"название продукта на русском\", \"grams\": ..., \"kcal\": ..., \"protein\": ..., \"fat\": ..., \"carb\": ..., \"fiber\": ...}]\n\n"
                "⚠️ Только готовые продукты. Только JSON. Без пояснений."
            )},
            {"role": "user", "content": desc}
        ]
        try:
            second_response = await client.chat.completions.create(
                model="gpt-4o",
                messages=second_prompt,
                max_tokens=700
            )
            second_content = second_response.choices[0].message.content.strip()
            if second_content.startswith("```"):
                second_content = second_content.replace("```json", "").replace("```", "").strip()
            gpt_items = json.loads(second_content)
            for item in gpt_items:
                results.append({
                    "name": item["name"],
                    "grams": item["grams"],
                    "kcal": round(item["kcal"]),
                    "protein": round(item["protein"], 1),
                    "fat": round(item["fat"], 1),
                    "carb": round(item["carb"], 1),
                    "fiber": round(item["fiber"], 1)
                })
        except Exception as e:
            await message.reply(f"⚠️ Ошибка при расчёте КБЖУ: {e}")
            return


    total_kcal = total_prot = total_fat = total_carb = total_fiber = 0
    text_lines = ["🍽️ В тарелке:"]
    not_found_names = {item["name"] for item in not_found if item.get("branded")}

    for r in results:
        total_kcal += r["kcal"]
        total_prot += r["protein"]
        total_fat += r["fat"]
        total_carb += r["carb"]
        total_fiber += r["fiber"]
        mark = " *" if r["name"] in not_found_names else ""
        text_lines.append(f"• {r['name']}{mark} – {r['grams']} г (~{r['kcal']} ккал)")

    text_lines.append(
        f"📊 Итого: {total_kcal} ккал, Белки: {total_prot} г, Жиры: {total_fat} г, "
        f"Углеводы: {total_carb} г, Клетчатка: {round(total_fiber, 1)} г"
    )

    if not_found_names:
        text_lines.append("🔸 * — точный состав не найден, возможна погрешность")

    if len(text_entries_today) == 0 and show_hint:
        text_lines.append("\n💡 Что-то не учёл? Нажми на кнопку «Исправить» и напиши уточнение или запиши голосом — я пересчитаю.\n")
        text_lines.append("Чтобы посмотреть итоги за день, нажми «🍎 Итоги за день» внизу. Если у тебя открыта клавиатура — нажми на кнопочку справа от поля ввода (похожа на 🎛), и появятся кнопки.")

    answer = "\n".join(text_lines)
    answer = round_totals_to_int(answer)

    entry = {
        "prompt": user_text,
        "response": answer,
        "timestamp": now,
        "type": "text",
        "data": results
    }
    await add_history_entry(user_id, entry)

    buttons = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💬 Исправить", callback_data=f"start_fix:{entry['timestamp'].isoformat()}"),
        InlineKeyboardButton("❌ Удалить", callback_data=f"del_id:{entry['timestamp'].isoformat()}")
    )
    await message.reply(answer, reply_markup=buttons)



@dp.message_handler(lambda message: message.text == "⚙️ Профиль")
async def show_user_profile(message: types.Message):
    user_id = str(message.from_user.id)
    data = await get_user_data(user_id)

    gender = data.get("gender", "не указано")
    age = data.get("age", "не указано")
    height = data.get("height", "не указано")
    weight = data.get("weight", "не указано")
    target = data.get("goal", "не указано")
    activity = data.get("activity", "не указано")

    # Используем актуальные ключи, как в итогах дня
    calories = data.get("target_kcal", "не рассчитано")
    proteins = data.get("target_protein", "–")
    fats = data.get("target_fat", "–")
    carbs = data.get("target_carb", "–")
    fiber = data.get("target_fiber", "–")

    text = (
        f"💁‍♀️ Вот что я про тебя знаю:\n\n"
        f"*Пол:* {gender}\n"
        f"*Возраст:* {age} лет\n"
        f"*Рост:* {height} см\n"
        f"*Вес:* {weight} кг\n"
        f"*Цель:* {target}\n"
        f"*Активность:* {activity}\n\n"
        f"📊 *Рассчитанная норма на день:*\n"
        f"• Калории: {calories} ккал\n"
        f"• Белки: {proteins} г\n"
        f"• Жиры: {fats} г\n"
        f"• Углеводы: {carbs} г\n"
        f"• Клетчатка: {fiber} г"
    )

    buttons = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("⚖️ Указать новый вес", callback_data="update_weight"),
        InlineKeyboardButton("🔄 Поменять все данные", callback_data="restart_profile"),
        InlineKeyboardButton("🆘 Написать в поддержку", url="https://t.me/alinaviaphoto")
    )

    await message.reply(text, reply_markup=buttons, parse_mode="Markdown")


@dp.callback_query_handler(lambda c: c.data == "update_weight")
async def update_weight_callback(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = await get_user_data(user_id)
    data["profile_stage"] = "edit_weight"
    await update_user_data(user_id, data)
    await bot.send_message(callback_query.from_user.id, "✏️ Введи *текущий вес* в кг (только число):", parse_mode="Markdown")
    await callback_query.answer()

@dp.callback_query_handler(lambda c: c.data == "restart_profile")
async def restart_profile_callback(callback_query: CallbackQuery):
    user_id = str(callback_query.from_user.id)
    data = await get_user_data(user_id)
    data["profile_stage"] = "gender"
    await update_user_data(user_id, data)

    kb = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("Муж", callback_data="gender:муж"),
        InlineKeyboardButton("Жен", callback_data="gender:жен")
    )

    await bot.send_message(
        callback_query.from_user.id,
        "🔄 Хорошо, начнём заново!\n\nВыбери свой пол:",
        reply_markup=kb
    )
    await callback_query.answer()


@dp.message_handler(fix_mode=False)
async def handle_text_food(message: types.Message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    data = await get_user_data(user_id)
    usage_count = data.get("usage_count", 0)
    show_hint = usage_count < 2
    data["usage_count"] = usage_count + 1
    await update_user_data(user_id, data)

    history_list = await get_history(user_id)
    user_offset = data.get("utc_offset", 0)
    today = datetime.utcnow().astimezone(timezone(timedelta(hours=user_offset))).date()
    text_entries_today = [e for e in history_list if e.get("type") == "text" and e["timestamp"].date() == today]
    if len(text_entries_today) >= 60:
        await message.reply("⚠️ Сегодня ты уже отправила 10 описаний еды. Новые можно будет отправить завтра.")
        return

    user_text = message.text.strip()
    if len(user_text) < 5:
        await message.reply("✍️ Пожалуйста, опиши еду подробнее. Пример: «Булочка с корицей размером с ладонь и кофе с молоком 250 мл»")
        return

    await message.reply("Считаю калории...", reply_markup=persistent_keyboard)

    try:
        client = get_openai_client()
        messages = [
            {"role": "system", "content": (
                "Ты нутрициолог. Пользователь описал текстом, что он ел.\n\n"
                "Определи, какие продукты он упомянул и примерный вес каждого (в граммах).\n\n"
                "Формат ответа:\n"
                "[{\"name\": \"название продукта на русском языке\", \"grams\": число}]\n\n"
                "⚠️ ВАЖНО:\n"
                "- Используй только готовые продукты (например: «гречка варёная», «куриная грудка жареная», «банан»)\n"
                "- Если в описании есть конкретное название бренда (например, «Йогурт Epica манго»), пометь его как branded: true\n"
                "- Если бренд не указан — branded: false\n"
                "- Не оценивай КБЖУ сам\n"
                "- Ответ строго в формате JSON без пояснений"
            )},
            {"role": "user", "content": user_text}
        ]
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0,
            max_tokens=700
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        food_items = json.loads(content)
    except Exception as e:
        await message.reply(f"⚠️ Не удалось обработать текст. Попробуй ещё раз.\n{e}")
        return

    # Сопоставление с двумя таблицами
    results = []
    not_found = []
    for item in food_items:
        name = item["name"]
        grams = item["grams"]
        is_branded = item.get("branded", False)

        cached = product_cache.get(name.lower())
        if cached:
            nutr = cached
            matched_name = name
        else:
            if is_branded:
                matched = await match_product_name_to_brand_table(name)
            else:
                matched = await match_product_name_to_ready_table(name)

            if matched:
                nutr = {
                    "kcal": matched["kcal"],
                    "protein": matched["protein"],
                    "fat": matched["fat"],
                    "carb": matched["carb"],
                    "fiber": matched["fiber"]
                }
                product_cache[name.lower()] = nutr
                matched_name = matched["matched_name"]
            else:
                nutr = None
                matched_name = name

        if nutr:
            logging.info(f"[✅ Из БД] {matched_name} — {grams} г")
            results.append({
                "name": matched_name,
                "grams": grams,
                "kcal": round(nutr["kcal"] * grams / 100),
                "protein": round(nutr["protein"] * grams / 100, 1),
                "fat": round(nutr["fat"] * grams / 100, 1),
                "carb": round(nutr["carb"] * grams / 100, 1),
                "fiber": round(nutr["fiber"] * grams / 100, 1)
            })
        else:
            logging.warning(f"[❌ GPT сам считает] {name} — {grams} г")
            not_found.append({"name": name, "grams": grams, "branded": is_branded})

    # Второй GPT-запрос, если что-то не найдено
    if not_found:
        desc = "\n".join([f"{item['name']} – {item['grams']} г" for item in not_found])
        second_prompt = [
            {"role": "system", "content": (
                "Ты нутрициолог. Рассчитай КБЖУ для следующих продуктов с известным весом.\n\n"
                "Формат ответа:\n"
                "[{\"name\": \"название продукта на русском\", \"grams\": ..., \"kcal\": ..., \"protein\": ..., \"fat\": ..., \"carb\": ..., \"fiber\": ...}]\n\n"
                "⚠️ Все названия продуктов пиши на русском языке.\n"
                "⚠️ Ответ только JSON, без пояснений."
            )},
            {"role": "user", "content": desc}
        ]
        try:
            second_response = await client.chat.completions.create(
                model="gpt-4o",
                temperature=0,
                messages=second_prompt,
                max_tokens=700
            )
            second_content = second_response.choices[0].message.content.strip()
            if second_content.startswith("```"):
                second_content = second_content.replace("```json", "").replace("```", "").strip()
            gpt_items = json.loads(second_content)
            for item in gpt_items:
                logging.warning(f"[🧠 Придумано GPT] {item['name']} — {item['grams']} г")
                results.append({
                    "name": item["name"],
                    "grams": item["grams"],
                    "kcal": round(item["kcal"]),
                    "protein": round(item["protein"], 1),
                    "fat": round(item["fat"], 1),
                    "carb": round(item["carb"], 1),
                    "fiber": round(item["fiber"], 1)
                })
        except Exception as e:
            await message.reply(f"⚠️ Ошибка при расчёте КБЖУ: {e}")
            return

    # Формируем итог
    total_kcal = total_prot = total_fat = total_carb = total_fiber = 0
    text_lines = ["🍽️ В тарелке:"]
    not_found_names = {item["name"] for item in not_found if item.get("branded")}

    for r in results:
        total_kcal += r["kcal"]
        total_prot += r["protein"]
        total_fat += r["fat"]
        total_carb += r["carb"]
        total_fiber += r["fiber"]

        mark = " *" if r["name"] in not_found_names else ""
        text_lines.append(f"• {r['name']}{mark} – {r['grams']} г (~{r['kcal']} ккал)")

    text_lines.append(
        f"📊 Итого: {total_kcal} ккал, Белки: {total_prot} г, Жиры: {total_fat} г, "
        f"Углеводы: {total_carb} г, Клетчатка: {round(total_fiber, 1)} г"
    )

    if not_found_names:
        text_lines.append("🔸 * — точный состав не найден, возможна погрешность")

    if len(text_entries_today) == 0 and show_hint:
        text_lines.append("\n💡 Что-то не учёл? Нажми на кнопку «Исправить» и напиши уточнение или запиши голосом — я пересчитаю.\n")
        text_lines.append("Чтобы посмотреть итоги за день, нажми «🍎 Итоги за день» внизу. Если у тебя открыта клавиатура — нажми на кнопочку справа от поля ввода (похожа на 🎛), и появятся кнопки.")

    answer = "\n".join(text_lines)
    answer = round_totals_to_int(answer)

    entry = {
        "prompt": user_text,
        "response": answer,
        "timestamp": now,
        "type": "text",
        "data": results
    }
    await add_history_entry(user_id, entry)

    buttons = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💬 Исправить", callback_data=f"start_fix:{entry['timestamp'].isoformat()}"),
        InlineKeyboardButton("❌ Удалить", callback_data=f"del_id:{entry['timestamp'].isoformat()}")
    )
    await message.reply(answer, reply_markup=buttons)


from io import BytesIO

@dp.message_handler(content_types=[ContentType.TEXT, ContentType.VOICE, ContentType.AUDIO], fix_mode=True)
async def handle_fix_input(message: types.Message):
    user_id = str(message.from_user.id)
    now = datetime.now()
    data = await get_user_data(user_id)

    # ⛔ Страховка: сбросить режим, если fix_mode невалидный или запись не найдена
    timestamp_str = data.get("fix_mode")
    if not timestamp_str:
        data["fix_mode"] = None
        data["prompts"] = []
        await update_user_data(user_id, data)
        await message.reply("⚠️ Режим 'исправить' сброшен. Можно отправлять еду заново.")
        return

    try:
        target_ts = datetime.fromisoformat(timestamp_str)
    except:
        data["fix_mode"] = None
        data["prompts"] = []
        await update_user_data(user_id, data)
        await message.reply("⚠️ Дата режима 'исправить' повреждена. Режим сброшен.")
        return

    history_list = await get_history(user_id)
    matched_entries = [e for e in history_list if e["timestamp"] == target_ts]
    if not matched_entries:
        data["fix_mode"] = None
        data["prompts"] = []
        await update_user_data(user_id, data)
        await message.reply("⚠️ Не удалось найти, что нужно исправить. Режим сброшен.")
        return

    # Распознаём текст из сообщения или аудио
    if message.text:
        user_fix = message.text.strip()
    else:
        await message.reply("🎧 Распознаю голос...")
        try:
            file_id = message.voice.file_id if message.voice else message.audio.file_id
            file = await bot.get_file(file_id)
            file_bytes = await bot.download_file(file.file_path)

            audio_file = BytesIO(file_bytes.getvalue())
            audio_file.name = "audio.ogg"

            client = get_openai_client()
            transcript_response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="text",
                prompt="Пользователь вносит уточнение по еде. Распознай его голос."
            )
            user_fix = transcript_response.strip()
        except Exception as e:
            await message.reply(f"⚠️ Не удалось распознать голос: {e}")
            return

    if len(user_fix) < 5:
        await message.reply("✍️ Пожалуйста, уточни подробнее, что нужно изменить.")
        return

    await message.reply("Уточнение принято. Пересчитываю...")

    data.setdefault("prompts", [])
    data["prompts"].append(user_fix)
    await update_user_data(user_id, data)

    history_list = await get_history(user_id)
    user_offset = data.get("utc_offset", 0)
    today = datetime.utcnow().astimezone(timezone(timedelta(hours=user_offset))).date()
    timestamp_str = data.get("fix_mode")
    if not timestamp_str:
        data["fix_mode"] = None
        data["prompts"] = []
        await update_user_data(user_id, data)
        await message.reply("⚠️ Не удалось определить, что исправлять. Режим 'Исправить' сброшен.")
        return

    target_ts = datetime.fromisoformat(timestamp_str)

    # Ищем точную запись по timestamp
    previous_entries = [e for e in history_list if e["timestamp"] == target_ts]
    if not previous_entries:
        await message.reply("⚠️ Не удалось найти запись для исправления.")
        return

    previous_entry = previous_entries[0]
    previous_response = previous_entry["response"]
    previous_type = previous_entry["type"]
    previous_data = previous_entry.get("data", [])

    previous_type = previous_entries[0]["type"] if previous_entries else ""
    previous_data = previous_entries[0].get("data", [])

    previous_response_text = previous_response

    system_prompt = (
        "Ты нутрициолог. Пользователь прислал блюдо (фото или текст), а потом уточнение. "
        "Твоя задача — скорректировать ТОЛЬКО те позиции, которые указаны в уточнении. "
        "Остальные позиции из предыдущего списка НЕ ИЗМЕНЯЙ. Просто перепиши их без изменений. "
        "Обязательно пересчитай калории и все нутриенты (белки, жиры, углеводы, клетчатку), даже если меняются только граммы! "
        "Не копируй старые значения — пересчитай их заново по новым граммам. Внизу снова выведи общий итог.\n\n"
        "Ничего не добавляй от себя. Не пиши никаких комментариев, пояснений, предупреждений.\n\n"
        "Выдай результат строго в формате:\n"
        "🍽️ Съедено:\n"
        "• Название – граммы (~ккал)\n"
        "📊 Итого: Х ккал, Белки: Х г, Жиры: Х г, Углеводы: Х г, Клетчатка: Х г"
    )

    try:
        openai_client = get_openai_client()
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Предыдущий список:\n{previous_response_text}\n\nНовое уточнение:\n{user_fix}"}
            ],
            max_tokens=700
        )

        answer = response.choices[0].message.content
        answer = round_totals_to_int(answer)

        buttons = InlineKeyboardMarkup().add(
            InlineKeyboardButton("💬 Исправить", callback_data=f"start_fix:{now.isoformat()}"),
            InlineKeyboardButton("❌ Удалить", callback_data=f"del_id:{now.isoformat()}")
        )
        await message.reply(answer, reply_markup=buttons)

        if previous_entries:
            old_entry = previous_entries[0]
            try:
                async with async_session() as session:
                    async with session.begin():
                        await session.execute(delete(UserHistory).where(
                            UserHistory.user_id == user_id,
                            UserHistory.timestamp == old_entry["timestamp"]
                        ))
            except Exception as e:
                logging.error(f"Failed to delete previous entry: {e}")

        new_entry = {
            "prompt": "\n".join(data.get("prompts", [])),
            "response": answer,
            "timestamp": now,
            "type": previous_type or "text"
        }
        await add_history_entry(user_id, new_entry)

    except Exception as e:
        await message.reply(f"⚠️ Ошибка GPT или при сохранении: {e}")

    finally:
        data["fix_mode"] = None
        data["prompts"] = []
        await update_user_data(user_id, data)

        try:
            last_messages = await bot.get_chat_history(message.chat.id, limit=3)
            for msg in last_messages:
                if msg.from_user.id == (await bot.me).id and msg.reply_markup:
                    await bot.edit_message_reply_markup(chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=None)
                    break
        except:
            pass





@dp.message_handler(content_types=ContentType.WEB_APP_DATA)
async def handle_webapp_data(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)

        if data.get("type") == "get_summary":
            user_id = str(message.from_user.id)
            date_str = data.get("date")

            summary_text = await calculate_summary_text(user_id, date_str)

            await bot.send_message(
                chat_id=message.chat.id,
                text=json.dumps({"type": "summary", "text": summary_text})
            )

        elif data.get("type") == "delete_entry":
            entry_id = data.get("id")

            # 🔥 Удаление записи из БД по ID
            async with async_session() as session:
                await session.execute(
                    delete(History).where(History.id == entry_id)
                )
                await session.commit()

            await message.answer(f"🗑 Удалено блюдо с ID {entry_id}")

    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке WebApp: {str(e)}")






# Startup and shutdown events
async def on_startup(dp):
    await load_products_from_db()
    # Ensure database tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


    # Запустить фоновую задачу
    asyncio.create_task(send_morning_reminders())
    asyncio.create_task(clean_old_photos())

    logging.info("🚀 Bot started, DB initialized, webhook set.")

async def on_shutdown(dp):
    logging.info("Выключение...")


from aiohttp import web

WEBHOOK_PATH = "/webhook/7828260564:AAHv_NqPmR8M-1IMjrXXPKwI-g6bXHsI-IM"
WEBHOOK_URL = f"https://via-alina-bot-webhook.onrender.com{WEBHOOK_PATH}"

async def handle_index(request):
    return web.Response(text="✅ Бот работает.")

async def handle_webhook(request):
    try:
        request_data = await request.json()
        update = types.Update.to_object(request_data)
        await asyncio.wait_for(dp.process_update(update), timeout=25)
    except asyncio.TimeoutError:
        logging.error("⏱ Вебхук завис — превышено время ожидания 25 секунд.")
    except Exception as e:
        logging.exception(f"Ошибка при обработке вебхука: {e}")
    return web.Response()

def normalize_name(text: str) -> str:
    return text.lower().replace("ё", "е").strip()

async def match_product_name_to_table(name: str, table_name: str) -> dict | None:
    async with async_session() as session:
        result = await session.execute(text(f"SELECT name, kcal, protein, fat, carb, fiber FROM {table_name}"))
        rows = result.fetchall()

    norm_name = normalize(name)
    name_list = [normalize(row[0]) for row in rows]
    match = process.extractOne(norm_name, name_list, scorer=fuzz.token_set_ratio)

    if match and match[1] >= 85:
        for row in rows:
            if normalize(row[0]) == match[0]:
                return {
                    "matched_name": row[0],
                    "kcal": row[1],
                    "protein": row[2],
                    "fat": row[3],
                    "carb": row[4],
                    "fiber": row[5]
                }
    return None

# 🔍 Поиск в таблице без брендов
async def match_product_name_to_ready_table(name: str) -> dict | None:
    return await match_product_name_to_table(name, "products")

# 🔍 Поиск в таблице брендов
async def match_product_name_to_brand_table(name: str) -> dict | None:
    return await match_product_name_to_table(name, "productbrend")


app = web.Application()
app.router.add_get("/", handle_index)
app.router.add_post(WEBHOOK_PATH, handle_webhook)

async def startup_wrapper(app):
    await on_startup(dp)

async def shutdown_wrapper(app):
    await on_shutdown(dp)

app.on_startup.append(startup_wrapper)
app.on_shutdown.append(shutdown_wrapper)

if __name__ == '__main__':

    # Устанавливаем текущие экземпляры бота и диспетчера для контекста
    bot.set_current(bot)
    dp.set_current(dp)

    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))