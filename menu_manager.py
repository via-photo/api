#!/usr/bin/env python3.11
"""
Модуль для управления данными меню и выбора подходящего меню
в зависимости от целевых калорий пользователя
"""

import json
import os
from typing import Dict, List, Any, Optional

class MenuManager:
    """Класс для управления данными меню"""
    
    def __init__(self):
        """Инициализация менеджера меню"""
        self.dishes = []
        self.load_dishes()
    
    def load_dishes(self):
        """Загрузка блюд из JSON файла"""
        try:
            # Используем относительный путь к файлу
            menu_json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'menu_dishes.json')
            with open(menu_json_path, 'r', encoding='utf-8') as f:
                self.dishes = json.load(f)
            print(f"Загружено {len(self.dishes)} блюд из меню")
        except Exception as e:
            print(f"Ошибка при загрузке данных меню: {e}")
            self.dishes = []
    
    def get_menu_for_user(self, target_calories: int) -> List[Dict[str, Any]]:
        """
        Получение меню для пользователя в зависимости от его целевых калорий
        
        Args:
            target_calories: Целевые калории пользователя
            
        Returns:
            Список блюд, подходящих для пользователя
        """
        menu_target = self._get_menu_target(target_calories)
        return [dish for dish in self.dishes if dish.get('target_calories') == menu_target]
    
    def get_dishes_by_category(self, target_calories: int, category: str) -> List[Dict[str, Any]]:
        """
        Получение блюд определенной категории для пользователя
        
        Args:
            target_calories: Целевые калории пользователя
            category: Категория блюд
            
        Returns:
            Список блюд указанной категории
        """
        menu_target = self._get_menu_target(target_calories)
        return [
            dish for dish in self.dishes 
            if dish.get('target_calories') == menu_target and dish.get('category') == category
        ]
    
    def get_dish_by_id(self, dish_id: int) -> Optional[Dict[str, Any]]:
        """
        Получение блюда по ID
        
        Args:
            dish_id: ID блюда
            
        Returns:
            Данные блюда или None, если блюдо не найдено
        """
        for dish in self.dishes:
            if dish.get('id') == dish_id:
                return dish
        return None
    
    def search_dishes(self, target_calories: int, query: str) -> List[Dict[str, Any]]:
        """
        Поиск блюд по запросу
        
        Args:
            target_calories: Целевые калории пользователя
            query: Поисковый запрос
            
        Returns:
            Список блюд, соответствующих запросу
        """
        menu_target = self._get_menu_target(target_calories)
        query = query.lower()
        
        return [
            dish for dish in self.dishes 
            if dish.get('target_calories') == menu_target and (
                query in dish.get('name', '').lower() or 
                query in dish.get('description', '').lower() or
                query in dish.get('category', '').lower()
            )
        ]
    
    def get_categories(self) -> List[str]:
        """
        Получение списка всех категорий блюд
        
        Returns:
            Список категорий
        """
        categories = set()
        for dish in self.dishes:
            if 'category' in dish:
                categories.add(dish['category'])
        
        # Сортируем категории в нужном порядке
        category_order = {
            'breakfast': 1,
            'lunch': 2,
            'dinner': 3,
            'snack': 4
        }
        
        return sorted(list(categories), key=lambda x: category_order.get(x, 99))
    
    def get_menu_stats(self, target_calories: int) -> Dict[str, Any]:
        """
        Получение статистики по меню
        
        Args:
            target_calories: Целевые калории пользователя
            
        Returns:
            Словарь со статистикой
        """
        menu_target = self._get_menu_target(target_calories)
        menu_dishes = [dish for dish in self.dishes if dish.get('target_calories') == menu_target]
        
        categories = {}
        for dish in menu_dishes:
            category = dish.get('category', 'other')
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        return {
            'total_dishes': len(menu_dishes),
            'categories': categories,
            'menu_target': menu_target
        }
    
    def _get_menu_target(self, target_calories: int) -> int:
        """
        Определение целевой калорийности меню в зависимости от целевых калорий пользователя
        
        Args:
            target_calories: Целевые калории пользователя
            
        Returns:
            Целевая калорийность меню
        """
        if target_calories <= 1300:
            return 1250
        elif target_calories <= 1500:
            return 1400
        elif target_calories <= 1800:
            return 1600
        else:
            return 1900

def format_dish_for_api(dish: Dict[str, Any]) -> Dict[str, Any]:
    """
    Форматирование данных блюда для API
    
    Args:
        dish: Данные блюда
        
    Returns:
        Отформатированные данные блюда
    """
    if not dish:
        return {}
    
    return {
        'id': dish.get('id'),
        'name': dish.get('name', ''),
        'description': dish.get('description', ''),
        'category': dish.get('category', ''),
        'calories': dish.get('calories', 0),
        'protein': dish.get('protein', 0),
        'fat': dish.get('fat', 0),
        'carb': dish.get('carb', 0),
        'fiber': dish.get('fiber', 0),
        'weight': dish.get('weight', 0),
        'prep_time': dish.get('prep_time', '15-30 мин'),
        'difficulty': dish.get('difficulty', 'Легко'),
        'recipe': dish.get('recipe', 'Рецепт не указан'),
        'target_calories': dish.get('target_calories', 0)
    }

# Создаем экземпляр менеджера меню
menu_manager = MenuManager()

