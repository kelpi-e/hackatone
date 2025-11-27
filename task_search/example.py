"""
Пример использования TaskSearcher для поиска практических задач.
"""

from task_searcher import TaskSearcher
from openai import OpenAI


def main():
    # Создание клиента OpenAI (тот же, что в Interactor)
    client = OpenAI(
        api_key="sk-EntOXD173KXh0i-jb0esww",
        base_url="https://llm.t1v.scibox.tech/v1"
    )
    
    # Создание поисковика задач с клиентом
    searcher = TaskSearcher(client=client, model_name="bge-m3")
    
    # Добавление задач из JSON
    tasks_json = [
        {
            "индекс": 1,
            "условие": "Дано число n",
            "описание": "Реализовать функцию для вычисления факториала числа n"
        },
        {
            "index": 2,
            "condition": "Дан массив целых чисел",
            "description": "Написать алгоритм сортировки пузырьком для массива целых чисел"
        },
        {
            "task_index": 3,
            "task_condition": "Реализовать структуру данных",
            "task_description": "Создать класс для работы с бинарным деревом поиска"
        },
    ]
    
    # Добавление задач из JSON
    print("Добавление задач из JSON...")
    searcher.add_tasks_from_json(tasks_json)
    
    # Добавление одной задачи из JSON
    single_task_json = {
        "индекс": 4,
        "условие": "Реализовать структуру данных стек",
        "описание": "Реализовать стек на основе массива с операциями push и pop"
    }
    searcher.add_task_from_json(single_task_json)
    
    # Также можно добавлять задачи старым способом (для обратной совместимости)
    searcher.add_task(5, "Написать функцию для поиска наибольшего общего делителя двух чисел")
    
    print(f"Добавлено задач: {searcher.get_task_count()}\n")
    
    # Демонстрация удаления задачи
    print("Удаление задачи с индексом 5...")
    removed = searcher.remove_task(5)
    if removed:
        print(f"Задача удалена. Осталось задач: {searcher.get_task_count()}\n")
    
    # Демонстрация добавления новой задачи
    print("Добавление новой задачи...")
    searcher.add_task(11, "Реализовать алгоритм поиска в ширину (BFS) для графа")
    print(f"Добавлена новая задача. Всего задач: {searcher.get_task_count()}\n")
    
    # Примеры поиска
    queries = [
        "Рекомендуется начать с базовых задач по массивам, поискам и структурам данных (например, хэш-таблицы, деревья), а также изучение паттернов управления состоянием в React.",
    ]
    
    for query in queries:
        print(f"Запрос: '{query}'")
        print("-" * 60)
        results = searcher.search(query, top_k=3)
        
        for i, (task_index, condition, description, similarity) in enumerate(results, 1):
            print(f"{i}. Задача #{task_index}:")
            if condition:
                print(f"   Условие: {condition}")
            print(f"   Описание: {description}")
            print(f"   Сходство: {similarity:.4f}\n")
        print()
    
    # Демонстрация полного очищения базы данных
    print("Очищение базы данных...")
    searcher.clear()
    print(f"База данных очищена. Осталось задач: {searcher.get_task_count()}")


if __name__ == "__main__":
    main()

