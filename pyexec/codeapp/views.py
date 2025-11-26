import os
import json
import subprocess
from django.shortcuts import render, redirect
from django.conf import settings
import unicodedata

TASKS_DIR = os.path.join(settings.BASE_DIR, "codeapp", "tests")
ANALYSIS_LOG = os.path.join(settings.BASE_DIR, "code_analysis.log")

# Символы, часто появляющиеся при копипасте или генерации ИИ
SUSPICIOUS_CHARS = {
    "\u00A0": "NBSP",
    "\u200B": "ZERO WIDTH SPACE",
    "\u200C": "ZERO WIDTH NON-JOINER",
    "\u200D": "ZERO WIDTH JOINER",
    "\u2060": "WORD JOINER",
    "\ufeff": "BOM",
    "\u2013": "EN DASH",
    "\u2014": "EM DASH",
    "\u2018": "LEFT SINGLE QUOTE",
    "\u2019": "RIGHT SINGLE QUOTE",
    "\u201C": "LEFT DOUBLE QUOTE",
    "\u201D": "RIGHT DOUBLE QUOTE",
}

def home(request):
    return render(request, "index.html")


def get_task_list():
    if not os.path.exists(TASKS_DIR):
        return []
    return [f for f in os.listdir(TASKS_DIR) if f.endswith(".txt")]


def get_task_text(task_file):
    if not task_file:
        return ""
    full = os.path.join(TASKS_DIR, task_file)
    if not os.path.exists(full):
        return f"Файл не найден: {task_file}"
    with open(full, encoding="utf-8") as f:
        return f.read()


def check_suspicious_code(code_text):
    """Проверяет код на невидимые и подозрительные символы"""
    found = []
    for i, ch in enumerate(code_text):
        if ch in SUSPICIOUS_CHARS:
            found.append((i+1, SUSPICIOUS_CHARS[ch]))
        elif ord(ch) > 127 and ch not in SUSPICIOUS_CHARS:
            found.append((i+1, f"UNEXPECTED CHAR {unicodedata.name(ch, '?')}"))
    return found


def index(request):
    # Уже правильно: рендерит ide.html как редактор
    tasks = get_task_list()
    selected = request.GET.get("task") or (tasks[0] if tasks else None)
    text = get_task_text(selected)

    return render(
        request,
        "codeapp/ide.html",  # Или просто "ide.html", если в templates/codeapp/
        {
            "tasks": tasks,
            "selected_task": selected,
            "task_text": text,
            "code": "",
            "output": "",
            "input_data": "",
            "tests_passed": None
        }
    )


def run_code(request):
    if request.method != "POST":
        return redirect("runcode")

    code = request.POST.get("code", "")
    selected = request.POST.get("task")
    mode = request.POST.get("mode", "run_code")
    user_input = request.POST.get("input_data", "")

    temp = os.path.join(settings.BASE_DIR, "temp_code.py")
    with open(temp, "w", encoding="utf-8") as f:
        f.write(code)

    output = ""
    tests_passed = None

    # ------------------------------
    # Статический анализ через docker
    # ------------------------------
    try:
        with open(ANALYSIS_LOG, "w", encoding="utf-8") as log:
            subprocess.run(
                ["docker", "run", "--rm",
                 "-v", f"{temp}:/usr/src/app/temp_code.py",
                 "python-analyzer",
                 "temp_code.py"],
                stdout=log,
                stderr=log,
                text=True,
                timeout=5
            )
    except Exception as e:
        with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
            log.write(f"Ошибка анализа: {e}\n")

    # ------------------------------
    # Проверка на подозрительные символы
    # ------------------------------
    suspicious = check_suspicious_code(code)
    if suspicious:
        warning_msg = "Подозрительные символы или возможный код ИИ/копипаста обнаружены:\n"
        for pos, desc in suspicious:
            warning_msg += f"позиция {pos}: {desc}\n"
        # Добавляем в лог и выводим на экран
        with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
            log.write("\n=== Предупреждение о подозрительном коде ===\n")
            log.write(warning_msg)
            log.write("=========================\n")
        output = warning_msg + "\n" + output

    # ------------------------------
    # Прогон тестов
    # ------------------------------
    if mode == "run_tests":
        json_file = selected.replace(".txt", ".json")
        json_path = os.path.join(TASKS_DIR, json_file)

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    tests = json.load(f)
            except Exception as e:
                tests = []
                output += f"Ошибка чтения тестов: {e}\n"

            logs = []
            passed = 0

            for i, test in enumerate(tests, start=1):
                test_input = " ".join(str(x) for x in test.get("input", []))
                expected = str(test.get("expected", "")).strip()

                try:
                    res = subprocess.run(
                        ["python", temp],
                        input=test_input,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    actual = res.stdout.strip()
                    err = res.stderr.strip()
                    ok = (actual == expected) and not err

                    if ok:
                        passed += 1
                        logs.append(f"Тест {i}: ✓")
                    else:
                        if err:
                            logs.append(f"Тест {i}: ✗ (ошибка)\n{err}")
                        else:
                            logs.append(f"Тест {i}: ✗ (неверный результат)")

                except subprocess.TimeoutExpired:
                    logs.append(f"Тест {i}: ✗ (таймаут)")

            output += "\n" + "\n".join(logs)
            tests_passed = f"{passed} / {len(tests)}"

            # Добавляем результаты тестов в лог
            try:
                with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
                    log.write("\n=== Результаты тестов ===\n")
                    for line in logs:
                        log.write(line + "\n")
                    log.write(f"Итог: {passed} / {len(tests)}\n")
                    log.write("=========================\n")
            except:
                pass

        else:
            output += f"\nФайл тестов {json_file} не найден."

    # ------------------------------
    # Обычный запуск с пользовательским вводом
    # ------------------------------
    else:
        try:
            res = subprocess.run(
                ["python", temp],
                input=user_input,
                capture_output=True,
                text=True,
                timeout=5
            )
            output += res.stdout + ("\n" + res.stderr if res.stderr else "")
        except subprocess.TimeoutExpired:
            output += "Ошибка: таймаут"
        except Exception as e:
            output += f"Ошибка запуска: {e}"

    return render(
        request,
        "codeapp/ide.html",
        {
            "tasks": get_task_list(),
            "selected_task": selected,
            "task_text": get_task_text(selected),
            "code": code,
            "output": output,
            "input_data": user_input,
            "tests_passed": tests_passed
        }
    )
