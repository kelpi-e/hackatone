import os
import json
import subprocess
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import UserRegistrationForm, UserLoginForm
from .models import User
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


@login_required(login_url='/login/')
def index(request):
    # Редактор доступен только для авторизованных пользователей
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
            "tests_passed": None,
            "test_results": [],
            "test_mode": False
        }
    )


@login_required(login_url='/login/')
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
    test_results = []
    test_mode = mode == "run_tests"

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
        # Добавляем в лог
        with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
            log.write("\n=== Предупреждение о подозрительном коде ===\n")
            log.write(warning_msg)
            log.write("=========================\n")
        # Добавляем предупреждение только в обычный вывод, не в тесты
        if not test_mode:
            output = warning_msg + "\n" + output

    # ------------------------------
    # Прогон тестов
    # ------------------------------
    if test_mode:
        json_file = selected.replace(".txt", ".json")
        json_path = os.path.join(TASKS_DIR, json_file)

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    tests = json.load(f)
            except Exception as e:
                tests = []
                output += f"Ошибка чтения тестов: {e}\n"

            passed = 0

            for i, test in enumerate(tests, start=1):
                test_input = " ".join(str(x) for x in test.get("input", []))
                expected = str(test.get("expected", "")).strip()

                test_result = {
                    "number": i,
                    "input": test_input,
                    "expected": expected,
                    "actual": "",
                    "error": "",
                    "passed": False,
                    "timeout": False
                }

                try:
                    res = subprocess.run(
                        ["python3", temp],
                        input=test_input,
                        capture_output=True,
                        text=True,
                        timeout=5
                    )

                    actual = res.stdout.strip()
                    err = res.stderr.strip()
                    ok = (actual == expected) and not err

                    test_result["actual"] = actual
                    test_result["error"] = err
                    test_result["passed"] = ok

                    if ok:
                        passed += 1

                except subprocess.TimeoutExpired:
                    test_result["timeout"] = True

                test_results.append(test_result)

            tests_passed = f"{passed} / {len(tests)}"

            # Добавляем результаты тестов в лог
            try:
                with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
                    log.write("\n=== Результаты тестов ===\n")
                    for result in test_results:
                        if result["passed"]:
                            log.write(f"Тест {result['number']}: ✓\n")
                        elif result["timeout"]:
                            log.write(f"Тест {result['number']}: ✗ (таймаут)\n")
                        elif result["error"]:
                            log.write(f"Тест {result['number']}: ✗ (ошибка)\n{result['error']}\n")
                        else:
                            log.write(f"Тест {result['number']}: ✗ (неверный результат)\n")
                    log.write(f"Итог: {passed} / {len(tests)}\n")
                    log.write("=========================\n")
            except:
                pass

        else:
            test_results = []
            tests_passed = None

    # ------------------------------
    # Обычный запуск с пользовательским вводом
    # ------------------------------
    else:
        try:
            res = subprocess.run(
                ["python3", temp],
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
            "tests_passed": tests_passed,
            "test_results": test_results,
            "test_mode": test_mode
        }
    )


def register(request):
    """Регистрация нового пользователя"""
    if request.user.is_authenticated:
        return redirect('runcode')
    
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='codeapp.backends.UsernameOnlyBackend')
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('runcode')
    else:
        form = UserRegistrationForm()
    
    return render(request, 'codeapp/auth.html', {
        'form': form,
        'form_type': 'register',
        'title': 'Регистрация'
    })


def user_login(request):
    """Вход пользователя (только по никнейму)"""
    if request.user.is_authenticated:
        return redirect('runcode')
    
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            try:
                user = User.objects.get(username=username)
                # Вход без проверки пароля (только по никнейму)
                login(request, user, backend='codeapp.backends.UsernameOnlyBackend')
                messages.success(request, f'Добро пожаловать, {user.username}!')
                return redirect('runcode')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь с таким никнеймом не найден.')
    else:
        form = UserLoginForm()
    
    return render(request, 'codeapp/auth.html', {
        'form': form,
        'form_type': 'login',
        'title': 'Вход'
    })


def user_logout(request):
    """Выход пользователя"""
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы.')
    return redirect('home')
