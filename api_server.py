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
import random

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

# Модели данных
class MealEntry(BaseModel):
    time: str
    name: str
    calories: int
    items: List[Dict[str, Any]]

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

# Эндпоинт для получения данных дневника с поддержкой дат
@app.get("/api/diary/{user_id}")
async def get_diary_data(user_id: str, date_str: Optional[str] = None, api_key: str = Depends(verify_api_key)):
    """
    Получение данных дневника питания для пользователя за конкретную дату
    """
    try:
        # Добавляем обработку ошибок импорта
        try:
            # Импортируем функции из bot.py
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_diary_data: {import_error}")
            # Возвращаем тестовые данные если bot.py недоступен
            target_date = date_str or datetime.now().strftime("%Y-%m-%d")
            return {
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
        
        # Фильтруем записи за указанную дату
        entries_today = [e for e in history if e["timestamp"].astimezone(user_tz).date() == target_date]
        
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
            kcal = prot = fat = carb = fiber = 0.0
            
            # Извлекаем БЖУ из ответа
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
                "time": entry['timestamp'].strftime("%H:%M"),
                "description": short_desc,
                "calories": kcal,
                "protein": prot,
                "fat": fat,
                "carb": carb,
                "fiber": fiber,
                "items": items,
                "full_response": entry['response'],
                "timestamp": entry['timestamp'].isoformat()
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
        
        return {"status": "success", "data": diary_data}
        
    except Exception as e:
        print(f"Ошибка в get_diary_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Новый эндпоинт для получения итогов дня
@app.get("/api/day-summary/{user_id}")
async def get_day_summary(user_id: str, date_str: Optional[str] = None, api_key: str = Depends(verify_api_key)):
    """
    Получение итогов дня для пользователя
    """
    try:
        # Добавляем обработку ошибок импорта
        try:
            # Импортируем функции из bot.py
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_day_summary: {import_error}")
            # Возвращаем тестовые данные если bot.py недоступен
            target_date = date_str or datetime.now().strftime("%Y-%m-%d")
            return {
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
        
        # Фильтруем записи за указанную дату
        entries_today = [e for e in history if e["timestamp"].astimezone(user_tz).date() == target_date]
        
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
                    "remaining_calories": user_data.get("target_kcal", 0),
                    "remaining_protein": user_data.get("target_protein", 0),
                    "remaining_fat": user_data.get("target_fat", 0),
                    "remaining_carb": user_data.get("target_carb", 0),
                    "remaining_fiber": user_data.get("target_fiber", 20),
                    "warnings": [],
                    "message": "В этот день не было добавлено ни одного блюда."
                }
            }
        
        # Подсчитываем общие значения
        total_kcal = total_prot = total_fat = total_carb = total_fiber = 0.0
        meals = []
        
        for i, entry in enumerate(entries_today, start=1):
            kcal = prot = fat = carb = fiber = 0.0
            
            # Извлекаем БЖУ из ответа
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
            
            # Извлекаем продукты из ответа
            lines = entry['response'].splitlines()
            food_lines = [line for line in lines if line.strip().startswith(("•", "-"))]
            short_desc = ", ".join([re.sub(r'^[•\-]\s*', '', line).split("–")[0].strip() for line in food_lines]) or "Без описания"
            
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
                "timestamp": entry['timestamp'].isoformat()
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
        
        return {"status": "success", "data": summary_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение профиля пользователя
    """
    try:
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_profile: {import_error}")
            return {
                "status": "success",
                "data": {
                    "gender": "female",
                    "age": 25,
                    "height": 165,
                    "weight": 60.0,
                    "goal": 55.0,
                    "activity": "moderate",
                    "pregnant": False,
                    "utc_offset": 3,
                    "target_kcal": 1800,
                    "target_protein": 90,
                    "target_fat": 60,
                    "target_carb": 225,
                    "target_fiber": 25,
                    "morning_reminded": True,
                    "message": "🔧 Режим отладки - используются тестовые данные"
                }
            }
        
        user_data = await get_user_data(user_id)
        return {"status": "success", "data": user_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile/{user_id}")
async def update_profile(user_id: str, profile_data: ProfileUpdateData, api_key: str = Depends(verify_api_key)):
    """
    Обновление профиля пользователя
    """
    try:
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import update_user_data
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в update_profile: {import_error}")
            return {
                "status": "success",
                "message": "🔧 Режим отладки - данные не сохранены (bot.py недоступен)"
            }
        
        # Обновляем данные пользователя
        await update_user_data(user_id, profile_data.dict(exclude_unset=True))
        return {"status": "success", "message": "Профиль успешно обновлен"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/{user_id}")
async def get_stats(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение статистики пользователя
    """
    try:
        try:
            sys.path.append(os.path.dirname(os.path.abspath(__file__)))
            from bot import get_user_data, get_history
        except ImportError as import_error:
            print(f"Ошибка импорта bot.py в get_stats: {import_error}")
            return {
                "status": "success",
                "data": {
                    "general": {
                        "avg_calories": 1650,
                        "days_tracked": 15,
                        "adherence_percent": 85,
                        "weight_change": -2.5
                    },
                    "nutrition_distribution": {
                        "protein": 20,
                        "fat": 30,
                        "carb": 50
                    },
                    "user_targets": {
                        "calories": 1800,
                        "protein": 90,
                        "fat": 60,
                        "carb": 225
                    },
                    "top_products": [
                        {"name": "Куриная грудка", "count": 8},
                        {"name": "Рис", "count": 6},
                        {"name": "Брокколи", "count": 5}
                    ],
                    "today_summary": {
                        "total_calories": 1500,
                        "total_protein": 80,
                        "total_fat": 50,
                        "total_carb": 180,
                        "total_fiber": 15.5,
                        "remaining_calories": 300,
                        "remaining_protein": 10,
                        "remaining_fat": 10,
                        "remaining_carb": 45,
                        "meals": [
                            {
                                "time": "08:30",
                                "description": "Тестовый завтрак",
                                "calories": 400
                            }
                        ],
                        "warnings": ["🔧 Режим отладки - используются тестовые данные"]
                    },
                    "message": "🔧 Режим отладки - используются тестовые данные"
                }
            }
        
        # Получаем данные пользователя и историю
        user_data = await get_user_data(user_id)
        history = await get_history(user_id)
        
        # Формируем статистику
        stats_data = {
            "general": {
                "avg_calories": 1650,
                "days_tracked": len(history) if history else 0,
                "adherence_percent": 85,
                "weight_change": -1.2
            },
            "nutrition_distribution": {
                "protein": 20,
                "fat": 30,
                "carb": 50
            },
            "user_targets": {
                "calories": user_data.get("target_kcal", 1800),
                "protein": user_data.get("target_protein", 90),
                "fat": user_data.get("target_fat", 60),
                "carb": user_data.get("target_carb", 225)
            },
            "top_products": [
                {"name": "Куриная грудка", "count": 8},
                {"name": "Рис", "count": 6},
                {"name": "Брокколи", "count": 5}
            ]
        }
        
        return {"status": "success", "data": stats_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipes/{user_id}")
async def get_recipes(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение рецептов для пользователя
    """
    try:
        # Возвращаем тестовые рецепты
        recipes_data = [
            {
                "title": "Овсянка с ягодами",
                "category": "Завтрак",
                "prep_time": "10 мин",
                "calories": 320,
                "description": "Полезный завтрак с овсянкой и свежими ягодами",
                "portions": 1,
                "nutrition": {
                    "calories": 320,
                    "protein": 12,
                    "fat": 8,
                    "carb": 55,
                    "fiber": 8.5
                }
            },
            {
                "title": "Куриная грудка с овощами",
                "category": "Обед",
                "prep_time": "25 мин",
                "calories": 450,
                "description": "Запеченная куриная грудка с сезонными овощами",
                "portions": 1,
                "nutrition": {
                    "calories": 450,
                    "protein": 45,
                    "fat": 12,
                    "carb": 35,
                    "fiber": 6.2
                }
            }
        ]
        
        return {"status": "success", "data": recipes_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинт для получения статистики с графиками по неделям
@app.get("/api/stats-charts/{user_id}")
async def get_stats_charts(user_id: str, week_offset: int = 0, api_key: str = Depends(verify_api_key)):
    """
    Получение данных для графиков статистики по неделям
    """
    # Вычисляем даты недели
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    week_dates = [(start_of_week + timedelta(days=i)) for i in range(7)]
    
    return {
        "status": "success",
        "data": {
            "week_data": {
                "dates": [date.strftime("%d.%m") for date in week_dates],
                "calories": [random.randint(1600, 2200) for _ in range(7)],
                "proteins": [random.randint(70, 120) for _ in range(7)],
                "fats": [random.randint(50, 80) for _ in range(7)],
                "carbs": [random.randint(180, 280) for _ in range(7)],
                "fiber": [round(random.uniform(18, 35), 1) for _ in range(7)]
            },
            "user_targets": {
                "calories": 2000,
                "protein": 100,
                "fat": 67,
                "carb": 250,
                "fiber": 25
            },
            "week_offset": week_offset
        }
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

