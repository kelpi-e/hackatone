import os
import subprocess
from django.shortcuts import render
from django.conf import settings

TASKS_DIR = os.path.join(settings.BASE_DIR, "codeapp", "tests")  # папка с описаниями задач


def index(request):
    tasks_dir = os.path.join(os.path.dirname(__file__), "tests")
    tasks = [f for f in os.listdir(tasks_dir) if f.endswith(".txt")]
    selected_task = request.GET.get("task", tasks[0] if tasks else None)

    task_text = ""
    if selected_task:
        with open(os.path.join(tasks_dir, selected_task), encoding="utf-8") as f:
            task_text = f.read()

    return render(request, "codeapp/index.html", {
        "tasks": tasks,
        "selected_task": selected_task,
        "task_text": task_text,
        "code": "",
        "output": ""
    })

def run_code(request):
    code = request.POST.get("code", "")
    temp_file = os.path.join(settings.BASE_DIR, "temp_code.py")

    # Сохраняем код пользователя
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)

    try:
        # Запускаем Docker контейнер с анализом
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
        output = result.stdout + "\n" + result.stderr
    except Exception as e:
        output = f"Ошибка при запуске контейнера: {e}"

    # Подгружаем текст задачи
    tasks = [f for f in os.listdir(TASKS_DIR) if f.endswith(".txt")]
    selected_task = request.POST.get("task", tasks[0] if tasks else None)
    task_text = ""
    if selected_task:
        task_path = os.path.join(TASKS_DIR, selected_task)
        if os.path.exists(task_path):
            with open(task_path, "r", encoding="utf-8") as f:
                task_text = f.read()

    return render(request, "codeapp/index.html", {
        "code": code,
        "output": output,
        "tasks": tasks,
        "selected_task": selected_task,
        "task_text": task_text
    })
