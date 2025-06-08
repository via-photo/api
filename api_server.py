from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import sqlite3
import logging
import re
from datetime import datetime, timedelta, date
import json

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Telegram Bot API", version="1.0.0")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене замените на конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Настройка аутентификации
security = HTTPBearer()

# Простая проверка API ключа (в продакшене используйте более надежную систему)
VALID_API_KEYS = {"test_api_key", "your_production_api_key"}

def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if credentials.credentials not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials.credentials

# Модели данных
class DaySummaryResponse(BaseModel):
    date: str
    total_calories: int
    total_protein: float
    total_fat: float
    total_carb: float
    total_fiber: float
    remaining_calories: int
    remaining_protein: float
    remaining_fat: float
    remaining_carb: float
    meals: List[Dict[str, Any]]
    warnings: List[str]
    message: Optional[str] = None

class HistoricalDataResponse(BaseModel):
    dates: List[str]
    calories: List[int]
    protein: List[float]
    fat: List[float]
    carb: List[float]
    fiber: List[float]

class WeeklyStatsResponse(BaseModel):
    week_start: str
    week_end: str
    daily_data: List[Dict[str, Any]]
    weekly_averages: Dict[str, float]
    weekly_totals: Dict[str, float]

# Функции для работы с базой данных
def get_db_connection():
    """Получение соединения с базой данных"""
    try:
        conn = sqlite3.connect('bot_database.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        logger.error(f"Ошибка подключения к базе данных: {e}")
        raise HTTPException(status_code=500, detail="Database connection error")

def parse_nutrition_from_text(text: str) -> Dict[str, float]:
    """Парсинг БЖУ из текста ответа бота"""
    nutrition = {
        'calories': 0.0,
        'protein': 0.0,
        'fat': 0.0,
        'carb': 0.0,
        'fiber': 0.0
    }
    
    try:
        # Регулярные выражения для поиска БЖУ
        patterns = {
            'calories': r'(?:калории|ккал|энергия):\s*(\d+(?:\.\d+)?)',
            'protein': r'(?:белки|белок|протеин):\s*(\d+(?:\.\d+)?)',
            'fat': r'(?:жиры|жир):\s*(\d+(?:\.\d+)?)',
            'carb': r'(?:углеводы|углевод|карб):\s*(\d+(?:\.\d+)?)',
            'fiber': r'(?:клетчатка|волокна):\s*(\d+(?:\.\d+)?)'
        }
        
        for nutrient, pattern in patterns.items():
            match = re.search(pattern, text.lower())
            if match:
                nutrition[nutrient] = float(match.group(1))
                
    except Exception as e:
        logger.warning(f"Ошибка при парсинге БЖУ: {e}")
    
    return nutrition

def get_user_targets(user_id: str) -> Dict[str, float]:
    """Получение целевых значений пользователя"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT target_kcal, target_protein, target_fat, target_carb, target_fiber
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        if result:
            return {
                'calories': result['target_kcal'] or 2000,
                'protein': result['target_protein'] or 150,
                'fat': result['target_fat'] or 65,
                'carb': result['target_carb'] or 250,
                'fiber': result['target_fiber'] or 25
            }
        else:
            # Значения по умолчанию
            return {
                'calories': 2000,
                'protein': 150,
                'fat': 65,
                'carb': 250,
                'fiber': 25
            }
    finally:
        conn.close()

def get_user_timezone_offset(user_id: str) -> int:
    """Получение часового пояса пользователя"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT utc_offset FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        return result['utc_offset'] if result and result['utc_offset'] is not None else 0
    finally:
        conn.close()

def get_user_local_date(user_id: str, target_date: Optional[date] = None) -> date:
    """Получение локальной даты пользователя"""
    offset = get_user_timezone_offset(user_id)
    
    if target_date:
        return target_date
    
    utc_now = datetime.utcnow()
    local_time = utc_now + timedelta(hours=offset)
    return local_time.date()

# API endpoints

@app.get("/api/day-summary/{user_id}")
async def get_day_summary(
    user_id: str, 
    date_str: Optional[str] = Query(None, description="Дата в формате YYYY-MM-DD"),
    api_key: str = Depends(verify_api_key)
):
    """Получение итогов дня для указанной даты"""
    logger.info(f"Запрос итогов дня для пользователя {user_id}, дата: {date_str}")
    
    try:
        # Определяем дату
        if date_str:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        else:
            target_date = get_user_local_date(user_id)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем записи за указанную дату
        cursor.execute("""
            SELECT created_at, bot_response 
            FROM user_history 
            WHERE user_id = ? AND date(created_at) = ?
            ORDER BY created_at
        """, (user_id, target_date.strftime("%Y-%m-%d")))
        
        records = cursor.fetchall()
        conn.close()
        
        if not records:
            return {
                "success": True,
                "data": {
                    "date": target_date.strftime("%Y-%m-%d"),
                    "message": "За этот день нет записей о питании",
                    "total_calories": 0,
                    "total_protein": 0.0,
                    "total_fat": 0.0,
                    "total_carb": 0.0,
                    "total_fiber": 0.0,
                    "remaining_calories": 0,
                    "remaining_protein": 0.0,
                    "remaining_fat": 0.0,
                    "remaining_carb": 0.0,
                    "meals": [],
                    "warnings": []
                }
            }
        
        # Получаем целевые значения
        targets = get_user_targets(user_id)
        
        # Анализируем записи
        total_nutrition = {
            'calories': 0.0,
            'protein': 0.0,
            'fat': 0.0,
            'carb': 0.0,
            'fiber': 0.0
        }
        
        meals = []
        
        for record in records:
            nutrition = parse_nutrition_from_text(record['bot_response'])
            
            # Суммируем БЖУ
            for key in total_nutrition:
                total_nutrition[key] += nutrition[key]
            
            # Добавляем прием пищи
            if nutrition['calories'] > 0:  # Только если есть калории
                meal_time = datetime.fromisoformat(record['created_at']).strftime("%H:%M")
                meals.append({
                    'time': meal_time,
                    'description': record['bot_response'][:100] + "..." if len(record['bot_response']) > 100 else record['bot_response'],
                    'calories': int(nutrition['calories']),
                    'protein': nutrition['protein'],
                    'fat': nutrition['fat'],
                    'carb': nutrition['carb']
                })
        
        # Рассчитываем остатки
        remaining = {}
        for key in total_nutrition:
            remaining[f'remaining_{key}'] = max(0, targets[key] - total_nutrition[key])
        
        # Генерируем предупреждения
        warnings = []
        
        if total_nutrition['calories'] > targets['calories'] * 1.2:
            warnings.append("⚠️ Превышена дневная норма калорий")
        elif total_nutrition['calories'] < targets['calories'] * 0.7:
            warnings.append("📉 Калорий потреблено меньше нормы")
        
        if total_nutrition['protein'] < targets['protein'] * 0.8:
            warnings.append("🥩 Недостаточно белка")
        
        if total_nutrition['fiber'] < targets['fiber'] * 0.6:
            warnings.append("🥬 Мало клетчатки")
        
        return {
            "success": True,
            "data": {
                "date": target_date.strftime("%Y-%m-%d"),
                "total_calories": int(total_nutrition['calories']),
                "total_protein": round(total_nutrition['protein'], 1),
                "total_fat": round(total_nutrition['fat'], 1),
                "total_carb": round(total_nutrition['carb'], 1),
                "total_fiber": round(total_nutrition['fiber'], 1),
                "remaining_calories": int(remaining['remaining_calories']),
                "remaining_protein": round(remaining['remaining_protein'], 1),
                "remaining_fat": round(remaining['remaining_fat'], 1),
                "remaining_carb": round(remaining['remaining_carb'], 1),
                "meals": meals,
                "warnings": warnings
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении итогов дня: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/historical-data/{user_id}")
async def get_historical_data(
    user_id: str,
    days: int = Query(7, description="Количество дней для получения данных"),
    end_date: Optional[str] = Query(None, description="Конечная дата в формате YYYY-MM-DD"),
    api_key: str = Depends(verify_api_key)
):
    """Получение исторических данных за указанный период"""
    logger.info(f"Запрос исторических данных для пользователя {user_id}, дней: {days}")
    
    try:
        # Определяем конечную дату
        if end_date:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
        else:
            end_date_obj = get_user_local_date(user_id)
        
        # Определяем начальную дату
        start_date_obj = end_date_obj - timedelta(days=days-1)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем данные за период
        cursor.execute("""
            SELECT date(created_at) as date, bot_response 
            FROM user_history 
            WHERE user_id = ? AND date(created_at) BETWEEN ? AND ?
            ORDER BY created_at
        """, (user_id, start_date_obj.strftime("%Y-%m-%d"), end_date_obj.strftime("%Y-%m-%d")))
        
        records = cursor.fetchall()
        conn.close()
        
        # Группируем данные по дням
        daily_data = {}
        current_date = start_date_obj
        
        # Инициализируем все дни нулями
        while current_date <= end_date_obj:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_data[date_str] = {
                'calories': 0.0,
                'protein': 0.0,
                'fat': 0.0,
                'carb': 0.0,
                'fiber': 0.0
            }
            current_date += timedelta(days=1)
        
        # Заполняем данными из базы
        for record in records:
            date_str = record['date']
            if date_str in daily_data:
                nutrition = parse_nutrition_from_text(record['bot_response'])
                for key in daily_data[date_str]:
                    daily_data[date_str][key] += nutrition[key]
        
        # Формируем ответ
        dates = []
        calories = []
        protein = []
        fat = []
        carb = []
        fiber = []
        
        for date_str in sorted(daily_data.keys()):
            dates.append(date_str)
            calories.append(int(daily_data[date_str]['calories']))
            protein.append(round(daily_data[date_str]['protein'], 1))
            fat.append(round(daily_data[date_str]['fat'], 1))
            carb.append(round(daily_data[date_str]['carb'], 1))
            fiber.append(round(daily_data[date_str]['fiber'], 1))
        
        return {
            "success": True,
            "data": {
                "dates": dates,
                "calories": calories,
                "protein": protein,
                "fat": fat,
                "carb": carb,
                "fiber": fiber
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении исторических данных: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weekly-stats/{user_id}")
async def get_weekly_stats(
    user_id: str,
    week_offset: int = Query(0, description="Смещение недели (0 - текущая, -1 - предыдущая, и т.д.)"),
    api_key: str = Depends(verify_api_key)
):
    """Получение статистики за неделю"""
    logger.info(f"Запрос недельной статистики для пользователя {user_id}, смещение: {week_offset}")
    
    try:
        # Определяем даты недели
        today = get_user_local_date(user_id)
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday) + timedelta(weeks=week_offset)
        week_end = week_start + timedelta(days=6)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем данные за неделю
        cursor.execute("""
            SELECT date(created_at) as date, bot_response 
            FROM user_history 
            WHERE user_id = ? AND date(created_at) BETWEEN ? AND ?
            ORDER BY created_at
        """, (user_id, week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d")))
        
        records = cursor.fetchall()
        conn.close()
        
        # Группируем данные по дням
        daily_data = {}
        current_date = week_start
        
        # Инициализируем все дни недели
        while current_date <= week_end:
            date_str = current_date.strftime("%Y-%m-%d")
            daily_data[date_str] = {
                'date': date_str,
                'day_name': current_date.strftime("%A"),
                'calories': 0.0,
                'protein': 0.0,
                'fat': 0.0,
                'carb': 0.0,
                'fiber': 0.0
            }
            current_date += timedelta(days=1)
        
        # Заполняем данными
        for record in records:
            date_str = record['date']
            if date_str in daily_data:
                nutrition = parse_nutrition_from_text(record['bot_response'])
                for key in ['calories', 'protein', 'fat', 'carb', 'fiber']:
                    daily_data[date_str][key] += nutrition[key]
        
        # Рассчитываем средние и общие значения
        weekly_totals = {
            'calories': 0.0,
            'protein': 0.0,
            'fat': 0.0,
            'carb': 0.0,
            'fiber': 0.0
        }
        
        days_with_data = 0
        for day_data in daily_data.values():
            if day_data['calories'] > 0:
                days_with_data += 1
            for key in weekly_totals:
                weekly_totals[key] += day_data[key]
        
        weekly_averages = {}
        for key in weekly_totals:
            if days_with_data > 0:
                weekly_averages[key] = round(weekly_totals[key] / days_with_data, 1)
            else:
                weekly_averages[key] = 0.0
            weekly_totals[key] = round(weekly_totals[key], 1)
        
        return {
            "success": True,
            "data": {
                "week_start": week_start.strftime("%Y-%m-%d"),
                "week_end": week_end.strftime("%Y-%m-%d"),
                "daily_data": list(daily_data.values()),
                "weekly_averages": weekly_averages,
                "weekly_totals": weekly_totals
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении недельной статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Обновляем существующий endpoint статистики
@app.get("/api/stats/{user_id}")
async def get_stats(user_id: str, api_key: str = Depends(verify_api_key)):
    """Получение общей статистики пользователя с итогами дня"""
    logger.info(f"Запрос статистики для пользователя: {user_id}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем итоги за сегодня
        today_date = get_user_local_date(user_id)
        cursor.execute("""
            SELECT created_at, bot_response 
            FROM user_history 
            WHERE user_id = ? AND date(created_at) = ?
            ORDER BY created_at
        """, (user_id, today_date.strftime("%Y-%m-%d")))
        
        today_records = cursor.fetchall()
        
        # Формируем итоги дня
        today_summary = None
        if today_records:
            targets = get_user_targets(user_id)
            total_nutrition = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carb': 0.0, 'fiber': 0.0}
            meals = []
            
            for record in today_records:
                nutrition = parse_nutrition_from_text(record['bot_response'])
                for key in total_nutrition:
                    total_nutrition[key] += nutrition[key]
                
                if nutrition['calories'] > 0:
                    meal_time = datetime.fromisoformat(record['created_at']).strftime("%H:%M")
                    meals.append({
                        'time': meal_time,
                        'description': record['bot_response'][:100] + "..." if len(record['bot_response']) > 100 else record['bot_response'],
                        'calories': int(nutrition['calories'])
                    })
            
            remaining = {}
            for key in total_nutrition:
                remaining[f'remaining_{key}'] = max(0, targets[key] - total_nutrition[key])
            
            warnings = []
            if total_nutrition['calories'] > targets['calories'] * 1.2:
                warnings.append("⚠️ Превышена дневная норма калорий")
            elif total_nutrition['calories'] < targets['calories'] * 0.7:
                warnings.append("📉 Калорий потреблено меньше нормы")
            
            today_summary = {
                "total_calories": int(total_nutrition['calories']),
                "total_protein": round(total_nutrition['protein'], 1),
                "total_fat": round(total_nutrition['fat'], 1),
                "total_carb": round(total_nutrition['carb'], 1),
                "remaining_calories": int(remaining['remaining_calories']),
                "remaining_protein": round(remaining['remaining_protein'], 1),
                "remaining_fat": round(remaining['remaining_fat'], 1),
                "remaining_carb": round(remaining['remaining_carb'], 1),
                "meals": meals,
                "warnings": warnings
            }
        
        # Получаем общую статистику (существующий код)
        cursor.execute("""
            SELECT COUNT(*) as total_records,
                   COUNT(DISTINCT date(created_at)) as days_tracked
            FROM user_history 
            WHERE user_id = ?
        """, (user_id,))
        
        general_stats = cursor.fetchone()
        
        # Получаем средние значения за последние 30 дней
        thirty_days_ago = today_date - timedelta(days=30)
        cursor.execute("""
            SELECT bot_response 
            FROM user_history 
            WHERE user_id = ? AND date(created_at) >= ?
        """, (user_id, thirty_days_ago.strftime("%Y-%m-%d")))
        
        recent_records = cursor.fetchall()
        conn.close()
        
        # Анализируем данные за 30 дней
        total_nutrition_30d = {'calories': 0.0, 'protein': 0.0, 'fat': 0.0, 'carb': 0.0}
        daily_calories = {}
        
        for record in recent_records:
            nutrition = parse_nutrition_from_text(record['bot_response'])
            for key in total_nutrition_30d:
                total_nutrition_30d[key] += nutrition[key]
        
        days_tracked = general_stats['days_tracked'] or 1
        avg_calories = int(total_nutrition_30d['calories'] / days_tracked) if days_tracked > 0 else 0
        
        # Получаем целевые значения
        targets = get_user_targets(user_id)
        
        # Рассчитываем соблюдение нормы
        adherence_percent = min(100, int((avg_calories / targets['calories']) * 100)) if targets['calories'] > 0 else 0
        
        # Распределение БЖУ
        total_macros = total_nutrition_30d['protein'] + total_nutrition_30d['fat'] + total_nutrition_30d['carb']
        if total_macros > 0:
            protein_percent = int((total_nutrition_30d['protein'] / total_macros) * 100)
            fat_percent = int((total_nutrition_30d['fat'] / total_macros) * 100)
            carb_percent = 100 - protein_percent - fat_percent
        else:
            protein_percent = fat_percent = carb_percent = 0
        
        return {
            "success": True,
            "data": {
                "today_summary": today_summary,
                "general": {
                    "avg_calories": avg_calories,
                    "days_tracked": days_tracked,
                    "adherence_percent": adherence_percent,
                    "weight_change": 0  # Заглушка, можно добавить реальные данные
                },
                "nutrition_distribution": {
                    "protein": protein_percent,
                    "fat": fat_percent,
                    "carb": carb_percent
                },
                "user_targets": {
                    "calories": int(targets['calories']),
                    "protein": int(targets['protein']),
                    "fat": int(targets['fat']),
                    "carb": int(targets['carb'])
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Остальные endpoints остаются без изменений...

@app.get("/api/diary/{user_id}")
async def get_diary(user_id: str, api_key: str = Depends(verify_api_key)):
    """Получение данных дневника питания"""
    logger.info(f"Запрос дневника для пользователя: {user_id}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем записи за последние 7 дней
        seven_days_ago = datetime.now() - timedelta(days=7)
        cursor.execute("""
            SELECT created_at, bot_response 
            FROM user_history 
            WHERE user_id = ? AND created_at >= ?
            ORDER BY created_at DESC
            LIMIT 50
        """, (user_id, seven_days_ago.isoformat()))
        
        records = cursor.fetchall()
        conn.close()
        
        diary_entries = []
        for record in records:
            # Парсим дату и время
            created_at = datetime.fromisoformat(record['created_at'])
            
            diary_entries.append({
                'date': created_at.strftime('%Y-%m-%d'),
                'time': created_at.strftime('%H:%M'),
                'content': record['bot_response'][:200] + "..." if len(record['bot_response']) > 200 else record['bot_response'],
                'full_content': record['bot_response']
            })
        
        return {
            "success": True,
            "data": {
                "entries": diary_entries,
                "total_entries": len(diary_entries)
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении дневника: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/recipes/{user_id}")
async def get_recipes(user_id: str, api_key: str = Depends(verify_api_key)):
    """Получение рецептов для пользователя"""
    logger.info(f"Запрос рецептов для пользователя: {user_id}")
    
    # Заглушка для рецептов
    sample_recipes = [
        {
            "title": "Овсяная каша с ягодами",
            "description": "Полезный завтрак с высоким содержанием клетчатки",
            "calories": 320,
            "protein": 12,
            "prep_time": "10 мин",
            "difficulty": "Легко"
        },
        {
            "title": "Куриная грудка с овощами",
            "description": "Белковое блюдо для обеда или ужина",
            "calories": 450,
            "protein": 35,
            "prep_time": "25 мин",
            "difficulty": "Средне"
        },
        {
            "title": "Греческий салат",
            "description": "Свежий салат с сыром фета и оливками",
            "calories": 280,
            "protein": 8,
            "prep_time": "15 мин",
            "difficulty": "Легко"
        }
    ]
    
    return {
        "success": True,
        "data": {
            "recipes": sample_recipes,
            "total_recipes": len(sample_recipes)
        }
    }

@app.get("/api/profile/{user_id}")
async def get_profile(user_id: str, api_key: str = Depends(verify_api_key)):
    """Получение данных профиля пользователя"""
    logger.info(f"Запрос профиля для пользователя: {user_id}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT gender, age, height, weight, goal, activity, pregnant, 
                   target_kcal, target_protein, target_fat, target_carb, target_fiber,
                   utc_offset, morning_reminded
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "data": {
                "gender": result['gender'],
                "age": result['age'],
                "height": result['height'],
                "weight": result['weight'],
                "goal": result['goal'],
                "activity": result['activity'],
                "pregnant": bool(result['pregnant']) if result['pregnant'] is not None else False,
                "target_kcal": result['target_kcal'],
                "target_protein": result['target_protein'],
                "target_fat": result['target_fat'],
                "target_carb": result['target_carb'],
                "target_fiber": result['target_fiber'],
                "utc_offset": result['utc_offset'] or 0,
                "morning_reminded": bool(result['morning_reminded']) if result['morning_reminded'] is not None else False
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при получении профиля: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/profile/{user_id}")
async def update_profile(user_id: str, profile_data: dict, api_key: str = Depends(verify_api_key)):
    """Обновление данных профиля пользователя"""
    logger.info(f"Обновление профиля для пользователя: {user_id}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Формируем SQL запрос динамически на основе переданных данных
        update_fields = []
        values = []
        
        allowed_fields = ['gender', 'age', 'height', 'weight', 'goal', 'activity', 'pregnant', 'utc_offset', 'morning_reminded']
        
        for field in allowed_fields:
            if field in profile_data:
                update_fields.append(f"{field} = ?")
                values.append(profile_data[field])
        
        if update_fields:
            values.append(user_id)
            sql = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
            cursor.execute(sql, values)
            conn.commit()
        
        conn.close()
        
        return {
            "success": True,
            "message": "Профиль успешно обновлен"
        }
        
    except Exception as e:
        logger.error(f"Ошибка при обновлении профиля: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile/{user_id}/recalculate")
async def recalculate_targets(user_id: str, api_key: str = Depends(verify_api_key)):
    """Пересчет целевых значений пользователя"""
    logger.info(f"Пересчет целевых значений для пользователя: {user_id}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Получаем данные пользователя
        cursor.execute("""
            SELECT gender, age, height, weight, goal, activity, pregnant
            FROM users WHERE user_id = ?
        """, (user_id,))
        
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Простой расчет BMR (базовый метаболизм)
        if result['gender'] == 'муж':
            bmr = 88.362 + (13.397 * result['weight']) + (4.799 * result['height']) - (5.677 * result['age'])
        else:
            bmr = 447.593 + (9.247 * result['weight']) + (3.098 * result['height']) - (4.330 * result['age'])
        
        # Коэффициент активности
        activity_multipliers = {
            'низкий': 1.2,
            'средний': 1.55,
            'высокий': 1.9
        }
        
        multiplier = activity_multipliers.get(result['activity'], 1.2)
        
        # Корректировка для беременности/ГВ
        if result['pregnant']:
            multiplier += 0.2
        
        target_calories = int(bmr * multiplier)
        
        # Расчет БЖУ (примерные пропорции)
        target_protein = int(target_calories * 0.25 / 4)  # 25% от калорий
        target_fat = int(target_calories * 0.30 / 9)      # 30% от калорий
        target_carb = int(target_calories * 0.45 / 4)     # 45% от калорий
        target_fiber = max(25, int(target_calories / 100)) # Примерно 1г на 100 ккал
        
        # Обновляем в базе данных
        cursor.execute("""
            UPDATE users SET 
                target_kcal = ?, target_protein = ?, target_fat = ?, 
                target_carb = ?, target_fiber = ?
            WHERE user_id = ?
        """, (target_calories, target_protein, target_fat, target_carb, target_fiber, user_id))
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "message": "Целевые значения пересчитаны",
            "data": {
                "target_kcal": target_calories,
                "target_protein": target_protein,
                "target_fat": target_fat,
                "target_carb": target_carb,
                "target_fiber": target_fiber
            }
        }
        
    except Exception as e:
        logger.error(f"Ошибка при пересчете целевых значений: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """Корневой endpoint"""
    return {"message": "Telegram Bot API Server", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Проверка состояния сервера"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

