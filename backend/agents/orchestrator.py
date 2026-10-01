"""
Chunk 3G: Orchestrator Agent (Change Router)
--------------------------------------------
Educational Note for Students:
When a user asks: "Change the button color to red and rename the title",
running the Logic Agent is a waste of tokens and money!
The Orchestrator inspects the change request and decides which specialized agents
need to run: 'ux' for visual changes, 'logic' for formulas/rules, or both.
"""

import json
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from models.spec import AppSpec
from llm import call_json

class RouteOut(BaseModel):
    agents: List[Literal["logic", "ux"]] = Field(min_length=1)
    reason: Optional[str] = None

async def run_orchestrator(prompt: str, current: AppSpec) -> RouteOut:
    """Determine minimal set of agents needed to fulfill an edit request."""
    system = (
        "You are the ORCHESTRATOR. Given an existing app and a change request, choose which agents must run:\n"
        "'logic' for calculations, rules, actions, or new state; 'ux' for layout, components, wording, theme.\n"
        "Run only what is necessary.\n"
        "Return valid JSON: {agents:['logic'|'ux'], reason: string}.\n"
        "Return ONLY a JSON object."
    )
    user_payload = {
        "app": {
            "name": current.meta.name,
            "state": list(current.state.keys()),
            "computed": list(current.computed.keys()),
            "actions": list(current.actions.keys()),
            "components": [f"{c.type}:{c.id}" for c in current.components],
        },
        "request": prompt,
    }
    return await call_json(system, json.dumps(user_payload), RouteOut)
