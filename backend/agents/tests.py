"""
Chunk 3E: Test Author Agent
---------------------------
Educational Note for Students:
Why is the Test Author 'blind' to the Logic Agent's formulas?
Because if the test author sees the formula, it might repeat the same mathematical
mistake or bias. By generating tests purely from the user's requirements and the contract,
it provides true INDEPENDENT VERIFICATION (TDD in a swarm).

However, for list-type state, we DO share the item schema from the Logic Agent
(just the field names of items, not the formulas) — so the test author can write
inputs with the correct field names (e.g., "done" vs "completed").
"""

import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from models.spec import Test
from agents.product import ProductOut
from llm import call_json

class TestOut(BaseModel):
    tests: List[Test] = Field(default_factory=list)

async def run_test_author(
    prompt: str,
    product: ProductOut,
    list_item_schemas: Optional[Dict[str, List[str]]] = None,
) -> TestOut:
    """Generate 4-6 independent unit test cases with boundary coverage.
    
    Args:
        list_item_schemas: Mapping of list state_id -> list of field names in each item.
                           Shared from the Logic Agent so tests use correct field names.
    """
    list_hint = ""
    if list_item_schemas:
        lines = []
        for state_id, fields in list_item_schemas.items():
            lines.append(f"  - '{state_id}' items have fields: {fields}")
        list_hint = (
            "\nLIST ITEM SCHEMAS (use EXACTLY these field names when writing list inputs):\n"
            + "\n".join(lines) + "\n"
        )

    system = (
        "You are the TEST AUTHOR. You have NOT seen any formulas, deliberately.\n"
        "From the requirement alone, write 4-6 test cases using only contract state ids as inputs "
        "and contract output ids as expectations.\n"
        "Compute the expected values by hand, carefully. Include boundary cases (zero, maximum, empty).\n"
        "Use null for 'no value'.\n"
        + list_hint +
        "CRITICAL RULES FOR TEST VALUES:\n"
        "- All values in 'inputs' and 'expect' MUST be raw literal JSON values: numbers, booleans, strings, null, or small literal arrays (e.g. 0 to 3 items max).\n"
        "- For list inputs: use the EXACT field names listed in LIST ITEM SCHEMAS above.\n"
        "- NEVER write code, functions, loops, or JavaScript expressions like '(function(){...})()' or 'Array(100)'. All inputs must be static literal JSON.\n"
        "Return valid JSON: {tests:[{name, inputs:{state_id:value}, expect:{output_id:value}}]}.\n"
        "Return ONLY a JSON object."
    )
    user_payload = {
        "request": prompt,
        "primary_question": product.primary_question,
        "features": product.features,
        "contract": product.contract.model_dump(by_alias=True),
    }
    return await call_json(system, json.dumps(user_payload), TestOut)
