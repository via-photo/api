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
    allow_origins=["*"],  # В продакшене заменить на конкретный домен Netlify
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

# Функция для проверки API-ключа (в реальном приложении должна быть более надежной)
async def verify_api_key(x_api_key: str = Header(None)):
    if not x_api_key or x_api_key != os.getenv("API_KEY", "test_api_key"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key

# Эндпоинты API

@app.get("/api/diary/{user_id}", response_model=Dict[str, Any])
async def get_diary(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение данных дневника питания пользователя
    """
    try:
        # Импортируем функции из bot.py
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
        # (здесь нужно адаптировать код под структуру ваших данных)
        
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
        from bot import get_user_data, get_history, calculate_summary_text
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Получаем историю пользователя
        history = await get_history(user_id)
        
        # Вычисляем статистику на основе истории
        # Здесь нужно адаптировать код под структуру ваших данных
        
        # Пример расчета средних калорий
        total_calories = 0
        days_tracked = 0
        food_entries = []
        
        for entry in history:
            if entry.get("type") == "food":
                total_calories += entry.get("calories", 0)
                food_entries.append(entry)
                
        # Группируем по дням для подсчета дней
        days = {}
        for entry in food_entries:
            date = entry.get("date", "").split(" ")[0]  # Получаем только дату
            if date:
                days[date] = True
                
        days_tracked = len(days)
        avg_calories = total_calories / days_tracked if days_tracked > 0 else 0
        
        # Расчет распределения БЖУ
        total_protein = sum(entry.get("protein", 0) for entry in food_entries)
        total_fat = sum(entry.get("fat", 0) for entry in food_entries)
        total_carb = sum(entry.get("carb", 0) for entry in food_entries)
        total_nutrients = total_protein + total_fat + total_carb
        
        protein_percent = round((total_protein / total_nutrients * 100) if total_nutrients > 0 else 0)
        fat_percent = round((total_fat / total_nutrients * 100) if total_nutrients > 0 else 0)
        carb_percent = round((total_carb / total_nutrients * 100) if total_nutrients > 0 else 0)
        
        # Расчет изменения веса
        weight_entries = [entry for entry in history if entry.get("type") == "weight"]
        weight_entries.sort(key=lambda x: x.get("date", ""))
        weight_change = 0
        if len(weight_entries) >= 2:
            first_weight = weight_entries[0].get("weight", 0)
            last_weight = weight_entries[-1].get("weight", 0)
            weight_change = last_weight - first_weight
        
        # Подсчет топ продуктов
        products = {}
        for entry in food_entries:
            for item in entry.get("items", []):
                product_name = item.get("name", "")
                if product_name:
                    products[product_name] = products.get(product_name, 0) + 1
        
        top_products = [{"name": name, "count": count} for name, count in sorted(products.items(), key=lambda x: x[1], reverse=True)[:5]]
        
        stats_data = {
            "general": {
                "avg_calories": round(avg_calories),
                "days_tracked": days_tracked,
                "adherence_percent": round((avg_calories / user_data.get("target_kcal", 2000) * 100) if user_data.get("target_kcal", 0) > 0 else 0),
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

@app.get("/api/recipes/{user_id}", response_model=Dict[str, Any])
async def get_recipes(user_id: str, api_key: str = Depends(verify_api_key)):
    """
    Получение рецептов для пользователя
    """
    try:
        # Импортируем функции из bot.py
        from bot import get_user_data, get_recipes_for_user
        
        # Получаем данные пользователя
        user_data = await get_user_data(user_id)
        
        # Если в вашем боте есть функция для получения рецептов, используйте её
        # recipes = await get_recipes_for_user(user_id)
        
        # Если такой функции нет, можно использовать статические данные из файла
        recipes_data = {
            "categories": ["Все", "Завтраки", "Обеды", "Ужины", "Салаты", "Десерты"],
            "recipes": []
        }
        
        # Чтение рецептов из файла
        try:
            with open("recepti.txt", "r", encoding="utf-8") as f:
                content = f.read()
                
            # Парсинг рецептов из файла
            # Адаптируйте этот код под формат вашего файла recepti.txt
            import re
            
            recipe_blocks = re.split(r'\n\s*\n', content)
            for block in recipe_blocks:
                if not block.strip():
                    continue
                    
                lines = block.strip().split('\n')
                if len(lines) < 3:
                    continue
                    
                title = lines[0].strip()
                category = "Обед"  # По умолчанию
                
                # Определяем категорию по ключевым словам
                if any(word in title.lower() for word in ["завтрак", "каша", "омлет", "яичница"]):
                    category = "Завтрак"
                elif any(word in title.lower() for word in ["салат", "закуска"]):
                    category = "Салат"
                elif any(word in title.lower() for word in ["десерт", "торт", "пирог", "сладкое"]):
                    category = "Десерт"
                elif any(word in title.lower() for word in ["ужин", "легкое"]):
                    category = "Ужин"
                
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
        # В реальном приложении здесь будет обращение к функциям из bot.py
        # для добавления приема пищи в историю пользователя
        
        # Пример ответа
        return {
            "status": "success", 
            "message": f"Прием пищи '{meal_data.meal_name}' успешно добавлен для пользователя {meal_data.user_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Telegram Bot WebApp API работает! Используйте /docs для просмотра документации API."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
