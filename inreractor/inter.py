from interactor import Interactor


def main():
    api_key = "sk-EntOXD173KXh0i-jb0esww"  # или возьми из env

    inter = Interactor(key=api_key)

    # Ввод hard_desc с валидацией
    while True:
        hard_desc = input("Опиши свои навыки (hard skills):\n> ")
        result = inter.put_hard_desc(hard_desc)
        
        if result["success"]:
            break
        
        print(f"\n⚠️ {result['message']}")
        if not result["needs_retry"]:
            print(f"Интервью прервано: {inter.termination_reason}")
            return
    
    # Запуск интервью
    result = inter.start_interview()
    if not result["success"]:
        print(f"\n❌ {result['message']}")
        if inter.terminated:
            print(f"Интервью прервано: {inter.termination_reason}")
        return

    print("\n--- Теоретическая часть ---")
    while True:
        if inter.terminated:
            print(f"\n❌ Интервью прервано: {inter.termination_reason}")
            break
            
        q = inter.get_next_question()
        if q is None:
            print("Теоретические вопросы закончились.")
            break

        print("\nВопрос:", q)
        
        # Ввод ответа с валидацией
        while True:
            ans = input("Твой ответ:\n> ")
            result = inter.submit_theory_answer(ans)
            
            if result["success"]:
                break
            
            print(f"\n⚠️ {result['message']}")
            if not result["needs_retry"]:
                print(f"Интервью прервано: {inter.termination_reason}")
                return

    if inter.terminated:
        print(f"\n❌ Интервью прервано: {inter.termination_reason}")
        return

    print("\n--- История по теории (сырой вид) ---")
    from pprint import pprint
    pprint(inter.chat_history)

    print("\n--- Оценка по теоретическим вопросам ---")
    try:
        theory_score = inter.compute_theory_score()
        pprint(theory_score)
    except AttributeError:
        print("Метод compute_theory_score пока не реализован в Interactor.")

    print("\n--- Текстовое резюме кандидата (для векторизации) ---")
    try:
        summary = inter.build_candidate_summary()
        print(summary)
    except AttributeError:
        print("Метод build_candidate_summary пока не реализован в Interactor.")


if __name__ == "__main__":
    main()