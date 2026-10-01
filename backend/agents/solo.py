"""
Chunk 3H: Solo Baseline Agent
-----------------------------
Educational Note for Students:
Why build a multi-agent swarm when you could just ask one LLM:
'Generate the whole app spec at once'?
The Solo Agent provides a direct baseline. Students will notice that
a single agent frequently forgets boundary cases, hallucinates uncontracted IDs,
and skips unit tests, whereas the Swarm validates and repairs iteratively.
"""

from models.spec import AppSpec
from llm import call_json
from agents.base import GUIDE

async def run_solo_agent(prompt: str) -> AppSpec:
    """Monolithic single-agent generation for benchmarking against the swarm."""
    system = (
        "You are a single agent. Produce a COMPLETE app spec for the student's request as JSON:\n"
        "{\n"
        "  meta: {name, theme},\n"
        "  state: {id: {type, default, min, max}},\n"
        "  computed: {id: formula},\n"
        "  rules: [{when, message}],\n"
        "  components: [...],\n"
        "  actions: {id: action},\n"
        "  tests: [{name, inputs, expect}]\n"
        "}\n"
        + GUIDE
    )
    user = f"Student request: {prompt}"
    return await call_json(system, user, AppSpec)
