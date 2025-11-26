import json
import random
import string

# =====================
# Лёгкая задача: сумма положительных чисел
# =====================
def generate_tests_easy(n=10):
    tests = []
    for _ in range(n):
        size = random.randint(1, 100)
        nums = [random.randint(-1000, 1000) for _ in range(size)]
        expected = sum(x for x in nums if x > 0)
        tests.append({"input": nums, "expected": expected})
    return tests

with open("codeapp/tests/easy.json", "w", encoding="utf-8") as f:
    json.dump(generate_tests_easy(), f, ensure_ascii=False, indent=2)


# =====================
# Средняя задача: палиндром
# =====================
def generate_tests_medium(n=10):
    tests = []
    for _ in range(n):
        length = random.randint(1, 20)
        half = ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
        palindrome = half + half[::-1]
        tests.append({"input": palindrome, "expected": True})

        # Отрицательный случай
        non_pal = half + ''.join(random.choice(string.ascii_lowercase) for _ in range(length))
        tests.append({"input": non_pal, "expected": False})
    return tests

with open("codeapp/tests/medium.json", "w", encoding="utf-8") as f:
    json.dump(generate_tests_medium(), f, ensure_ascii=False, indent=2)


# =====================
# Сложная задача: минимальная сумма подмассива длины k
# =====================
def generate_tests_hard(n=10):
    tests = []
    for _ in range(n):
        size = random.randint(5, 20)
        k = random.randint(1, size)
        nums = [random.randint(-10, 10) for _ in range(size)]
        min_sum = min(sum(nums[i:i+k]) for i in range(size-k+1))
        tests.append({"input": {"nums": nums, "k": k}, "expected": min_sum})
    return tests

with open("codeapp/tests/hard.json", "w", encoding="utf-8") as f:
    json.dump(generate_tests_hard(), f, ensure_ascii=False, indent=2)
