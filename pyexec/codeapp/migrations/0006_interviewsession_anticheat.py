# Generated migration for anti-cheat fields

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codeapp', '0005_interviewsession_candidate_summary'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewsession',
            name='suspicious_activities',
            field=models.JSONField(blank=True, default=list, help_text='Список подозрительных действий: переключение вкладок, копирование, долгие паузы', verbose_name='Подозрительная активность'),
        ),
        migrations.AddField(
            model_name='interviewsession',
            name='tab_switches',
            field=models.IntegerField(default=0, help_text='Количество переключений на другие вкладки', verbose_name='Переключения вкладок'),
        ),
        migrations.AddField(
            model_name='interviewsession',
            name='copy_paste_count',
            field=models.IntegerField(default=0, help_text='Количество операций копирования/вставки', verbose_name='Копирование/вставка'),
        ),
    ]

