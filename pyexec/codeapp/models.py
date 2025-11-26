from django.db import models
from django.core.validators import MinValueValidator
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
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    # Опциональное поле для связи с кандидатом (если понадобится в будущем)
    candidate_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name="Имя кандидата",
        help_text="Имя кандидата (опционально)"
    )
    
    class Meta:
        verbose_name = "Рапорт"
        verbose_name_plural = "Рапорты"
        ordering = ['-created_at']
    
    def __str__(self):
        if self.candidate_name:
            return f"Рапорт: {self.candidate_name} ({self.created_at.strftime('%d.%m.%Y')})"
        return f"Рапорт от {self.created_at.strftime('%d.%m.%Y %H:%M')}"
    
    def get_full_summary(self):
        """Возвращает полный текст рапорта"""
        return f"""
Хард скилы:
{self.hard_skills_summary}

Теоретическое тестирование:
{self.theoretical_test_summary}

Практическое тестирование:
{self.practical_test_summary}
        """.strip()
