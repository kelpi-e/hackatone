import re
import os
import sys
import django
from openai import OpenAI

# Настройка Django для работы с БД
# resum.py находится в hackatone/, Django проект в hackatone/pyexec/
pyexec_path = os.path.join(os.path.dirname(__file__), 'pyexec')
sys.path.insert(0, pyexec_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pyexec.settings')
django.setup()

from codeapp.models import Report


class Resume:
    def __init__(self, text: str = '', api_key: str = '', base_url: str = '', model_name: str = '', candidate_name: str = ''):
        self.text = text
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name
        self.candidate_name = candidate_name

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def push_hard(self, text_hard: str = ''):
        self.text += f"<hard>{text_hard}</hard>"

    def push_theoretical(self, text_answer: str = ''):
        self.text += f"<theoretical_test>{text_answer}</theoretical_test>"

    def push_practical(self, text_answer: str = ''):
        self.text += f"<practical_test>{text_answer}</practical_test>"

    def find_hard(self) -> list:
        pattern_hard = r"<hard>(.*?)</hard>"
        return re.findall(pattern_hard, self.text)

    def find_theoretical(self) -> list:
        pattern_theoretical = r"<theoretical_test>(.*?)</theoretical_test>"
        return re.findall(pattern_theoretical, self.text)

    def find_practical(self) -> list:
        pattern_practical = r"<practical_test>(.*?)</practical_test>"
        return re.findall(pattern_practical, self.text)

    def summarize_hard_skills(self) -> str:
        """
        Суммаризирует hard skills с помощью LLM.
        Возвращает краткое резюме технических навыков кандидата.
        """
        hard_list = self.find_hard()
        if not hard_list:
            return "Хард скилы не указаны."

        hard_text = "\n".join([f"- {item}" for item in hard_list])
        
        prompt = (
            "/no_think Ты технический рекрутер. "
            "Проанализируй список технических навыков кандидата и составь краткое резюме (3-5 предложений). "
            "Укажи:\n"
            "- Основные технологии и языки программирования\n"
            "- Уровень владения (junior/middle/senior) на основе указанных навыков\n"
            "- Сильные стороны и специализация\n"
            "- Потенциальные пробелы в знаниях (если видны)\n\n"
            "Ответ должен быть структурированным и информативным для рекрутера."
        )

        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Навыки кандидата:\n{hard_text}"},
            ],
            temperature=0,
        )

        return resp.choices[0].message.content.strip()

    def summarize_theoretical(self) -> str:
        """
        Суммаризирует результаты теоретического тестирования с помощью LLM.
        Возвращает анализ ответов на теоретические вопросы.
        """
        theoretical_list = self.find_theoretical()
        if not theoretical_list:
            return "Теоретические тесты не пройдены."

        theoretical_text = "\n\n".join([f"Ответ {i+1}:\n{item}" for i, item in enumerate(theoretical_list)])
        
        prompt = (
            "/no_think Ты технический интервьюер. "
            "Проанализируй ответы кандидата на теоретические вопросы по программированию. "
            "Составь краткий отчет (4-6 предложений) с указанием:\n"
            "- Общий уровень теоретических знаний\n"
            "- Сильные темы (алгоритмы, структуры данных, паттерны и т.д.)\n"
            "- Слабые места и пробелы в знаниях\n"
            "- Оценка глубины понимания (поверхностное/глубокое)\n"
            "- Рекомендации по дальнейшему развитию\n\n"
            "Ответ должен быть объективным и полезным для принятия решения о найме."
        )

        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Ответы кандидата на теоретические вопросы:\n{theoretical_text}"},
            ],
            temperature=0,
        )

        return resp.choices[0].message.content.strip()

    def summarize_practical(self) -> str:
        """
        Суммаризирует результаты практического тестирования с помощью LLM.
        Возвращает анализ написанного кода и решения задач.
        """
        practical_list = self.find_practical()
        if not practical_list:
            return "Практические задания не выполнены."

        practical_text = "\n\n".join([f"Решение {i+1}:\n{item}" for i, item in enumerate(practical_list)])
        
        prompt = (
            "/no_think Ты senior разработчик, проводящий code review. "
            "Проанализируй код, написанный кандидатом во время практического тестирования. "
            "Составь детальный отчет (5-7 предложений) с указанием:\n"
            "- Качество кода (читаемость, структура, стиль)\n"
            "- Правильность решения задач\n"
            "- Использование алгоритмов и структур данных\n"
            "- Оптимальность решений (временная и пространственная сложность)\n"
            "- Обработка edge cases и ошибок\n"
            "- Следование best practices\n"
            "- Общая оценка практических навыков программирования\n\n"
            "Ответ должен быть технически точным и содержать конкретные примеры из кода."
        )

        resp = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Код кандидата:\n{practical_text}"},
            ],
            temperature=0,
        )

        return resp.choices[0].message.content.strip()

    def summary(self):
        """
        Генерирует все три типа суммаризаций и выводит их.
        """
        hard_summary = self.summarize_hard_skills()
        theoretical_summary = self.summarize_theoretical()
        practical_summary = self.summarize_practical()

        '''print("=" * 60)
        print("СУММАРИЗАЦИЯ РЕЗУЛЬТАТОВ СОБЕСЕДОВАНИЯ")
        print("=" * 60)
        print("\n[ХАРД СКИЛЫ]")
        print(hard_summary)
        print("\n[ТЕОРЕТИЧЕСКОЕ ТЕСТИРОВАНИЕ]")
        print(theoretical_summary)
        print("\n[ПРАКТИЧЕСКОЕ ТЕСТИРОВАНИЕ]")
        print(practical_summary)
        print("=" * 60)'''

        return {
            "hard_skills_summary": hard_summary,
            "theoretical_test_summary": theoretical_summary,
            "practical_test_summary": practical_summary,
        }

    def save_to_db(self, candidate_name: str = None) -> Report:
        """
        Сохраняет суммаризации в базу данных (модель Report).
        
        Args:
            candidate_name: Имя кандидата (опционально, можно использовать self.candidate_name)
        
        Returns:
            Созданный или обновленный объект Report
        """
        summaries = self.summary()
        
        name = candidate_name or self.candidate_name or ""
        
        report = Report.objects.create(
            hard_skills_summary=summaries["hard_skills_summary"],
            theoretical_test_summary=summaries["theoretical_test_summary"],
            practical_test_summary=summaries["practical_test_summary"],
            candidate_name=name,
        )
        
        print(f"\nРапорт успешно сохранен в БД (ID: {report.id})")
        return report

    def get_full_summary(self) -> str:

        summaries = self.summary()
        return f"""
                ХАРД СКИЛЫ:
                {summaries['hard_skills_summary']}

                ТЕОРЕТИЧЕСКОЕ ТЕСТИРОВАНИЕ:
                {summaries['theoretical_test_summary']}

                ПРАКТИЧЕСКОЕ ТЕСТИРОВАНИЕ:
                {summaries['practical_test_summary']}
                        """.strip()


'''if __name__ == "__main__":
    obj = Resume(
        api_key="sk-EntOXD173KXh0i-jb0esww",
        base_url="https://llm.t1v.scibox.tech/v1",
        model_name="qwen3-coder-30b-a3b-instruct-fp8",
        candidate_name="Иван Иванов"
    )
    
    obj.push_hard("знаю ООП, Python, Django, PostgreSQL")
    obj.push_hard("опыт работы с REST API, Docker")
    obj.push_theoretical("Динамическое программирование - это метод решения задач путем разбиения на подзадачи")
    obj.push_practical("def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)")
    
    summaries = obj.summary()
    
    report = obj.save_to_db()
    
    full_text = obj.get_full_summary()
    print("\n" + "=" * 60)
    print("ПОЛНЫЙ ТЕКСТ РАПОРТА:")
    print("=" * 60)
    print(full_text)
'''