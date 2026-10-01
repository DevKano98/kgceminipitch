import { evaluate, idsOf, templateExprs, UnknownId, type Env } from "./formula";
import type { AppSpec } from "./schema";

export type Issue = { owner: "ux" | "logic"; msg: string };
export type CheckResult = { layer: "invariant" | "example" | "fuzz"; name: string; pass: boolean; detail?: string };

export function defaultState(spec: AppSpec): Env {
  const s: Env = {};
  for (const [k, d] of Object.entries(spec.state)) s[k] = d.default ?? (d.type === "list" ? [] : d.type === "bool" ? false : d.type === "text" ? "" : d.min ?? 0);
  return s;
}

/** Evaluate computed values; they may reference each other in any order. */
export function compute(spec: AppSpec, state: Env): Env {
  const env: Env = { ...state };
  let pending = Object.keys(spec.computed);
  for (let pass = 0; pending.length && pass <= Object.keys(spec.computed).length; pass++) {
    const next: string[] = [];
    for (const k of pending) {
      try { env[k] = evaluate(spec.computed[k], env); }
      catch (e) { if (e instanceof UnknownId) next.push(k); else env[k] = null; }
    }
    if (next.length === pending.length) { next.forEach((k) => (env[k] = null)); break; }
    pending = next;
  }
  return env;
}

/** Static validation: every reference must resolve. Issues are routed to the owning agent. */
export function validateSpec(spec: AppSpec): Issue[] {
  const issues: Issue[] = [];
  const known = new Set([...Object.keys(spec.state), ...Object.keys(spec.computed)]);
  const chk = (owner: Issue["owner"], where: string, src: string, extra: string[] = []) => {
    try { for (const id of idsOf(src)) if (!known.has(id) && !extra.includes(id)) issues.push({ owner, msg: `${where}: unknown id "${id}"` }); }
    catch (e: any) { issues.push({ owner, msg: `${where}: ${e.message}` }); }
  };
  for (const [k, f] of Object.entries(spec.computed)) chk("logic", `computed.${k}`, f);
  spec.rules.forEach((r, i) => chk("logic", `rules[${i}]`, r.when));
  const checkAction = (where: string, a: any) => {
    if (a.target && !spec.state[a.target]) issues.push({ owner: "logic", msg: `${where}: target "${a.target}" is not a state id` });
    if (a.from && !spec.state[a.from]) issues.push({ owner: "logic", msg: `${where}: from "${a.from}" is not a state id` });
    for (const e of [a.amount, a.value]) if (e) chk("logic", where, e);
    Object.values(a.item ?? {}).forEach((e) => chk("logic", where, e as string));
    (a.steps ?? []).forEach((s: any, i: number) => checkAction(`${where}.steps[${i}]`, s));
  };
  for (const [k, a] of Object.entries(spec.actions)) checkAction(`actions.${k}`, a);
  const seen = new Set<string>();
  for (const c of spec.components) {
    if (seen.has(c.id)) issues.push({ owner: "ux", msg: `duplicate component id "${c.id}"` });
    seen.add(c.id);
    if (c.bind && !spec.state[c.bind]) issues.push({ owner: "ux", msg: `component ${c.id}: bind "${c.bind}" is not a state id` });
    if (["number_input", "text_input", "slider", "select", "checkbox", "list"].includes(c.type) && !c.bind)
      issues.push({ owner: "ux", msg: `component ${c.id}: ${c.type} needs bind` });
    for (const e of [c.value, c.max, c.visible_if]) if (e) chk("ux", `component ${c.id}`, e);
    if (c.chart) chk("ux", `component ${c.id}.chart`, c.chart.y, ["i"]);
    if (c.action && !spec.actions[c.action]) issues.push({ owner: "ux", msg: `component ${c.id}: action "${c.action}" is not defined` });
    if (c.type === "button" && !c.action) issues.push({ owner: "ux", msg: `button ${c.id} has no action` });
    for (const t of [c.text, c.label]) if (t) templateExprs(t).forEach((e) => chk("ux", `component ${c.id} text`, e));
  }
  return issues;
}

function rng(seed: number) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
const bad = (v: unknown) => typeof v === "number" && !Number.isFinite(v);

function stateAt(spec: AppSpec, mode: "min" | "max" | "rand", r: () => number): Env {
  const s = defaultState(spec);
  for (const [k, d] of Object.entries(spec.state)) {
    if (d.type === "int" || d.type === "number" || d.type === "percent") {
      const lo = d.min ?? 0, hi = d.max ?? 1000;
      s[k] = mode === "min" ? lo : mode === "max" ? hi : lo + r() * (hi - lo);
      if (d.type === "int") s[k] = Math.round(s[k] as number);
    } else if (d.type === "bool" && mode === "rand") s[k] = r() > 0.5;
  }
  return s;
}

/** Deterministic checks: invariants, example tests (from the Test Author), fuzzing. */
export function runChecks(spec: AppSpec): CheckResult[] {
  const out: CheckResult[] = [];
  const finite = (env: Env) => Object.keys(spec.computed).filter((k) => bad(env[k]));
  for (const [name, mode] of [["defaults", null], ["all inputs at minimum", "min"], ["all inputs at maximum", "max"]] as const) {
    const env = compute(spec, mode ? stateAt(spec, mode, Math.random) : defaultState(spec));
    const b = finite(env);
    out.push({ layer: "invariant", name: `No NaN/Infinity: ${name}`, pass: !b.length, detail: b.length ? `bad: ${b.join(", ")}` : undefined });
  }
  for (const t of spec.tests) {
    const env = compute(spec, { ...defaultState(spec), ...(t.inputs as Env) });
    const fails: string[] = [];
    for (const [k, exp] of Object.entries(t.expect)) {
      const got = env[k];
      const ok = typeof exp === "number" && typeof got === "number" ? Math.abs(exp - got) < 0.01 : exp === got;
      if (!ok) fails.push(`${k}: expected ${JSON.stringify(exp)}, received ${JSON.stringify(got ?? null)}`);
    }
    out.push({ layer: "example", name: t.name, pass: !fails.length, detail: fails.join("; ") || undefined });
  }
  const r = rng(42);
  let badRun: string | undefined;
  for (let i = 0; i < 100 && !badRun; i++) {
    const env = compute(spec, stateAt(spec, "rand", r));
    const b = finite(env);
    if (b.length) badRun = `${b.join(", ")} not finite for state ${JSON.stringify(Object.fromEntries(Object.keys(spec.state).map((k) => [k, env[k]])))}`;
  }
  out.push({ layer: "fuzz", name: "100 random in-range inputs stay finite", pass: !badRun, detail: badRun });
  return out;
}
