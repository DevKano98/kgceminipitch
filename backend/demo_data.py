"""
Chunk 4A: Reference Demo Mini-App Specification
------------------------------------------------
Educational Note for Students:
This reference spec serves two vital roles:
1. Ground Truth / Gold Standard for self-testing the verifier and runtime.
2. Offline Fallback: If no GROQ_API_KEY is supplied, the server seamlessly
   demonstrates full streaming execution using this verified mini-app.
"""

from models.spec import AppSpec

DEMO_SPEC = AppSpec.model_validate({
    "meta": {"name": "Can I Bunk? 🎓", "theme": "light"},
    "state": {
        "conducted": {"type": "int", "default": 64, "min": 0, "max": 1000},
        "attended": {"type": "int", "default": 53, "min": 0, "max": 1000},
        "target": {"type": "percent", "default": 75, "min": 1, "max": 99},
    },
    "computed": {
        "attendance_pct": "if(conducted > 0, attended * 100 / conducted, null)",
        "max_skippable": "max(0, floor(attended * 100 / target - conducted))",
        "can_skip_tomorrow": "conducted > 0 and attended * 100 / (conducted + 1) >= target",
        "classes_to_recover": "if(conducted == 0, null, if(attendance_pct >= target, 0, max(0, ceil((target * conducted - 100 * attended) / (100 - target)))))",
    },
    "rules": [
        {"when": "attended > conducted", "message": "Attended lectures cannot exceed conducted lectures."}
    ],
    "components": [
        {"id": "h1", "type": "heading", "text": "Can I bunk tomorrow?"},
        {"id": "in_conducted", "type": "number_input", "label": "Lectures conducted", "bind": "conducted"},
        {"id": "in_attended", "type": "number_input", "label": "Lectures attended", "bind": "attended"},
        {"id": "in_target", "type": "slider", "label": "Minimum attendance %", "bind": "target"},
        {"id": "m_pct", "type": "metric", "label": "Current attendance", "value": "attendance_pct", "format": "percent:2"},
        {"id": "p_pct", "type": "progress", "value": "attendance_pct", "max": "100"},
        {
            "id": "a_yes",
            "type": "alert",
            "tone": "success",
            "visible_if": "can_skip_tomorrow",
            "text": "Yes, skip tomorrow and you'd still be at {{round(attended * 100 / (conducted + 1), 1)}}%."
        },
        {
            "id": "a_no",
            "type": "alert",
            "tone": "warning",
            "visible_if": "conducted > 0 and not can_skip_tomorrow",
            "text": "Don't skip tomorrow: you'd drop to {{round(attended * 100 / (conducted + 1), 1)}}%, below your {{target}}% target."
        },
        {"id": "m_skip", "type": "metric", "label": "Lectures you can still skip", "value": "max_skippable", "format": "int"},
        {"id": "m_rec", "type": "metric", "label": "Lectures to attend in a row to recover", "value": "classes_to_recover", "format": "int"},
        {"id": "b_skip", "type": "button", "label": "Simulate: I skip tomorrow", "action": "skip_tomorrow"},
        {"id": "b_att", "type": "button", "label": "Simulate: I attend tomorrow", "action": "attend_tomorrow"},
        {"id": "ch", "type": "chart", "label": "Attendance % if you attend the next 10 lectures", "chart": {"from": 0, "to": 10, "y": "(attended + i) * 100 / (conducted + i)"}},
    ],
    "actions": {
        "skip_tomorrow": {"type": "increment", "target": "conducted", "amount": "1"},
        "attend_tomorrow": {
            "type": "run",
            "steps": [
                {"type": "increment", "target": "conducted", "amount": "1"},
                {"type": "increment", "target": "attended", "amount": "1"}
            ]
        },
    },
    "tests": [
        {"name": "100 conducted, 75 attended → 75%", "inputs": {"conducted": 100, "attended": 75, "target": 75}, "expect": {"attendance_pct": 75, "max_skippable": 0}},
        {"name": "Boundary: 0% attendance", "inputs": {"conducted": 100, "attended": 0, "target": 75}, "expect": {"attendance_pct": 0, "max_skippable": 0, "classes_to_recover": 300}},
        {"name": "Boundary: 100% attendance", "inputs": {"conducted": 100, "attended": 100, "target": 75}, "expect": {"attendance_pct": 100, "max_skippable": 33}},
        {"name": "Nothing conducted yet", "inputs": {"conducted": 0, "attended": 0, "target": 75}, "expect": {"attendance_pct": None, "can_skip_tomorrow": False}},
        {"name": "Reference: 53/64 at 75%", "inputs": {"conducted": 64, "attended": 53, "target": 75}, "expect": {"max_skippable": 6, "can_skip_tomorrow": True}},
    ],
})
