import numpy as np
from openai import OpenAI
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from hackatone.task_search import TaskSearcher
else:
    # Для обратной совместимости при отсутствии модуля
    try:
        from hackatone.task_search import TaskSearcher
    except ImportError:
        TaskSearcher = None


class Interactor:
    def __init__(self, key: Optional[str] = None, task_searcher: Optional['TaskSearcher'] = None):
        self.client = OpenAI(
            api_key=key or "sk-EntOXD173KXh0i-jb0esww",
            base_url="https://llm.t1v.scibox.tech/v1"
        )
        self.hard_desc: Optional[str] = None
        self.chat_history: List[Dict[str, Any]] = []
        self.theory_questions: List[str] = []
        self.current_question_idx: int = 0
        self.stage: str = "init"
        self.awaiting_hint_answer: bool = False
        self.current_hint: Optional[str] = None
        self.candidate_summary: Optional[str] = None
        self.terminated: bool = False
        self.termination_reason: Optional[str] = None
        self.hard_desc_attempts: int = 0
        self.answer_attempts: Dict[int, int] = {}
        
        # Практические задачи
        self.task_searcher: Optional['TaskSearcher'] = task_searcher
        self.recommended_tasks: List[Dict[str, Any]] = []
        self.current_task: Optional[Dict[str, Any]] = None
        self.current_task_idx: int = -1
        self.task_solution_attempts: Dict[int, int] = {}  # Индекс задачи -> количество попыток
        self.task_dialogue_history: List[Dict[str, Any]] = []  # История диалога по текущей задаче

    def _validate_input(self, text: str, context: str = "answer") -> Dict[str, Any]:
        """
        Валидирует ввод пользователя: проверяет на пустоту, неинформативность и провокационность.
        
        Args:
            text: текст для проверки
            context: "hard_desc" или "answer"
        
        Returns:
            {
                "valid": bool,
                "reason": str,  # "empty" | "too_short" | "not_informative" | "provocative" | "ok"
                "is_provocative": bool,
                "message": str  # сообщение для пользователя
            }
        """
        text = text.strip()
        
        if not text or len(text) < 3:
            return {
                "valid": False,
                "reason": "empty",
                "is_provocative": False,
                "message": "Ваш ответ слишком короткий или пустой. Пожалуйста, дайте более развернутый ответ."
            }
        
        system_prompt = (
            "/no_think Ты модератор технического интервью. "
            "Проанализируй текст и определи:\n"
            "1. Является ли текст провокационным, оскорбительным, неуместным или нарушающим правила общения?\n"
            "2. Является ли текст осмысленным и относящимся к теме вопроса? Ответы типа 'не знаю', 'не понимаю' являются осмысленными.\n"
            "Верни JSON строго с ключами:\n"
            "{\n"
            '  \"is_provocative\": true/false,\n'
            '  \"is_informative\": true/false,\n'
            '  \"reason\": \"краткое объяснение на русском\"\n'
            "}"
        )
        
        user_content = (
            f"Контекст: {context}\n"
            f"Текст для проверки: {text}\n"
            "Проанализируй и верни JSON."
        )
        
        try:
            resp = self.client.chat.completions.create(
                model="qwen3-coder-30b-a3b-instruct-fp8",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                stream=False,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            data = json.loads(resp.choices[0].message.content)
            is_provocative = data.get("is_provocative", False)
            is_informative = data.get("is_informative", True)
            
            if is_provocative:
                return {
                    "valid": False,
                    "reason": "provocative",
                    "is_provocative": True,
                    "message": "Ваше поведение нарушает правила интервью. Интервью прервано."
                }
            
            if not is_informative:
                return {
                    "valid": False,
                    "reason": "not_informative",
                    "is_provocative": False,
                    "message": "Ваш ответ недостаточно информативен. Пожалуйста, дайте более развернутый ответ."
                }
            
            return {
                "valid": True,
                "reason": "ok",
                "is_provocative": False,
                "message": ""
            }
            
        except Exception:
            return {
                "valid": False,
                "reason": "too_short",
                "is_provocative": False,
                "message": "Ваше сообщение не понятно, либо произошла ошибка. Пожалуйста, попробуйте еще раз."
            }

    def put_hard_desc(self, desc: str) -> Dict[str, Any]:
        """
        Сохранить описание хард-скиллов кандидата с валидацией.
        
        Returns:
            {
                "success": bool,
                "message": str,  # сообщение для пользователя
                "needs_retry": bool  # нужно ли повторить запрос
            }
        """
        if self.terminated:
            return {
                "success": False,
                "message": "Интервью было прервано.",
                "needs_retry": False
            }
        
        validation = self._validate_input(desc, context="hard_desc")
        
        if validation["is_provocative"]:
            self.terminated = True
            self.termination_reason = "Провокационное поведение при описании навыков"
            return {
                "success": False,
                "message": validation["message"],
                "needs_retry": False
            }
        
        if not validation["valid"]:
            self.hard_desc_attempts += 1
            if self.hard_desc_attempts >= 3:
                self.terminated = True
                self.termination_reason = "Превышено количество попыток для описания навыков"
                return {
                    "success": False,
                    "message": "Превышено количество попыток. Интервью прервано.",
                    "needs_retry": False
                }
            return {
                "success": False,
                "message": validation["message"],
                "needs_retry": True
            }
        
        self.hard_desc = desc
        self.hard_desc_attempts = 0
        return {
            "success": True,
            "message": "",
            "needs_retry": False
        }

    def start_interview(self, desc: Optional[str] = None) -> Dict[str, Any]:
        """
        Запустить интервью с валидацией hard_desc.
        
        Returns:
            {
                "success": bool,
                "message": str,
                "needs_retry": bool
            }
        """
        if self.terminated:
            return {
                "success": False,
                "message": "Интервью было прервано.",
                "needs_retry": False
            }
        
        if desc is not None:
            result = self.put_hard_desc(desc)
            if not result["success"]:
                return result
        
        if not self.hard_desc:
            return {
                "success": False,
                "message": "hard_desc не задан. Передай его в start_interview() или put_hard_desc().",
                "needs_retry": True
            }
        
        try:
            self.get_theory_questions()
            self.current_question_idx = 0
            self.stage = "theory"
            self.chat_history = []
            return {
                "success": True,
                "message": "",
                "needs_retry": False
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка при генерации вопросов: {str(e)}",
                "needs_retry": False
            }


    def get_theory_questions(self) -> List[str]:
        """
        Генерирует список теоретических вопросов по self.hard_desc
        и сохраняет их в self.theory_questions.
        Возвращает список вопросов.
        """
        if not self.hard_desc:
            raise ValueError("hard_desc не задан. Сначала вызови put_hard_desc() или start_interview().")

        response = self.client.chat.completions.create(
            model="qwen3-coder-30b-a3b-instruct-fp8",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "/no_think Ты интервьюер, который получает описание навыков собеседуемого программиста. "
                        "Твоя задача — придумать теоретические вопросы по программированию, исходя из его заявленных навыков. "
                        "Каждый вопрос должен проверять знания АЛГОРИТМОВ и СТРУКТУР ДАННЫХ и относиться к одной из заявленных областей. "
                        "Вопросы должны быть общими и не требовать написания кода, только устного объяснения. "
                        "Сгенерируй РОВНО ОДИН вопрос. "
                        "Верни ответ строго в формате JSON-массива строк, без лишнего текста, например: "
                        "[\"Вопрос 1?\"]"
                    )
                },
                {"role": "user", "content": self.hard_desc}
            ],
            stream=False,
            temperature=0.0
        )

        raw = response.choices[0].message.content.strip()

        import json
        questions: List[str] = []

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, str):
                        q = item.strip()
                        if not q.endswith("?"):
                            q = q.rstrip(".") + "?"
                        questions.append(q)
        except Exception:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            for p in parts:
                if not p.endswith("?"):
                    p = p.rstrip(".") + "?"
                questions.append(p)

        self.theory_questions = questions
        return self.theory_questions


    def _evaluate_answer_with_llm(self, question: str, answer: str) -> Dict[str, Any]:
        """
        Оценивает ответ с помощью LLM.
        Возвращает dict:
        {
            "verdict": "correct" | "partially_correct" | "incorrect",
            "hint": Optional[str],    # наводящий вопрос, если есть
            "comment": str            # короткий комментарий-оценка
        }
        """
        system_prompt = (
            "/no_think Ты опытный технический интервьюер по алгоритмам и структурам данных. "
            "Тебе дан вопрос и ответ кандидата. "
            "Твоя задача: строго оценить, насколько ответ корректен, и при необходимости предложить наводящий вопрос.\n\n"
            "Формат ответа: JSON без пояснений, строго с ключами:\n"
            "{\n"
            '  \"verdict\": \"correct\" | \"partially_correct\" | \"incorrect\", \n'
            '  \"hint\": \"строка с наводящим вопросом или пустая строка\", \n'
            '  \"comment\": \"краткий комментарий на русском\"\n'
            "}"
        )

        user_content = (
            f"Вопрос: {question}\n"
            f"Ответ кандидата: {answer}\n"
            "Проанализируй ответ и верни JSON."
        )

        resp = self.client.chat.completions.create(
            model="qwen3-coder-30b-a3b-instruct-fp8",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            stream=False,
            response_format={"type": "json_object"},
            temperature=0.0
        )

        import json
        raw = resp.choices[0].message.content
        try:
            data = json.loads(raw)
        except Exception:
            data = {
                "verdict": "partially_correct",
                "hint": "",
                "comment": raw[:200],
            }
        return data

    def get_next_question(self) -> Optional[str]:
        """
        Вернуть следующий теоретический вопрос или наводящий вопрос, если он сейчас ожидается.
        Если вопросы закончились – переводит стадию в 'finished' и возвращает None.
        """
        if self.terminated:
            return None
            
        if self.stage != "theory":
            return None

        if self.awaiting_hint_answer and self.current_hint:
            return self.current_hint

        if self.current_question_idx >= len(self.theory_questions):
            self.stage = "finished"
            return None

        question = self.theory_questions[self.current_question_idx]
        return question

    def submit_theory_answer(self, answer: str) -> Dict[str, Any]:
        """
        Принять ответ кандидата с валидацией.
        
        Returns:
            {
                "success": bool,
                "message": str,  # сообщение для пользователя
                "needs_retry": bool  # нужно ли повторить запрос
            }
        """
        if self.terminated:
            return {
                "success": False,
                "message": "Интервью было прервано.",
                "needs_retry": False
            }
        
        if self.stage != "theory":
            return {
                "success": False,
                "message": "Сейчас не этап теории. Сначала вызови start_interview().",
                "needs_retry": False
            }

        if self.current_question_idx >= len(self.theory_questions):
            return {
                "success": False,
                "message": "Теоретические вопросы уже закончились.",
                "needs_retry": False
            }
        
        validation = self._validate_input(answer, context="answer")
        
        if validation["is_provocative"]:
            self.terminated = True
            self.termination_reason = "Провокационное поведение при ответе на вопрос"
            return {
                "success": False,
                "message": validation["message"],
                "needs_retry": False
            }
        
        if not validation["valid"]:
            q_idx = self.current_question_idx
            self.answer_attempts[q_idx] = self.answer_attempts.get(q_idx, 0) + 1
            
            if self.answer_attempts[q_idx] >= 3:
                self.terminated = True
                self.termination_reason = f"Превышено количество попыток для вопроса {q_idx + 1}"
                return {
                    "success": False,
                    "message": "Превышено количество попыток. Интервью прервано.",
                    "needs_retry": False
                }
            
            return {
                "success": False,
                "message": validation["message"],
                "needs_retry": True
            }
        
        q_idx = self.current_question_idx
        self.answer_attempts[q_idx] = 0
        
        if self.awaiting_hint_answer:
            base_question = self.theory_questions[self.current_question_idx]
            eval_result = self._evaluate_answer_with_llm(base_question, answer)

            verdict = eval_result.get("verdict", "partially_correct")
            comment = eval_result.get("comment", "")

            self.chat_history.append(
                {
                    "type": "theory_qa",
                    "index": self.current_question_idx,
                    "question": self.current_hint,
                    "answer": answer,
                    "after_hint": True,
                    "verdict": verdict,
                    "comment": comment,
                }
            )

            self.awaiting_hint_answer = False
            self.current_hint = None
            self.current_question_idx += 1
            return {
                "success": True,
                "message": "",
                "needs_retry": False
            }

        question = self.theory_questions[self.current_question_idx]
        eval_result = self._evaluate_answer_with_llm(question, answer)

        verdict = eval_result.get("verdict", "partially_correct")
        hint = (eval_result.get("hint") or "").strip()
        comment = eval_result.get("comment", "")

        self.chat_history.append(
            {
                "type": "theory_qa",
                "index": self.current_question_idx,
                "question": question,
                "answer": answer,
                "after_hint": False,
                "verdict": verdict,
                "comment": comment,
            }
        )

        if verdict == "correct" or not hint:
            self.current_question_idx += 1
            self.awaiting_hint_answer = False
            self.current_hint = None
        else:
            self.awaiting_hint_answer = True
            self.current_hint = hint
        
        return {
            "success": True,
            "message": "",
            "needs_retry": False
        }

    def compute_theory_score(self) -> Dict[str, float]:
        """
        Подсчитать оценку по теоретическим вопросам.
        correct без наводки = 2 балла, correct после наводки = 1, остальное = 0.

        max_score считается как 2 * количество теоретических вопросов (даже если кандидат не ответил).
        """
        total = 0
        answered = 0
        total_questions = len(self.theory_questions)
        max_score = 2 * total_questions if total_questions else 0

        for item in self.chat_history:
            if item.get("type") != "theory_qa":
                continue
            answered += 1
            if item.get("verdict") == "correct":
                total += 1 if item.get("after_hint") else 2

        return {
            "questions_total": total_questions,
            "answered": answered,
            "score": total,
            "max_score": max_score,
            "ratio": total / max_score if max_score else 0.0,
        }

    def build_candidate_summary(self) -> str:
        """
        Строит текстовое мнение о кандидате по истории ответов.
        Этот текст удобно векторизовать и использовать для подбора задач.
        """
        theory_score = self.compute_theory_score()
        theory_qa = [
            {
                "question": item.get("question"),
                "answer": item.get("answer"),
                "verdict": item.get("verdict"),
                "after_hint": item.get("after_hint"),
                "comment": item.get("comment"),
            }
            for item in self.chat_history
            if item.get("type") == "theory_qa"
        ]

        import json
        user_content = json.dumps(
            {
                "hard_skills_description": self.hard_desc,
                "theory_score": theory_score,
                "theory_qa": theory_qa,
            },
            ensure_ascii=False,
        )

        system_prompt = (
            "/no_think Ты технический интервьюер. "
            "По данным об ответах кандидата составь КОРОТКОЕ текстовое резюме его уровня по алгоритмам и структурам данных. "
            "Резюме должно быть удобно для векторизации и подбора задач, поэтому:\n"
            "- не пиши лишний вводный текст,\n"
            "- используй 3–6 коротких предложений,\n"
            "- явно упомяни сильные и слабые темы (например: графы, деревья, сложность, динамическое программирование),\n"
            "- укажи примерный уровень (junior/middle/senior по АиСД),\n"
            "- укажи, какие типы задач стоит дать кандидату (по каким темам и примерно какой сложности).\n"
            "Ответ верни одним абзацем на русском языке."
        )

        resp = self.client.chat.completions.create(
            model="qwen3-coder-30b-a3b-instruct-fp8",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            stream=False,
        )

        summary = resp.choices[0].message.content.strip()
        self.candidate_summary = summary
        return summary

    def get_recommended_tasks(self, task_searcher: Optional['TaskSearcher'] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Получает список рекомендованных задач для кандидата на основе его резюме.
        Возвращает только описание задач без лишней информации о навыках.
        
        Args:
            task_searcher: экземпляр TaskSearcher (если не передан, используется self.task_searcher)
            top_k: количество задач для подбора
        
        Returns:
            Список словарей с задачами:
            {
                "task_index": int,
                "condition": str,
                "description": str,
                "similarity": float
            }
        """
        if not self.candidate_summary:
            self.build_candidate_summary()
        
        searcher = task_searcher or self.task_searcher
        if not searcher:
            raise ValueError("TaskSearcher не задан. Передай его в конструктор или в этот метод.")
        
        # Ищем задачи по резюме кандидата
        search_results = searcher.search(self.candidate_summary, top_k=top_k)
        
        recommended = []
        for task_index, condition, description, similarity in search_results:
            recommended.append({
                "task_index": task_index,
                "condition": condition,
                "description": description,
                "similarity": similarity
            })
        
        self.recommended_tasks = recommended
        return recommended
    
    def get_task_description_for_candidate(self) -> Optional[str]:
        """
        Возвращает четкое описание текущей задачи для кандидата (без лишней информации).
        
        Returns:
            Строка с описанием задачи или None, если задача не выбрана
        """
        if not self.current_task:
            return None
        
        condition = self.current_task.get("condition", "").strip()
        description = self.current_task.get("description", "").strip()
        
        if condition:
            return f"{condition}\n\n{description}"
        return description
    
    def start_practice_stage(self, task_searcher: Optional['TaskSearcher'] = None, top_k: int = 5) -> Dict[str, Any]:
        """
        Начинает этап практических задач. Подбирает задачи и переводит интервью в стадию "practice".
        
        Args:
            task_searcher: экземпляр TaskSearcher
            top_k: количество задач для подбора
        
        Returns:
            {
                "success": bool,
                "message": str,
                "tasks_count": int  # количество подобранных задач
            }
        """
        if self.terminated:
            return {
                "success": False,
                "message": "Интервью было прервано.",
                "tasks_count": 0
            }
        
        if self.stage != "theory" and self.stage != "finished":
            return {
                "success": False,
                "message": "Сначала заверши теоретическую часть интервью.",
                "tasks_count": 0
            }
        
        try:
            tasks = self.get_recommended_tasks(task_searcher, top_k)
            if not tasks:
                return {
                    "success": False,
                    "message": "Не удалось подобрать задачи. Убедись, что TaskSearcher содержит задачи.",
                    "tasks_count": 0
                }
            
            self.stage = "practice"
            self.current_task_idx = -1
            self.current_task = None
            self.task_solution_attempts = {}
            self.task_dialogue_history = []
            
            return {
                "success": True,
                "message": "",
                "tasks_count": len(tasks)
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка при подборе задач: {str(e)}",
                "tasks_count": 0
            }
    
    def get_next_task(self) -> Optional[Dict[str, Any]]:
        """
        Возвращает следующую задачу для решения.
        
        Returns:
            Словарь с задачей или None, если задачи закончились
        """
        if self.terminated or self.stage != "practice":
            return None
        
        if not self.recommended_tasks:
            return None
        
        self.current_task_idx += 1
        if self.current_task_idx >= len(self.recommended_tasks):
            self.stage = "finished"
            return None
        
        self.current_task = self.recommended_tasks[self.current_task_idx]
        self.task_dialogue_history = []
        self.task_solution_attempts[self.current_task_idx] = 0
        
        return {
            "task_index": self.current_task["task_index"],
            "description": self.get_task_description_for_candidate()
        }
        
    def _generate_hinting_question(self, code_quality: str, solution_completeness: str, 
                                   attempt: int) -> str:
        """
        Генерирует наводящий вопрос на основе качества кода и полноты решения.
        
        Args:
            code_quality: описание качества кода
            solution_completeness: описание полноты решения
            attempt: номер попытки
        
        Returns:
            Наводящий вопрос для кандидата
        """
        task_info = ""
        if self.current_task:
            condition = self.current_task.get("condition", "")
            description = self.current_task.get("description", "")
            task_info = f"Условие задачи: {condition}\nОписание: {description}"
        
        system_prompt = (
            "/no_think Ты опытный технический интервьюер. "
            "Твоя задача — сформулировать наводящий вопрос для кандидата, который поможет ему улучшить решение задачи.\n\n"
            "Наводящий вопрос должен:\n"
            "- быть конкретным и направленным на проблему в решении\n"
            "- не давать прямого ответа, а подталкивать к правильному направлению\n"
            "- учитывать тип задачи и выявленные проблемы\n"
            "- быть кратким (1-2 предложения)\n\n"
            "Верни только наводящий вопрос на русском языке, без дополнительных пояснений."
        )
        
        user_content = (
            f"{task_info}\n\n"
            f"Качество кода: {code_quality}\n"
            f"Полнота решения: {solution_completeness}\n"
            f"Номер попытки: {attempt}\n\n"
            "Сформулируй наводящий вопрос, который поможет кандидату улучшить решение."
        )
        
        try:
            resp = self.client.chat.completions.create(
                model="qwen3-coder-30b-a3b-instruct-fp8",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                stream=False,
                temperature=0.7
            )
            
            hint = resp.choices[0].message.content.strip()
            return hint
        except Exception:
            # Fallback наводящий вопрос
            return "Подумайте, какие аспекты решения можно улучшить? Проверьте все требования задачи."
    
    def _evaluate_solution_with_llm(self, code_quality: str, solution_completeness: str, 
                                    previous_dialogue: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Оценивает решение задачи с учетом качества кода и полноты решения.
        
        Args:
            code_quality: описание качества кода (например, "хороший код", "есть ошибки", "неоптимальное решение")
            solution_completeness: описание полноты решения (например, "полное решение", "частичное решение", "не решено")
            previous_dialogue: история предыдущего диалога по задаче
        
        Returns:
            {
                "verdict": "mastered" | "partially_mastered" | "not_mastered" | "continue",
                "message": str,  # сообщение для кандидата
                "hint": Optional[str],  # наводящий вопрос, если нужен
                "should_continue": bool  # нужно ли продолжать диалог
            }
        """
        task_info = ""
        if self.current_task:
            condition = self.current_task.get("condition", "")
            description = self.current_task.get("description", "")
            task_info = f"Условие задачи: {condition}\nОписание: {description}"
        
        dialogue_context = ""
        if previous_dialogue:
            dialogue_context = "\nПредыдущий диалог:\n"
            for entry in previous_dialogue[-3:]:  # Последние 3 записи
                dialogue_context += f"- {entry.get('role', 'unknown')}: {entry.get('content', '')}\n"
        
        system_prompt = (
            "/no_think Ты опытный технический интервьюер. "
            "Твоя задача — оценить, владеет ли кандидат навыками, которые проверяет задача, "
            "на основе качества кода и полноты решения.\n\n"
            "Ты должен принять финальное решение только если:\n"
            "1. Кандидат явно владеет навыками (mastered) — код качественный, решение полное и правильное\n"
            "2. Кандидат явно не владеет навыками (not_mastered) — код некачественный, решение неполное или неправильное, и уже было несколько попыток\n"
            "3. Кандидат частично владеет навыками (partially_mastered) — код приемлемый, но решение неполное, или наоборот\n\n"
            "Если информации недостаточно для финального решения, верни 'continue' и предложи наводящий вопрос.\n\n"
            "Формат ответа: JSON строго с ключами:\n"
            "{\n"
            '  \"verdict\": \"mastered\" | \"partially_mastered\" | \"not_mastered\" | \"continue\",\n'
            '  \"message\": \"сообщение для кандидата на русском\",\n'
            '  \"hint\": \"наводящий вопрос на русском (если verdict == continue, иначе пустая строка)\",\n'
            '  \"should_continue\": true/false\n'
            "}"
        )
        
        user_content = (
            f"{task_info}\n\n"
            f"Качество кода: {code_quality}\n"
            f"Полнота решения: {solution_completeness}\n"
            f"{dialogue_context}\n"
            "Оцени решение и верни JSON."
        )
        
        resp = self.client.chat.completions.create(
            model="qwen3-coder-30b-a3b-instruct-fp8",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            stream=False,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        try:
            data = json.loads(resp.choices[0].message.content)
            verdict = data.get("verdict", "continue")
            message = data.get("message", "")
            hint = data.get("hint", "").strip()
            should_continue = data.get("should_continue", True)
            
            # Если вердикт "continue" и наводящий вопрос не был сгенерирован, генерируем его
            if verdict == "continue" and not hint:
                attempt = self.task_solution_attempts.get(self.current_task_idx, 0) + 1
                hint = self._generate_hinting_question(code_quality, solution_completeness, attempt)
            
            return {
                "verdict": verdict,
                "message": message,
                "hint": hint,
                "should_continue": should_continue
            }
        except Exception:
            # Генерируем наводящий вопрос как fallback
            attempt = self.task_solution_attempts.get(self.current_task_idx, 0) + 1
            hint = self._generate_hinting_question(code_quality, solution_completeness, attempt)
            return {
                "verdict": "continue",
                "message": "Требуется дополнительная информация для оценки.",
                "hint": hint,
                "should_continue": True
            }
    
    def submit_task_solution(self, code_quality: str, solution_completeness: str, 
                            candidate_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Принимает информацию о решении задачи и оценивает его.
        
        Args:
            code_quality: описание качества кода
            solution_completeness: описание полноты решения
            candidate_message: опциональное сообщение от кандидата
        
        Returns:
            {
                "success": bool,
                "verdict": "mastered" | "partially_mastered" | "not_mastered" | "continue",
                "message": str,  # сообщение для кандидата
                "task_completed": bool,  # завершена ли работа с задачей
                "needs_retry": bool  # нужно ли повторить запрос
            }
        """
        if self.terminated:
            return {
                "success": False,
                "message": "Интервью было прервано.",
                "verdict": None,
                "task_completed": False,
                "needs_retry": False
            }
        
        if self.stage != "practice":
            return {
                "success": False,
                "message": "Сейчас не этап практических задач. Сначала вызови start_practice_stage().",
                "verdict": None,
                "task_completed": False,
                "needs_retry": False
            }
        
        if not self.current_task:
            return {
                "success": False,
                "message": "Задача не выбрана. Сначала вызови get_next_task().",
                "verdict": None,
                "task_completed": False,
                "needs_retry": False
            }
        
        # Добавляем сообщение кандидата в историю диалога
        if candidate_message:
            validation = self._validate_input(candidate_message, context="answer")
            if validation["is_provocative"]:
                self.terminated = True
                self.termination_reason = "Провокационное поведение при решении задачи"
                return {
                    "success": False,
                    "message": validation["message"],
                    "verdict": None,
                    "task_completed": False,
                    "needs_retry": False
                }
            
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"],
                    "verdict": None,
                    "task_completed": False,
                    "needs_retry": True
                }
            
            self.task_dialogue_history.append({
                "role": "candidate",
                "content": candidate_message
            })
        
        # Оцениваем решение
        eval_result = self._evaluate_solution_with_llm(
            code_quality, 
            solution_completeness,
            self.task_dialogue_history
        )
        
        verdict = eval_result.get("verdict", "continue")
        message = eval_result.get("message", "")
        hint = eval_result.get("hint", "").strip()
        should_continue = eval_result.get("should_continue", True)
        
        # Сохраняем в историю
        attempt_num = self.task_solution_attempts.get(self.current_task_idx, 0) + 1
        self.chat_history.append({
            "type": "practice_task",
            "task_index": self.current_task["task_index"],
            "task_idx": self.current_task_idx,
            "code_quality": code_quality,
            "solution_completeness": solution_completeness,
            "candidate_message": candidate_message,
            "verdict": verdict,
            "message": message,
            "hint": hint,
            "attempt": attempt_num
        })
        
        self.task_dialogue_history.append({
            "role": "evaluator",
            "content": message
        })
        
        # Если есть наводящий вопрос, сохраняем его в историю диалога
        if hint and verdict == "continue":
            self.task_dialogue_history.append({
                "role": "interviewer",
                "content": hint
            })
        
        # Если решение принято, завершаем работу с задачей
        task_completed = verdict in ["mastered", "partially_mastered", "not_mastered"]
        
        if task_completed:
            self.task_solution_attempts[self.current_task_idx] = self.task_solution_attempts.get(self.current_task_idx, 0) + 1
        else:
            # Увеличиваем счетчик попыток
            self.task_solution_attempts[self.current_task_idx] = self.task_solution_attempts.get(self.current_task_idx, 0) + 1
            
            # Если слишком много попыток, завершаем задачу как "not_mastered"
            if self.task_solution_attempts[self.current_task_idx] >= 5:
                verdict = "not_mastered"
                message = "Превышено количество попыток. Задача помечена как не решенная."
                task_completed = True
                self.chat_history[-1]["verdict"] = verdict
                self.chat_history[-1]["message"] = message
        
        return {
            "success": True,
            "verdict": verdict,
            "message": message,
            "hint": hint if verdict == "continue" else None,  # Возвращаем наводящий вопрос, если нужен
            "task_completed": task_completed,
            "needs_retry": not task_completed and should_continue
        }
    
    def continue_task_dialogue(self, candidate_message: str) -> Dict[str, Any]:
        """
        Продолжает диалог о текущей задаче. Используется для уточняющих вопросов и обсуждения решения.
        
        Args:
            candidate_message: сообщение кандидата
        
        Returns:
            {
                "success": bool,
                "message": str,  # ответ интервьюера
                "needs_retry": bool
            }
        """
        if self.terminated:
            return {
                "success": False,
                "message": "Интервью было прервано.",
                "needs_retry": False
            }
        
        if self.stage != "practice" or not self.current_task:
            return {
                "success": False,
                "message": "Сейчас нет активной задачи для обсуждения.",
                "needs_retry": False
            }
        
        validation = self._validate_input(candidate_message, context="answer")
        
        if validation["is_provocative"]:
            self.terminated = True
            self.termination_reason = "Провокационное поведение при обсуждении задачи"
            return {
                "success": False,
                "message": validation["message"],
                "needs_retry": False
            }
        
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"],
                "needs_retry": True
            }
        
        # Генерируем ответ интервьюера на основе контекста задачи
        task_info = self.get_task_description_for_candidate()
        dialogue_context = "\n".join([
            f"{entry.get('role', 'unknown')}: {entry.get('content', '')}"
            for entry in self.task_dialogue_history[-5:]  # Последние 5 записей
        ])
        
        system_prompt = (
            "/no_think Ты технический интервьюер, который обсуждает решение задачи с кандидатом. "
            "Твоя задача — задавать уточняющие вопросы, помогать разобраться в проблеме, "
            "но не давать прямых ответов. Будь вежливым и профессиональным.\n\n"
            "Ответ должен быть кратким (1-2 предложения) и на русском языке."
        )
        
        user_content = (
            f"Задача:\n{task_info}\n\n"
            f"Контекст диалога:\n{dialogue_context}\n\n"
            f"Сообщение кандидата: {candidate_message}\n\n"
            "Ответь кандидату."
        )
        
        try:
            resp = self.client.chat.completions.create(
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
            self.task_dialogue_history.append({
                "role": "candidate",
                "content": candidate_message
            })
            self.task_dialogue_history.append({
                "role": "interviewer",
                "content": response_message
            })
            
            return {
                "success": True,
                "message": response_message,
                "needs_retry": False
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Ошибка при генерации ответа: {str(e)}",
                "needs_retry": False
            }

    def _build_practice_report(self) -> List[Dict[str, Any]]:
        """
        Формирует подробные данные о выполненных практических задачах на основе chat_history.
        Возвращает список словарей с ключами:
            {
                "task_index": int,
                "condition": str,
                "description": str,
                "attempts": List[
                    {
                        "attempt": int,
                        "code_quality": str,
                        "solution_completeness": str,
                        "verdict": str,
                        "message": str,
                        "hint": Optional[str]
                    }
                ],
                "final_verdict": str
            }
        """
        report: Dict[int, Dict[str, Any]] = {}

        # Собираем информацию по каждой задаче
        for entry in self.chat_history:
            if entry.get("type") != "practice_task":
                continue

            task_idx = entry.get("task_idx")
            task_index = entry.get("task_index")
            if task_idx is None or task_index is None:
                continue

            if task_idx not in report:
                # Получаем описание задачи из TaskSearcher (если доступен)
                condition = ""
                description = ""
                if self.task_searcher:
                    task_info = self.task_searcher.get_task_by_index(task_index)
                    if task_info:
                        condition, description = task_info
                else:
                    if self.current_task and self.current_task.get("task_index") == task_index:
                        condition = self.current_task.get("condition", "")
                        description = self.current_task.get("description", "")

                report[task_idx] = {
                    "task_index": task_index,
                    "condition": condition,
                    "description": description,
                    "attempts": [],
                    "final_verdict": entry.get("verdict", "unknown")
                }

            report[task_idx]["attempts"].append({
                "attempt": entry.get("attempt"),
                "code_quality": entry.get("code_quality"),
                "solution_completeness": entry.get("solution_completeness"),
                "verdict": entry.get("verdict"),
                "message": entry.get("message"),
                "hint": entry.get("hint")
            })

            # Обновляем финальный вердикт
            report[task_idx]["final_verdict"] = entry.get("verdict", report[task_idx]["final_verdict"])

        # Преобразуем в список и сортируем по task_idx
        report_list = [
            {
                "task_index": data["task_index"],
                "condition": data["condition"],
                "description": data["description"],
                "attempts": sorted(data["attempts"], key=lambda x: x["attempt"] or 0),
                "final_verdict": data["final_verdict"]
            }
            for data in sorted(report.values(), key=lambda x: x["task_index"])
        ]

        return report_list

    def get_practice_report_text(self) -> str:
        """
        Возвращает текстовый отчет о решении практических задач.
        Для каждой задачи указываются условие, описание, качество кода и полнота решения по каждой попытке.
        """
        report_data = self._build_practice_report()
        if not report_data:
            return "Практические задачи не выполнялись."

        parts = []
        for task in report_data:
            task_header = (
                f"Задача #{task['task_index']}:\n"
                f"Условие: {task['condition'] or 'не указано'}\n"
                f"Описание: {task['description'] or 'не указано'}\n"
                f"Финальный вердикт: {task['final_verdict']}\n"
            )
            attempt_lines = []
            for attempt in task["attempts"]:
                attempt_lines.append(
                    f"  - Попытка {attempt['attempt'] or 'N/A'}:\n"
                    f"      Качество кода: {attempt['code_quality']}\n"
                    f"      Полнота решения: {attempt['solution_completeness']}\n"
                    f"      Вердикт: {attempt['verdict']} — {attempt['message']}\n"
                    f"      Наводящая подсказка: {attempt['hint'] or 'не было'}"
                )

            parts.append(task_header + "\n".join(attempt_lines))

        return "\n\n".join(parts)

    
    def reset(self):
        self.hard_desc = None
        self.chat_history = []
        self.theory_questions = []
        self.current_question_idx = 0
        self.stage = "init"
        self.awaiting_hint_answer = False
        self.current_hint = None
        self.candidate_summary = None
        self.terminated = False
        self.termination_reason = None
        self.hard_desc_attempts = 0
        self.answer_attempts = {}
        self.recommended_tasks = []
        self.current_task = None
        self.current_task_idx = -1
        self.task_solution_attempts = {}
        self.task_dialogue_history = []
