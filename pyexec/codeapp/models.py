from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
import json


class Task(models.Model):
    """Модель для хранения заданий по программированию"""
    
    title = models.CharField(
        max_length=200,
        verbose_name="Название задачи",
        help_text="Краткое название задачи"
    )
    
    description = models.TextField(
        verbose_name="Описание",
        help_text="Полное описание задачи, условия, требования"
    )
    
    examples = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Примеры",
        help_text="Примеры ввода и вывода в формате JSON: [{'input': '...', 'output': '...'}]"
    )
    
    tests = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Тесты",
        help_text="Тестовые случаи в формате JSON: [{'input': [...], 'expected': '...'}]"
    )
    
    max_execution_time = models.FloatField(
        default=5.0,
        validators=[MinValueValidator(0.1)],
        verbose_name="Максимальное время выполнения (секунды)",
        help_text="Максимальное время выполнения программы в секундах"
    )
    
    max_memory_mb = models.IntegerField(
        default=512,
        validators=[MinValueValidator(1)],
        verbose_name="Максимальная память (МБ)",
        help_text="Максимальный объем памяти в мегабайтах"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
        help_text="Показывать ли задачу пользователям"
    )
    
    class Meta:
        verbose_name = "Задание"
        verbose_name_plural = "Задания"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title
    
    def get_examples_display(self):
        """Возвращает примеры в читаемом формате"""
        if not self.examples:
            return []
        return self.examples
    
    def get_tests_display(self):
        """Возвращает тесты в читаемом формате"""
        if not self.tests:
            return []
        return self.tests


class Report(models.Model):
    """Модель для хранения рапортов после собеседований"""
    
    candidate = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='reports_as_candidate',
        limit_choices_to={'role': 'CANDIDATE'},
        verbose_name="Кандидат",
        help_text="Кандидат, который прошел тестирование"
    )
    
    hr = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='reports_as_hr',
        limit_choices_to={'role': 'HR'},
        verbose_name="HR",
        help_text="HR, к которому идет кандидат"
    )
    
    hard_skills_summary = models.TextField(
        verbose_name="Суммированные хард скилы",
        help_text="Обобщенная информация о технических навыках кандидата"
    )
    
    theoretical_test_summary = models.TextField(
        verbose_name="Суммированные результаты теоретического тестирования",
        help_text="Обобщенные результаты теоретических тестов и вопросов"
    )
    
    practical_test_summary = models.TextField(
        verbose_name="Суммированные результаты практического тестирования",
        help_text="Обобщенные результаты практических заданий и написания кода"
    )
    
    suspicious_activity_summary = models.TextField(
        verbose_name="Суммированная подозрительная активность",
        help_text="Обобщенная информация о подозрительной активности кандидата (копипаст, использование ИИ и т.д.)",
        blank=True,
        default=""
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        verbose_name = "Рапорт"
        verbose_name_plural = "Рапорты"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Рапорт: {self.candidate.username} → {self.hr.username} ({self.created_at.strftime('%d.%m.%Y')})"
    
    def get_full_summary(self):
        """Возвращает полный текст рапорта"""
        suspicious_text = f"\n\nПодозрительная активность:\n{self.suspicious_activity_summary}" if self.suspicious_activity_summary else ""
        return f"""
Хард скилы:
{self.hard_skills_summary}

Теоретическое тестирование:
{self.theoretical_test_summary}

Практическое тестирование:
{self.practical_test_summary}{suspicious_text}
        """.strip()


class User(AbstractUser):
    """Кастомная модель пользователя с никнеймом и ролью"""
    
    ROLE_CHOICES = [
        ('HR', 'HR'),
        ('CANDIDATE', 'Кандидат'),
    ]
    
    username = models.CharField(
        max_length=150,
        unique=True,
        verbose_name="Никнейм",
        help_text="Уникальный никнейм пользователя"
    )
    
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        verbose_name="Роль",
        help_text="Роль пользователя: HR или Кандидат"
    )
    
    # Убираем обязательные поля email, first_name, last_name
    email = models.EmailField(blank=True, null=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата регистрации"
    )
    
    # Поля для бана
    is_banned = models.BooleanField(
        default=False,
        verbose_name="Заблокирован",
        help_text="Заблокирован ли пользователь за плохое поведение"
    )
    ban_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Причина блокировки",
        help_text="Причина блокировки пользователя"
    )
    banned_at = models.DateTimeField(
        blank=True,
        null=True,
        verbose_name="Дата блокировки"
    )
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['role']
    
    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"
    
    def is_hr(self):
        """Проверяет, является ли пользователь HR"""
        return self.role == 'HR'
    
    def is_candidate(self):
        """Проверяет, является ли пользователь кандидатом"""
        return self.role == 'CANDIDATE'


class InterviewSession(models.Model):
    """Модель для хранения состояния интервью пользователя"""
    
    user = models.OneToOneField(
        'User',
        on_delete=models.CASCADE,
        related_name='interview_session',
        limit_choices_to={'role': 'CANDIDATE'},
        verbose_name="Пользователь",
        help_text="Кандидат, проходящий интервью"
    )
    
    stage = models.CharField(
        max_length=50,
        default='init',
        verbose_name="Стадия",
        help_text="Текущая стадия интервью: init, hard_desc, theory, finished"
    )
    
    hard_desc = models.TextField(
        blank=True,
        null=True,
        verbose_name="Описание навыков",
        help_text="Описание технических навыков кандидата"
    )
    
    theory_questions = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Теоретические вопросы",
        help_text="Список теоретических вопросов"
    )
    
    current_question_idx = models.IntegerField(
        default=0,
        verbose_name="Текущий индекс вопроса",
        help_text="Индекс текущего вопроса в списке"
    )
    
    chat_history = models.JSONField(
        default=list,
        blank=True,
        verbose_name="История чата",
        help_text="История сообщений интервью в формате JSON"
    )
    
    terminated = models.BooleanField(
        default=False,
        verbose_name="Прервано",
        help_text="Было ли интервью прервано из-за плохого поведения"
    )
    
    termination_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name="Причина прерывания",
        help_text="Причина прерывания интервью"
    )
    
    awaiting_hint_answer = models.BooleanField(
        default=False,
        verbose_name="Ожидается ответ на наводящий вопрос",
        help_text="Ожидается ли ответ на наводящий вопрос"
    )
    
    current_hint = models.TextField(
        blank=True,
        null=True,
        verbose_name="Текущий наводящий вопрос",
        help_text="Текущий наводящий вопрос, если есть"
    )
    
    candidate_summary = models.TextField(
        blank=True,
        null=True,
        verbose_name="Резюме кандидата",
        help_text="Сгенерированное резюме о навыках кандидата для ранжирования задач"
    )
    
    theory_completed = models.BooleanField(
        default=False,
        verbose_name="Теория завершена",
        help_text="Завершена ли теоретическая часть интервью"
    )
    
    interview_started = models.BooleanField(
        default=False,
        verbose_name="Интервью начато",
        help_text="Начато ли интервью"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        verbose_name = "Сессия интервью"
        verbose_name_plural = "Сессии интервью"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Интервью: {self.user.username} ({self.stage})"
    
    def get_interactor_data(self):
        """Возвращает данные в формате для Interactor"""
        return {
            'stage': self.stage,
            'hard_desc': self.hard_desc,
            'theory_questions': self.theory_questions,
            'current_question_idx': self.current_question_idx,
            'chat_history': self.chat_history,
            'terminated': self.terminated,
            'awaiting_hint_answer': self.awaiting_hint_answer,
            'current_hint': self.current_hint
        }
    
    def update_from_interactor(self, interactor):
        """Обновляет данные из объекта Interactor"""
        self.stage = interactor.stage
        self.hard_desc = interactor.hard_desc
        self.theory_questions = interactor.theory_questions
        self.current_question_idx = interactor.current_question_idx
        self.chat_history = interactor.chat_history
        self.terminated = interactor.terminated
        self.termination_reason = getattr(interactor, 'termination_reason', None)
        self.awaiting_hint_answer = interactor.awaiting_hint_answer
        self.current_hint = interactor.current_hint
        self.candidate_summary = getattr(interactor, 'candidate_summary', None)
        self.save()
