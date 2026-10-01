"""
Chunk 3A: Agent Base Definitions & Shared Runtime Vocabulary
------------------------------------------------------------
Educational Note for Students:
Every agent must adhere to the exact same vocabulary contract.
Without this shared boundary, agents will hallucinate components or functions
that the execution runtime does not support.
"""

GUIDE = """
=== APP RUNTIME VOCABULARY (you may use ONLY this) ===
Formulas: numbers, "strings", true/false/null, + - * / % < <= > >= == != and or not, parentheses.
Functions: if(cond,a,b) min max abs floor ceil round(x,digits) clamp(x,lo,hi) pow sqrt len(list) sumOf(list,"field") avgOf(list,"field").
Division by zero gives null; null propagates through arithmetic. Identifiers are state ids or computed ids (snake_case).
State types: int number percent text bool list (list default is an array of objects). Give min/max for numbers.
Components: every component MUST have a unique "id" (snake_case) and "type" from the vocabulary:
 heading(id,text) text(id,text) divider(id) button(id,label,action) number_input(id,label,bind) text_input(id,label,bind)
 slider(id,label,bind) select(id,label,bind,options) checkbox(id,label,bind) metric(id,label,value,format) progress(id,label,value,max)
 alert(id,text,tone,visible_if) list(id,label,bind,fields,removable) chart(id,label,chart:{from,to,y}; y may use variable i).
 "value","max","visible_if" are formulas. Text may embed {{formula}}. format: percent:2 | number:2 | int.
 button.action is the id of an entry in the actions map.
Actions MUST be JSON objects (never shorthand strings!):
- set: {"type": "set", "target": "state_id", "value": "formula"}
- increment / decrement: {"type": "increment", "target": "state_id", "amount": "formula"}
- toggle: {"type": "toggle", "target": "state_id"}
- reset: {"type": "reset", "target": "state_id"} (or omit target to reset all state)
- add_item: {"type": "add_item", "target": "list_id", "item": {"field": "formula"}}
- remove_item: {"type": "remove_item", "target": "list_id", "amount": "index_formula"}
- random_pick: {"type": "random_pick", "from": "list_id", "field": "field_name", "target": "state_id"}
Action formulas are strings: a text literal must be quoted, e.g. "'hello'".
Rules: [{when: formula that is true when input is INVALID, message}].
Return ONLY a valid JSON object.
"""
