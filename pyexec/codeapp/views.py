import os
import json
import subprocess
import unicodedata
import shutil
import sys
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from .forms import UserRegistrationForm, UserLoginForm
from .models import User, Report, InterviewSession
from django.utils import timezone

# Добавляем путь к interactor
interactor_path = os.path.join(settings.BASE_DIR.parent, 'inreractor')
if interactor_path not in sys.path:
    sys.path.insert(0, interactor_path)

# =============================================================================
# Пути и настройки
# =============================================================================
TASKS_DIR = os.path.join(settings.BASE_DIR, "codeapp", "tests")
ANALYSIS_LOG = os.path.join(settings.BASE_DIR, "code_analysis.log")
TEMP_DIR = os.path.join(settings.BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Docker настройки
DOCKER_IMAGE = "codesphere-analyzer"
USE_DOCKER = True  # Включить/выключить Docker


def check_docker_image():
    """Проверяет, существует ли Docker-образ."""
    try:
        result = subprocess.run(
            ["docker", "images", "-q", DOCKER_IMAGE],
            capture_output=True, text=True, timeout=10
        )
        return bool(result.stdout.strip())
    except:
        return False


def build_docker_image():
    """Собирает Docker-образ, если его нет."""
    dockerfile_dir = os.path.join(settings.BASE_DIR, "codeAnalysis")
    try:
        subprocess.run(
            ["docker", "build", "-t", DOCKER_IMAGE, dockerfile_dir],
            capture_output=True, text=True, timeout=300
        )
        return True
    except:
        return False


def run_in_docker(mode, code_path, language, tests_json="[]", input_data=""):
    """
    Запускает код в Docker-контейнере.
    
    Args:
        mode: "analyze", "run", "test"
        code_path: путь к файлу с кодом
        language: "Python" или "C++"
        tests_json: JSON-строка с тестами
        input_data: входные данные для программы
    
    Returns:
        dict с результатами
    """
    # Проверяем/собираем образ
    if not check_docker_image():
        if not build_docker_image():
            return {"success": False, "error": "Не удалось собрать Docker-образ"}
    
    # Определяем имя файла в контейнере
    ext = "py" if language == "Python" else "cpp"
    container_code_path = f"/tmp/code.{ext}"
    
    # Формируем команду Docker
    docker_cmd = [
        "docker", "run", "--rm",
        "--network=none",  # Без сети
        "--memory=256m",   # Лимит памяти
        "--cpus=1",        # Лимит CPU
        "-v", f"{os.path.abspath(code_path)}:{container_code_path}:ro",
        DOCKER_IMAGE,
        mode, container_code_path, language
    ]
    
    # Добавляем тесты или input
    if mode == "test":
        docker_cmd.append(tests_json)
    elif mode == "run":
        docker_cmd.append(input_data)
    
    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Парсим JSON-ответ
        try:
            return json.loads(result.stdout)
        except:
            return {
                "success": False,
                "error": result.stderr or result.stdout or "Неизвестная ошибка Docker"
            }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Таймаут Docker-контейнера"}
    except FileNotFoundError:
        return {"success": False, "error": "Docker не установлен"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# Подозрительные символы (ИИ/копипаста)
SUSPICIOUS_CHARS = {
    "\u00A0": "NBSP", "\u200B": "ZERO WIDTH SPACE", "\u200C": "ZERO WIDTH NON-JOINER",
    "\u200D": "ZERO WIDTH JOINER", "\u2060": "WORD JOINER", "\ufeff": "BOM",
    "\u2013": "EN DASH", "\u2014": "EM DASH", "\u2018": "LEFT SINGLE QUOTE",
    "\u2019": "RIGHT SINGLE QUOTE", "\u201C": "LEFT DOUBLE QUOTE", "\u201D": "RIGHT DOUBLE QUOTE",
}

# =============================================================================
# Функции для работы с баном
# =============================================================================
def ban_user(user, reason):
    """
    Блокирует пользователя за плохое поведение
    """
    if not user.is_banned:
        user.is_banned = True
        user.ban_reason = reason
        user.banned_at = timezone.now()
        user.save(update_fields=['is_banned', 'ban_reason', 'banned_at'])

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
        # Игнорируем стандартные ASCII и русские буквы
        if ch in SUSPICIOUS_CHARS:
            found.append((i+1, SUSPICIOUS_CHARS[ch]))
        elif ord(ch) > 127 and not ('А' <= ch <= 'я' or ch in 'Ёё'):
            found.append((i+1, f"UNEXPECTED CHAR {unicodedata.name(ch, '?')}"))
    return found

# =============================================================================
# Авторизация
# =============================================================================
def register(request):
    if request.user.is_authenticated:
        # Проверяем, прошёл ли пользователь теоретическую часть
        if request.user.is_candidate():
            try:
                interview_session = InterviewSession.objects.get(user=request.user)
                if not interview_session.theory_completed:
                    return redirect('interview')
            except InterviewSession.DoesNotExist:
                return redirect('interview')
        return redirect('runcode')
    
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Явно указываем backend для логина
            login(request, user, backend='codeapp.backends.UsernameOnlyBackend')
            messages.success(request, f'Добро пожаловать, {user.username}!')
            # Проверяем, нужно ли пройти интервью
            if user.is_candidate():
                # Для кандидатов всегда начинаем с интервью
                return redirect('interview')
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
        # Проверяем, прошёл ли пользователь теоретическую часть
        if request.user.is_candidate():
            try:
                interview_session = InterviewSession.objects.get(user=request.user)
                if not interview_session.theory_completed:
                    return redirect('interview')
            except InterviewSession.DoesNotExist:
                return redirect('interview')
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
                # Проверяем, нужно ли пройти интервью
                if user.is_candidate():
                    try:
                        interview_session = InterviewSession.objects.get(user=user)
                        if not interview_session.theory_completed:
                            return redirect('interview')
                    except InterviewSession.DoesNotExist:
                        return redirect('interview')
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
    context = {}
    if request.user.is_authenticated:
        if hasattr(request.user, 'is_banned') and request.user.is_banned:
            context['show_ban_modal'] = True
        # Определяем стадию для кандидатов
        if request.user.is_candidate():
            try:
                interview_session = InterviewSession.objects.get(user=request.user)
                theory_completed = interview_session.theory_completed
            except InterviewSession.DoesNotExist:
                theory_completed = False
            context['show_interview_link'] = not theory_completed
            context['show_editor_link'] = theory_completed
    return render(request, "index.html", context)

@login_required
def interview(request):
    """
    Страница интервью - показывается только для кандидатов
    При первом заходе показывается чат интервью
    После завершения теории - переход в редактор
    """
    # Проверяем роль - только кандидаты могут проходить интервью
    if not request.user.is_candidate():
        messages.error(request, 'Интервью доступно только для кандидатов.')
        return redirect('runcode')
    
    # Получаем или создаем сессию интервью из БД
    try:
        interview_session = InterviewSession.objects.get(user=request.user)
        interview_started = interview_session.interview_started
        theory_completed = interview_session.theory_completed
        interview_chat_history = interview_session.chat_history
    except InterviewSession.DoesNotExist:
        interview_session = None
        interview_started = False
        theory_completed = False
        interview_chat_history = []
    
    # Если теория завершена, перенаправляем в редактор
    if theory_completed:
        return redirect('runcode')
    
    context = {
        'interview_started': interview_started,
        'theory_completed': theory_completed,
        'show_interview_link': True,  # На странице интервью всегда показываем ссылку на интервью
        'show_editor_link': False,
        'interview_chat_history': interview_chat_history,
    }
    if request.user.is_banned:
        context['show_ban_modal'] = True
    return render(request, "codeapp/interview.html", context)

@login_required
@require_http_methods(["POST"])
def interview_api(request):
    """
    API endpoint для работы с интервью (AJAX запросы)
    """
    if not request.user.is_candidate():
        return JsonResponse({'error': 'Доступно только для кандидатов'}, status=403)
    
    action = request.POST.get('action')
    
    # Импортируем Interactor
    try:
        from interactor import Interactor
    except ImportError as e:
        import traceback
        error_msg = str(e)
        # Проверяем, какая именно ошибка импорта
        if 'openai' in error_msg.lower():
            return JsonResponse({
                'error': 'Модуль openai не установлен. Установите его командой: pip install openai',
                'details': str(e)
            }, status=500)
        else:
            return JsonResponse({
                'error': f'Ошибка импорта Interactor: {error_msg}',
                'details': traceback.format_exc()
            }, status=500)
    except Exception as e:
        import traceback
        return JsonResponse({
            'error': f'Ошибка при инициализации Interactor: {str(e)}',
            'details': traceback.format_exc()
        }, status=500)
    
    # Получаем или создаем InterviewSession из БД
    try:
        interview_session = InterviewSession.objects.get(user=request.user)
    except InterviewSession.DoesNotExist:
        interview_session = InterviewSession.objects.create(user=request.user)
    
    api_key = "sk-EntOXD173KXh0i-jb0esww"  # TODO: вынести в settings
    interactor = Interactor(key=api_key)
    
    # Восстанавливаем состояние из БД
    # Всегда восстанавливаем hard_desc, если он есть в БД
    if interview_session.hard_desc:
        interactor.hard_desc = interview_session.hard_desc
    
    if interview_session.stage != 'init' or interview_session.chat_history:
        interactor.stage = interview_session.stage
        interactor.theory_questions = interview_session.theory_questions
        interactor.current_question_idx = interview_session.current_question_idx
        interactor.chat_history = interview_session.chat_history
        interactor.terminated = interview_session.terminated
        interactor.awaiting_hint_answer = interview_session.awaiting_hint_answer
        interactor.current_hint = interview_session.current_hint
        if interview_session.termination_reason:
            interactor.termination_reason = interview_session.termination_reason
    
    if action == 'start_hard_desc':
        # Начало интервью - описание навыков
        try:
            hard_desc = request.POST.get('hard_desc', '').strip()
            result = interactor.put_hard_desc(hard_desc)
            
            if result['success']:
                # Сохраняем в БД
                interview_session.interview_started = True
                interview_session.update_from_interactor(interactor)
            
            # Проверяем, был ли интервью прерван - если да, баним пользователя
            if interactor.terminated and interactor.termination_reason:
                ban_user(request.user, interactor.termination_reason)
                result['banned'] = True
                result['ban_reason'] = interactor.termination_reason
            
            return JsonResponse(result)
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': f'Ошибка при обработке описания навыков: {str(e)}',
                'details': traceback.format_exc()
            }, status=500)
    
    elif action == 'start_interview':
        # Запуск интервью после описания навыков
        try:
            # Убеждаемся, что hard_desc восстановлен из БД
            if not interactor.hard_desc and interview_session.hard_desc:
                interactor.hard_desc = interview_session.hard_desc
            
            result = interactor.start_interview()
            
            if result['success']:
                # Сохраняем в БД
                interview_session.update_from_interactor(interactor)
            
            return JsonResponse(result)
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': f'Ошибка при запуске интервью: {str(e)}',
                'details': traceback.format_exc()
            }, status=500)
    
    elif action == 'get_question':
        # Получить следующий вопрос
        try:
            question = interactor.get_next_question()
            
            # Сохраняем в БД
            interview_session.update_from_interactor(interactor)
            
            if question is None:
                # Интервью завершено
                if interactor.stage == 'finished':
                    # Генерируем резюме кандидата для ранжирования задач
                    try:
                        candidate_summary = interactor.build_candidate_summary()
                        interview_session.candidate_summary = candidate_summary
                    except Exception as e:
                        print(f"Ошибка генерации резюме: {e}")
                    
                    interview_session.theory_completed = True
                    interview_session.save()
                    return JsonResponse({
                        'question': None,
                        'finished': True,
                        'message': 'Теоретическая часть завершена! Переход к практическим заданиям...'
                    })
            
            return JsonResponse({
                'question': question,
                'finished': False,
                'is_hint': interactor.awaiting_hint_answer,
                'total_questions': len(interactor.theory_questions),
                'current_idx': interactor.current_question_idx
            })
        except Exception as e:
            import traceback
            return JsonResponse({
                'error': f'Ошибка при получении вопроса: {str(e)}',
                'details': traceback.format_exc()
            }, status=500)
    
    elif action == 'submit_answer':
        # Отправить ответ на вопрос
        try:
            answer = request.POST.get('answer', '').strip()
            result = interactor.submit_theory_answer(answer)
            
            if result['success']:
                # Получаем последний элемент из chat_history для отображения
                last_qa = interactor.chat_history[-1] if interactor.chat_history else None
                
                # Сохраняем в БД
                interview_session.update_from_interactor(interactor)
                
                # Проверяем, завершена ли теория
                if interactor.stage == 'finished':
                    interview_session.theory_completed = True
                    interview_session.save()
                    result['theory_completed'] = True
                
                result['last_qa'] = last_qa
            
            return JsonResponse(result)
        except Exception as e:
            import traceback
            return JsonResponse({
                'success': False,
                'error': f'Ошибка при отправке ответа: {str(e)}',
                'details': traceback.format_exc()
            }, status=500)
    
    elif action == 'get_history':
        # Получить историю чата из БД
        try:
            return JsonResponse({
                'chat_history': interview_session.chat_history,
                'stage': interview_session.stage
            })
        except Exception as e:
            import traceback
            return JsonResponse({
                'error': f'Ошибка при получении истории: {str(e)}',
                'details': traceback.format_exc()
            }, status=500)
    
    if not action:
        return JsonResponse({'error': 'Не указано действие (action)'}, status=400)
    
    return JsonResponse({'error': f'Неизвестное действие: {action}'}, status=400)

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def code_chat_api(request):
    """
    API endpoint для чата с интервьюером во время написания кода.
    Анализирует код и возвращает подсказки/наводящие вопросы.
    """
    if not request.user.is_candidate():
        return JsonResponse({'error': 'Доступно только для кандидатов'}, status=403)
    
    try:
        from interactor import Interactor
    except ImportError as e:
        return JsonResponse({'error': f'Ошибка импорта Interactor: {e}'}, status=500)
    
    from openai import OpenAI
    
    # Получаем сессию интервью
    try:
        interview_session = InterviewSession.objects.get(user=request.user)
        if not interview_session.theory_completed:
            return JsonResponse({'error': 'Сначала завершите теоретическую часть интервью'}, status=400)
    except InterviewSession.DoesNotExist:
        return JsonResponse({'error': 'Сессия интервью не найдена'}, status=404)
    
    action = request.POST.get('action')
    message = request.POST.get('message', '').strip()
    code = request.POST.get('code', '')
    task_text = request.POST.get('task_text', '')
    test_results = request.POST.get('test_results', '')
    language = request.POST.get('language', 'Python')
    
    api_key = "sk-EntOXD173KXh0i-jb0esww"
    client = OpenAI(api_key=api_key, base_url="https://llm.t1v.scibox.tech/v1")
    
    if action == 'analyze_code':
        # Анализируем код после запуска тестов и даём обратную связь
        system_prompt = (
            "/no_think Ты опытный технический интервьюер. "
            "Кандидат решает задачу по программированию. "
            "Проанализируй его код и результаты тестов.\n\n"
            "Твоя задача:\n"
            "1. Оценить качество кода (читаемость, структура, эффективность)\n"
            "2. Если тесты не прошли - дать НАВОДЯЩИЙ вопрос (не ответ!), который поможет найти ошибку\n"
            "3. Если тесты прошли - похвалить и предложить улучшения (если есть)\n"
            "4. Быть кратким и конструктивным\n\n"
            "Верни JSON:\n"
            "{\n"
            '  \"feedback\": \"краткий отзыв о коде на русском\",\n'
            '  \"hint\": \"наводящий вопрос или подсказка (если нужна)\",\n'
            '  \"code_quality\": \"good\" | \"needs_improvement\" | \"poor\",\n'
            '  \"encouragement\": \"мотивирующее сообщение\"\n'
            "}"
        )
        
        user_content = (
            f"Язык: {language}\n\n"
            f"Задача:\n{task_text}\n\n"
            f"Код кандидата:\n```{language.lower()}\n{code}\n```\n\n"
            f"Результаты тестов:\n{test_results}\n\n"
            "Проанализируй и дай обратную связь."
        )
        
        try:
            resp = client.chat.completions.create(
                model="qwen3-coder-30b-a3b-instruct-fp8",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                stream=False,
                response_format={"type": "json_object"},
                temperature=0.7
            )
            
            data = json.loads(resp.choices[0].message.content)
            
            # Сохраняем в историю чата
            chat_entry = {
                "type": "code_feedback",
                "code_snippet": code[:500] + "..." if len(code) > 500 else code,
                "test_results": test_results,
                "feedback": data.get("feedback", ""),
                "hint": data.get("hint", ""),
                "code_quality": data.get("code_quality", ""),
                "timestamp": timezone.now().isoformat()
            }
            
            chat_history = interview_session.chat_history or []
            chat_history.append(chat_entry)
            interview_session.chat_history = chat_history
            interview_session.save()
            
            return JsonResponse({
                'success': True,
                'feedback': data.get("feedback", ""),
                'hint': data.get("hint", ""),
                'code_quality': data.get("code_quality", "needs_improvement"),
                'encouragement': data.get("encouragement", "Продолжайте работать!")
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Ошибка анализа: {str(e)}'
            }, status=500)
    
    elif action == 'send_message':
        # Кандидат отправляет сообщение/вопрос
        if not message:
            return JsonResponse({'error': 'Сообщение не может быть пустым'}, status=400)
        
        # Получаем контекст из истории
        chat_history = interview_session.chat_history or []
        recent_context = chat_history[-5:] if chat_history else []
        
        system_prompt = (
            "/no_think Ты технический интервьюер, который помогает кандидату решить задачу. "
            "Отвечай на вопросы кандидата, но НЕ давай прямых ответов на задачу. "
            "Задавай наводящие вопросы, помогай разобраться в проблеме. "
            "Будь кратким (1-3 предложения), вежливым и профессиональным. "
            "Отвечай на русском языке."
        )
        
        context_str = ""
        for entry in recent_context:
            if entry.get("type") == "code_feedback":
                context_str += f"[Предыдущий отзыв]: {entry.get('feedback', '')}\n"
            elif entry.get("type") == "chat_message":
                context_str += f"[{entry.get('role', 'user')}]: {entry.get('content', '')}\n"
        
        user_content = (
            f"Задача:\n{task_text}\n\n"
            f"Текущий код:\n```{language.lower()}\n{code[:1000]}\n```\n\n"
            f"Контекст диалога:\n{context_str}\n\n"
            f"Вопрос кандидата: {message}\n\n"
            "Ответь кратко и помоги разобраться."
        )
        
        try:
            resp = client.chat.completions.create(
                model="qwen3-coder-30b-a3b-instruct-fp8",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                stream=False,
                temperature=0.7
            )
            
            response_message = resp.choices[0].message.content.strip()
            
            # Сохраняем в историю
            chat_history.append({
                "type": "chat_message",
                "role": "candidate",
                "content": message,
                "timestamp": timezone.now().isoformat()
            })
            chat_history.append({
                "type": "chat_message",
                "role": "interviewer",
                "content": response_message,
                "timestamp": timezone.now().isoformat()
            })
            interview_session.chat_history = chat_history
            interview_session.save()
            
            return JsonResponse({
                'success': True,
                'message': response_message
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Ошибка: {str(e)}'
            }, status=500)
    
    return JsonResponse({'error': f'Неизвестное действие: {action}'}, status=400)


@login_required
@require_http_methods(["GET", "POST"])
def get_ranked_tasks_api(request):
    """
    API endpoint для получения задач, ранжированных по релевантности для кандидата.
    GET: возвращает все задачи в порядке ранжирования
    POST: принимает candidate_summary для персонализированного ранжирования
    """
    if not request.user.is_candidate():
        return JsonResponse({'error': 'Доступно только для кандидатов'}, status=403)
    
    try:
        from .task_manager import get_ranked_tasks, get_all_tasks
    except ImportError as e:
        return JsonResponse({'error': f'Ошибка импорта task_manager: {e}'}, status=500)
    
    # Получаем сессию интервью для профиля кандидата
    try:
        interview_session = InterviewSession.objects.get(user=request.user)
    except InterviewSession.DoesNotExist:
        return JsonResponse({'error': 'Сессия интервью не найдена'}, status=404)
    
    top_k = int(request.GET.get('top_k', request.POST.get('top_k', 10)))
    
    if request.method == 'POST':
        candidate_summary = request.POST.get('candidate_summary', '')
    else:
        # Используем сохранённое резюме кандидата или hard_desc
        candidate_summary = getattr(interview_session, 'candidate_summary', '') or interview_session.hard_desc or ''
    
    if not candidate_summary:
        # Если нет профиля, возвращаем все задачи без ранжирования
        tasks = get_all_tasks()
        return JsonResponse({
            'success': True,
            'ranked': False,
            'tasks': tasks
        })
    
    try:
        ranked_tasks = get_ranked_tasks(candidate_summary, top_k=top_k)
        return JsonResponse({
            'success': True,
            'ranked': True,
            'tasks': ranked_tasks
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Ошибка ранжирования: {str(e)}'
        }, status=500)


@login_required
def index(request):
    # Для кандидатов проверяем, прошли ли они теоретическую часть
    if request.user.is_candidate():
        try:
            interview_session = InterviewSession.objects.get(user=request.user)
            if not interview_session.theory_completed:
                # Перенаправляем на интервью, если теория не завершена
                return redirect('interview')
            theory_completed = True
            interview_chat_history = interview_session.chat_history
        except InterviewSession.DoesNotExist:
            # Если сессии нет, перенаправляем на интервью
            return redirect('interview')
    else:
        # Для не-кандидатов (HR, админы) не проверяем интервью
        theory_completed = False
        interview_chat_history = []
    
    tasks = get_task_list()
    selected = request.GET.get("task") or (tasks[0] if tasks else None)
    language = request.GET.get("language", "Python")
    
    context = {
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
        "theory_completed": theory_completed,
        "interview_chat_history": interview_chat_history,
        'show_interview_link': False,  # На странице редактора показываем ссылку на редактор
        'show_editor_link': True,
    }
    if request.user.is_banned:
        context['show_ban_modal'] = True
    return render(request, "codeapp/ide.html", context)

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
    analysis_parts = []

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

    # === Попытка запуска через Docker ===
    if USE_DOCKER:
        # Загружаем тесты
        tests_json = "[]"
        if test_mode:
            json_file = selected_task.replace(".txt", ".json") if selected_task else None
            json_path = os.path.join(TASKS_DIR, json_file) if json_file else None
            if json_path and os.path.exists(json_path):
                with open(json_path, "r", encoding="utf-8") as f:
                    tests_json = f.read()

        # Определяем режим Docker
        docker_mode = "test" if test_mode else "run"
        
        # Запускаем в Docker
        docker_result = run_in_docker(
            mode=docker_mode,
            code_path=src_path,
            language=language,
            tests_json=tests_json,
            input_data=user_input
        )

        if docker_result.get("success", False) or "analysis" in docker_result:
            # Парсим результаты из Docker
            if test_mode:
                test_results = docker_result.get("test_results", [])
                tests_passed = docker_result.get("tests_passed", "0/0")
            else:
                output += docker_result.get("output", "")
                if docker_result.get("error"):
                    output += "\nОшибка:\n" + docker_result["error"]
            
            # Анализ кода
            analysis = docker_result.get("analysis", {})
            if language == "Python":
                analysis_parts.append(f"=== pylint ===\n{analysis.get('pylint', 'Н/Д')}\n")
                analysis_parts.append(f"=== mypy ===\n{analysis.get('mypy', 'Н/Д')}\n")
                analysis_parts.append(f"=== bandit ===\n{analysis.get('bandit', 'Н/Д')}\n")
            else:
                analysis_parts.append(f"=== cppcheck ===\n{analysis.get('cppcheck', 'Н/Д')}\n")
                analysis_parts.append(f"=== g++ warnings ===\n{analysis.get('g++', 'Н/Д')}\n")
            
            # Ошибка компиляции
            if docker_result.get("compile_error"):
                output += f"Ошибка компиляции:\n{docker_result['compile_error']}\n"
        else:
            # Docker не сработал, fallback на локальный запуск
            output += f"Docker недоступен: {docker_result.get('error', 'неизвестная ошибка')}\n"
            output += "Используется локальный запуск...\n\n"
            USE_DOCKER_FALLBACK = False  # Переключаемся на локальный
    else:
        USE_DOCKER_FALLBACK = False

    # === Локальный fallback (если Docker не работает) ===
    if not USE_DOCKER or (USE_DOCKER and not docker_result.get("success", False) and "analysis" not in docker_result):
        compile_error = None
        
        # C++: компиляция
        if language == "C++":
            if shutil.which("g++"):
                compile_cmd = ["g++", src_path, "-o", exe_path, "-std=c++17", "-O2", "-Wall"]
                result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=15)
                if result.returncode != 0:
                    compile_error = result.stderr.strip() or "Ошибка компиляции"
                    if not test_mode:
                        output += f"Ошибка компиляции:\n{compile_error}\n"
            else:
                compile_error = "g++ не установлен"
                output += "g++ не установлен. Установите компилятор C++.\n"

        # Запуск тестов
        if test_mode and not compile_error:
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
                            if language == "Python":
                                cmd = [get_python_command(), src_path]
                            else:
                                cmd = [exe_path]
                            
                            res = subprocess.run(
                                cmd,
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
                    test_results.append({
                        "number": 0,
                        "error": f"Ошибка запуска тестов: {e}",
                        "passed": False,
                        "timeout": False
                    })

        # Обычный запуск
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

        # Локальный анализ
        if language == "C++":
            if shutil.which("cppcheck"):
                try:
                    r = subprocess.run(["cppcheck", "--enable=all", "--std=c++17", src_path],
                                      capture_output=True, text=True, timeout=30)
                    analysis_parts.append("=== cppcheck ===\n" + (r.stderr or "Ошибок не найдено") + "\n")
                except Exception as e:
                    analysis_parts.append(f"=== cppcheck ===\nОшибка: {e}\n")
            else:
                analysis_parts.append("=== cppcheck ===\nНе установлен\n")

            if shutil.which("g++"):
                try:
                    r = subprocess.run(["g++", "-Wall", "-Wextra", "-std=c++17", src_path, "-o", exe_path],
                                      capture_output=True, text=True, timeout=30)
                    analysis_parts.append("=== g++ warnings ===\n" + (r.stderr or "Предупреждений нет") + "\n")
                except Exception as e:
                    analysis_parts.append(f"=== g++ ===\nОшибка: {e}\n")

        if language == "Python":
            if shutil.which("pylint"):
                try:
                    r = subprocess.run(["pylint", "--disable=R,C", src_path],
                                      capture_output=True, text=True, timeout=30)
                    analysis_parts.append("=== pylint ===\n" + (r.stdout or "Ошибок не найдено") + "\n")
                except Exception as e:
                    analysis_parts.append(f"=== pylint ===\nОшибка: {e}\n")
            else:
                analysis_parts.append("=== pylint ===\nНе установлен\n")

            if shutil.which("mypy"):
                try:
                    r = subprocess.run(["mypy", "--ignore-missing-imports", src_path],
                                      capture_output=True, text=True, timeout=30)
                    analysis_parts.append("=== mypy ===\n" + (r.stdout or "") + (r.stderr or "") + "\n")
                except Exception as e:
                    analysis_parts.append(f"=== mypy ===\nОшибка: {e}\n")
            else:
                analysis_parts.append("=== mypy ===\nНе установлен\n")

            if shutil.which("bandit"):
                try:
                    r = subprocess.run(["bandit", "-q", "-r", src_path],
                                      capture_output=True, text=True, timeout=30)
                    analysis_parts.append("=== bandit ===\n" + (r.stdout or "Уязвимостей не найдено") + "\n")
                except Exception as e:
                    analysis_parts.append(f"=== bandit ===\nОшибка: {e}\n")
            else:
                analysis_parts.append("=== bandit ===\nНе установлен\n")

    # Запись анализа в лог
    with open(ANALYSIS_LOG, "w", encoding="utf-8") as f:
        f.write(f"=== Анализ кода ({language}) ===\n" + "".join(analysis_parts))

    # === Очистка временных файлов ===
    for path in (src_path, exe_path):
        try:
            if os.path.exists(path):
                os.remove(path)
        except:
            pass

    # === Сохранение полного отчета (анализ + тесты) ===
    RESULT_LOG = os.path.join(settings.BASE_DIR, "analysis_and_tests.log")

    full_report = []
    full_report.append(f"=== Полный отчет ({language}) ===\n")
    full_report.append(f"Задача: {selected_task or 'не выбрана'}\n")
    full_report.append(f"Режим: {'Тесты' if test_mode else 'Ручной запуск'}\n\n")

    # Добавляем результаты анализа
    full_report.append("=== Результаты анализа ===\n")
    try:
        with open(ANALYSIS_LOG, "r", encoding="utf-8") as f:
            full_report.append(f.read())
    except:
        full_report.append("Лог анализа недоступен.\n")

    # Добавляем результаты тестов
    full_report.append("\n=== Результаты тестов ===\n")
    if test_results:
        for t in test_results:
            status = "✓ Пройден" if t.get('passed') else ("⏱ Таймаут" if t.get('timeout') else "✗ Не пройден")
            full_report.append(
                f"Тест {t.get('number')}: {status}\n"
                f"  Ввод: {t.get('input', '')}\n"
                f"  Ожидалось: {t.get('expected', '')}\n"
                f"  Получено: {t.get('actual', '')}\n"
            )
            if t.get('error'):
                full_report.append(f"  Ошибка: {t.get('error')}\n")
            full_report.append("\n")
        
        # Итоговая статистика
        passed_count = sum(1 for t in test_results if t.get('passed'))
        full_report.append(f"Итого: {passed_count}/{len(test_results)} тестов пройдено\n")
    else:
        full_report.append("Тесты не выполнялись.\n")

    with open(RESULT_LOG, "w", encoding="utf-8") as f:
        f.write("".join(full_report))

    # Получаем данные интервью для отображения чата
    theory_completed = False
    interview_chat_history = []
    if request.user.is_candidate():
        try:
            interview_session = InterviewSession.objects.get(user=request.user)
            theory_completed = interview_session.theory_completed
            interview_chat_history = interview_session.chat_history
        except InterviewSession.DoesNotExist:
            pass

    return render(request, "codeapp/ide.html", {
        "tasks": get_task_list(),
        "selected_task": selected_task,
        "task_text": get_task_text(selected_task),
        "code": code,
        "output": output,
        "input_data": user_input,
        "tests_passed": tests_passed,
        "test_results": test_results,
        "test_mode": test_mode,
        "language": language,
        "code_executed": True,
        "theory_completed": theory_completed,
        "interview_chat_history": interview_chat_history,
        'show_interview_link': False,
        'show_editor_link': True,
    })