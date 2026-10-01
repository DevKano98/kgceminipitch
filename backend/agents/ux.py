"""
Chunk 3D: UX & Interface Design Agent
-------------------------------------
Educational Note for Students:
The UX Agent acts as the 'Frontend Designer'.
It organizes the user interface into an ordered tree of components:
- Heading and explanation
- Form controls (inputs, sliders, dropdowns)
- Key result metrics and progress bars
- Action triggers (buttons)
Every component is data-bound ONLY to IDs present in the Product Contract.
"""

import json
from typing import Any, List, Literal, Optional
from pydantic import BaseModel, Field, model_validator
from models.spec import Component, AppSpec
from agents.product import ProductOut
from llm import call_json
from agents.base import GUIDE

class UxOut(BaseModel):
    name: str = Field(default="Mini App", max_length=60)
    theme: Optional[Literal["light", "dark"]] = "light"
    components: List[Component] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def preprocess_ux(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "components" not in data:
                for alt in ("ui", "elements", "widgets", "layout"):
                    if alt in data and isinstance(data[alt], list):
                        data["components"] = data[alt]
                        break
        return data

async def run_ux_agent(
    prompt: str,
    product: ProductOut,
    feedback: Optional[str] = None,
    previous: Optional[UxOut] = None
) -> UxOut:
    """Design a single-page layout bound strictly to the contracted IDs."""
    system = (
        "You are the UX agent. Design a single-page layout as an ordered 'components' array "
        "bound ONLY to ids in the CONTRACT (state ids, output ids, action ids).\n"
        "Order: heading, inputs, key results, explanation/alerts, buttons. "
        "Every contract output must appear somewhere. Use visible_if for conditional messages.\n"
        "Every component in 'components' MUST have a unique 'id' (snake_case) and a valid 'type'.\n"
        "For list components: 'fields' must be an array of simple string field names (e.g. ['task', 'done']), never objects.\n"
        "Return valid JSON: {name, theme:'light'|'dark', components:[...]}.\n"
        + GUIDE
    )
    user_payload = {
        "request": prompt,
        "primary_question": product.primary_question,
        "contract": product.contract.model_dump(by_alias=True),
        "previous_attempt": previous.model_dump(by_alias=True) if previous else None,
        "problems_to_fix": feedback,
    }
    return await call_json(system, json.dumps(user_payload), UxOut)

async def run_ux_modify(prompt: str, current: AppSpec, feedback: Optional[str] = None) -> UxOut:
    """Update UI components when user requests a layout or design change."""
    system = (
        "You are the UX agent modifying an existing app. Return the COMPLETE updated components array (and name/theme).\n"
        "Keep components the request does not affect. Bind only to ids that exist in state, computed or actions.\n"
        "Every component MUST have an 'id' and valid 'type'.\n"
        "Return valid JSON: {name, theme, components}.\n"
        + GUIDE
    )
    user_payload = {
        "request": prompt,
        "name": current.meta.name,
        "theme": current.meta.theme,
        "available_state": {k: v.model_dump(by_alias=True) for k, v in current.state.items()},
        "available_computed": list(current.computed.keys()),
        "available_actions": list(current.actions.keys()),
        "components": [c.model_dump(by_alias=True) for c in current.components],
        "problems_to_fix": feedback,
    }
    return await call_json(system, json.dumps(user_payload), UxOut)
