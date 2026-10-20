"""Accuracy test: ask the agent each question and compare its query result with a known-correct query.

A question passes when the agent returns the same number of rows and every correct row's
values appear in the matching agent row (extra columns like names are allowed).

Follow-up cases (followups.json) first ask `previous` for real, then grade the follow-up `question`.

Usage: python -m evaluation.evaluate            # single questions
       python -m evaluation.evaluate followups  # two-turn conversations
"""
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

from zax_backend.tools import run_query
from zax_backend.workflow import app

SUITE = sys.argv[1] if len(sys.argv) > 1 else "questions"
QUESTIONS = json.loads((Path(__file__).parent / f"{SUITE}.json").read_text())


def normalize(value):
    if isinstance(value, (float, Decimal)):
        return f"{float(value):.2f}"
    return str(value).strip().lower()


def rows_match(gold_rows, pred_rows):
    if len(gold_rows) != len(pred_rows):
        return False
    pred_sets = [{normalize(v) for v in row} for row in pred_rows]
    gold_sets = [{normalize(v) for v in row} for row in gold_rows]
    # Every correct row must be contained in some predicted row (order doesn't matter).
    return all(any(g <= p for p in pred_sets) for g in gold_sets)


def main():
    passed, results = 0, []
    for i, item in enumerate(QUESTIONS, 1):
        _, gold_rows, gold_error = run_query(item["sql"])
        assert gold_error is None, f"Gold SQL broken for: {item['question']}\n{gold_error}"

        start, out = time.time(), {}
        try:
            history = []
            if "previous" in item:
                prev = app.invoke({"user_input": item["previous"]})
                history = [{"question": item["previous"], "sql": prev.get("sql", ""), "answer": prev.get("answer", "")}]
            out = app.invoke({"user_input": item["question"], "history": history})
            ok = out.get("error") is None and rows_match(gold_rows, out.get("rows", []))
            attempts, sql = out.get("attempts"), out.get("sql", "")
        except Exception as e:  # count crashes (e.g. rate limits) as failures, keep going
            ok, attempts, sql = False, 0, f"{type(e).__name__}: {e}"
        passed += ok
        results.append({"question": item["question"], "passed": ok, "attempts": attempts,
                        "seconds": round(time.time() - start, 1), "sql": sql})
        print(f"[{i:2d}/{len(QUESTIONS)}] {'PASS' if ok else 'FAIL'}  {attempts} attempt(s)  "
              f"{results[-1]['seconds']:>5}s  {item['question']}")
        if "previous" in item and out:
            print("        interpreted as:", out.get("question"))
        if not ok:
            print("        agent SQL:", " ".join(sql.split())[:300])

    print(f"\nScore: {passed}/{len(QUESTIONS)} ({passed / len(QUESTIONS):.0%})")
    (Path(__file__).parent / f"last_run_{SUITE}.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
