"""
Chunk 3F: Critic & QA Auditor Agent
-----------------------------------
Educational Note for Students:
The Critic agent acts as a Senior Code Reviewer / QA Engineer.
It receives the integrated draft spec and aggressively checks for:
- Missing edge cases (zero division, empty lists)
- Unbounded slider/number inputs
- Unbound outputs or misleading labels
Severity levels:
- HIGH: Breaks the application or calculates false numbers (BLOCKS the build).
- MEDIUM/LOW: Minor cosmetic or stylistic suggestions (non-blocking).
"""

import json
from typing import List, Literal
from pydantic import BaseModel, Field
from models.spec import AppSpec
from llm import call_json

class CriticIssue(BaseModel):
    agent: Literal["product", "ux", "logic"]
    severity: Literal["high", "medium", "low"]
    problem: str

class CriticOut(BaseModel):
    approved: bool
    issues: List[CriticIssue] = Field(default_factory=list)

async def run_critic_agent(spec: AppSpec) -> CriticOut:
    """Audit the complete spec and flag high-severity flaws."""
    system = (
        "You are the CRITIC. Attack this app spec: missing edge cases, unsafe ranges, "
        "missing or wrong calculations, unexplained results, unbound outputs.\n"
        "Mark severity 'high' ONLY if the app would be wrong or broken.\n"
        "Do not nitpick; if it is sound, approve with no issues.\n"
        "Return valid JSON: {approved: bool, issues:[{agent:'product'|'ux'|'logic', severity:'high'|'medium'|'low', problem: string}]}.\n"
        "Return ONLY a JSON object."
    )
    user_payload = {
        "name": spec.meta.name,
        "state": {k: v.model_dump(by_alias=True) for k, v in spec.state.items()},
        "computed": spec.computed,
        "rules": [r.model_dump(by_alias=True) for r in spec.rules],
        "actions": {k: v.model_dump(by_alias=True) for k, v in spec.actions.items()},
        "components": [c.model_dump(by_alias=True) for c in spec.components],
    }
    return await call_json(system, json.dumps(user_payload), CriticOut)
