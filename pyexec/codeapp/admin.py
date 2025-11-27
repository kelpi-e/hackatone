from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Task, Report, User, InterviewSession


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'max_execution_time', 'max_memory_mb', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'is_active')
        }),
        ('Примеры и тесты', {
            'fields': ('examples', 'tests'),
            'description': 'Примеры: [{"input": "...", "output": "..."}]. Тесты: [{"input": [...], "expected": "..."}]'
        }),
        ('Ограничения', {
            'fields': ('max_execution_time', 'max_memory_mb')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'candidate', 'hr', 'created_at')
    list_filter = ('created_at', 'candidate', 'hr')
    search_fields = ('candidate__username', 'hr__username', 'hard_skills_summary', 'theoretical_test_summary', 'practical_test_summary', 'suspicious_activity_summary')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Участники', {
            'fields': ('candidate', 'hr'),
            'description': 'Кандидат и HR, связанные с этим рапортом'
        }),
        ('Результаты', {
            'fields': ('hard_skills_summary', 'theoretical_test_summary', 'practical_test_summary', 'suspicious_activity_summary')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'role', 'is_active', 'is_banned', 'banned_at', 'created_at')
    list_filter = ('role', 'is_active', 'is_banned', 'created_at')
    search_fields = ('username',)
    readonly_fields = ('created_at', 'last_login', 'date_joined', 'banned_at')
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Персональная информация', {
            'fields': ('role',)
        }),
        ('Блокировка', {
            'fields': ('is_banned', 'ban_reason', 'banned_at'),
            'classes': ('collapse',)
        }),
        ('Права доступа', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Важные даты', {
            'fields': ('last_login', 'date_joined', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'role', 'password1', 'password2'),
        }),
    )


@admin.register(InterviewSession)
class InterviewSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'stage', 'theory_completed', 'interview_started', 'terminated', 'updated_at')
    list_filter = ('stage', 'theory_completed', 'interview_started', 'terminated', 'created_at')
    search_fields = ('user__username',)
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'stage', 'theory_completed', 'interview_started', 'terminated')
        }),
        ('Данные интервью', {
            'fields': ('hard_desc', 'theory_questions', 'current_question_idx', 'chat_history')
        }),
        ('Дополнительно', {
            'fields': ('termination_reason', 'awaiting_hint_answer', 'current_hint')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    readonly_fields = ('created_at', 'updated_at')
