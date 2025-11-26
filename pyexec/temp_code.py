def sum_positive(nums):
    return sum(x for x in nums if x > 0)

nums = list(map(int, input().split()))
print(sum_positive(nums))
