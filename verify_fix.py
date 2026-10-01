"""Verify the null-tasks fix works in the Python verifier."""
import sys
sys.path.insert(0, 'backend')
from verifier import SAFE_FUNCTIONS, evaluate_formula, run_checks
from models.spec import AppSpec, StateDef, Test

# 1. Direct null-safety tests
lenFn = SAFE_FUNCTIONS["len"]
sumOfFn = SAFE_FUNCTIONS["sumOf"]

assert lenFn(None) == 0, f"len(None) should be 0, got {lenFn(None)}"
assert lenFn([]) == 0, "len([]) should be 0"
assert lenFn([1,2,3]) == 3, "len([1,2,3]) should be 3"
print("PASS: len(None)==0")

assert sumOfFn(None, "done") == 0, f"sumOf(None,'done') should be 0, got {sumOfFn(None, 'done')}"
assert sumOfFn([], "done") == 0, "sumOf([], 'done') should be 0"
assert sumOfFn([{"done": True}, {"done": False}], "done") == 1, "sumOf with booleans should count Trues"
assert sumOfFn([{"done": True}, {"done": True}], "done") == 2, "sumOf 2 done=True should be 2"
print("PASS: sumOf null-safe and bool-aware")

# 2. Formula evaluation with null state
result = evaluate_formula('len(tasks)', {"tasks": None})
assert result == 0, f"len(null) via formula should be 0, got {result}"
print("PASS: evaluate_formula len(null)==0")

result2 = evaluate_formula('sumOf(tasks,"done")', {"tasks": None})
assert result2 == 0, f"sumOf(null,'done') via formula should be 0, got {result2}"
print("PASS: evaluate_formula sumOf(null,'done')==0")

# 3. Full spec test with null tasks
spec = AppSpec.model_validate({
    "meta": {"name": "Todo Test", "theme": "light"},
    "state": {
        "tasks": {"type": "list", "default": []},
        "new_task_text": {"type": "text", "default": ""},
    },
    "computed": {
        "total_tasks": "len(tasks)",
        "completed_tasks": 'sumOf(tasks,"done")',
    },
    "rules": [],
    "components": [],
    "actions": {
        "add_task": {"type": "add_item", "target": "tasks", "item": {"text": "new_task_text", "done": False}}
    },
    "tests": [
        {"name": "null tasks", "inputs": {"tasks": None}, "expect": {"total_tasks": 0, "completed_tasks": 0}},
        {"name": "empty tasks", "inputs": {"tasks": []}, "expect": {"total_tasks": 0, "completed_tasks": 0}},
        {"name": "one complete", "inputs": {"tasks": [{"text": "A", "done": True}]}, "expect": {"total_tasks": 1, "completed_tasks": 1}},
        {"name": "mixed", "inputs": {"tasks": [{"text": "A", "done": False}, {"text": "B", "done": True}]}, "expect": {"total_tasks": 2, "completed_tasks": 1}},
    ]
})

results = run_checks(spec)
passed = sum(1 for r in results if r.pass_)
total = len(results)
print(f"\nVerifier results: {passed}/{total} passed")
for r in results:
    status = "PASS" if r.pass_ else "FAIL"
    detail = f" — {r.detail}" if r.detail else ""
    print(f"  [{r.layer}] {status}: {r.name}{detail}")

assert passed == total, f"Expected all {total} checks to pass, got {passed}"
print(f"\nAll {total}/{total} checks PASSED!")
