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
