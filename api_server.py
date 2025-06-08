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

# Загрузка переменных окружения
load_dotenv()

app = FastAPI(title="Telegram Bot WebApp API", 
              description="API для интеграции WebApp с Telegram ботом трекера питания")

# Настройка CORS для доступа с Netlify
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://reliable-toffee-e14334.netlify.app"],  # Ваш домен на Netlify
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

# Модель для запроса итогов дня
class DailySummaryRequest(BaseModel):
    date: str  # Формат YYYY-MM-DD

# Функция для проверки API-ключа (в реальном приложении должна быть более надежной)
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != os.getenv("API_KEY", "test_api_key"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

# Корневой эндпоинт API
@app.get("/api")
async def api_root():
    return {"status": "success", "message": "API работает", "timestamp": datetime.now().isoformat()}

# Эндпоинт для проверки здоровья API
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Эндпоинты API
@app.get("/api/diary/{user_id}", response_model=Dict[str, Any])
async def get_diary(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение данных дневника питания пользователя
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import get_user_data, get_history
        
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
            if entry.get("type") != "food":
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
        
        return {"status": "success", "data": diary_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats/{user_id}", response_model=Dict[str, Any])
async def get_stats(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение статистики пользователя
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import get_user_data, get_history, calculate_summary_text
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Получаем историю пользователя
        history = await get_history(user_id)
        
        # Фильтруем записи о еде
        food_entries = [entry for entry in history if entry.get("type") == "food"]
        
        # Группируем по дням для подсчета дней
        days = {}
        total_calories = 0
        total_protein = 0
        total_fat = 0
        total_carb = 0
        
        for entry in food_entries:
            # Получаем дату из timestamp
            entry_date = entry.get("timestamp").date() if isinstance(entry.get("timestamp"), datetime) else datetime.fromisoformat(entry.get("timestamp")).date()
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
            
            # Извлекаем БЖУ из ответа
            match = re.search(r"(\d+(?:[.,]\d+)?) ккал, Белки: (\d+(?:[.,]\d+)?) г, Жиры: (\d+(?:[.,]\d+)?) г, Углеводы: (\d+(?:[.,]\d+)?) г", entry.get("response", ""))
            if match:
                kcal, prot, fat, carb = map(lambda x: float(x.replace(",", ".")), match.groups()[:4])
                days[date_str]["calories"] += kcal
                days[date_str]["protein"] += prot
                days[date_str]["fat"] += fat
                days[date_str]["carb"] += carb
                
                total_calories += kcal
                total_protein += prot
                total_fat += fat
                total_carb += carb
        
        days_tracked = len(days)
        avg_calories = round(total_calories / days_tracked) if days_tracked > 0 else 0
        
        # Расчет распределения БЖУ
        total_nutrients = total_protein + total_fat + total_carb
        
        protein_percent = round((total_protein / total_nutrients * 100) if total_nutrients > 0 else 0)
        fat_percent = round((total_fat / total_nutrients * 100) if total_nutrients > 0 else 0)
        carb_percent = round((total_carb / total_nutrients * 100) if total_nutrients > 0 else 0)
        
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
            }
        }
        
        return {"status": "success", "data": stats_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Новый эндпоинт для получения итогов дня
@app.post("/api/stats/{user_id}/daily-summary", response_model=Dict[str, Any])
async def get_daily_summary(user_id: str, request: DailySummaryRequest, api_key: str = Depends(verify_api_key)):
    """
    Получение итогов дня по указанной дате
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import calculate_summary_text
        
        # Получаем итоги дня
        summary_text = await calculate_summary_text(user_id, request.date)
        
        # Парсим результат
        calories = protein = fat = carb = fiber = 0
        
        # Извлекаем значения из текста
        match = re.search(r"📊 Итого: (\d+) ккал\nБелки: (\d+) г\nЖиры: (\d+) г\nУглеводы: (\d+) г\nКлетчатка: (\d+) г", summary_text)
        if match:
            calories, protein, fat, carb, fiber = map(int, match.groups())
        
        # Формируем ответ
        summary_data = {
            "date": request.date,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carb": carb,
            "fiber": fiber,
            "summary_text": summary_text
        }
        
        return {"status": "success", "data": summary_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipes/{user_id}", response_model=Dict[str, Any])
async def get_recipes(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение рецептов для пользователя
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import get_user_data
        
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
        
        return {"status": "success", "data": recipes_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Эндпоинты для профиля пользователя
@app.get("/api/profile/{user_id}", response_model=Dict[str, Any])
async def get_profile(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение данных профиля пользователя
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import get_user_data
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Формируем данные профиля
        profile_data = {
            "personal": {
                "gender": user_data.get("gender", "male"),
                "age": user_data.get("age", 30),
                "height": user_data.get("height", 170),
                "weight": user_data.get("weight", 70),
                "goal": user_data.get("goal", 0),
                "activity": user_data.get("activity", "medium")
            },
            "targets": {
                "calories": user_data.get("target_kcal", 2000),
                "protein": user_data.get("target_protein", 100),
                "fat": user_data.get("target_fat", 67),
                "carb": user_data.get("target_carb", 250),
                "fiber": user_data.get("target_fiber", 25)
            },
            "settings": {
                "utc_offset": user_data.get("utc_offset", 3),
                "morning_reminded": user_data.get("morning_reminded", False),
                "pregnant": user_data.get("pregnant", False)
            }
        }
        
        return {"status": "success", "data": profile_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profile/{user_id}", response_model=Dict[str, Any])
async def update_profile(user_id: str, profile_data: ProfileUpdateData, api_key: str = Depends(verify_api_key)):
    """
    Обновление данных профиля пользователя
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import get_user_data, update_user_data
        
        # Получаем текущие данные пользователя
        user_data = await get_user_data(user_id)
        
        # Обновляем только предоставленные поля
        for field, value in profile_data.dict(exclude_unset=True).items():
            if value is not None:
                user_data[field] = value
        
        # Сохраняем обновленные данные
        await update_user_data(user_id, user_data)
        
        return {"status": "success", "message": "Профиль успешно обновлен"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile/{user_id}/recalculate", response_model=Dict[str, Any])
async def recalculate_targets(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Пересчет целевых значений калорий и БЖУ
    """
    try:
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import get_user_data, update_user_data
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Получаем необходимые параметры
        gender = user_data.get("gender", "male")
        age = user_data.get("age", 30)
        height = user_data.get("height", 170)
        weight = user_data.get("weight", 70)
        activity = user_data.get("activity", "medium")
        goal = user_data.get("goal", 0)
        pregnant = user_data.get("pregnant", False)
        
        # Расчет базового метаболизма (BMR) по формуле Миффлина-Сан Жеора
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
            
        # Коэффициент активности
        activity_factors = {
            "low": 1.2,      # Малоподвижный образ жизни
            "medium": 1.55,  # Умеренная активность
            "high": 1.725    # Высокая активность
        }
        
        activity_factor = activity_factors.get(activity, 1.55)
        
        # Расчет суточной нормы калорий (TDEE)
        tdee = bmr * activity_factor
        
        # Корректировка для беременных
        if gender == "female" and pregnant:
            tdee += 300  # Дополнительные калории для беременных
        
        # Корректировка по цели
        if goal < 0:  # Похудение
            target_kcal = tdee + goal * 100  # Каждые 0.1 кг цели = -100 ккал
        elif goal > 0:  # Набор веса
            target_kcal = tdee + goal * 100  # Каждые 0.1 кг цели = +100 ккал
        else:  # Поддержание веса
            target_kcal = tdee
        
        # Минимальный порог калорий
        min_kcal = 1200 if gender == "female" else 1500
        target_kcal = max(min_kcal, round(target_kcal))
        
        # Расчет БЖУ
        # Белки: 1.6-2.2 г на кг веса
        target_protein = round(weight * 1.8)
        
        # Жиры: 20-35% от общей калорийности
        target_fat = round((target_kcal * 0.3) / 9)  # 30% калорий из жиров, 9 ккал/г
        
        # Углеводы: оставшиеся калории
        protein_calories = target_protein * 4  # 4 ккал/г
        fat_calories = target_fat * 9  # 9 ккал/г
        carb_calories = target_kcal - protein_calories - fat_calories
        target_carb = round(carb_calories / 4)  # 4 ккал/г
        
        # Клетчатка: 14г на 1000 ккал
        target_fiber = round(target_kcal * 14 / 1000)
        
        # Обновляем данные пользователя
        user_data["target_kcal"] = target_kcal
        user_data["target_protein"] = target_protein
        user_data["target_fat"] = target_fat
        user_data["target_carb"] = target_carb
        user_data["target_fiber"] = target_fiber
        
        # Сохраняем обновленные данные
        await update_user_data(user_id, user_data)
        
        # Формируем ответ
        targets_data = {
            "calories": target_kcal,
            "protein": target_protein,
            "fat": target_fat,
            "carb": target_carb,
            "fiber": target_fiber
        }
        
        return {"status": "success", "data": targets_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Запуск сервера
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
