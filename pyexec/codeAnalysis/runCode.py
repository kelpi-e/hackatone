#!/usr/bin/env python3
"""
Скрипт для запуска и анализа кода в Docker-контейнере.
Поддерживает Python и C++.
"""

import sys
import subprocess
import os
import json

def run_command(cmd, timeout=30, input_data=None):
    """Запускает команду и возвращает результат."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            input=input_data
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Таймаут выполнения", "returncode": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1}


def analyze_python(code_file):
    """Анализирует Python-код."""
    results = {}
    
    # pylint
    r = run_command(["pylint", "--disable=R,C", "--output-format=text", code_file])
    results["pylint"] = r["stdout"] or r["stderr"] or "Ошибок не найдено"
    
    # mypy
    r = run_command(["mypy", "--ignore-missing-imports", code_file])
    results["mypy"] = (r["stdout"] + r["stderr"]).strip() or "Ошибок не найдено"
    
    # bandit
    r = run_command(["bandit", "-q", "-r", code_file])
    results["bandit"] = (r["stdout"] + r["stderr"]).strip() or "Уязвимостей не найдено"
    
    return results


def analyze_cpp(code_file, exe_file="/tmp/a.out"):
    """Анализирует C++-код."""
    results = {}
    
    # cppcheck
    r = run_command(["cppcheck", "--enable=all", "--inconclusive", "--std=c++17", code_file])
    results["cppcheck"] = r["stderr"] or "Ошибок не найдено"
    
    # g++ compile with warnings
    r = run_command(["g++", "-Wall", "-Wextra", "-std=c++17", code_file, "-o", exe_file])
    results["g++"] = r["stderr"] or "Предупреждений нет"
    results["compile_success"] = r["returncode"] == 0
    
    return results


def run_python(code_file, input_data="", timeout=5):
    """Запускает Python-код."""
    return run_command(["python3", code_file], timeout=timeout, input_data=input_data)


def run_cpp(exe_file, input_data="", timeout=5):
    """Запускает скомпилированный C++-код."""
    if not os.path.exists(exe_file):
        return {"stdout": "", "stderr": "Исполняемый файл не найден", "returncode": -1}
    return run_command([exe_file], timeout=timeout, input_data=input_data)


def run_tests(code_file, tests, language, exe_file="/tmp/a.out"):
    """Запускает тесты для кода."""
    results = []
    passed = 0
    
    for i, test in enumerate(tests, 1):
        test_input = " ".join(map(str, test.get("input", [])))
        expected = str(test.get("expected", "")).strip()
        
        if language == "Python":
            r = run_python(code_file, test_input + "\n", timeout=5)
        else:
            r = run_cpp(exe_file, test_input + "\n", timeout=5)
        
        actual = r["stdout"].strip()
        error = r["stderr"].strip()
        timeout_flag = "Таймаут" in error
        ok = actual == expected and not error
        
        results.append({
            "number": i,
            "input": test_input,
            "expected": expected,
            "actual": actual,
            "error": error,
            "passed": ok,
            "timeout": timeout_flag
        })
        
        if ok:
            passed += 1
    
    return results, f"{passed}/{len(tests)}"


def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: runCode.py <mode> <code_file> [options]"}))
        sys.exit(1)
    
    mode = sys.argv[1]  # analyze, run, test
    code_file = sys.argv[2]
    language = sys.argv[3] if len(sys.argv) > 3 else "Python"
    
    exe_file = "/tmp/a.out"
    
    result = {
        "success": True,
        "language": language,
        "mode": mode
    }
    
    # Для C++ сначала компилируем
    if language == "C++":
        compile_result = run_command(["g++", "-std=c++17", "-O2", "-Wall", code_file, "-o", exe_file])
        if compile_result["returncode"] != 0:
            result["compile_error"] = compile_result["stderr"]
            result["success"] = False
    
    if mode == "analyze":
        # Только анализ
        if language == "Python":
            result["analysis"] = analyze_python(code_file)
        else:
            result["analysis"] = analyze_cpp(code_file, exe_file)
    
    elif mode == "run":
        # Запуск с вводом
        input_data = sys.argv[4] if len(sys.argv) > 4 else ""
        if language == "Python":
            r = run_python(code_file, input_data, timeout=7)
        else:
            if result.get("success", True):
                r = run_cpp(exe_file, input_data, timeout=7)
            else:
                r = {"stdout": "", "stderr": result.get("compile_error", ""), "returncode": -1}
        result["output"] = r["stdout"]
        result["error"] = r["stderr"]
    
    elif mode == "test":
        # Запуск тестов
        tests_json = sys.argv[4] if len(sys.argv) > 4 else "[]"
        try:
            tests = json.loads(tests_json)
        except:
            tests = []
        
        if result.get("success", True) or language == "Python":
            test_results, tests_passed = run_tests(code_file, tests, language, exe_file)
            result["test_results"] = test_results
            result["tests_passed"] = tests_passed
        else:
            result["test_results"] = []
            result["tests_passed"] = "0/0"
        
        # Также запускаем анализ
        if language == "Python":
            result["analysis"] = analyze_python(code_file)
        else:
            result["analysis"] = analyze_cpp(code_file, exe_file)
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
