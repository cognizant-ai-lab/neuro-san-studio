import argparse
import json
import random


def generate_long_multiplication(n, min_digits, max_digits, seed=0):
    rnd = random.Random(seed)
    for i in range(n):
        d1 = rnd.randint(min_digits, max_digits)
        d2 = rnd.randint(min_digits, max_digits)
        a = rnd.randint(10 ** (d1 - 1), 10**d1 - 1)
        b = rnd.randint(10 ** (d2 - 1), 10**d2 - 1)
        yield {
            "id": f"mul-{d1}x{d2}-{i}",
            "question": f"Multiply the following numbers:\n{a} × {b}",
            # plain numeric string; we'll compare numerically
            "answer": str(a * b),
        }


def generate_sorting_tasks(n, list_len, min_val, max_val, seed=0):
    rnd = random.Random(seed)
    for i in range(n):
        lst = [rnd.randint(min_val, max_val) for _ in range(list_len)]
        yield {
            "id": f"sort-{list_len}-{i}",
            "question": f"Sort the following list of integers in ascending order and output ONLY the JSON list on a single line after '####':\n{lst}",
            # canonical JSON list string; we'll compare list equality
            "answer": json.dumps(sorted(lst), separators=(",", ":")),
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-prefix", default="synthetic", help="Prefix for files")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    sets = [
        # Long multiplication, varying difficulty
        # ("long_mul_4_4__200.jsonl", generate_long_multiplication(200, 4, 4, args.seed)),
        # ("long_mul_5_5__200.jsonl", generate_long_multiplication(200, 5, 5, args.seed)),
        ("long_mul_6_6__200.jsonl", generate_long_multiplication(200, 6, 6, args.seed)),
        # ("long_mul_10_10__200.jsonl", generate_long_multiplication(200, 10, 10, args.seed)),
        # ("long_mul_20_20__200.jsonl", generate_long_multiplication(200, 20, 20, args.seed)),
        # ("long_mul_30_30__200.jsonl", generate_long_multiplication(200, 30, 30, args.seed+1)),
        # ("long_mul_50_50__100.jsonl", generate_long_multiplication(100, 50, 50, args.seed+2)),
        # Sorting, varying lengths
        # ("sort_len_3__200.jsonl",  generate_sorting_tasks(200, 3,  -10_000, 10_000, args.seed)),
        # ("sort_len_4__200.jsonl",  generate_sorting_tasks(200, 4,  -10_000, 10_000, args.seed)),
        # ("sort_len_5__200.jsonl",  generate_sorting_tasks(200, 5,  -10_000, 10_000, args.seed)),
        # ("sort_len_10__200.jsonl",  generate_sorting_tasks(200, 10,  -10_000, 10_000, args.seed)),
        # ("sort_len_20__200.jsonl",  generate_sorting_tasks(200, 20,  -10_000, 10_000, args.seed)),
        # ("sort_len_50__200.jsonl",  generate_sorting_tasks(200, 50,  -10_000, 10_000, args.seed)),
        # ("sort_len_100__200.jsonl", generate_sorting_tasks(200, 100, -10_000, 10_000, args.seed+1)),
        # ("sort_len_500__50.jsonl",  generate_sorting_tasks(50,  500, -10_000, 10_000, args.seed+2)),
    ]

    for fname, gen in sets:
        path = f"{args.out_prefix}_{fname}"
        with open(path, "w", encoding="utf-8") as f:
            for rec in gen:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("Wrote", path)


if __name__ == "__main__":
    main()
