import os
import json
import subprocess
from django.shortcuts import render, redirect
from django.conf import settings

TASKS_DIR = os.path.join(settings.BASE_DIR, "codeapp", "tests")
ANALYSIS_LOG = os.path.join(settings.BASE_DIR, "code_analysis.log")


def home(request):
    return render(request, "index.html")


def get_task_list():
    """Возвращает список задач по .txt файлам"""
    if not os.path.exists(TASKS_DIR):
        return []
    return [f for f in os.listdir(TASKS_DIR) if f.endswith(".txt")]


def get_task_text(task_file):
    """Читает текст задачи из .txt"""
    if not task_file:
        return ""
    path = os.path.join(TASKS_DIR, task_file)
    if not os.path.exists(path):
        return f"Файл не найден: {task_file}"
    with open(path, encoding="utf-8") as f:
        return f.read()


def index(request):
    tasks = get_task_list()
    selected_task = request.GET.get("task") or (tasks[0] if tasks else None)
    task_text = get_task_text(selected_task)
    context = {
        "tasks": tasks,
        "selected_task": selected_task,
        "task_text": task_text,
        "code": "",
        "output": "",
        "input_data": "",
        "tests_passed": None
    }
    return render(request, "codeapp/index.html", context)


def run_code(request):
    if request.method != "POST":
        return redirect("index")

    code = request.POST.get("code", "")
    selected_task = request.POST.get("task")
    mode = request.POST.get("mode", "run_code")
    input_data = request.POST.get("input_data", "")

    temp_file = os.path.join(settings.BASE_DIR, "temp_code.py")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)

    output = ""
    tests_passed = None

    # Запуск статического анализа в фоне и запись в файл
    try:
        with open(ANALYSIS_LOG, "w", encoding="utf-8") as log_file:
            subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{temp_file}:/usr/src/app/temp_code.py",
                    "python-analyzer",
                    "temp_code.py"
                ],
                stdout=log_file,
                stderr=log_file,
                text=True,
                timeout=20
            )
    except Exception as e:
        with open(ANALYSIS_LOG, "a", encoding="utf-8") as log_file:
            log_file.write(f"Ошибка статического анализа: {e}\n")

    # Прогон по тестам
    if mode == "run_tests":
        json_file = selected_task.replace(".txt", ".json")
        json_path = os.path.join(TASKS_DIR, json_file)
        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    tests = json.load(f)
            except Exception as e:
                output = f"Ошибка чтения файла тестов: {e}"
                tests = []

            passed_count = 0
            test_outputs = []

            for idx, test in enumerate(tests, 1):
                test_input = "\n".join(map(str, test.get("input", [])))
                expected_output = str(test.get("expected", "")).strip()
                try:
                    result = subprocess.run(
                        ["python", temp_file],
                        input=test_input,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    actual_output = result.stdout.strip()
                    error_output = result.stderr.strip()
                    passed = actual_output == expected_output and not error_output
                    if passed:
                        passed_count += 1

                    if error_output:
                        test_outputs.append(f"Тест {idx}: Ошибка\n{error_output}")
                    else:
                        test_outputs.append(f"Тест {idx}: {actual_output}")

                except subprocess.TimeoutExpired:
                    test_outputs.append(f"Тест {idx}: Превышено время выполнения")

            output = "\n".join(test_outputs)
            tests_passed = f"{passed_count} / {len(tests)} тестов пройдено"
        else:
            output = f"Файл тестов {json_file} не найден."

    else:  # обычный запуск с пользовательскими данными
        try:
            result = subprocess.run(
                ["python", temp_file],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=10
            )
            output = result.stdout + ("\n" + result.stderr if result.stderr else "")
        except subprocess.TimeoutExpired:
            output = "Ошибка: Превышено время выполнения (10 сек)"
        except Exception as e:
            output = f"Ошибка запуска кода: {e}"

    context = {
        "tasks": get_task_list(),
        "selected_task": selected_task,
        "task_text": get_task_text(selected_task),
        "code": code,
        "output": output,
        "input_data": input_data,
        "tests_passed": tests_passed
    }
    return render(request, "codeapp/index.html", context)
