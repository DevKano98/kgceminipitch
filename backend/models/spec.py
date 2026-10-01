"""
Chunk 2: Sandboxed Application Specification Schema (Pydantic V2)
------------------------------------------------------------------
Educational Note for Students:
Why do we NOT let LLMs generate arbitrary Python or JavaScript code?
Because executing arbitrary code requires sandboxing against malicious operations
(like disk access, crypto mining, or infinite loops).

Instead, we use a DECLARATIVE DOMAIN SPECIFICATION (AppSpec).
The LLM specifies:
1. State variables (int, number, text, bool, list) with bounds
2. Computed derivations (pure math/logic formulas)
3. Business rules (validation warnings)
4. UI Components (declarative widgets mapped to state)
5. Actions (deterministic state transformations)
6. Automated Tests (unit expectations)

The frontend or runtime interprets this specification safely in pure memory.
"""

from __future__ import annotations
import re
import uuid
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, field_validator, model_validator

# Type definitions
StateType = Literal["int", "number", "percent", "text", "bool", "list"]
ActionType = Literal[
    "set", "increment", "decrement", "toggle", "add_item",
    "remove_item", "reset", "random_pick", "run"
]
ComponentType = Literal[
    "heading", "text", "divider", "button", "number_input", "text_input",
    "slider", "select", "checkbox", "metric", "progress", "alert", "list", "chart"
]
ToneType = Literal["info", "success", "warning", "error"]

# Aliases to make LLM outputs resilient
STATE_ALIASES = {
    "boolean": "bool", "string": "text", "str": "text",
    "integer": "int", "float": "number", "double": "number",
    "array": "list", "percentage": "percent"
}

ACTION_ALIASES = {
    "inc": "increment", "dec": "decrement", "add": "add_item",
    "remove": "remove_item", "clear": "reset"
}

COMPONENT_ALIASES = {
    "header": "heading", "title": "heading", "h1": "heading", "h2": "heading", "h3": "heading",
    "paragraph": "text", "p": "text", "label": "text", "description": "text",
    "hr": "divider", "separator": "divider", "line": "divider", "btn": "button",
    "input": "text_input", "textfield": "text_input", "text_field": "text_input", "string_input": "text_input",
    "number": "number_input", "numeric_input": "number_input", "int_input": "number_input",
    "range": "slider", "dropdown": "select", "combobox": "select",
    "switch": "checkbox", "toggle": "checkbox", "check": "checkbox",
    "stat": "metric", "counter": "metric", "display": "metric", "card": "metric",
    "progress_bar": "progress", "progressbar": "progress",
    "notification": "alert", "banner": "alert", "message": "alert",
    "table": "list", "items": "list", "graph": "chart", "plot": "chart"
}

def normalize_id(v: Any, prefix: str = "item") -> str:
    """Normalize identifier into valid snake_case max 32 chars."""
    if not v or not isinstance(v, str):
        return f"{prefix}_{uuid.uuid4().hex[:6]}"
    cleaned = v.strip().lower()
    cleaned = re.sub(r"[\s-]+", "_", cleaned)
    cleaned = re.sub(r"[^a-z0-9_]", "", cleaned)
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"id_{cleaned}"
    return cleaned[:32]

class StateDef(BaseModel):
    """Definition of an application state variable."""
    type: StateType
    default: Any = None
    min: Optional[float] = None
    max: Optional[float] = None

    @field_validator("type", mode="before")
    @classmethod
    def coerce_state_type(cls, v: Any) -> str:
        if isinstance(v, str):
            lowered = v.strip().lower()
            return STATE_ALIASES.get(lowered, lowered)
        return "text"

class ChartConfig(BaseModel):
    """Specification for dynamic SVG charts."""
    from_: float = Field(default=0, alias="from")
    to: float = Field(default=10)
    y: str

    model_config = {"populate_by_name": True}

def _coerce_item_value(v: Any) -> Any:
    """Preserve native booleans, numbers, and null; keep formulas as strings."""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v
    if v is None:
        return None
    s = str(v).strip()
    # Recognise literal true/false/null from unquoted JSON / LLM output
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    if s.lower() in ("null", "none"):
        return None
    # Try numeric
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    # Strip surrounding quotes if the LLM quoted a string value
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]
    return s

def _parse_item_dict(item_raw: Any) -> Dict[str, Any]:
    """Parse dictionary or object-string like {text:new_task_text,done:false} into Dict[str, Any].
    
    Preserves native types: false→False, true→True, null→None, numbers→int/float.
    """
    if isinstance(item_raw, dict):
        return {str(k): _coerce_item_value(v) for k, v in item_raw.items()}
    if not isinstance(item_raw, str):
        return {}
    item_str = item_raw.strip()
    if item_str.startswith("{") and item_str.endswith("}"):
        item_str = item_str[1:-1].strip()
    result: Dict[str, str] = {}
    if not item_str:
        return result
    pairs = []
    curr = []
    in_q = None
    depth = 0
    for c in item_str:
        if in_q:
            curr.append(c)
            if c == in_q:
                in_q = None
        elif c in ('"', "'"):
            in_q = c
            curr.append(c)
        elif c in ('{', '[', '('):
            depth += 1
            curr.append(c)
        elif c in ('}', ']', ')'):
            depth -= 1
            curr.append(c)
        elif c == ',' and depth == 0:
            pairs.append(''.join(curr).strip())
            curr = []
        else:
            curr.append(c)
    if curr:
        pairs.append(''.join(curr).strip())

    for pair in pairs:
        if ":" in pair:
            k, v = pair.split(":", 1)
            k = re.sub(r'[\'"]', '', k.strip())
            result[k] = _coerce_item_value(v.strip())
        elif "=" in pair:
            k, v = pair.split("=", 1)
            k = re.sub(r'[\'"]', '', k.strip())
            result[k] = _coerce_item_value(v.strip())
    return result

def parse_action_shorthand(raw: Any) -> Any:
    """Parse shorthand string representation of an action into an Action dict.
    
    Examples:
    - 'add_item(tasks, {text:new_task_text,done:false})' -> {'type': 'add_item', 'target': 'tasks', 'item': {...}}
    - 'increment(count, 1)' -> {'type': 'increment', 'target': 'count', 'amount': '1'}
    - 'set(active, true)' -> {'type': 'set', 'target': 'active', 'value': 'true'}
    - 'toggle(dark_mode)' -> {'type': 'toggle', 'target': 'dark_mode'}
    - 'reset' or 'reset()' -> {'type': 'reset'}
    """
    if not isinstance(raw, str):
        return raw

    s = raw.strip()
    if not s:
        return {"type": "reset"}

    match = re.match(r"^([a-zA-Z_]\w*)(?:\((.*)\))?$", s, re.DOTALL)
    if not match:
        return {"type": ACTION_ALIASES.get(s.lower(), s.lower())}

    fn_name = match.group(1).lower().strip()
    fn_name = ACTION_ALIASES.get(fn_name, fn_name)
    args_str = match.group(2)

    if not args_str or not args_str.strip():
        return {"type": fn_name}

    # Split top-level comma-separated arguments
    args = []
    current = []
    depth = 0
    in_quote = None
    for char in args_str:
        if in_quote:
            current.append(char)
            if char == in_quote:
                in_quote = None
        elif char in ('"', "'"):
            in_quote = char
            current.append(char)
        elif char in ('{', '[', '('):
            depth += 1
            current.append(char)
        elif char in ('}', ']', ')'):
            depth -= 1
            current.append(char)
        elif char == ',' and depth == 0:
            args.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        args.append(''.join(current).strip())

    args = [a for a in args if a]
    action_dict: Dict[str, Any] = {"type": fn_name}

    positional = []
    for arg in args:
        if "=" in arg and not (arg.startswith("{") or arg.startswith("[")):
            k, v = arg.split("=", 1)
            k = k.strip().lower()
            v = v.strip()
            if k == "item":
                action_dict["item"] = _parse_item_dict(v)
            elif k in ("target", "amount", "value", "field", "from"):
                action_dict[k] = v
            else:
                positional.append(arg)
        else:
            positional.append(arg)

    if fn_name == "add_item":
        if positional and "target" not in action_dict:
            action_dict["target"] = positional[0]
        if len(positional) > 1 and "item" not in action_dict:
            action_dict["item"] = _parse_item_dict(positional[1])
    elif fn_name in ("increment", "decrement"):
        if positional and "target" not in action_dict:
            action_dict["target"] = positional[0]
        if len(positional) > 1 and "amount" not in action_dict:
            action_dict["amount"] = positional[1]
    elif fn_name == "set":
        if positional and "target" not in action_dict:
            action_dict["target"] = positional[0]
        if len(positional) > 1 and "value" not in action_dict:
            action_dict["value"] = positional[1]
    elif fn_name == "toggle":
        if positional and "target" not in action_dict:
            action_dict["target"] = positional[0]
    elif fn_name == "reset":
        if positional and "target" not in action_dict:
            action_dict["target"] = positional[0]
    elif fn_name == "remove_item":
        if positional and "target" not in action_dict:
            action_dict["target"] = positional[0]
        if len(positional) > 1 and "amount" not in action_dict:
            action_dict["amount"] = positional[1]
    elif fn_name == "random_pick":
        if positional and "from" not in action_dict:
            action_dict["from"] = positional[0]
        if len(positional) > 1 and "field" not in action_dict:
            action_dict["field"] = positional[1]
        if len(positional) > 2 and "target" not in action_dict:
            action_dict["target"] = positional[2]

    return action_dict

class Action(BaseModel):
    """Atomic or multi-step state mutation."""
    type: ActionType
    target: Optional[str] = None
    amount: Optional[str] = None
    value: Optional[str] = None
    item: Optional[Dict[str, Any]] = None
    from_: Optional[str] = Field(default=None, alias="from")
    field: Optional[str] = None
    steps: Optional[List[Action]] = None

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def parse_action_input(cls, data: Any) -> Any:
        if isinstance(data, str):
            data = parse_action_shorthand(data)
        if isinstance(data, dict):
            # Normalize type alias if present
            if "type" in data and isinstance(data["type"], str):
                t = data["type"].strip().lower()
                data["type"] = ACTION_ALIASES.get(t, t)
            # If item is present and is a string, parse it
            if "item" in data and isinstance(data["item"], str):
                data["item"] = _parse_item_dict(data["item"])
        return data

    @field_validator("type", mode="before")
    @classmethod
    def coerce_action_type(cls, v: Any) -> str:
        if isinstance(v, str):
            lowered = v.strip().lower()
            return ACTION_ALIASES.get(lowered, lowered)
        return "set"

    @field_validator("amount", "value", mode="before")
    @classmethod
    def coerce_expr_string(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    @field_validator("target", "from_", "field", mode="before")
    @classmethod
    def clean_ids(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return normalize_id(v)

class Component(BaseModel):
    """A declarative UI component."""
    id: str = Field(default_factory=lambda: f"comp_{uuid.uuid4().hex[:6]}")
    type: ComponentType
    label: Optional[str] = None
    text: Optional[str] = None
    bind: Optional[str] = None
    value: Optional[str] = None
    max: Optional[str] = None
    format: Optional[str] = None
    visible_if: Optional[str] = None
    tone: Optional[ToneType] = None
    action: Optional[str] = None
    options: Optional[List[str]] = None
    fields: Optional[List[str]] = None
    removable: Optional[bool] = None
    chart: Optional[ChartConfig] = None

    @field_validator("type", mode="before")
    @classmethod
    def coerce_component_type(cls, v: Any) -> str:
        if isinstance(v, str):
            lowered = v.strip().lower()
            if lowered in COMPONENT_ALIASES:
                return COMPONENT_ALIASES[lowered]
            if lowered in ComponentType.__args__:
                return lowered
        return "text"

    @field_validator("id", mode="before")
    @classmethod
    def ensure_id(cls, v: Any) -> str:
        return normalize_id(v, prefix="comp")

    @field_validator("value", "max", "visible_if", mode="before")
    @classmethod
    def coerce_expr_string(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v)

    @field_validator("fields", mode="before")
    @classmethod
    def coerce_fields_list(cls, v: Any) -> Optional[List[str]]:
        if not v:
            return None
        if isinstance(v, str):
            return [normalize_id(s) for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    result.append(normalize_id(item))
                elif isinstance(item, dict):
                    val = item.get("id") or item.get("key") or item.get("name") or item.get("field") or item.get("label")
                    if val is not None:
                        result.append(normalize_id(str(val)))
                elif item is not None:
                    result.append(str(item))
            return result
        return None

    @field_validator("options", mode="before")
    @classmethod
    def coerce_options_list(cls, v: Any) -> Optional[List[str]]:
        if not v:
            return None
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        if isinstance(v, list):
            result = []
            for item in v:
                if isinstance(item, str):
                    result.append(str(item))
                elif isinstance(item, dict):
                    val = item.get("value") or item.get("label") or item.get("name")
                    if val is not None:
                        result.append(str(val))
                elif item is not None:
                    result.append(str(item))
            return result
        return None

class Rule(BaseModel):
    """Validation or business alert rule."""
    when: str
    message: str

    @field_validator("when", mode="before")
    @classmethod
    def coerce_when_expr(cls, v: Any) -> str:
        return str(v) if v is not None else "false"

class Test(BaseModel):
    """Black-box unit test with inputs and expected outputs."""
    name: str
    inputs: Dict[str, Any]
    expect: Dict[str, Any]

class ContractStateItem(BaseModel):
    id: str
    label: Optional[str] = None
    type: StateType
    default: Any = None
    min: Optional[float] = None
    max: Optional[float] = None

    @field_validator("id", mode="before")
    def clean_id(cls, v: Any) -> str:
        return normalize_id(v, prefix="state")

    @field_validator("type", mode="before")
    def clean_type(cls, v: Any) -> str:
        if isinstance(v, str):
            return STATE_ALIASES.get(v.strip().lower(), v.strip().lower())
        return "number"

class ContractOutputItem(BaseModel):
    id: str
    label: Optional[str] = None
    type: Optional[str] = None

    @field_validator("id", mode="before")
    def clean_id(cls, v: Any) -> str:
        return normalize_id(v, prefix="out")

class ContractActionItem(BaseModel):
    id: str
    label: Optional[str] = None

    @field_validator("id", mode="before")
    def clean_id(cls, v: Any) -> str:
        return normalize_id(v, prefix="act")

class Contract(BaseModel):
    """The interface agreement produced by the Product Agent."""
    state: List[ContractStateItem] = Field(default_factory=list)
    outputs: List[ContractOutputItem] = Field(default_factory=list)
    actions: List[ContractActionItem] = Field(default_factory=list)

class AppMeta(BaseModel):
    name: str = "Mini App"
    theme: Literal["light", "dark"] = "light"

class AppSpec(BaseModel):
    """Complete validated application specification."""
    meta: AppMeta = Field(default_factory=AppMeta)
    state: Dict[str, StateDef] = Field(default_factory=dict)
    computed: Dict[str, str] = Field(default_factory=dict)
    rules: List[Rule] = Field(default_factory=list)
    components: List[Component] = Field(default_factory=list)
    actions: Dict[str, Action] = Field(default_factory=dict)
    tests: List[Test] = Field(default_factory=list)

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

    @field_validator("computed", mode="before")
    @classmethod
    def coerce_computed_expressions(cls, v: Any) -> Dict[str, str]:
        if isinstance(v, dict):
            return {normalize_id(k, "calc"): str(val) for k, val in v.items()}
        return {}

class Issue(BaseModel):
    owner: Literal["ux", "logic", "product"]
    msg: str

class CheckResult(BaseModel):
    layer: Literal["invariant", "example", "fuzz"]
    name: str
    pass_: bool = Field(alias="pass")
    detail: Optional[str] = None

    model_config = {"populate_by_name": True}
