FROM python:3.13-slim

WORKDIR /usr/src/app

# Устанавливаем анализаторы Python
RUN pip install pylint mypy bandit

# Устанавливаем cppcheck
RUN apt-get update && apt-get install -y cppcheck && apt-get clean

# Копируем скрипт запуска
COPY runCode.py /usr/src/app/runCode.py

ENTRYPOINT ["python", "runCode.py"]
