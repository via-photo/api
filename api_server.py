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

# Установка фиксированного API-ключа для безопасности
FIXED_API_KEY = "telegram_webapp_secure_key_2025"

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

# Функция для проверки API-ключа
async def verify_api_key(x_api_key: str = Header(None)):
    # Проверяем API-ключ из заголовка
    if not x_api_key or x_api_key != FIXED_API_KEY:
        # Для отладки - выводим полученный ключ
        print(f"Received API key: {x_api_key}, Expected: {FIXED_API_KEY}")
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
            entry_date = None
            timestamp = entry.get("timestamp")
            if isinstance(timestamp, datetime):
                entry_date = timestamp.date()
            elif isinstance(timestamp, str):
                try:
                    entry_date = datetime.fromisoformat(timestamp).date()
                except ValueError:
                    # Если не удалось распарсить дату, пропускаем запись
                    continue
            else:
                # Если timestamp отсутствует или имеет неизвестный формат, пропускаем запись
                continue
                
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
        print(f"Error in get_diary: {str(e)}")
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
            entry_date = None
            timestamp = entry.get("timestamp")
            if isinstance(timestamp, datetime):
                entry_date = timestamp.date()
            elif isinstance(timestamp, str):
                try:
                    entry_date = datetime.fromisoformat(timestamp).date()
                except ValueError:
                    # Если не удалось распарсить дату, пропускаем запись
                    continue
            else:
                # Если timestamp отсутствует или имеет неизвестный формат, пропускаем запись
                continue
                
            date_str = entry_date.strftime("%Y-%m-%d")
            
            # Инициализируем день, если его еще нет
            if date_str not in days:
                days[date_str] = {
                    "calories": 0,
                    "protein": 0,
                    "fat": 0,
                    "carb": 0
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
        print(f"Error in get_stats: {str(e)}")
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
        print(f"Error in get_recipes: {str(e)}")
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
        # Импортируем функции из bot.py
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from bot import add_history_entry
        
        # Формируем текст для добавления в историю
        items_text = "\n".join([f"• {item['name']} – {item.get('weight', 100)} г (~{item.get('calories', 0)} ккал)" for item in meal_data.items])
        total_calories = sum(item.get('calories', 0) for item in meal_data.items)
        
        # Расчет БЖУ
        total_protein = sum(item.get('protein', 0) for item in meal_data.items)
        total_fat = sum(item.get('fat', 0) for item in meal_data.items)
        total_carb = sum(item.get('carb', 0) for item in meal_data.items)
        total_fiber = sum(item.get('fiber', 0) for item in meal_data.items)
        
        response_text = f"🍽️ {meal_data.meal_name}:\n{items_text}\n\n📊 Итого: {total_calories} ккал, Белки: {total_protein} г, Жиры: {total_fat} г, Углеводы: {total_carb} г, Клетчатка: {total_fiber} г"
        
        # Добавляем запись в историю
        entry = {
            "prompt": f"Добавлен прием пищи: {meal_data.meal_name}",
            "response": response_text,
            "timestamp": datetime.now(),
            "type": "food",
            "data": {
                "meal_name": meal_data.meal_name,
                "meal_time": meal_data.meal_time,
                "items": meal_data.items
            }
        }
        
        await add_history_entry(meal_data.user_id, entry)
        
        return {
            "status": "success", 
            "message": f"Прием пищи '{meal_data.meal_name}' успешно добавлен для пользователя {meal_data.user_id}"
        }
    except Exception as e:
        print(f"Error in add_meal: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Telegram Bot WebApp API работает! Используйте /docs для просмотра документации API."}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
