import { evaluate, type Env, type Val } from "./formula";
import { compute } from "./verify";
import type { Action, AppSpec } from "./schema";

const MAX_ITEMS = 200;

export function fmt(v: Val | undefined, format?: string | null): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "string") return v;
  if (typeof v !== "number") return JSON.stringify(v);
  if (!Number.isFinite(v)) return "—";
  const [kind, d] = (format ?? "").split(":");
  const digits = d ? Number(d) : 2;
  if (kind === "percent") return v.toFixed(digits) + "%";
  if (kind === "number") return v.toFixed(digits);
  if (kind === "int") return String(Math.round(v));
  return String(Math.round(v * 100) / 100);
}

export function interpolate(text: string, env: Env): string {
  return text.replace(/\{\{(.+?)\}\}/g, (_, e) => { try { return fmt(evaluate(e, env)); } catch { return "—"; } });
}

function clampTo(spec: AppSpec, id: string, v: Val): Val {
  const d = spec.state[id];
  if (!d || typeof v !== "number") return v;
  if (d.type === "int") v = Math.round(v);
  if (d.min != null) v = Math.max(d.min, v as number);
  if (d.max != null) v = Math.min(d.max, v as number);
  return v;
}

/** The only way state changes. Pure; never throws; unknown/invalid actions are no-ops. */
export function applyAction(spec: AppSpec, a: Action | Omit<Action, "steps">, state: Env, rand: () => number = Math.random): Env {
  try {
    let s: Env = { ...state };
    const env = () => compute(spec, s);
    const t = a.target ?? "";
    const isState = t in spec.state;
    const amt = () => (a.amount ? Number(evaluate(a.amount, env())) : 1);
    switch (a.type) {
      case "set": if (isState && a.value) s[t] = clampTo(spec, t, evaluate(a.value, env())); break;
      case "increment": if (isState) s[t] = clampTo(spec, t, (Number(s[t]) || 0) + amt()); break;
      case "decrement": if (isState) s[t] = clampTo(spec, t, (Number(s[t]) || 0) - amt()); break;
      case "toggle": if (isState) s[t] = !s[t]; break;
      case "reset": if (isState) s[t] = spec.state[t].default ?? (spec.state[t].type === "list" ? [] : 0);
        else for (const k of Object.keys(spec.state)) s[k] = spec.state[k].default ?? s[k]; break;
      case "add_item": {
        const list = Array.isArray(s[t]) ? (s[t] as Val[]) : [];
        if (isState && a.item && list.length < MAX_ITEMS) {
          const e = env();
          const item: Record<string, Val> = {};
          for (const [k, f] of Object.entries(a.item)) {
            // If the value is already a primitive (bool, null, number) use directly;
            // otherwise treat it as a formula string to evaluate
            if (typeof f === "boolean" || f === null || typeof f === "number") {
              item[k] = f;
            } else {
              item[k] = evaluate(String(f), e);
            }
          }
          s[t] = [...list, item];
        }
        break;
      }
      case "remove_item": {
        const list = Array.isArray(s[t]) ? (s[t] as Val[]) : [];
        const idx = Number(evaluate(a.amount ?? "0", env()));
        if (isState && idx >= 0 && idx < list.length) s[t] = list.filter((_, i) => i !== idx);
        break;
      }
      case "random_pick": {
        const list = a.from && Array.isArray(s[a.from]) ? (s[a.from] as Val[]) : [];
        if (list.length && isState) {
          const it = list[Math.floor(rand() * list.length)] as any;
          s[t] = a.field && it && typeof it === "object" ? it[a.field] : it;
        }
        break;
      }
      case "run": for (const step of (a as Action).steps ?? []) s = applyAction(spec, step, s, rand); break;
    }
    return s;
  } catch { return state; }
}
