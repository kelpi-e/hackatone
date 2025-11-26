from django.contrib import admin
from .models import Task, Report


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
    list_display = ('__str__', 'candidate_name', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('candidate_name', 'hard_skills_summary', 'theoretical_test_summary', 'practical_test_summary')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Информация о кандидате', {
            'fields': ('candidate_name',)
        }),
        ('Результаты', {
            'fields': ('hard_skills_summary', 'theoretical_test_summary', 'practical_test_summary')
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
