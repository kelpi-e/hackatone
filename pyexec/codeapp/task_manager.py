"""
Модуль для управления задачами и их ранжирования на основе профиля кандидата.
"""

import os
import json
import sys
from typing import List, Dict, Any, Optional

# Добавляем путь к task_search
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASK_SEARCH_PATH = os.path.join(os.path.dirname(BASE_DIR), 'task_search')
if TASK_SEARCH_PATH not in sys.path:
    sys.path.insert(0, TASK_SEARCH_PATH)

from openai import OpenAI
from task_searcher import TaskSearcher

# Путь к файлам
TASKS_DB_PATH = os.path.join(BASE_DIR, 'codeapp', 'tests', 'tasks_db.json')
VECTOR_DB_PATH = os.path.join(BASE_DIR, 'codeapp', 'tests', 'tasks_vectors.pkl')

# API ключ
API_KEY = "sk-EntOXD173KXh0i-jb0esww"
API_BASE_URL = "https://llm.t1v.scibox.tech/v1"


def get_openai_client() -> OpenAI:
    """Возвращает клиент OpenAI."""
    return OpenAI(api_key=API_KEY, base_url=API_BASE_URL)


def load_tasks_from_json() -> List[Dict[str, Any]]:
    """Загружает задачи из JSON файла."""
    if not os.path.exists(TASKS_DB_PATH):
        return []
    
    with open(TASKS_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_task_searcher() -> TaskSearcher:
    """
    Получает экземпляр TaskSearcher.
    Загружает из файла, если существует, иначе создаёт новый и индексирует задачи.
    """
    client = get_openai_client()
    
    # Пробуем загрузить из файла
    if os.path.exists(VECTOR_DB_PATH):
        try:
            searcher = TaskSearcher.load_from_file(client, VECTOR_DB_PATH)
            return searcher
        except Exception as e:
            print(f"Ошибка загрузки векторной базы: {e}")
    
    # Создаём новый и индексируем
    searcher = TaskSearcher(client)
    tasks = load_tasks_from_json()
    
    for task in tasks:
        searcher.add_task(
            task_index=task['index'],
            task_description=task['description'],
            task_condition=task['condition']
        )
    
    # Сохраняем для будущего использования
    if tasks:
        try:
            searcher.save_to_file(VECTOR_DB_PATH)
        except Exception as e:
            print(f"Ошибка сохранения векторной базы: {e}")
    
    return searcher


def rebuild_vector_db() -> bool:
    """
    Пересоздаёт векторную базу данных из JSON файла.
    Возвращает True при успехе.
    """
    try:
        client = get_openai_client()
        searcher = TaskSearcher(client)
        tasks = load_tasks_from_json()
        
        for task in tasks:
            searcher.add_task(
                task_index=task['index'],
                task_description=task['description'],
                task_condition=task['condition']
            )
        
        if tasks:
            searcher.save_to_file(VECTOR_DB_PATH)
        
        return True
    except Exception as e:
        print(f"Ошибка пересоздания векторной базы: {e}")
        return False


def get_ranked_tasks(candidate_summary: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """
    Возвращает задачи, ранжированные по релевантности для кандидата.
    
    Args:
        candidate_summary: описание навыков/профиля кандидата
        top_k: максимальное количество задач
    
    Returns:
        Список задач в порядке убывания релевантности
    """
    searcher = get_task_searcher()
    results = searcher.search(candidate_summary, top_k=top_k)
    
    ranked_tasks = []
    for task_index, condition, description, similarity in results:
        ranked_tasks.append({
            'index': task_index,
            'condition': condition,
            'description': description,
            'similarity': similarity
        })
    
    return ranked_tasks


def get_task_by_index(task_index: int) -> Optional[Dict[str, Any]]:
    """
    Получает задачу по индексу.
    
    Args:
        task_index: индекс задачи
    
    Returns:
        Словарь с данными задачи или None
    """
    tasks = load_tasks_from_json()
    for task in tasks:
        if task['index'] == task_index:
            return task
    return None


def get_all_tasks() -> List[Dict[str, Any]]:
    """Возвращает все задачи из базы."""
    return load_tasks_from_json()


if __name__ == '__main__':
    # Тестовый запуск - пересоздаём векторную базу
    print("Пересоздание векторной базы данных...")
    if rebuild_vector_db():
        print("Векторная база успешно создана!")
        
        # Тестовый поиск
        print("\nТестовый поиск для 'базовые алгоритмы и массивы':")
        results = get_ranked_tasks("базовые алгоритмы и массивы", top_k=3)
        for i, task in enumerate(results, 1):
            print(f"{i}. Задача #{task['index']} (similarity: {task['similarity']:.3f})")
            print(f"   {task['condition'][:50]}...")
    else:
        print("Ошибка создания векторной базы")

