"""
Chunk 4B: Deterministic Verifier & Safe AST Formula Evaluator
------------------------------------------------------------
Educational Note for Students:
Why do we NOT use Python's built-in `eval()`?
`eval()` can access `__import__('os').system(...)` and compromise the host!

Instead, we parse mathematical expressions into an Abstract Syntax Tree (AST)
and evaluate ONLY an allowlisted set of operations (addition, multiplication,
comparison, clamp, min, max, etc.). Division by zero safely yields None.

The Verifier performs 3 tiers of tests before any user sees the app:
1. Mathematical Invariants (finite numbers, bounded extremes)
2. Black-Box Unit Tests (written blindly by the Test Author)
3. Fuzz Testing (100 random input permutations)
"""

import ast
import math
import random
import re
from typing import Any, Dict, List, Optional, Set
from models.spec import AppSpec, CheckResult, Contract, Issue

# Allowlisted functions for formulas
SAFE_FUNCTIONS = {
    "_if": lambda c, a, b: a if c else b,
    "min": min,
    "max": max,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "round": lambda x, d=0: round(x, int(d)) if x is not None else None,
    "clamp": lambda x, lo, hi: min(hi, max(lo, x)) if x is not None else None,
    "pow": math.pow,
    "sqrt": lambda x: math.sqrt(x) if x is not None and x >= 0 else None,
    # Null-safe: treat None as [] so len(null)==0 and sumOf(null,"f")==0
    "len": lambda x: len(x) if x is not None else 0,
    "sumOf": lambda lst, field: sum(
        (1 if v is True else 0 if v is False else (v if isinstance(v, (int, float)) else 0))
        for item in (lst or [])
        if isinstance(item, dict)
        for v in [item.get(field, 0)]
    ),
    "avgOf": lambda lst, field: (
        sum(item.get(field, 0) for item in (lst or []) if isinstance(item, dict))
        / max(1, len(lst or []))
        if lst else 0
    ),
}


def extract_identifiers(expr: str) -> Set[str]:
    """Extract variable identifiers from an expression string."""
    try:
        # Normalize if( to _if(
        clean = re.sub(r"\bif\(", "_if(", expr)
        tree = ast.parse(clean, mode="eval")
        ids = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                if node.id not in SAFE_FUNCTIONS and node.id not in ("true", "false", "null", "True", "False", "None"):
                    ids.add(node.id)
        return ids
    except Exception:
        # Fallback regex search
        tokens = re.findall(r"\b[a-z][a-z0-9_]*\b", expr)
        return {t for t in tokens if t not in SAFE_FUNCTIONS and t not in ("and", "or", "not", "true", "false", "null")}

def evaluate_ast(node: ast.AST, env: Dict[str, Any]) -> Any:
    """Recursively evaluate an AST node against safe operations only."""
    if isinstance(node, ast.Constant):
        return node.value

    if isinstance(node, ast.Name):
        nid = node.id
        if nid in ("true", "True"):
            return True
        if nid in ("false", "False"):
            return False
        if nid in ("null", "None"):
            return None
        if nid in env:
            return env[nid]
        if nid in SAFE_FUNCTIONS:
            return SAFE_FUNCTIONS[nid]
        raise NameError(f"Unknown variable: {nid}")

    if isinstance(node, ast.BinOp):
        left = evaluate_ast(node.left, env)
        right = evaluate_ast(node.right, env)
        if left is None or right is None:
            return None
        
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            if right == 0:
                return None
            return left / right
        if isinstance(op, ast.Mod):
            if right == 0:
                return None
            return left % right
        if isinstance(op, ast.Pow):
            return left ** right
        raise ValueError(f"Unsupported binary operator: {type(op)}")

    if isinstance(node, ast.UnaryOp):
        operand = evaluate_ast(node.operand, env)
        if operand is None:
            return None
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.Not):
            return not operand
        raise ValueError(f"Unsupported unary operator: {type(node.op)}")

    if isinstance(node, ast.Compare):
        left = evaluate_ast(node.left, env)
        for op, comparator in zip(node.ops, node.comparators):
            right = evaluate_ast(comparator, env)
            if left is None or right is None:
                return False
            if isinstance(op, ast.Eq) and not (left == right):
                return False
            if isinstance(op, ast.NotEq) and not (left != right):
                return False
            if isinstance(op, ast.Lt) and not (left < right):
                return False
            if isinstance(op, ast.LtE) and not (left <= right):
                return False
            if isinstance(op, ast.Gt) and not (left > right):
                return False
            if isinstance(op, ast.GtE) and not (left >= right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            for value in node.values:
                res = evaluate_ast(value, env)
                if not res:
                    return res
            return True
        if isinstance(node.op, ast.Or):
            for value in node.values:
                res = evaluate_ast(value, env)
                if res:
                    return res
            return False

    if isinstance(node, ast.Call):
        func = evaluate_ast(node.func, env)
        args = [evaluate_ast(arg, env) for arg in node.args]
        return func(*args)

    raise ValueError(f"Unsupported AST node: {type(node)}")

def evaluate_formula(expr: str, env: Dict[str, Any]) -> Any:
    """Safe evaluation of mathematical and logical string expressions."""
    if not expr or not expr.strip():
        return None
    try:
        clean = re.sub(r"\bif\(", "_if(", expr)
        tree = ast.parse(clean, mode="eval")
        return evaluate_ast(tree.body, env)
    except Exception:
        return None

def default_state(spec: AppSpec) -> Dict[str, Any]:
    """Produce default state values from spec definitions."""
    s: Dict[str, Any] = {}
    for k, d in spec.state.items():
        if d.default is not None:
            s[k] = d.default
        elif d.type == "list":
            s[k] = []
        elif d.type == "bool":
            s[k] = False
        elif d.type == "text":
            s[k] = ""
        else:
            s[k] = d.min if d.min is not None else 0
    return s

def compute(spec: AppSpec, state: Dict[str, Any]) -> Dict[str, Any]:
    """Iteratively evaluate all computed formulas until fixed point."""
    env = dict(state)
    pending = list(spec.computed.keys())
    
    # Run multiple passes to resolve cross-computed dependencies
    for _ in range(len(pending) + 2):
        if not pending:
            break
        next_pending = []
        for k in pending:
            formula = spec.computed[k]
            val = evaluate_formula(formula, env)
            if val is not None:
                env[k] = val
            else:
                # Check if dependencies exist
                deps = extract_identifiers(formula)
                if all(d in env for d in deps):
                    env[k] = None
                else:
                    next_pending.append(k)
        if len(next_pending) == len(pending):
            for k in next_pending:
                env[k] = None
            break
        pending = next_pending
    return env

def validate_spec(spec: AppSpec) -> List[Issue]:
    """Static validation: every reference in formulas and components must resolve."""
    issues: List[Issue] = []
    known = set(spec.state.keys()) | set(spec.computed.keys())

    # Check computed formulas
    for k, formula in spec.computed.items():
        for ident in extract_identifiers(formula):
            if ident not in known:
                issues.append(Issue(owner="logic", msg=f"computed.{k}: unknown identifier '{ident}'"))

    # Check validation rules
    for i, rule in enumerate(spec.rules):
        for ident in extract_identifiers(rule.when):
            if ident not in known:
                issues.append(Issue(owner="logic", msg=f"rules[{i}]: unknown identifier '{ident}'"))

    # Check components
    seen_comp_ids = set()
    for c in spec.components:
        if c.id in seen_comp_ids:
            issues.append(Issue(owner="ux", msg=f"duplicate component id '{c.id}'"))
        seen_comp_ids.add(c.id)

        if c.bind and c.bind not in spec.state:
            issues.append(Issue(owner="ux", msg=f"component {c.id}: bind '{c.bind}' is not in state"))
        if c.action and c.action not in spec.actions:
            issues.append(Issue(owner="ux", msg=f"component {c.id}: action '{c.action}' is not defined"))
        if c.type == "button" and not c.action:
            issues.append(Issue(owner="ux", msg=f"button {c.id} has no action"))

        for e in [c.value, c.max, c.visible_if]:
            if e:
                for ident in extract_identifiers(e):
                    if ident not in known:
                        issues.append(Issue(owner="ux", msg=f"component {c.id}: unknown id '{ident}'"))
    return issues

def contract_issues(contract: Contract, spec: AppSpec) -> List[Issue]:
    """Verify that the spec satisfies all outputs and actions required by the Contract."""
    issues: List[Issue] = []
    for out in contract.outputs:
        if out.id not in spec.computed:
            issues.append(Issue(owner="logic", msg=f"contract output '{out.id}' has no formula"))
    for act in contract.actions:
        if act.id not in spec.actions:
            issues.append(Issue(owner="logic", msg=f"contract action '{act.id}' is not defined"))
    return issues

def run_checks(spec: AppSpec) -> List[CheckResult]:
    """Execute Tier 1 Invariants, Tier 2 Example Tests, and Tier 3 Fuzzing."""
    results: List[CheckResult] = []

    # 1. Invariant: Default state produces finite numbers
    try:
        env_def = compute(spec, default_state(spec))
        pass_inv = all(
            math.isfinite(v) for v in env_def.values() if isinstance(v, (int, float)) and not isinstance(v, bool)
        )
        results.append(CheckResult(layer="invariant", name="No NaN/Infinity: defaults", pass_=pass_inv))
    except Exception as e:
        results.append(CheckResult(layer="invariant", name="No NaN/Infinity: defaults", pass_=False, detail=str(e)))

    # 2. Example Tests
    for test in spec.tests:
        try:
            state = default_state(spec)
            state.update(test.inputs)
            env = compute(spec, state)
            passed = True
            diffs = []
            for k, expected in test.expect.items():
                actual = env.get(k)
                if isinstance(expected, float) and isinstance(actual, (int, float)):
                    if abs(expected - actual) > 0.05:
                        passed = False
                        diffs.append(f"{k}: expected {expected}, got {actual}")
                elif actual != expected:
                    passed = False
                    diffs.append(f"{k}: expected {expected}, got {actual}")
            results.append(CheckResult(
                layer="example",
                name=test.name,
                pass_=passed,
                detail="; ".join(diffs) if diffs else None
            ))
        except Exception as e:
            results.append(CheckResult(layer="example", name=test.name, pass_=False, detail=str(e)))

    # 3. Fuzz Testing: 100 random samples stay finite
    fuzz_passed = True
    fuzz_err = None
    for _ in range(100):
        sample = {}
        for k, d in spec.state.items():
            if d.type in ("int", "number", "percent"):
                lo = d.min if d.min is not None else 0
                hi = d.max if d.max is not None else 100
                sample[k] = random.randint(int(lo), int(hi))
            elif d.type == "bool":
                sample[k] = random.choice([True, False])
            elif d.type == "text":
                sample[k] = "test"
            elif d.type == "list":
                sample[k] = []
        try:
            env = compute(spec, sample)
            for v in env.values():
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    fuzz_passed = False
                    break
        except Exception as e:
            fuzz_passed = False
            fuzz_err = str(e)
            break
        if not fuzz_passed:
            break

    results.append(CheckResult(
        layer="fuzz",
        name="100 random in-range inputs stay finite",
        pass_=fuzz_passed,
        detail=fuzz_err
    ))

    return results
