import sys
import subprocess

if len(sys.argv) < 2:
    print("No code file provided")
    sys.exit(1)

CODE_FILE = sys.argv[1]

print("=== OUTPUT ===")
try:
    # Выполняем код пользователя
    result = subprocess.run(
        ["python", CODE_FILE],
        capture_output=True,
        text=True,
        timeout=5
    )
    print(result.stdout)
    print(result.stderr)
except Exception as e:
    print(f"Error running code: {e}")

# Статический анализ
for tool in ["pylint", "mypy", "bandit"]:
    print(f"\n=== {tool.upper()} ===")
    try:
        subprocess.run([tool, CODE_FILE])
    except Exception as e:
        print(f"{tool} error: {e}")
