#!/bin/bash
# Скрипт для запуска Django сервера с активированным виртуальным окружением

cd "$(dirname "$0")"
source venv/bin/activate
cd pyexec
python manage.py runserver

