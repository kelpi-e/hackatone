FROM python:3.13-slim

WORKDIR /usr/src/app

# Устанавливаем анализаторы
RUN pip install pylint mypy bandit

# Копируем скрипт, который будет запускать код
COPY runCode.py /usr/src/app/runCode.py

# ENTRYPOINT будет запускать runCode.py с аргументом (файл кода)
ENTRYPOINT ["python", "runCode.py"]
