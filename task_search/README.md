# Task Search Module

Модуль для поиска практических задач по текстовому запросу с использованием модели bge-m3.

## Зависимости

Использует тот же клиент OpenAI, что и `Interactor` из `hackatone.inreractor.interactor`.

## Использование

```python
from hackatone.task_search import TaskSearcher
from openai import OpenAI

# Создание клиента OpenAI (тот же, что в Interactor)
client = OpenAI(
    api_key="your-api-key",
    base_url="https://llm.t1v.scibox.tech/v1"
)

# Создание поисковика с клиентом
searcher = TaskSearcher(client=client, model_name="bge-m3")

# Добавление задач из JSON
tasks_json = [
    {
        "индекс": 1,
        "условие": "Дано число n",
        "описание": "Реализовать функцию для вычисления факториала числа"
    },
    {
        "index": 2,
        "condition": "Дан массив",
        "description": "Написать алгоритм сортировки пузырьком"
    }
]
searcher.add_tasks_from_json(tasks_json)

# Добавление одной задачи из JSON
task_json = {
    "индекс": 3,
    "условие": "Реализовать структуру данных",
    "описание": "Создать класс для работы с бинарным деревом"
}
searcher.add_task_from_json(task_json)

# Также можно добавлять задачи напрямую (для обратной совместимости)
searcher.add_task(4, "Описание задачи", "Условие задачи")

# Удаление задачи по индексу
searcher.remove_task(1)  # Удаляет задачу с индексом 1

# Полное очищение базы данных
searcher.clear()  # Удаляет все задачи

# Поиск топ 3 наиболее близких задач
results = searcher.search("алгоритм сортировки", top_k=3)

for task_index, condition, description, similarity in results:
    print(f"Задача {task_index}:")
    if condition:
        print(f"  Условие: {condition}")
    print(f"  Описание: {description}")
    print(f"  Сходство: {similarity:.4f}")
```

## API

### TaskSearcher

#### Методы управления базой данных

- `add_task(task_index: int, task_description: str, task_condition: str = "")` - добавляет одну задачу в базу данных
- `add_tasks(tasks: List[Tuple[int, str, str]])` - добавляет несколько задач в базу данных (поддерживает обратную совместимость)
- `add_task_from_json(task_json: Union[Dict[str, Any], str])` - добавляет задачу из JSON объекта или строки
- `add_tasks_from_json(tasks_json: Union[List[Dict[str, Any]], str])` - добавляет несколько задач из JSON массива или строки
- `remove_task(task_index: int) -> bool` - удаляет задачу по её индексу, возвращает True если задача была найдена и удалена
- `clear()` - полностью очищает базу данных (удаляет все задачи)

**Формат JSON для задач:**
JSON объект должен содержать следующие поля (поддерживаются варианты на русском и английском):
- Индекс: `"индекс"`, `"index"` или `"task_index"` (обязательно)
- Условие: `"условие"`, `"condition"` или `"task_condition"` (опционально)
- Описание: `"описание"`, `"description"` или `"task_description"` (обязательно)

#### Методы поиска и получения информации

- `search(query: str, top_k: int = 5) -> List[Tuple[int, str, str, float]]` - ищет топ k наиболее близких задач по текстовому запросу. Возвращает список кортежей (индекс, условие, описание, сходство)
- `get_task_count() -> int` - возвращает количество задач в базе данных
- `get_task_by_index(task_index: int) -> Optional[Tuple[str, str]]` - получает задачу по её индексу. Возвращает кортеж (условие, описание) или None

