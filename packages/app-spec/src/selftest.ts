import { DEMO_SPEC, runChecks, validateSpec, compute, defaultState, applyAction, evaluate } from "./index";

let failed = 0;
const ok = (c: boolean, m: string) => { console.log((c ? "✓ " : "✗ ") + m); if (!c) failed++; };

ok(validateSpec(DEMO_SPEC).length === 0, "demo spec has no dangling references");
const results = runChecks(DEMO_SPEC);
results.forEach((r) => ok(r.pass, `${r.layer}: ${r.name}${r.detail ? " — " + r.detail : ""}`));
const env = compute(DEMO_SPEC, defaultState(DEMO_SPEC));
ok(Math.abs((env.attendance_pct as number) - 82.8125) < 1e-9, "53/64 = 82.81%");
const after = compute(DEMO_SPEC, applyAction(DEMO_SPEC, DEMO_SPEC.actions.attend_tomorrow, defaultState(DEMO_SPEC)));
ok(after.conducted === 65 && after.attended === 54, "attend_tomorrow increments both");
for (const bad of ["__proto__", "constructor", "process", "a.b"]) {
  let threw = false; try { evaluate(bad, {}); } catch { threw = true; }
  ok(threw, `unsafe expression rejected: ${bad}`);
}
ok(evaluate("1/0", {}) === null, "division by zero → null");

import { Component, Action } from "./schema";
const c1 = Component.parse({ type: "heading", text: "Welcome" });
ok(!!c1.id && c1.type === "heading", "auto-assign id to component without id");
const c2 = Component.parse({ type: "header", text: "Title" });
ok(c2.type === "heading", "normalize component type alias header -> heading");
const c3 = Component.parse({ id: "123-bad-id", type: "dropdown", label: "Select", bind: "opt" });
ok(/^[a-z][a-z0-9_]{0,31}$/.test(c3.id) && c3.type === "select", "normalize component id & alias dropdown -> select");

const a1 = Action.parse("add_item(tasks, {text:new_task_text,done:false})");
ok(a1.type === "add_item" && a1.target === "tasks" && a1.item?.text === "new_task_text", "parse add_item shorthand string");
const a2 = Action.parse("increment(counter, 1)");
ok(a2.type === "increment" && a2.target === "counter" && a2.amount === "1", "parse increment shorthand string");

process.exit(failed ? 1 : 0);
