"""
Chunk 5: Multi-Agent Swarm Pipeline & Orchestration
---------------------------------------------------
Educational Note for Students:
This is the master coordination engine of AppForge Swarm.
Key principles to teach:
1. Hard Call Budget: Capped at 12 LLM calls per build to strictly prevent runaway API bills.
2. The Deterministic Integrator: Code (not an LLM) stitches together the output of
   Product, Logic, UX, and Tests.
3. Automated Critic Loop: The Critic reviews the draft. Only 'HIGH' severity flaws block
   and trigger targeted revisions.
4. Independent Test & Repair: Tests written by the Test Author are executed by the Verifier.
   If any fail, the error details are sent directly to the Logic Agent for targeted repair.
5. Real-Time Streaming: Events stream via Server-Sent Events (SSE) so the frontend shows
   live agent progress badges and logs.
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Set
from config import HAS_KEY, MAX_LLM_CALLS_PER_BUILD
from models.spec import AppSpec, Contract, Issue, AppMeta, StateDef, Test

logger = logging.getLogger("appforge.pipeline")
from agents import (
    run_product_agent, ProductOut,
    run_logic_agent, run_logic_modify, LogicOut,
    run_ux_agent, run_ux_modify, UxOut,
    run_test_author, TestOut,
    run_critic_agent,
    run_orchestrator,
    run_solo_agent,
)
from verifier import run_checks, validate_spec, contract_issues
from demo_data import DEMO_SPEC

EmitFn = Callable[[Dict[str, Any]], Any]
ALL_AGENTS = ["orchestrator", "product", "logic", "ux", "tests", "critic"]

class CallTracker:
    """Enforces strict hard budget on LLM API calls."""
    def __init__(self, emit: EmitFn, max_calls: int = MAX_LLM_CALLS_PER_BUILD):
        self.emit = emit
        self.max_calls = max_calls
        self.call_count = 0

    def calls(self) -> int:
        return self.call_count

    async def step(self, agent_name: str, coroutine):
        if self.call_count >= self.max_calls:
            raise RuntimeError(f"LLM call budget exhausted ({self.max_calls} calls maximum)")
        self.call_count += 1
        self.emit({"type": "agent_start", "agent": agent_name})
        t0 = time.time()
        result = await coroutine
        duration_ms = int((time.time() - t0) * 1000)
        self.emit({"type": "agent_done", "agent": agent_name, "ms": duration_ms})
        return result

def integrate(contract: Contract, logic: LogicOut, ux: UxOut, tests: list) -> AppSpec:
    """Deterministic Code Integrator: merges agent outputs into one AppSpec."""
    state_dict: Dict[str, StateDef] = {}
    for s in contract.state:
        state_dict[s.id] = StateDef(
            type=s.type,
            default=s.default,
            min=s.min,
            max=s.max,
        )
    if logic.state_add:
        state_dict.update(logic.state_add)

    return AppSpec(
        meta=AppMeta(name=ux.name, theme=ux.theme or "light"),
        state=state_dict,
        computed=logic.computed,
        rules=logic.rules,
        actions=logic.actions,
        components=ux.components,
        tests=tests,
    )

async def refine(
    spec: AppSpec,
    emit: EmitFn,
    tracker: CallTracker,
    contract: Optional[Contract],
    revise_fn: Callable[[Set[str], str], Any]
) -> Dict[str, Any]:
    """Critic rounds (max 2, only HIGH blocks) + Verifier repair rounds (max 2)."""
    def find_structural_issues(s: AppSpec) -> List[Issue]:
        issues = []
        if contract:
            issues.extend(contract_issues(contract, s))
        issues.extend(validate_spec(s))
        return issues

    # 1. Critic Review Loop (max 2 rounds)
    for _ in range(2):
        if tracker.calls() >= tracker.max_calls - 3:
            break
        c = await tracker.step("critic", run_critic_agent(spec))
        emit({
            "type": "critic",
            "approved": c.approved,
            "issues": [i.model_dump() for i in c.issues],
        })

        blocking: List[Issue] = find_structural_issues(spec)
        for issue in c.issues:
            if issue.severity == "high":
                owner = "ux" if issue.agent == "ux" else "logic"
                blocking.append(Issue(owner=owner, msg=issue.problem))

        if not blocking:
            break

        owners = {b.owner for b in blocking}
        feedback_msg = "\n".join(f"- {b.msg}" for b in blocking)
        spec = await revise_fn(owners, feedback_msg)

    # 2. Automated Verifier Checks & Targeted Repair
    emit({"type": "agent_start", "agent": "verifier"})
    results = run_checks(spec)
    for _ in range(2):
        failed_tests = [r for r in results if not r.pass_]
        structural = find_structural_issues(spec)
        emit({"type": "tests", "results": [r.model_dump(by_alias=True) for r in results]})

        if (not failed_tests and not structural) or tracker.calls() >= tracker.max_calls:
            break

        owners = {i.owner for i in structural}
        feedback_lines = [f"- {i.msg}" for i in structural]
        if failed_tests:
            owners.add("logic")
            for f in failed_tests:
                detail = f.detail or "failed expectation"
                feedback_lines.append(f"- TEST FAILED '{f.name}': {detail}")

        spec = await revise_fn(owners, "\n".join(feedback_lines))
        results = run_checks(spec)

    emit({"type": "tests", "results": [r.model_dump(by_alias=True) for r in results]})
    return {"spec": spec, "results": results}

async def forge(prompt: str, emit: EmitFn):
    """Full Swarm build pipeline for a new application."""
    start_time = time.time()
    if not HAS_KEY:
        await demo_stream(emit, start_time)
        return

    tracker = CallTracker(emit)
    emit({
        "type": "route",
        "agents": [a for a in ALL_AGENTS if a != "orchestrator"],
        "skipped": ["orchestrator"],
    })

    # Step 1: Product Planning & Contract Definition
    product = await tracker.step("product", run_product_agent(prompt))
    emit({
        "type": "plan",
        "plan": {
            "problem": product.problem,
            "primary_question": product.primary_question,
            "features": product.features,
        },
        "contract": product.contract.model_dump(by_alias=True),
    })

    # Step 2a: Logic and UX run concurrently
    logic_task = tracker.step("logic", run_logic_agent(prompt, product))
    ux_task = tracker.step("ux", run_ux_agent(prompt, product))
    logic, ux = await asyncio.gather(logic_task, ux_task)

    # Step 2b: Test Author runs after Logic so it knows the exact item field names
    # (e.g. whether the list field is "done" or "completed")
    def extract_list_schemas(logic_out: LogicOut) -> Dict[str, List[str]]:
        """Extract item field names from add_item actions so tests use correct names."""
        schemas: Dict[str, List[str]] = {}
        for action in logic_out.actions.values():
            if action.type == "add_item" and action.target and action.item:
                schemas[action.target] = list(action.item.keys())
        return schemas

    list_schemas = extract_list_schemas(logic)

    async def safe_test_author() -> TestOut:
        try:
            return await run_test_author(prompt, product, list_item_schemas=list_schemas or None)
        except Exception as e:
            logger.warning(f"Test author generation encountered error: {e}. Falling back to default contract tests.")
            default_inputs = {s.id: s.default for s in product.contract.state if s.default is not None}
            return TestOut(tests=[Test(name="Default Inputs Finite Check", inputs=default_inputs, expect={})])

    tests = await tracker.step("tests", safe_test_author())

    # Step 3: Deterministic Integration
    emit({"type": "agent_start", "agent": "integrator"})
    current_spec = integrate(product.contract, logic, ux, tests.tests)
    emit({"type": "agent_done", "agent": "integrator", "ms": 0})

    # Revision closure for Critic & Verifier loops
    async def revise(owners: Set[str], feedback: str) -> AppSpec:
        nonlocal logic, ux
        tasks = []
        if "logic" in owners:
            async def update_logic():
                nonlocal logic
                logic = await run_logic_agent(prompt, product, feedback, logic)
            tasks.append(tracker.step("logic", update_logic()))
        if "ux" in owners:
            async def update_ux():
                nonlocal ux
                ux = await run_ux_agent(prompt, product, feedback, ux)
            tasks.append(tracker.step("ux", update_ux()))
        if tasks:
            await asyncio.gather(*tasks)
        return integrate(product.contract, logic, ux, tests.tests)

    # Step 4: Refinement (Critic + Verifier)
    out = await refine(current_spec, emit, tracker, product.contract, revise)
    duration_ms = int((time.time() - start_time) * 1000)
    emit({
        "type": "done",
        "spec": out["spec"].model_dump(by_alias=True),
        "results": [r.model_dump(by_alias=True) for r in out["results"]],
        "calls": tracker.calls(),
        "ms": duration_ms,
    })

async def modify(prompt: str, current: AppSpec, emit: EmitFn):
    """Modify an existing application using Orchestrator routing."""
    start_time = time.time()
    if not HAS_KEY:
        raise RuntimeError("Modifying apps requires GROQ_API_KEY in .env")

    tracker = CallTracker(emit)
    route = await tracker.step("orchestrator", run_orchestrator(prompt, current))
    emit({
        "type": "route",
        "agents": route.agents,
        "skipped": [a for a in ALL_AGENTS if a != "orchestrator" and a not in route.agents and a != "critic"],
    })

    cur_spec = current

    async def patch(owners: Set[str], feedback: str) -> AppSpec:
        nonlocal cur_spec
        next_data = cur_spec.model_dump(by_alias=True)
        tasks = []

        if "logic" in owners:
            async def update_logic():
                l = await run_logic_modify(prompt, cur_spec, feedback)
                if l.state_add:
                    next_data["state"].update({k: v.model_dump(by_alias=True) for k, v in l.state_add.items()})
                next_data["computed"] = l.computed
                next_data["rules"] = [r.model_dump(by_alias=True) for r in l.rules]
                next_data["actions"] = {k: v.model_dump(by_alias=True) for k, v in l.actions.items()}
            tasks.append(tracker.step("logic", update_logic()))

        if "ux" in owners:
            async def update_ux():
                u = await run_ux_modify(prompt, cur_spec, feedback)
                next_data["meta"]["name"] = u.name or next_data["meta"]["name"]
                next_data["meta"]["theme"] = u.theme or next_data["meta"]["theme"]
                next_data["components"] = [c.model_dump(by_alias=True) for c in u.components]
            tasks.append(tracker.step("ux", update_ux()))

        if tasks:
            await asyncio.gather(*tasks)

        cur_spec = AppSpec.model_validate(next_data)
        return cur_spec

    first = await patch(set(route.agents), "")
    out = await refine(first, emit, tracker, None, patch)
    duration_ms = int((time.time() - start_time) * 1000)
    emit({
        "type": "done",
        "spec": out["spec"].model_dump(by_alias=True),
        "results": [r.model_dump(by_alias=True) for r in out["results"]],
        "calls": tracker.calls(),
        "ms": duration_ms,
    })

async def solo_benchmark(prompt: str) -> Dict[str, Any]:
    """Execute monolithic 1-shot baseline for educational comparison."""
    t0 = time.time()
    try:
        spec = await run_solo_agent(prompt)
        results = run_checks(spec)
        duration_ms = int((time.time() - t0) * 1000)
        passed = sum(1 for r in results if r.pass_)
        issues = [i.msg for i in validate_spec(spec)]
        return {
            "ok": True,
            "calls": 1,
            "ms": duration_ms,
            "issues": issues,
            "passed": passed,
            "total": len(results),
            "spec": spec.model_dump(by_alias=True),
        }
    except Exception as e:
        duration_ms = int((time.time() - t0) * 1000)
        return {
            "ok": False,
            "calls": 1,
            "ms": duration_ms,
            "error": str(e),
        }

async def demo_stream(emit: EmitFn, start_time: float):
    """Simulate streaming demo execution when no API key is set."""
    emit({
        "type": "route",
        "agents": [a for a in ALL_AGENTS if a != "orchestrator"],
        "skipped": ["orchestrator"],
    })
    for agent in ["product", "logic", "ux", "tests", "critic", "integrator"]:
        emit({"type": "agent_start", "agent": agent})
        await asyncio.sleep(0.35)
        emit({"type": "agent_done", "agent": agent, "ms": 350})

    emit({"type": "agent_start", "agent": "verifier"})
    results = run_checks(DEMO_SPEC)
    emit({"type": "tests", "results": [r.model_dump(by_alias=True) for r in results]})
    duration_ms = int((time.time() - start_time) * 1000)
    emit({
        "type": "done",
        "spec": DEMO_SPEC.model_dump(by_alias=True),
        "results": [r.model_dump(by_alias=True) for r in results],
        "calls": 0,
        "ms": duration_ms,
        "demo": True,
    })
