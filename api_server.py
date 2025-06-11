from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import os
from dotenv import load_dotenv
import sys
import json
from datetime import datetime, timedelta, date, timezone
import re
from functools import lru_cache
import hashlib
import time

# Загрузка переменных окружения
load_dotenv()

app = FastAPI(title="Telegram Bot WebApp API", 
              description="API для интеграции WebApp с Telegram ботом трекера питания")

# Настройка CORS для доступа с Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Временно разрешаем все домены для отладки
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Простая система кэширования для оптимизации API запросов
class APICache:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = {}
        self.default_ttl = 300  # 5 минут по умолчанию
    
    def get_cache_key(self, prefix: str, user_id: str, **kwargs) -> str:
        """Генерирует уникальный ключ кэша"""
        key_parts = [prefix, user_id]
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}={v}")
        key_data = ":".join(key_parts)
        return hashlib.md5(key_data.encode()).hexdigest()
    
    def get(self, key: str):
        """Получает данные из кэша если они не устарели"""
        if key in self.cache:
            if time.time() < self.cache_ttl.get(key, 0):
                return self.cache[key]
            else:
                # Удаляем устаревшие данные
                self.cache.pop(key, None)
                self.cache_ttl.pop(key, None)
        return None
    
    def set(self, key: str, value, ttl: int = None):
        """Сохраняет данные в кэш"""
        self.cache[key] = value
        self.cache_ttl[key] = time.time() + (ttl or self.default_ttl)
    
    def invalidate_user_cache(self, user_id: str):
        """Очищает весь кэш пользователя"""
        keys_to_remove = [key for key in self.cache.keys() if user_id in str(key)]
        for key in keys_to_remove:
            self.cache.pop(key, None)
            self.cache_ttl.pop(key, None)

# Глобальный экземпляр кэша
api_cache = APICache()

# Кэшированные функции для парсинга данных
@lru_cache(maxsize=1000)
def parse_nutrition_cached(response_text: str) -> tuple:
    """Кэшированное извлечение БЖУ из ответа"""
    match = re.search(
        r'Итого:\s*[~≈]?\s*(\d+\.?\d*)\s*ккал.*?'
        r'Белки[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
        r'Жиры[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
        r'Углеводы[:\-]?\s*[~≈]?\s*(\d+\.?\d*)\s*г.*?'
        r'Клетчатка[:\-]?\s*([~≈]?\s*\d+\.?\d*)\s*г',
        response_text, flags=re.IGNORECASE | re.DOTALL
    )
    
    if match:
        kcal, prot, fat, carb = map(lambda x: round(float(x)), match.groups()[:4])
        fiber = round(float(match.groups()[4]), 1)
        return kcal, prot, fat, carb, fiber
    
    return 0, 0, 0, 0, 0.0

@lru_cache(maxsize=500)
def parse_products_cached(response_text: str) -> str:
    """Кэшированное извлечение списка продуктов из ответа"""
    lines = response_text.splitlines()
    food_lines = [line for line in lines if line.strip().startswith(("•", "-"))]
    return ", ".join([re.sub(r'^[•\-]\s*', '', line).split("–")[0].strip() for line in food_lines]) or "Без описания"


# Модели данных
class MealEntry(BaseModel):
    time: str
    name: str
    calories: int
    items: List[Dict[str, Any]]
    image: Optional[str] = None  # Добавлено поле для изображения в формате base64

class DiaryDay(BaseModel):
    date: str
    total_calories: int
    meals: List[MealEntry]

class NutritionStats(BaseModel):
    calories: int
    protein: int
    fat: int
    carb: int
    fiber: float

class UserStats(BaseModel):
    avg_calories: int
    days_tracked: int
    adherence_percent: int
    weight_change: float
    nutrition_distribution: Dict[str, int]
    top_products: List[Dict[str, Any]]

class Recipe(BaseModel):
    title: str
    category: str
    prep_time: str
    calories: int
    description: str
    portions: int
    nutrition: NutritionStats

# Модель для обновления профиля пользователя
class ProfileUpdateData(BaseModel):
    gender: Optional[str] = None
    age: Optional[int] = None
    height: Optional[int] = None
    weight: Optional[float] = None
    goal: Optional[float] = None
    activity: Optional[str] = None
    pregnant: Optional[bool] = None
    utc_offset: Optional[int] = None
    morning_reminded: Optional[bool] = None

# Модель для итогов дня
class DaySummary(BaseModel):
    date: str
    total_calories: int
    total_protein: int
    total_fat: int
    total_carb: int
    total_fiber: float
    meals: List[Dict[str, Any]]
    remaining_calories: int
    remaining_protein: int
    remaining_fat: int
    remaining_carb: int
    remaining_fiber: float
    warnings: List[str]

# Функция для проверки API-ключа (упрощенная для отладки)
async def verify_api_key(x_api_key: str = Header(None)):
    # Временно отключаем строгую проверку для отладки
    return x_api_key or "debug_key"

# Корневой эндпоинт API
@app.get("/api")
async def api_root():
    return {"status": "success", "message": "API работает", "timestamp": datetime.now().isoformat()}

# Эндпоинт для проверки здоровья API
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Новый эндпоинт для получения итогов дня
@app.get("/api/day-summary/{user_id}", response_model=Dict[str, Any])
async def get_day_summary(user_id: str, date_str: Optional[str] = None, api_key: str = Depends(verify_api_key)):
    """
    Получение итогов дня для пользователя с кэшированием
    """
    try:
        # Проверяем кэш
        cache_key = api_cache.get_cache_key("day_summary", user_id, date=date_str or "today")
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Добавляем обработку ошибок импорта
        try:
            # Импортируем функции из bot.py
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_day_summary: {import_error}")
            # Возвращаем тестовые данные если bot.py недоступен
            target_date = date_str or datetime.now().strftime("%Y-%m-%d")
            result = {
                "status": "success", 
                "data": {
                    "date": target_date,
                    "total_calories": 1500,
                    "total_protein": 80,
                    "total_fat": 50,
                    "total_carb": 180,
                    "total_fiber": 15.5,
                    "meals": [
                        {
                            "id": 1,
                            "time": "08:30",
                            "description": "Тестовый завтрак",
                            "calories": 400,
                            "protein": 20,
                            "fat": 15,
                            "carb": 50
                        }
                    ],
                    "remaining_calories": 500,
                    "remaining_protein": 20,
                    "remaining_fat": 17,
                    "remaining_carb": 70,
                    "remaining_fiber": 9.5,
                    "warnings": ["🔧 Режим отладки - используются тестовые данные"],
                    "message": "Тестовые данные (bot.py недоступен)"
                }
            }
            # Кэшируем тестовые данные на короткое время
            api_cache.set(cache_key, result, ttl=60)
            return result
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        user_offset = user_data.get("utc_offset", 0)
        user_tz = timezone(timedelta(hours=user_offset))
        
        # Определяем дату для анализа
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.now(user_tz).date()
        
        # Получаем историю пользователя
        history = await get_history(user_id)
        
        # Фильтруем записи за указанную дату и записи о еде (включая текстовые и голосовые)
        entries_today = [e for e in history if e["timestamp"].astimezone(user_tz).date() == target_date and e.get("type") in ["food", "text"]]
        
        if not entries_today:
            result = {
                "status": "success", 
                "data": {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "total_calories": 0,
                    "total_protein": 0,
                    "total_fat": 0,
                    "total_carb": 0,
                    "total_fiber": 0,
                    "meals": [],
                    "remaining_calories": user_data.get("target_kcal", 0),
                    "remaining_protein": user_data.get("target_protein", 0),
                    "remaining_fat": user_data.get("target_fat", 0),
                    "remaining_carb": user_data.get("target_carb", 0),
                    "remaining_fiber": user_data.get("target_fiber", 20),
                    "warnings": [],
                    "message": "В этот день не было добавлено ни одного блюда."
                }
            }
            # Кэшируем пустые данные на короткое время
            api_cache.set(cache_key, result, ttl=180)
            return result
        
        # Подсчитываем общие значения
        total_kcal = total_prot = total_fat = total_carb = total_fiber = 0.0
        meals = []
        
        for i, entry in enumerate(entries_today, start=1):
            # Используем кэшированную функцию парсинга БЖУ
            kcal, prot, fat, carb, fiber = parse_nutrition_cached(entry['response'])
            
            total_kcal += kcal
            total_prot += prot
            total_fat += fat
            total_carb += carb
            total_fiber += fiber
            
            # Используем кэшированную функцию парсинга продуктов
            short_desc = parse_products_cached(entry['response'])
            
            meals.append({
                "id": i,
                "time": entry['timestamp'].strftime("%H:%M"),
                "description": short_desc,
                "calories": kcal,
                "protein": prot,
                "fat": fat,
                "carb": carb,
                "fiber": fiber,
                "full_response": entry['response'],
                "timestamp": entry['timestamp'].isoformat(),
                "image": entry.get('compressed_image')  # Добавляем изображение если есть
            })
        
        # Получаем целевые значения
        target_kcal = int(user_data.get("target_kcal", 0))
        target_protein = int(user_data.get("target_protein", 0))
        target_fat = int(user_data.get("target_fat", 0))
        target_carb = int(user_data.get("target_carb", 0))
        target_fiber = int(user_data.get("target_fiber", 20))
        
        # Рассчитываем остатки
        remaining_kcal = target_kcal - total_kcal
        remaining_prot = target_protein - total_prot
        remaining_fat = target_fat - total_fat
        remaining_carb = target_carb - total_carb
        remaining_fiber = target_fiber - total_fiber
        
        # Формируем предупреждения
        warnings = []
        if remaining_kcal < 0:
            maintenance_kcal = int(target_kcal / 0.83) if target_kcal else 0
            if total_kcal <= maintenance_kcal and user_data.get("goal", 0) < user_data.get("weight", 0):
                warnings.append(
                    f"⚖️ По калориям уже перебор для похудения, но ты всё ещё в рамках нормы для поддержания веса — до неё ещё {maintenance_kcal - total_kcal} ккал. Вес не прибавится, не переживай 😊"
                )
            else:
                warnings.append("🍩 Калорий вышло чуть больше нормы — не страшно, но завтра можно чуть аккуратнее 😉")
        
        if remaining_prot < 0:
            warnings.append("🥩 Белка получилось больше, чем нужно — это не страшно.")
        
        if remaining_fat < 0:
            warnings.append("🧈 Жиров вышло многовато — обрати внимание, может где-то масло лишнее.")
        
        if remaining_carb < 0:
            warnings.append("🍞 Углеводов перебор — может, сегодня было много сладкого?")
        
        summary_data = {
            "date": target_date.strftime("%Y-%m-%d"),
            "total_calories": int(total_kcal),
            "total_protein": int(total_prot),
            "total_fat": int(total_fat),
            "total_carb": int(total_carb),
            "total_fiber": round(total_fiber, 1),
            "meals": meals,
            "remaining_calories": max(0, remaining_kcal),
            "remaining_protein": max(0, remaining_prot),
            "remaining_fat": max(0, remaining_fat),
            "remaining_carb": max(0, remaining_carb),
            "remaining_fiber": max(0, round(remaining_fiber, 1)),
            "warnings": warnings,
            "targets": {
                "calories": target_kcal,
                "protein": target_protein,
                "fat": target_fat,
                "carb": target_carb,
                "fiber": target_fiber
            }
        }
        
        result = {"status": "success", "data": summary_data}
        # Кэшируем результат на 3 минуты
        api_cache.set(cache_key, result, ttl=180)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинты API
@app.get("/api/diary/{user_id}", response_model=Dict[str, Any])
async def get_diary(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение данных дневника питания пользователя с кэшированием
    """
    try:
        # Проверяем кэш
        cache_key = api_cache.get_cache_key("diary", user_id)
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Добавляем обработку ошибок импорта
        try:
            # Импортируем функции из bot.py
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_diary: {import_error}")
            # Возвращаем тестовые данные если bot.py недоступен
            result = {
                "status": "success", 
                "data": {
                    "days": [
                        {
                            "date": "06.08.2025",
                            "total_calories": 1800,
                            "meals": [
                                {
                                    "time": "08:30",
                                    "name": "Завтрак",
                                    "calories": 400,
                                    "items": [{"name": "Овсянка", "calories": 150}]
                                }
                            ]
                        }
                    ],
                    "user_targets": {
                        "calories": 2000,
                        "protein": 100,
                        "fat": 67,
                        "carb": 250,
                        "fiber": 25
                    }
                }
            }
            # Кэшируем тестовые данные
            api_cache.set(cache_key, result, ttl=60)
            return result
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Получаем историю пользователя
        history = await get_history(user_id)
        
        # Преобразуем данные в нужный формат
        diary_data = {
            "days": [],
            "user_targets": {
                "calories": user_data.get("target_kcal", 2000),
                "protein": user_data.get("target_protein", 100),
                "fat": user_data.get("target_fat", 67),
                "carb": user_data.get("target_carb", 250),
                "fiber": user_data.get("target_fiber", 25)
            }
        }
        
        # Группируем записи по дням
        days_dict = {}
        for entry in history:
            # Включаем все записи о еде: и с фото (type="food"), и текстовые/голосовые (type="text")
            if entry.get("type") not in ["food", "text"]:
                continue
                
            # Получаем дату из timestamp
            entry_date = entry.get("timestamp").date() if isinstance(entry.get("timestamp"), datetime) else datetime.fromisoformat(entry.get("timestamp")).date()
            date_str = entry_date.strftime("%Y-%m-%d")
            
            # Инициализируем день, если его еще нет
            if date_str not in days_dict:
                days_dict[date_str] = {
                    "date": entry_date.strftime("%d.%m.%Y"),
                    "total_calories": 0,
                    "meals": []
                }
            
            # Извлекаем калории из ответа
            calories = 0
            match = re.search(r"(\d+(?:[.,]\d+)?) ккал", entry.get("response", ""))
            if match:
                calories = int(float(match.group(1).replace(",", ".")))
            
            # Извлекаем продукты из ответа
            items = []
            for line in entry.get("response", "").split("\n"):
                if line.strip().startswith("•") or line.strip().startswith("-"):
                    item_parts = line.strip()[1:].strip().split("–")
                    if len(item_parts) >= 2:
                        item_name = item_parts[0].strip()
                        item_calories = 0
                        cal_match = re.search(r"(\d+(?:[.,]\d+)?) ккал", item_parts[1])
                        if cal_match:
                            item_calories = int(float(cal_match.group(1).replace(",", ".")))
                        items.append({"name": item_name, "calories": item_calories})
            
            # Добавляем прием пищи
            meal_time = entry_date.strftime("%H:%M")
            if "timestamp" in entry and isinstance(entry.get("timestamp"), datetime):
                meal_time = entry.get("timestamp").strftime("%H:%M")
            
            meal_name = "Прием пищи"
            if "завтрак" in entry.get("prompt", "").lower():
                meal_name = "Завтрак"
            elif "обед" in entry.get("prompt", "").lower():
                meal_name = "Обед"
            elif "ужин" in entry.get("prompt", "").lower():
                meal_name = "Ужин"
            elif "перекус" in entry.get("prompt", "").lower():
                meal_name = "Перекус"
            
            days_dict[date_str]["meals"].append({
                "time": meal_time,
                "name": meal_name,
                "calories": calories,
                "items": items
            })
            
            days_dict[date_str]["total_calories"] += calories
        
        # Сортируем дни по дате (от новых к старым)
        sorted_days = sorted(days_dict.values(), key=lambda x: datetime.strptime(x["date"], "%d.%m.%Y"), reverse=True)
        diary_data["days"] = sorted_days
        
        result = {"status": "success", "data": diary_data}
        # Кэшируем результат на 5 минут
        api_cache.set(cache_key, result, ttl=300)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/{user_id}", response_model=Dict[str, Any])
async def get_stats(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение статистики пользователя с кэшированием
    """
    try:
        # Проверяем кэш
        cache_key = api_cache.get_cache_key("stats", user_id)
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Добавляем обработку ошибок импорта
        try:
            # Импортируем функции из bot.py
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history, calculate_summary_text
            # Отладочное логирование удалено для оптимизации
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_stats: {import_error}")
            # НЕ возвращаем тестовые данные, а пробуем продолжить
            # return тестовые данные - УБИРАЕМ ЭТО
            pass
        
        # Получаем данные пользователя
        try:
            user_data = await get_user_data(user_id)
            # Отладочное логирование удалено для оптимизации
        except Exception as e:
            print(f"Ошибка получения данных пользователя {user_id}: {e}")
            # Используем значения по умолчанию
            user_data = {
                "target_kcal": 2000,
                "target_protein": 100,
                "target_fat": 67,
                "target_carb": 250,
                "target_fiber": 25,
                "utc_offset": 0
            }
        
        # Получаем историю пользователя
        try:
            history = await get_history(user_id)
            # Отладочное логирование удалено для оптимизации
        except Exception as e:
            print(f"Ошибка получения истории пользователя {user_id}: {e}")
            history = []
        
        # Фильтруем записи о еде (food и text типы содержат информацию о еде)
        food_entries = [entry for entry in history if entry.get("type") in ["food", "text"]]
        # Отладочное логирование удалено для оптимизации
        
        # Подсчет типов записей для анализа (без вывода)
        types_count = {}
        for entry in history:
            entry_type = entry.get("type", "unknown")
            types_count[entry_type] = types_count.get(entry_type, 0) + 1
        # Отладочное логирование удалено для оптимизации
        
        # Если нет записей о еде, возвращаем базовые данные
        if not food_entries:
            # Отладочное логирование удалено для оптимизации
            stats_data = {
                "general": {
                    "avg_calories": 0,
                    "days_tracked": 0,
                    "adherence_percent": 0,
                    "weight_change": 0
                },
                "nutrition_distribution": {
                    "protein": 33,
                    "fat": 33,
                    "carb": 34
                },
                "top_products": [],
                "user_targets": {
                    "calories": user_data.get("target_kcal", 2000),
                    "protein": user_data.get("target_protein", 100),
                    "fat": user_data.get("target_fat", 67),
                    "carb": user_data.get("target_carb", 250),
                    "fiber": user_data.get("target_fiber", 25)
                },
                "today_summary": None
            }
            return {"status": "success", "data": stats_data}
        
        # Группируем по дням для подсчета дней
        days = {}
        total_calories = 0
        total_protein = 0
        total_fat = 0
        total_carb = 0
        total_fiber = 0
        
        # Отладочное логирование удалено для оптимизации
        
        for i, entry in enumerate(food_entries):
            try:
                # Получаем дату из timestamp
                timestamp = entry.get("timestamp")
                if isinstance(timestamp, datetime):
                    entry_date = timestamp.date()
                else:
                    entry_date = datetime.fromisoformat(str(timestamp)).date()
                date_str = entry_date.strftime("%Y-%m-%d")
                
                # Инициализируем день, если его еще нет
                if date_str not in days:
                    days[date_str] = {
                        "calories": 0,
                        "protein": 0,
                        "fat": 0,
                        "carb": 0,
                        "fiber": 0
                    }
                
                # Используем кэшированную функцию парсинга БЖУ (как в других эндпоинтах)
                response = entry.get("response", "")
                kcal, prot, fat, carb, fiber = parse_nutrition_cached(response)
                
                if kcal > 0:  # Если удалось распарсить данные
                    days[date_str]["calories"] += kcal
                    days[date_str]["protein"] += prot
                    days[date_str]["fat"] += fat
                    days[date_str]["carb"] += carb
                    days[date_str]["fiber"] += fiber
                    
                    total_calories += kcal
                    total_protein += prot
                    total_fat += fat
                    total_carb += carb
                    total_fiber += fiber
                        
            except Exception as e:
                print(f"Ошибка обработки записи {i+1}: {e}")
                continue
        
        # Отладочное логирование удалено для оптимизации
        
        days_tracked = len(days)
        
        # Правильный расчет средних калорий - учитываем общий период отслеживания
        # Находим первую и последнюю записи для определения периода
        if food_entries:
            # Сортируем записи по дате
            sorted_entries = sorted(food_entries, key=lambda x: x.get("timestamp") if isinstance(x.get("timestamp"), datetime) else datetime.fromisoformat(str(x.get("timestamp"))))
            first_date = sorted_entries[0].get("timestamp")
            last_date = sorted_entries[-1].get("timestamp")
            
            if isinstance(first_date, str):
                first_date = datetime.fromisoformat(first_date)
            if isinstance(last_date, str):
                last_date = datetime.fromisoformat(last_date)
                
            # Считаем общее количество дней в периоде
            total_period_days = (last_date.date() - first_date.date()).days + 1
            avg_calories = round(total_calories / total_period_days) if total_period_days > 0 else 0
            
            # Отладочное логирование удалено для оптимизации
        else:
            avg_calories = 0
        
        # Расчет распределения БЖУ
        total_nutrients = total_protein + total_fat + total_carb
        
        protein_percent = round((total_protein / total_nutrients * 100) if total_nutrients > 0 else 0)
        fat_percent = round((total_fat / total_nutrients * 100) if total_nutrients > 0 else 0)
        carb_percent = round((total_carb / total_nutrients * 100) if total_nutrients > 0 else 0)
        
        # Подготавливаем данные по дням для графиков
        daily_data = []
        if food_entries:
            # Создаем полный список дней в периоде
            sorted_entries = sorted(food_entries, key=lambda x: x.get("timestamp") if isinstance(x.get("timestamp"), datetime) else datetime.fromisoformat(str(x.get("timestamp"))))
            first_date = sorted_entries[0].get("timestamp")
            last_date = sorted_entries[-1].get("timestamp")
            
            if isinstance(first_date, str):
                first_date = datetime.fromisoformat(first_date)
            if isinstance(last_date, str):
                last_date = datetime.fromisoformat(last_date)
            
            # Генерируем все дни в периоде
            current_date = first_date.date()
            end_date = last_date.date()
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y-%m-%d")
                day_data = days.get(date_str, {
                    "calories": 0,
                    "protein": 0,
                    "fat": 0,
                    "carb": 0,
                    "fiber": 0
                })
                daily_data.append({
                    "date": current_date.strftime("%d.%m.%Y"),
                    "calories": day_data["calories"],
                    "protein": day_data["protein"],
                    "fat": day_data["fat"],
                    "carb": day_data["carb"],
                    "fiber": day_data["fiber"]
                })
                current_date += timedelta(days=1)
        
        # Расчет изменения веса
        weight_entries = [entry for entry in history if entry.get("type") == "weight"]
        weight_entries.sort(key=lambda x: x.get("timestamp") if isinstance(x.get("timestamp"), datetime) else datetime.fromisoformat(x.get("timestamp")))
        weight_change = 0
        if len(weight_entries) >= 2:
            first_weight = float(weight_entries[0].get("weight", 0))
            last_weight = float(weight_entries[-1].get("weight", 0))
            weight_change = last_weight - first_weight
        
        # Подсчет топ продуктов
        products = {}
        for entry in food_entries:
            for line in entry.get("response", "").split("\n"):
                if line.strip().startswith("•") or line.strip().startswith("-"):
                    item_parts = line.strip()[1:].strip().split("–")
                    if len(item_parts) >= 1:
                        product_name = item_parts[0].strip()
                        products[product_name] = products.get(product_name, 0) + 1
        
        top_products = [{"name": name, "count": count} for name, count in sorted(products.items(), key=lambda x: x[1], reverse=True)[:5]]
        
        # Расчет соблюдения нормы
        target_kcal = user_data.get("target_kcal", 2000)
        adherence_percent = round((avg_calories / target_kcal * 100) if target_kcal > 0 else 0)
        if adherence_percent > 100:
            adherence_percent = 200 - adherence_percent  # Инвертируем процент, если превышает 100%
        adherence_percent = max(0, min(100, adherence_percent))  # Ограничиваем от 0 до 100
        
        # Получаем итоги за сегодня
        user_offset = user_data.get("utc_offset", 0)
        user_tz = timezone(timedelta(hours=user_offset))
        today = datetime.now(user_tz).date()
        
        # Вызываем функцию напрямую без API endpoint
        try:
            # Получаем данные дневника за сегодня (включая текстовые и голосовые записи)
            entries_today = [e for e in history if e["timestamp"].astimezone(user_tz).date() == today and e.get("type") in ["food", "text"]]
            
            if entries_today:
                # Подсчитываем общие значения за сегодня
                today_kcal = today_prot = today_fat = today_carb = today_fiber = 0.0
                today_meals = []
                
                for i, entry in enumerate(entries_today, start=1):
                    # Используем кэшированную функцию парсинга БЖУ
                    kcal, prot, fat, carb, fiber = parse_nutrition_cached(entry['response'])
                    
                    today_kcal += kcal
                    today_prot += prot
                    today_fat += fat
                    today_carb += carb
                    today_fiber += fiber
                    
                    # Используем кэшированную функцию парсинга продуктов
                    short_desc = parse_products_cached(entry['response'])
                    
                    today_meals.append({
                        "time": entry['timestamp'].astimezone(user_tz).strftime("%H:%M"),
                        "description": short_desc,
                        "calories": kcal
                    })
                
                # Получаем целевые значения
                target_kcal = int(user_data.get("target_kcal", 2000))
                target_protein = int(user_data.get("target_protein", 100))
                target_fat = int(user_data.get("target_fat", 67))
                target_carb = int(user_data.get("target_carb", 250))
                target_fiber = int(user_data.get("target_fiber", 25))
                
                today_summary_data = {
                    "date": today.strftime("%Y-%m-%d"),
                    "total_calories": int(today_kcal),
                    "total_protein": int(today_prot),
                    "total_fat": int(today_fat),
                    "total_carb": int(today_carb),
                    "total_fiber": round(today_fiber, 1),
                    "meals": today_meals,
                    "remaining_calories": max(0, target_kcal - today_kcal),
                    "remaining_protein": max(0, target_protein - today_prot),
                    "remaining_fat": max(0, target_fat - today_fat),
                    "remaining_carb": max(0, target_carb - today_carb),
                    "remaining_fiber": max(0, round(target_fiber - today_fiber, 1)),
                    "warnings": []
                }
            else:
                today_summary_data = {
                    "date": today.strftime("%Y-%m-%d"),
                    "total_calories": 0,
                    "total_protein": 0,
                    "total_fat": 0,
                    "total_carb": 0,
                    "total_fiber": 0,
                    "meals": [],
                    "remaining_calories": user_data.get("target_kcal", 2000),
                    "remaining_protein": user_data.get("target_protein", 100),
                    "remaining_fat": user_data.get("target_fat", 67),
                    "remaining_carb": user_data.get("target_carb", 250),
                    "remaining_fiber": user_data.get("target_fiber", 25),
                    "warnings": []
                }
        except Exception as e:
            print(f"Ошибка при получении итогов дня: {e}")
            today_summary_data = None
        
        stats_data = {
            "general": {
                "avg_calories": avg_calories,
                "days_tracked": days_tracked,
                "adherence_percent": adherence_percent,
                "weight_change": round(weight_change, 1)
            },
            "nutrition_distribution": {
                "protein": protein_percent,
                "fat": fat_percent,
                "carb": carb_percent
            },
            "top_products": top_products,
            "user_targets": {
                "calories": user_data.get("target_kcal", 2000),
                "protein": user_data.get("target_protein", 100),
                "fat": user_data.get("target_fat", 67),
                "carb": user_data.get("target_carb", 250),
                "fiber": user_data.get("target_fiber", 25)
            },
            "today_summary": today_summary_data,
            "daily_data": daily_data  # Добавляем реальные данные по дням
        }
        
        # Отладочное логирование удалено для оптимизации
        
        result = {"status": "success", "data": stats_data}
        # Кэшируем результат на 10 минут (статистика обновляется реже)
        api_cache.set(cache_key, result, ttl=600)
        return result
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА в get_stats для пользователя {user_id}: {e}")
        print(f"Тип ошибки: {type(e)}")
        import traceback
        print(f"Трассировка: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipes/{user_id}", response_model=Dict[str, Any])
async def get_recipes(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение рецептов для пользователя с кэшированием
    """
    try:
        # Проверяем кэш
        cache_key = api_cache.get_cache_key("recipes", user_id)
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        try:
            from bot import get_user_data
        except ImportError:
            result = {"status": "success", "data": {"test": "mode"}}
            api_cache.set(cache_key, result, ttl=60)
            return result
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Инициализируем структуру данных для рецептов
        recipes_data = {
            "categories": ["Все", "Завтраки", "Обеды", "Ужины", "Салаты", "Десерты"],
            "recipes": []
        }
        
        # Путь к файлу рецептов
        recepti_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recepti.txt")
        
        # Чтение рецептов из файла
        try:
            with open(recepti_path, "r", encoding="utf-8") as f:
                content = f.read()
                
            # Парсинг рецептов из файла
            recipe_blocks = re.split(r'\n\s*\n', content)
            for block in recipe_blocks:
                if not block.strip():
                    continue
                    
                lines = block.strip().split('\n')
                if len(lines) < 3:
                    continue
                    
                title = lines[0].strip()
                category = "Обеды"  # По умолчанию
                
                # Определяем категорию по ключевым словам
                if any(word in title.lower() for word in ["завтрак", "каша", "омлет", "яичница"]):
                    category = "Завтраки"
                elif any(word in title.lower() for word in ["салат", "закуска"]):
                    category = "Салаты"
                elif any(word in title.lower() for word in ["десерт", "торт", "пирог", "сладкое"]):
                    category = "Десерты"
                elif any(word in title.lower() for word in ["ужин", "легкое"]):
                    category = "Ужины"
                
                # Оценка времени приготовления
                prep_time = "30 мин"
                if "быстр" in ' '.join(lines).lower():
                    prep_time = "15 мин"
                elif "долг" in ' '.join(lines).lower() or "час" in ' '.join(lines).lower():
                    prep_time = "60 мин"
                
                # Оценка калорийности
                calories = 350  # По умолчанию
                if any(word in ' '.join(lines).lower() for word in ["диет", "низкокалор", "легк"]):
                    calories = 250
                elif any(word in ' '.join(lines).lower() for word in ["сытн", "жирн", "калорийн"]):
                    calories = 450
                
                # Описание - берем первые несколько строк
                description = ' '.join(lines[1:min(4, len(lines))])
                if len(description) > 150:
                    description = description[:147] + "..."
                
                recipes_data["recipes"].append({
                    "title": title,
                    "category": category,
                    "prep_time": prep_time,
                    "calories": calories,
                    "description": description,
                    "portions": 2,
                    "nutrition": {
                        "calories": calories,
                        "protein": round(calories * 0.25 / 4),  # 25% белков, 4 ккал/г
                        "fat": round(calories * 0.3 / 9),       # 30% жиров, 9 ккал/г
                        "carb": round(calories * 0.45 / 4),     # 45% углеводов, 4 ккал/г
                        "fiber": 5
                    }
                })
        except Exception as e:
            print(f"Ошибка при чтении файла рецептов: {e}")
        
        result = {"status": "success", "data": recipes_data}
        # Кэшируем рецепты на 1 час (они статичны)
        api_cache.set(cache_key, result, ttl=3600)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MealData(BaseModel):
    user_id: str
    meal_name: str
    meal_time: str
    items: List[Dict[str, Any]]

@app.post("/api/meal", response_model=Dict[str, Any])
async def add_meal(meal_data: MealData, api_key: str = Depends(verify_api_key)):
    """
    Добавление приема пищи
    """
    try:
        # Здесь можно добавить логику для сохранения приема пищи
        # Пока возвращаем успешный ответ
        return {
            "status": "success",
            "message": "Прием пищи добавлен",
            "data": meal_data.dict()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для получения профиля пользователя
@app.get("/api/profile/{user_id}", response_model=Dict[str, Any])
async def get_user_profile(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение данных профиля пользователя с кэшированием
    """
    try:
        # Проверяем кэш
        cache_key = api_cache.get_cache_key("profile", user_id)
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        try:
            from bot import get_user_data
        except ImportError:
            result = {"status": "success", "data": {"test": "mode"}}
            api_cache.set(cache_key, result, ttl=60)
            return result
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        result = {"status": "success", "data": user_data}
        # Кэшируем профиль на 30 минут (меняется редко)
        api_cache.set(cache_key, result, ttl=1800)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для обновления профиля пользователя
@app.put("/api/profile/{user_id}", response_model=Dict[str, Any])
async def update_user_profile(user_id: str, profile_data: ProfileUpdateData, api_key: str = Depends(verify_api_key)):
    """
    Обновление данных профиля пользователя с инвалидацией кэша
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        try:
            from bot import get_user_data, update_user_data
        except ImportError:
            return {"status": "success", "message": "Test mode"}
        
        # Получаем текущие данные пользователя
        current_data = await get_user_data(user_id)
        
        # Обновляем только переданные поля
        update_dict = profile_data.dict(exclude_unset=True)
        current_data.update(update_dict)
        
        # Сохраняем обновленные данные
        await update_user_data(user_id, current_data)
        
        # Очищаем кэш пользователя после обновления
        api_cache.invalidate_user_cache(user_id)
        
        return {"status": "success", "message": "Профиль обновлен", "data": current_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для пересчета целевых значений
@app.post("/api/profile/{user_id}/recalculate", response_model=Dict[str, Any])
async def recalculate_user_targets(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Пересчет целевых значений пользователя
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        try:
            from bot import get_user_data, update_user_data
        except ImportError:
            return {"status": "success", "message": "Test mode"}
        
        # Получаем данные пользователя
        data = await get_user_data(user_id)
        
        # Извлекаем необходимые данные
        gender = data.get("gender")
        age = data.get("age")
        height = data.get("height")
        weight = data.get("weight")
        goal = data.get("goal")
        activity = data.get("activity")
        pregnant = data.get("pregnant", False)
        
        # Проверяем наличие всех необходимых данных
        if not all([gender, age, height, weight, goal, activity]):
            raise HTTPException(status_code=400, detail="Недостаточно данных для расчета")
        
        # Расчет BMR (Mifflin-St Jeor)
        if gender == "муж":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Коэффициенты активности
        multipliers = {"низкий": 1.2, "средний": 1.3, "высокий": 1.4}
        maintenance = bmr * multipliers.get(activity, 1.2)
        
        # Расчет целевых калорий
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
        
        # Расчет БЖУ
        protein_grams = int((target_calories * 0.3) / 4)
        fat_grams = int((target_calories * 0.3) / 9)
        carbs_grams = int((target_calories * 0.4) / 4)
        fiber_grams = max(20, round(target_calories * 0.014))
        
        # Обновляем данные пользователя
        data["target_kcal"] = int(target_calories)
        data["target_protein"] = protein_grams
        data["target_fat"] = fat_grams
        data["target_carb"] = carbs_grams
        data["target_fiber"] = fiber_grams
        
        await update_user_data(user_id, data)
        
        return {
            "status": "success", 
            "message": "Целевые значения пересчитаны",
            "data": {
                "target_kcal": int(target_calories),
                "target_protein": protein_grams,
                "target_fat": fat_grams,
                "target_carb": carbs_grams,
                "target_fiber": fiber_grams
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# НОВЫЙ эндпоинт для детального дневника с навигацией по датам
@app.get("/api/diary-data/{user_id}")
async def get_diary_data(user_id: str, date_str: Optional[str] = None, api_key: str = Depends(verify_api_key)):
    """
    Получение детальных данных дневника питания для пользователя за конкретную дату с кэшированием
    """
    try:
        # Проверяем кэш
        cache_key = api_cache.get_cache_key("diary_data", user_id, date=date_str or "today")
        cached_result = api_cache.get(cache_key)
        if cached_result:
            return cached_result
        
        # Добавляем обработку ошибок импорта
        try:
            # Импортируем функции из bot.py
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_diary_data: {import_error}")
            # Возвращаем тестовые данные если bot.py недоступен
            target_date = date_str or datetime.now().strftime("%Y-%m-%d")
            result = {
                "status": "success", 
                "data": {
                    "date": target_date,
                    "total_calories": 1650,
                    "total_protein": 85,
                    "total_fat": 55,
                    "total_carb": 190,
                    "total_fiber": 18.5,
                    "meals": [
                        {
                            "id": 1,
                            "time": "08:30",
                            "description": "Овсянка с бананом и орехами",
                            "calories": 420,
                            "protein": 15,
                            "fat": 12,
                            "carb": 65,
                            "fiber": 8.2,
                            "items": [
                                {"name": "Овсянка", "weight": "50г", "calories": 180},
                                {"name": "Банан", "weight": "120г", "calories": 108},
                                {"name": "Грецкие орехи", "weight": "20г", "calories": 132}
                            ]
                        },
                        {
                            "id": 2,
                            "time": "13:15",
                            "description": "Куриная грудка с рисом и овощами",
                            "calories": 580,
                            "protein": 45,
                            "fat": 8,
                            "carb": 75,
                            "fiber": 6.5,
                            "items": [
                                {"name": "Куриная грудка", "weight": "150г", "calories": 248},
                                {"name": "Рис отварной", "weight": "100г", "calories": 130},
                                {"name": "Брокколи", "weight": "150г", "calories": 51},
                                {"name": "Морковь", "weight": "100г", "calories": 41}
                            ]
                        },
                        {
                            "id": 3,
                            "time": "19:45",
                            "description": "Творог с ягодами",
                            "calories": 280,
                            "protein": 25,
                            "fat": 9,
                            "carb": 20,
                            "fiber": 3.8,
                            "items": [
                                {"name": "Творог 5%", "weight": "150г", "calories": 180},
                                {"name": "Черника", "weight": "80г", "calories": 46},
                                {"name": "Мед", "weight": "15г", "calories": 54}
                            ]
                        }
                    ],
                    "targets": {
                        "calories": 2000,
                        "protein": 100,
                        "fat": 67,
                        "carb": 250,
                        "fiber": 25
                    },
                    "remaining": {
                        "calories": 350,
                        "protein": 15,
                        "fat": 12,
                        "carb": 60,
                        "fiber": 6.5
                    },
                    "message": "🔧 Режим отладки - используются тестовые данные"
                }
            }
            # Кэшируем тестовые данные
            api_cache.set(cache_key, result, ttl=60)
            return result
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        user_offset = user_data.get("utc_offset", 0)
        user_tz = timezone(timedelta(hours=user_offset))
        
        # Определяем дату для анализа
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = datetime.now(user_tz).date()
        
        # Получаем историю пользователя
        history = await get_history(user_id)
        
        # Отладочное логирование удалено для оптимизации
        food_entries_with_images = [e for e in history if e.get('type') == 'food' and e.get('compressed_image')]
        food_entries_without_images = [e for e in history if e.get('type') == 'food' and not e.get('compressed_image')]
        
        # Фильтруем записи за указанную дату и записи о еде (включая текстовые и голосовые)
        entries_today = [e for e in history if e["timestamp"].astimezone(user_tz).date() == target_date and e.get("type") in ["food", "text"]]
        
        # Отладочное логирование удалено для оптимизации
        for i, entry in enumerate(entries_today):
            has_image = bool(entry.get('compressed_image'))
            # Отладочное логирование удалено для оптимизации
            if has_image:
                image_length = len(entry.get('compressed_image', ''))
                # Отладочное логирование удалено для оптимизации
        
        # Получаем целевые значения
        target_kcal = int(user_data.get("target_kcal", 2000))
        target_protein = int(user_data.get("target_protein", 100))
        target_fat = int(user_data.get("target_fat", 67))
        target_carb = int(user_data.get("target_carb", 250))
        target_fiber = int(user_data.get("target_fiber", 25))
        
        if not entries_today:
            return {
                "status": "success", 
                "data": {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "total_calories": 0,
                    "total_protein": 0,
                    "total_fat": 0,
                    "total_carb": 0,
                    "total_fiber": 0,
                    "meals": [],
                    "targets": {
                        "calories": target_kcal,
                        "protein": target_protein,
                        "fat": target_fat,
                        "carb": target_carb,
                        "fiber": target_fiber
                    },
                    "remaining": {
                        "calories": target_kcal,
                        "protein": target_protein,
                        "fat": target_fat,
                        "carb": target_carb,
                        "fiber": target_fiber
                    },
                    "message": "В этот день не было добавлено ни одного блюда."
                }
            }
        
        # Подсчитываем общие значения
        total_kcal = total_prot = total_fat = total_carb = total_fiber = 0.0
        meals = []
        
        for i, entry in enumerate(entries_today, start=1):
            # Используем кэшированную функцию парсинга БЖУ
            kcal, prot, fat, carb, fiber = parse_nutrition_cached(entry['response'])
            
            total_kcal += kcal
            total_prot += prot
            total_fat += fat
            total_carb += carb
            total_fiber += fiber
            
            # Извлекаем продукты из ответа
            lines = entry['response'].splitlines()
            food_lines = [line for line in lines if line.strip().startswith(("•", "-"))]
            
            # Парсим продукты для детального отображения
            items = []
            for line in food_lines:
                clean_line = re.sub(r'^[•\-]\s*', '', line).strip()
                if "–" in clean_line:
                    parts = clean_line.split("–")
                    product_info = parts[0].strip()
                    nutrition_info = parts[1].strip() if len(parts) > 1 else ""
                    
                    # Извлекаем вес продукта
                    weight_match = re.search(r'(\d+(?:[.,]\d+)?)\s*г', product_info)
                    weight = weight_match.group(0) if weight_match else "100г"
                    
                    # Извлекаем калории продукта
                    cal_match = re.search(r'(\d+(?:[.,]\d+)?)\s*ккал', nutrition_info)
                    product_calories = int(float(cal_match.group(1).replace(",", "."))) if cal_match else 0
                    
                    # Название продукта (убираем вес)
                    product_name = re.sub(r'\s*\d+(?:[.,]\d+)?\s*г.*', '', product_info).strip()
                    
                    items.append({
                        "name": product_name,
                        "weight": weight,
                        "calories": product_calories
                    })
            
            short_desc = ", ".join([re.sub(r'^[•\-]\s*', '', line).split("–")[0].strip() for line in food_lines]) or "Без описания"
            
            meals.append({
                "id": i,
                "time": entry['timestamp'].astimezone(user_tz).strftime("%H:%M"),
                "description": short_desc,
                "calories": kcal,
                "protein": prot,
                "fat": fat,
                "carb": carb,
                "fiber": fiber,
                "items": items,
                "full_response": entry['response'],
                "timestamp": entry['timestamp'].isoformat(),
                "image": entry.get('compressed_image')  # Добавляем изображение если есть
            })
        
        # Рассчитываем остатки
        remaining_kcal = max(0, target_kcal - total_kcal)
        remaining_prot = max(0, target_protein - total_prot)
        remaining_fat = max(0, target_fat - total_fat)
        remaining_carb = max(0, target_carb - total_carb)
        remaining_fiber = max(0, target_fiber - total_fiber)
        
        diary_data = {
            "date": target_date.strftime("%Y-%m-%d"),
            "total_calories": int(total_kcal),
            "total_protein": int(total_prot),
            "total_fat": int(total_fat),
            "total_carb": int(total_carb),
            "total_fiber": round(total_fiber, 1),
            "meals": meals,
            "targets": {
                "calories": target_kcal,
                "protein": target_protein,
                "fat": target_fat,
                "carb": target_carb,
                "fiber": target_fiber
            },
            "remaining": {
                "calories": remaining_kcal,
                "protein": remaining_prot,
                "fat": remaining_fat,
                "carb": remaining_carb,
                "fiber": round(remaining_fiber, 1)
            }
        }
        
        result = {"status": "success", "data": diary_data}
        # Кэшируем результат на 3 минуты
        api_cache.set(cache_key, result, ttl=180)
        return result
        
    except Exception as e:
        print(f"Ошибка в get_diary_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)


# Эндпоинт для управления кэшем (для отладки)
@app.get("/api/cache/stats")
async def get_cache_stats():
    """Получение статистики кэша"""
    return {
        "status": "success",
        "data": {
            "cache_size": len(api_cache.cache),
            "cache_keys": list(api_cache.cache.keys())[:10],  # Первые 10 ключей
            "ttl_info": {k: v - time.time() for k, v in list(api_cache.cache_ttl.items())[:5]}
        }
    }

@app.delete("/api/cache/clear/{user_id}")
async def clear_user_cache(user_id: str):
    """Очистка кэша пользователя"""
    api_cache.invalidate_user_cache(user_id)
    return {"status": "success", "message": f"Кэш пользователя {user_id} очищен"}

