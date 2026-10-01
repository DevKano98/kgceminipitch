"""
Chunk 3C: Logic & Calculation Agent
-----------------------------------
Educational Note for Students:
The Logic Agent acts as the 'Backend Developer'.
It is responsible purely for business logic:
1. Writing computed formulas for every contracted output
2. Defining validation rules for bad inputs
3. Specifying deterministic actions (increment, set, reset)
It NEVER deals with colors, fonts, or HTML/DOM elements.
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from models.spec import Action, Rule, StateDef, AppSpec, normalize_id
from agents.product import ProductOut
from llm import call_json
from agents.base import GUIDE

class LogicOut(BaseModel):
    computed: Dict[str, str] = Field(default_factory=dict)
    rules: List[Rule] = Field(default_factory=list)
    actions: Dict[str, Action] = Field(default_factory=dict)
    state_add: Optional[Dict[str, StateDef]] = None

    @field_validator("actions", mode="before")
    @classmethod
    def coerce_actions_dict(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, list):
            res = {}
            for i, item in enumerate(v):
                if isinstance(item, dict) and "id" in item:
                    aid = normalize_id(item["id"], "act")
                    res[aid] = item
                else:
                    res[f"act_{i}"] = item
            return res
        return v if isinstance(v, dict) else {}

async def run_logic_agent(
    prompt: str,
    product: ProductOut,
    feedback: Optional[str] = None,
    previous: Optional[LogicOut] = None
) -> LogicOut:
    """Generate formulas, validation rules, and actions satisfying the product contract."""
    system = (
        "You are the LOGIC agent. You own behaviour only: calculations, validation rules, actions.\n"
        "Write one formula in 'computed' for EVERY contract output id (formulas may use state ids and other computed ids), "
        "one entry in 'actions' for EVERY contract action id, and 'rules' for invalid input.\n"
        "Handle zero/empty/out-of-range cases explicitly. Never invent ids outside the contract (new state goes in 'state_add' with defaults).\n"
        "CRITICAL — actions must be JSON objects, NEVER shorthand strings:\n"
        "  add_item:    {\"type\": \"add_item\",    \"target\": \"tasks\", \"item\": {\"text\": \"new_task_input\", \"done\": false}}\n"
        "  remove_item: {\"type\": \"remove_item\", \"target\": \"tasks\", \"amount\": \"index_formula\"}\n"
        "  toggle:      {\"type\": \"toggle\",      \"target\": \"some_bool_state\"}\n"
        "  set:         {\"type\": \"set\",         \"target\": \"state_id\",  \"value\": \"formula\"}\n"
        "  increment:   {\"type\": \"increment\",   \"target\": \"state_id\",  \"amount\": \"formula\"}\n"
        "ITEM VALUES: use native JSON types — booleans must be unquoted (false not \"false\"), "
        "strings must be state-id identifiers (not quoted), null is null.\n"
        "Return valid JSON: {computed:{id:formula}, rules:[{when,message}], actions:{id:action_object}, state_add?:{id:{type,default,min,max}}}.\n"
        + GUIDE
    )
    user_payload = {
        "request": prompt,
        "primary_question": product.primary_question,
        "features": product.features,
        "contract": product.contract.model_dump(by_alias=True),
        "previous_attempt": previous.model_dump(by_alias=True) if previous else None,
        "problems_to_fix": feedback,
    }
    return await call_json(system, json.dumps(user_payload), LogicOut)

async def run_logic_modify(prompt: str, current: AppSpec, feedback: Optional[str] = None) -> LogicOut:
    """Modify logic for an existing app without breaking existing IDs."""
    system = (
        "You are the LOGIC agent modifying an existing app. Return the COMPLETE updated computed, rules and actions: "
        "keep everything the request does not affect, never remove or rename existing ids.\n"
        "Put new state in state_add (with defaults).\n"
        "Return valid JSON: {computed, rules, actions, state_add?}.\n"
        + GUIDE
    )
    user_payload = {
        "request": prompt,
        "state": {k: v.model_dump(by_alias=True) for k, v in current.state.items()},
        "computed": current.computed,
        "rules": [r.model_dump(by_alias=True) for r in current.rules],
        "actions": {k: v.model_dump(by_alias=True) for k, v in current.actions.items()},
        "problems_to_fix": feedback,
    }
    return await call_json(system, json.dumps(user_payload), LogicOut)
