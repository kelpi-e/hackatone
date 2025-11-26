import numpy as np
from openai import OpenAI
from typing import List, Dict, Any, Optional
import json


class Interactor:
    def __init__(self, key: Optional[str] = None):
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
            "2. Является ли текст информативным и содержательным (не просто 'да', 'нет', 'не знаю', случайные символы)?\n\n"
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
                "message": "Ваше сообщение не понятно. Пожалуйста, попробуйте еще раз."
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
                        "Сгенерируй РОВНО ТРИ вопроса. "
                        "Верни ответ строго в формате JSON-массива строк, без лишнего текста, например: "
                        "[\"Вопрос 1?\", \"Вопрос 2?\", \"Вопрос 3?\"]"
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

    def reset(self):
        """Полностью сбрасывает состояние интервью."""
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
