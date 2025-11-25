import subprocess
import os
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def run_code(request):
    output = ""
    code = ""
    if request.method == "POST":
        code = request.POST.get("code", "")
        filename = os.path.join(os.path.dirname(__file__), "temp_code.py")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(code)
        try:
            result = subprocess.run(
                ["python", filename],
                capture_output=True,
                text=True,
                timeout=5
            )
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            output = "Превышено время выполнения!"
        except Exception as e:
            output = f"Ошибка при запуске кода: {str(e)}"

    return render(request, "codeapp/index.html", {"code": code, "output": output})

