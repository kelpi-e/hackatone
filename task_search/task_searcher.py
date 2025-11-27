"""
Модуль для поиска практических задач по текстовому запросу с использованием модели bge-m3.
"""

from typing import List, Tuple, Optional, Dict, Any, Union
import numpy as np
from openai import OpenAI
import json


class TaskSearcher:
    """
    Класс для хранения и поиска практических задач по текстовому запросу.
    
    Хранит задачи в формате (индекс задачи, условие задачи, описание задачи) и позволяет
    находить топ k наиболее близких задач по семантическому сходству.
    """
    
    def __init__(self, client: OpenAI, model_name: str = "bge-m3"):
        """
        Инициализация поисковика задач.
        
        Args:
            client: клиент OpenAI (тот же, что используется в Interactor)
            model_name: название модели для эмбеддингов (по умолчанию bge-m3)
        """
        self.client = client
        self.model_name = model_name
        # Структура: (индекс, условие, описание)
        self.tasks: List[Tuple[int, str, str]] = []
        self.embeddings: Optional[np.ndarray] = None
        self._needs_reindex = False
    
    def add_task(self, task_index: int, task_description: str, task_condition: str = "") -> None:
        """
        Добавляет задачу в хранилище.
        
        Args:
            task_index: индекс задачи
            task_description: описание практической задачи
            task_condition: условие задачи (опционально, для обратной совместимости)
        """
        self.tasks.append((task_index, task_condition, task_description))
        self._needs_reindex = True
    
    def add_tasks(self, tasks: List[Tuple[int, str, str]]) -> None:
        """
        Добавляет несколько задач в хранилище.
        
        Args:
            tasks: список кортежей (индекс задачи, условие задачи, описание задачи)
                  или (индекс задачи, описание задачи) для обратной совместимости
        """
        normalized_tasks = []
        for task in tasks:
            if len(task) == 2:
                # Обратная совместимость: (индекс, описание)
                normalized_tasks.append((task[0], "", task[1]))
            elif len(task) == 3:
                # Новый формат: (индекс, условие, описание)
                normalized_tasks.append(task)
        self.tasks.extend(normalized_tasks)
        self._needs_reindex = True
    
    def add_task_from_json(self, task_json: Union[Dict[str, Any], str]) -> None:
        """
        Добавляет задачу из JSON объекта или строки.
        
        Args:
            task_json: JSON объект (dict) или JSON строка со следующими полями:
                      - "индекс" или "index" или "task_index": индекс задачи
                      - "условие" или "condition" или "task_condition": условие задачи
                      - "описание" или "description" или "task_description": описание задачи
        """
        if isinstance(task_json, str):
            task_json = json.loads(task_json)
        
        # Извлекаем индекс
        task_index = task_json.get("индекс") or task_json.get("index") or task_json.get("task_index")
        if task_index is None:
            raise ValueError("JSON должен содержать поле 'индекс', 'index' или 'task_index'")
        
        # Извлекаем условие
        task_condition = (
            task_json.get("условие") or 
            task_json.get("condition") or 
            task_json.get("task_condition") or 
            ""
        )
        
        # Извлекаем описание
        task_description = (
            task_json.get("описание") or 
            task_json.get("description") or 
            task_json.get("task_description")
        )
        if task_description is None:
            raise ValueError("JSON должен содержать поле 'описание', 'description' или 'task_description'")
        
        self.tasks.append((int(task_index), str(task_condition), str(task_description)))
        self._needs_reindex = True
    
    def add_tasks_from_json(self, tasks_json: Union[List[Dict[str, Any]], str]) -> None:
        """
        Добавляет несколько задач из JSON массива или строки.
        
        Args:
            tasks_json: JSON массив объектов (list) или JSON строка, где каждый объект содержит:
                       - "индекс" или "index" или "task_index": индекс задачи
                       - "условие" или "condition" или "task_condition": условие задачи
                       - "описание" или "description" или "task_description": описание задачи
        """
        if isinstance(tasks_json, str):
            tasks_json = json.loads(tasks_json)
        
        if not isinstance(tasks_json, list):
            raise ValueError("tasks_json должен быть списком JSON объектов")
        
        for task_json in tasks_json:
            self.add_task_from_json(task_json)
    
    def remove_task(self, task_index: int) -> bool:
        """
        Удаляет задачу по её индексу.
        
        Args:
            task_index: индекс задачи для удаления
        
        Returns:
            True, если задача была найдена и удалена, False если задача не найдена
        """
        initial_count = len(self.tasks)
        self.tasks = [(idx, condition, desc) for idx, condition, desc in self.tasks if idx != task_index]
        
        if len(self.tasks) < initial_count:
            self._needs_reindex = True
            return True
        return False
    
    def _get_embeddings(self, texts: List[str]) -> np.ndarray:
        """
        Получает эмбеддинги для списка текстов через OpenAI API.
        
        Args:
            texts: список текстов для векторизации
        
        Returns:
            Массив эмбеддингов (numpy array)
        """
        try:
            # Используем embeddings API через тот же клиент
            response = self.client.embeddings.create(
                model=self.model_name,
                input=texts
            )
            embeddings = [item.embedding for item in response.data]
            embeddings_array = np.array(embeddings)
            
            # Нормализуем эмбеддинги для косинусного сходства
            norms = np.linalg.norm(embeddings_array, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Избегаем деления на ноль
            embeddings_array = embeddings_array / norms
            
            return embeddings_array
        except Exception as e:
            # Если модель не найдена, пробуем использовать другую модель
            # или возвращаем ошибку
            raise ValueError(f"Ошибка при получении эмбеддингов: {str(e)}")
    
    def _build_index(self) -> None:
        """
        Строит индекс эмбеддингов для всех задач.
        Вызывается автоматически при необходимости.
        Использует описание задачи для поиска (можно объединить с условием при необходимости).
        """
        if not self.tasks:
            self.embeddings = None
            return
        
        # Для поиска используем описание, при необходимости можно объединить с условием
        search_texts = []
        for idx, condition, description in self.tasks:
            # Объединяем условие и описание для лучшего поиска
            if condition:
                search_text = f"{condition} {description}".strip()
            else:
                search_text = description
            search_texts.append(search_text)
        
        # Получаем эмбеддинги через OpenAI API
        self.embeddings = self._get_embeddings(search_texts)
        self._needs_reindex = False
    
    def search(self, query: str, top_k: int = 5) -> List[Tuple[int, str, str, float]]:
        """
        Ищет топ k наиболее близких задач по текстовому запросу.
        
        Args:
            query: текстовый запрос для поиска
            top_k: количество возвращаемых результатов
        
        Returns:
            Список кортежей (индекс задачи, условие задачи, описание задачи, оценка сходства),
            отсортированный по убыванию сходства
        """
        if not self.tasks:
            return []
        
        # Пересобираем индекс, если нужно
        if self._needs_reindex or self.embeddings is None:
            self._build_index()
        
        # Получаем эмбеддинг запроса через OpenAI API
        query_embeddings = self._get_embeddings([query])
        query_embedding = query_embeddings[0]
        
        # Вычисляем косинусное сходство
        similarities = np.dot(self.embeddings, query_embedding)
        
        # Получаем индексы топ k наиболее похожих задач
        top_indices = np.argsort(similarities)[::-1][:top_k]
        
        # Формируем результат
        results = []
        for idx in top_indices:
            task_index, task_condition, task_description = self.tasks[idx]
            similarity_score = float(similarities[idx])
            results.append((task_index, task_condition, task_description, similarity_score))
        
        return results
    
    def clear(self) -> None:
        """
        Очищает все задачи и индекс.
        """
        self.tasks = []
        self.embeddings = None
        self._needs_reindex = False
    
    def get_task_count(self) -> int:
        """
        Возвращает количество задач в хранилище.
        
        Returns:
            Количество задач
        """
        return len(self.tasks)
    
    def get_task_by_index(self, task_index: int) -> Optional[Tuple[str, str]]:
        """
        Получает задачу по её индексу.
        
        Args:
            task_index: индекс задачи
        
        Returns:
            Кортеж (условие задачи, описание задачи) или None, если задача не найдена
        """
        for idx, condition, description in self.tasks:
            if idx == task_index:
                return (condition, description)
        return None

