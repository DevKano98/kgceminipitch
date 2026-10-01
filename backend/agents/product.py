"""
Chunk 3B: Product Manager Agent
-------------------------------
Educational Note for Students:
The Product Agent establishes the 'Contract' before any code or layout is written.
It specifies the exact state inputs (with realistic defaults and bounds),
the required output metrics, and the allowed actions.
All downstream agents must adhere strictly to this contract.
"""

from typing import List
from pydantic import BaseModel, Field
from models.spec import Contract
from llm import call_json
from agents.base import GUIDE

class ProductOut(BaseModel):
    problem: str
    primary_question: str
    features: List[str] = Field(default_factory=list)
    contract: Contract

async def run_product_agent(prompt: str) -> ProductOut:
    """Analyze student prompt and define the application scope & state contract."""
    system = (
        "You are the PRODUCT agent in an app-building team. A student gave a one-sentence request. "
        "Decide what the app must actually do.\n"
        "Answer the literal question first (e.g. 'can I skip tomorrow?' needs a yes/no output, then extras). "
        "Keep it small: <=8 state inputs, <=10 outputs.\n"
        "Produce the CONTRACT every other agent must use: state inputs (id,label,type,default,min,max), "
        "outputs (computed ids), actions (button ids).\n"
        "Choose realistic defaults so the app shows a meaningful result immediately. "
        "Cap percents so formulas cannot divide by zero (e.g. 1..99).\n"
        "Return valid JSON: {problem, primary_question, features:[...], contract:{state:[...], outputs:[{id,label,type}], actions:[{id,label}]}}.\n"
        + GUIDE
    )
    user = f"Student request: {prompt}"
    return await call_json(system, user, ProductOut)
