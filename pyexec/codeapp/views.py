import os
import json
import subprocess
import unicodedata
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.conf import settings

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
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('runcode')
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})

def user_login(request):
    if request.method == "POST":
        form = AuthenticationForm(data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('runcode')
    else:
        form = AuthenticationForm()
    return render(request, "registration/login.html", {"form": form})

def user_logout(request):
    logout(request)
    return redirect('home')

# =============================================================================
# Основные страницы
# =============================================================================
def home(request):
    return render(request, "index.html")

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
    })

# =============================================================================
# Главная функция — запуск и тестирование кода (Python + C++)
# =============================================================================
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
                            ["python", src_path],
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
                output += f"Ошибка тестов: {e}"

    # === Обычный запуск (Python или скомпилированный C++) ===
    if not test_mode and not compile_error:
        try:
            cmd = ["python", src_path] if language == "Python" else [exe_path]
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
    return render(request, "codeapp/ide.html", {
        "tasks": get_task_list(),
        "selected_task": selected_task,
        "task_text": get_task_text(selected_task),
        "code": code,
        "output": output or "Готово!",
        "input_data": user_input,
        "tests_passed": tests_passed,
        "test_results": test_results,
        "test_mode": test_mode,
        "language": language,
    })