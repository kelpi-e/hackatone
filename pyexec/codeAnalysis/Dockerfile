FROM python:3.13-slim

WORKDIR /usr/src/app

# Устанавливаем базовые утилиты и компилятор C++
RUN apt-get update && apt-get install -y \
        build-essential \
        cppcheck \
        valgrind \
        git \
        wget \
        curl \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/*

# Обновляем pip и устанавливаем анализаторы Python
RUN python -m ensurepip \
    && pip install --upgrade pip \
    && pip install pylint mypy bandit

# Копируем скрипт запуска
COPY runCode.py /usr/src/app/runCode.py

ENTRYPOINT ["python", "runCode.py"]
