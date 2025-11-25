from django.shortcuts import render, redirect
import os
import subprocess
from django.shortcuts import render
from django.conf import settings

TASKS_DIR = os.path.join(settings.BASE_DIR, "codeapp", "tests")


def get_task_list():
    """Возвращает список .txt файлов в папке tests"""
    if not os.path.exists(TASKS_DIR):
        return []
    return [f for f in os.listdir(TASKS_DIR) if f.endswith(".txt")]


def get_task_text(selected_task):
    """Читает и возвращает содержимое выбранной задачи"""
    if not selected_task:
        return ""
    task_path = os.path.join(TASKS_DIR, selected_task)
    if not os.path.exists(task_path):
        return f"Файл не найден: {selected_task}"
    try:
        with open(task_path, encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Ошибка чтения файла: {e}"


def index(request):
    """Главная страница + смена задачи (GET)"""
    tasks = get_task_list()
    selected_task = request.GET.get("task") or (tasks[0] if tasks else None)
    task_text = get_task_text(selected_task)

    context = {
        "tasks": tasks,
        "selected_task": selected_task,
        "task_text": task_text,
        "code": "",
        "output": "",
    }
    return render(request, "codeapp/index.html", context)


def run_code(request):
    """Выполнение кода (POST)"""
    if request.method != "POST":
        return redirect("index")  # если кто-то зайдёт по GET — редиректим

    code = request.POST.get("code", "")
    selected_task = request.POST.get("task")  # из hidden поля

    # Сохраняем код во временный файл
    temp_file = os.path.join(settings.BASE_DIR, "temp_code.py")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)

    # Запуск в Docker
    try:
        result = subprocess.run(
            [
                "docker", "run", "--rm",
                "-v", f"{temp_file}:/usr/src/app/temp_code.py",
                "python-analyzer",
                "temp_code.py"
            ],
            capture_output=True,
            text=True,
            timeout=20
        )
        output = result.stdout + ("\n" + result.stderr if result.stderr else "")
    except subprocess.TimeoutExpired:
        output = "Ошибка: Превышено время выполнения (20 сек)"
    except Exception as e:
        output = f"Ошибка запуска контейнера: {e}"

    # Снова готовим контекст
    tasks = get_task_list()
    task_text = get_task_text(selected_task)

    context = {
        "tasks": tasks,
        "selected_task": selected_task,
        "task_text": task_text,
        "code": code,
        "output": output,
    }
    return render(request, "codeapp/index.html", context)