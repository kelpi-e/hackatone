# Generated migration for candidate_summary field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('codeapp', '0004_interviewsession'),
    ]

    operations = [
        migrations.AddField(
            model_name='interviewsession',
            name='candidate_summary',
            field=models.TextField(blank=True, help_text='Сгенерированное резюме о навыках кандидата для ранжирования задач', null=True, verbose_name='Резюме кандидата'),
        ),
    ]

