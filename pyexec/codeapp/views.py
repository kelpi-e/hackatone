import os
import json
import subprocess
import unicodedata
import shutil
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .forms import UserRegistrationForm, UserLoginForm
from .models import User

# =============================================================================
# Пути и настройки
# =============================================================================
TASKS_DIR = os.path.join(settings.BASE_DIR, "codeapp", "tests")
ANALYSIS_LOG = os.path.join(settings.BASE_DIR, "code_analysis.log")
TEMP_DIR = os.path.join(settings.BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Подозрительные символы (ИИ/копипаста)
SUSPICIOUS_CHARS = {
    "\u00A0": "NBSP", "\u200B": "ZERO WIDTH SPACE", "\u200C": "ZERO WIDTH NON-JOINER",
    "\u200D": "ZERO WIDTH JOINER", "\u2060": "WORD JOINER", "\ufeff": "BOM",
    "\u2013": "EN DASH", "\u2014": "EM DASH", "\u2018": "LEFT SINGLE QUOTE",
    "\u2019": "RIGHT SINGLE QUOTE", "\u201C": "LEFT DOUBLE QUOTE", "\u201D": "RIGHT DOUBLE QUOTE",
}

# =============================================================================
# Вспомогательные функции
# =============================================================================
def get_python_command():
    """
    Определяет доступную команду Python (python или python3).
    Возвращает 'python3' если доступен, иначе 'python'.
    """
    # Кэшируем результат, чтобы не проверять каждый раз
    if not hasattr(get_python_command, '_cached'):
        # Проверяем python3 сначала (чаще доступен на Mac/Linux)
        if shutil.which('python3'):
            get_python_command._cached = 'python3'
        elif shutil.which('python'):
            get_python_command._cached = 'python'
        else:
            # Fallback на python3, если ничего не найдено
            get_python_command._cached = 'python3'
    return get_python_command._cached

def get_task_list():
    if not os.path.exists(TASKS_DIR):
        return []
    return sorted(f for f in os.listdir(TASKS_DIR) if f.endswith(".txt"))

def get_task_text(task_file):
    if not task_file:
        return ""
    path = os.path.join(TASKS_DIR, task_file)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "Ошибка чтения задачи"

def check_suspicious_code(code_text):
    found = []
    for i, ch in enumerate(code_text):
        if ch in SUSPICIOUS_CHARS:
            found.append((i+1, SUSPICIOUS_CHARS[ch]))
        elif ord(ch) > 127 and ch not in SUSPICIOUS_CHARS:
            found.append((i+1, f"UNEXPECTED CHAR {unicodedata.name(ch, '?')}"))
    return found

# =============================================================================
# Авторизация
# =============================================================================
def register(request):
    if request.user.is_authenticated:
        return redirect('runcode')
    
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Явно указываем backend для логина
            login(request, user, backend='codeapp.backends.UsernameOnlyBackend')
            messages.success(request, f'Добро пожаловать, {user.username}!')
            return redirect('runcode')
    else:
        form = UserRegistrationForm()
    return render(request, "codeapp/auth.html", {
        "form": form, 
        "form_type": "register",
        "title": "Регистрация"
    })

def user_login(request):
    if request.user.is_authenticated:
        return redirect('runcode')
    
    if request.method == "POST":
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            try:
                user = User.objects.get(username=username)
                # Явно указываем backend для логина
                login(request, user, backend='codeapp.backends.UsernameOnlyBackend')
                messages.success(request, f'Добро пожаловать, {user.username}!')
                return redirect('runcode')
            except User.DoesNotExist:
                messages.error(request, 'Пользователь с таким никнеймом не найден.')
        else:
            messages.error(request, 'Ошибка входа. Проверьте введенные данные.')
    else:
        form = UserLoginForm()
    return render(request, "codeapp/auth.html", {
        "form": form,
        "form_type": "login",
        "title": "Вход"
    })

def user_logout(request):
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы.')
    return redirect('home')

# =============================================================================
# Основные страницы
# =============================================================================
def home(request):
    return render(request, "index.html")

@login_required
def index(request):
    tasks = get_task_list()
    selected = request.GET.get("task") or (tasks[0] if tasks else None)
    language = request.GET.get("language", "Python")
    return render(request, "codeapp/ide.html", {
        "tasks": tasks,
        "selected_task": selected,
        "task_text": get_task_text(selected),
        "code": "",
        "output": "",
        "input_data": "",
        "tests_passed": None,
        "test_results": [],
        "test_mode": False,
        "language": language,
        "code_executed": False,  # Код еще не был запущен
    })

# =============================================================================
# Главная функция — запуск и тестирование кода (Python + C++)
# =============================================================================
@login_required
def run_code(request):
    if request.method != "POST":
        return redirect("runcode")

    code = request.POST.get("code", "")
    selected_task = request.POST.get("task", "")
    mode = request.POST.get("mode", "run_code")
    user_input = request.POST.get("input_data", "").strip()
    language = request.POST.get("language", "Python")

    test_mode = mode == "run_tests"
    output = ""
    tests_passed = None
    test_results = []

    # Определяем расширения и пути
    src_ext = "py" if language == "Python" else "cpp"
    src_path = os.path.join(TEMP_DIR, f"temp_code.{src_ext}")
    exe_path = os.path.join(TEMP_DIR, "temp_code.exe" if os.name == "nt" else "temp_code")

    # Сохраняем код
    with open(src_path, "w", encoding="utf-8") as f:
        f.write(code)

    # === Лог ===
    with open(ANALYSIS_LOG, "w", encoding="utf-8") as log:
        log.write(f"=== Запуск: {language} | Задача: {selected_task or '—'} | "
                  f"Режим: {'Тесты' if test_mode else 'Ручной ввод'} ===\n\n")

    # === Проверка на подозрительные символы ===
    suspicious = check_suspicious_code(code)
    if suspicious:
        warning = "Обнаружены подозрительные символы (возможно, код от ИИ или копипаста):\n"
        for pos, name in suspicious:
            warning += f"  → позиция {pos}: {name}\n"
        with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
            log.write("ПРЕДУПРЕЖДЕНИЕ: подозрительный код\n" + warning + "\n")
        # Предупреждения показываем только в режиме ручного запуска
        if not test_mode:
            output += warning + "\n"

    # === C++: статический анализ и компиляция ===
    compile_error = None
    if language == "C++":
        # cppcheck
        try:
            result = subprocess.run(
                ["cppcheck", "--enable=all", "--suppress=missingIncludeSystem", "--quiet", src_path],
                capture_output=True, text=True, timeout=10
            )
            report = result.stderr.strip() or "Статических ошибок не найдено."
            report = report.replace(src_path, "ваш код")
            with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
                log.write("cppcheck:\n" + report + "\n\n")
        except FileNotFoundError:
            with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
                log.write("cppcheck не установлен\n")

        # Компиляция
        compile_cmd = ["g++", src_path, "-o", exe_path, "-std=c++17", "-O2", "-Wall"]
        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            compile_error = result.stderr.strip() or "Ошибка компиляции"
            # Ошибки компиляции показываем только в режиме ручного запуска
            if not test_mode:
                output += f"Ошибка компиляции:\n{compile_error}\n"
            with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
                log.write(f"Ошибка g++:\n{compile_error}\n\n")

    # === Запуск тестов (только Python и только если нет ошибок компиляции) ===
    if test_mode and not compile_error and language == "Python":
        json_file = selected_task.replace(".txt", ".json") if selected_task else None
        json_path = os.path.join(TASKS_DIR, json_file) if json_file else None

        if json_path and os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    tests = json.load(f)
                passed = 0
                for i, test in enumerate(tests, 1):
                    test_input = " ".join(map(str, test.get("input", [])))
                    expected = str(test.get("expected", "")).strip()

                    try:
                        res = subprocess.run(
                            [get_python_command(), src_path],
                            input=test_input + "\n",
                            capture_output=True,
                            text=True,
                            timeout=5
                        )
                        actual = res.stdout.strip()
                        ok = actual == expected and not res.stderr.strip()

                        test_results.append({
                            "number": i,
                            "input": test_input,
                            "expected": expected,
                            "actual": actual,
                            "error": res.stderr.strip(),
                            "passed": ok,
                            "timeout": False
                        })
                        if ok:
                            passed += 1
                    except subprocess.TimeoutExpired:
                        test_results.append({"number": i, "timeout": True, "passed": False})
                tests_passed = f"{passed}/{len(tests)}"
            except Exception as e:
                # Ошибки тестов не добавляем в output, они отображаются во вкладке "Тест-кейсы"
                # Но логируем для отладки
                with open(ANALYSIS_LOG, "a", encoding="utf-8") as log:
                    log.write(f"Ошибка тестов: {e}\n")
                # Добавляем в test_results для отображения
                test_results.append({
                    "number": 0,
                    "input": "",
                    "expected": "",
                    "actual": "",
                    "error": f"Ошибка запуска тестов: {e}",
                    "passed": False,
                    "timeout": False
                })

    # === Обычный запуск (Python или скомпилированный C++) ===
    if not test_mode and not compile_error:
        try:
            cmd = [get_python_command(), src_path] if language == "Python" else [exe_path]
            proc = subprocess.run(
                cmd,
                input=user_input.replace("\r\n", "\n") + "\n",
                capture_output=True,
                text=True,
                timeout=7
            )
            output += proc.stdout
            if proc.stderr:
                output += "\nОшибка:\n" + proc.stderr
        except subprocess.TimeoutExpired:
            output += "Таймаут выполнения (7 сек)"
        except Exception as e:
            output += f"Ошибка запуска: {e}"

    # === Valgrind для C++ (только в ручном режиме) ===
    if language == "C++" and not compile_error and not test_mode and os.name != "nt":  # valgrind только Linux/macOS
        try:
            vg = subprocess.run(["valgrind", "--leak-check=full", "--error-exitcode=1", exe_path],
                                capture_output=True, text=True, timeout=8)
            if "definitely lost" in vg.stderr.lower():
                output += "\nУТЕЧКИ ПАМЯТИ ОБНАРУЖЕНЫ!"
            else:
                output += "\nУтечек памяти не обнаружено."
        except FileNotFoundError:
            pass

    # === Очистка временных файлов ===
    for path in (src_path, exe_path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass

    # === Ответ ===
    # В режиме тестов output должен быть пустым (или содержать только ошибки компиляции для C++)
    # Все результаты тестов отображаются во вкладке "Тест-кейсы"
    # Если код был запущен, но ничего не вывел - это нормально, показываем пустую строку
    
    return render(request, "codeapp/ide.html", {
        "tasks": get_task_list(),
        "selected_task": selected_task,
        "task_text": get_task_text(selected_task),
        "code": code,
        "output": output,  # Может быть пустым, если код ничего не вывел - это нормально
        "input_data": user_input,
        "tests_passed": tests_passed,
        "test_results": test_results,
        "test_mode": test_mode,
        "language": language,
        "code_executed": True,  # Флаг, что код был запущен
    })