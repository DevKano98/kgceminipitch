import { z } from "zod";

const o = <T extends z.ZodTypeAny>(t: T) => t.nullish(); // LLMs like to emit null for "absent"

export const Id = z.string().regex(/^[a-z][a-z0-9_]{0,31}$/, "ids are snake_case, max 32 chars");
export const Expr = z.preprocess(
  (v) => (typeof v === "number" || typeof v === "boolean" ? String(v) : v),
  z.string().min(1).max(400)
);

export const STATE_TYPES = ["int", "number", "percent", "text", "bool", "list"] as const;
const STATE_ALIASES: Record<string, typeof STATE_TYPES[number]> = {
  boolean: "bool", string: "text", str: "text", integer: "int", float: "number", double: "number", array: "list", percentage: "percent",
};

const StateDefRaw = z.object({
  type: z.enum(STATE_TYPES),
  default: z.any(),
  min: o(z.number()),
  max: o(z.number()),
});

export const StateDef = z.preprocess((val: any) => {
  if (!val || typeof val !== "object") return val;
  let type = typeof val.type === "string" ? val.type.toLowerCase().trim() : val.type;
  if (STATE_ALIASES[type]) type = STATE_ALIASES[type];
  return { ...val, type };
}, StateDefRaw);

const ACTION_TYPES = ["set", "increment", "decrement", "toggle", "add_item", "remove_item", "reset", "random_pick"] as const;
const ACTION_ALIASES: Record<string, typeof ACTION_TYPES[number]> = {
  inc: "increment", dec: "decrement", add: "add_item", remove: "remove_item", clear: "reset",
};

function coerceItemValue(v: any): any {
  if (typeof v === "boolean" || v === null || v === undefined) return v;
  if (typeof v === "number") return v;
  const s = String(v).trim();
  if (s === "true") return true;
  if (s === "false") return false;
  if (s === "null" || s === "none") return null;
  const n = Number(s);
  if (!isNaN(n) && s !== "") return n;
  // Strip surrounding quotes
  if ((s.startsWith('"') && s.endsWith('"')) || (s.startsWith("'") && s.endsWith("'")))
    return s.slice(1, -1);
  return s;
}

function parseItemDict(itemRaw: any): Record<string, unknown> {
  if (typeof itemRaw === "object" && itemRaw !== null) {
    const res: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(itemRaw)) res[k] = coerceItemValue(v);
    return res;
  }
  if (typeof itemRaw !== "string") return {};
  let s = itemRaw.trim();
  if (s.startsWith("{") && s.endsWith("}")) s = s.slice(1, -1).trim();
  const res: Record<string, unknown> = {};
  if (!s) return res;
  const pairs: string[] = [];
  let curr = "";
  let inQ: string | null = null;
  let depth = 0;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (inQ) {
      curr += c;
      if (c === inQ) inQ = null;
    } else if (c === '"' || c === "'") {
      inQ = c;
      curr += c;
    } else if (c === '{' || c === '[' || c === '(') {
      depth++;
      curr += c;
    } else if (c === '}' || c === ']' || c === ')') {
      depth--;
      curr += c;
    } else if (c === ',' && depth === 0) {
      pairs.push(curr.trim());
      curr = "";
    } else {
      curr += c;
    }
  }
  if (curr.trim()) pairs.push(curr.trim());

  for (const pair of pairs) {
    if (pair.includes(":")) {
      const idx = pair.indexOf(":");
      const k = pair.slice(0, idx).trim().replace(/^['"]|['"]$/g, "");
      const v = pair.slice(idx + 1).trim();
      res[k] = coerceItemValue(v);
    } else if (pair.includes("=")) {
      const idx = pair.indexOf("=");
      const k = pair.slice(0, idx).trim().replace(/^['"]|['"]$/g, "");
      const v = pair.slice(idx + 1).trim();
      res[k] = coerceItemValue(v);
    }
  }
  return res;
}

function parseActionShorthand(raw: any): any {
  if (typeof raw !== "string") return raw;
  const s = raw.trim();
  if (!s) return { type: "reset" };
  const match = s.match(/^([a-zA-Z_]\w*)(?:\((.*)\))?$/s);
  if (!match) return { type: (ACTION_ALIASES as any)[s.toLowerCase()] || s.toLowerCase() };
  let fnName = match[1].toLowerCase().trim();
  fnName = (ACTION_ALIASES as any)[fnName] || fnName;
  const argsStr = match[2];
  if (!argsStr || !argsStr.trim()) return { type: fnName };

  const args: string[] = [];
  let curr = "";
  let inQ: string | null = null;
  let depth = 0;
  for (let i = 0; i < argsStr.length; i++) {
    const c = argsStr[i];
    if (inQ) {
      curr += c;
      if (c === inQ) inQ = null;
    } else if (c === '"' || c === "'") {
      inQ = c;
      curr += c;
    } else if (c === '{' || c === '[' || c === '(') {
      depth++;
      curr += c;
    } else if (c === '}' || c === ']' || c === ')') {
      depth--;
      curr += c;
    } else if (c === ',' && depth === 0) {
      args.push(curr.trim());
      curr = "";
    } else {
      curr += c;
    }
  }
  if (curr.trim()) args.push(curr.trim());

  const act: any = { type: fnName };
  const positional: string[] = [];
  for (const arg of args) {
    if (arg.includes("=") && !arg.startsWith("{") && !arg.startsWith("[")) {
      const idx = arg.indexOf("=");
      const k = arg.slice(0, idx).trim().toLowerCase();
      const v = arg.slice(idx + 1).trim();
      if (k === "item") act.item = parseItemDict(v);
      else if (["target", "amount", "value", "field", "from"].includes(k)) act[k] = v;
      else positional.push(arg);
    } else {
      positional.push(arg);
    }
  }

  if (fnName === "add_item") {
    if (positional.length > 0 && !act.target) act.target = positional[0];
    if (positional.length > 1 && !act.item) act.item = parseItemDict(positional[1]);
  } else if (fnName === "increment" || fnName === "decrement") {
    if (positional.length > 0 && !act.target) act.target = positional[0];
    if (positional.length > 1 && !act.amount) act.amount = positional[1];
  } else if (fnName === "set") {
    if (positional.length > 0 && !act.target) act.target = positional[0];
    if (positional.length > 1 && !act.value) act.value = positional[1];
  } else if (fnName === "toggle" || fnName === "reset") {
    if (positional.length > 0 && !act.target) act.target = positional[0];
  } else if (fnName === "remove_item") {
    if (positional.length > 0 && !act.target) act.target = positional[0];
    if (positional.length > 1 && !act.amount) act.amount = positional[1];
  } else if (fnName === "random_pick") {
    if (positional.length > 0 && !act.from) act.from = positional[0];
    if (positional.length > 1 && !act.field) act.field = positional[1];
    if (positional.length > 2 && !act.target) act.target = positional[2];
  }
  return act;
}

const normalizeActionObj = (val: any) => {
  if (typeof val === "string") val = parseActionShorthand(val);
  if (!val || typeof val !== "object") return val;
  let type = typeof val.type === "string" ? val.type.toLowerCase().trim() : val.type;
  if ((ACTION_ALIASES as any)[type]) type = (ACTION_ALIASES as any)[type];
  let target = typeof val.target === "string" ? val.target.toLowerCase().trim().replace(/[\s-]+/g, "_") : val.target;
  if (typeof val.item === "string") val.item = parseItemDict(val.item);
  return { ...val, type, target };
};

const ActionBaseRaw = z.object({
  type: z.enum(ACTION_TYPES),
  target: o(Id),
  amount: o(Expr),
  value: o(Expr),
  item: o(z.record(Id, z.unknown())),
  from: o(Id),
  field: o(Id),
});

export const ActionBase = z.preprocess(normalizeActionObj, ActionBaseRaw);

const ActionRaw = ActionBaseRaw.extend({
  type: z.enum([...ACTION_TYPES, "run"]),
  steps: o(z.array(ActionBase).max(10)),
});

export const Action = z.preprocess(normalizeActionObj, ActionRaw);

export const COMPONENT_TYPES = [
  "heading", "text", "divider", "button", "number_input", "text_input", "slider",
  "select", "checkbox", "metric", "progress", "alert", "list", "chart",
] as const;

const COMPONENT_ALIASES: Record<string, typeof COMPONENT_TYPES[number]> = {
  header: "heading", title: "heading", h1: "heading", h2: "heading", h3: "heading",
  paragraph: "text", p: "text", label: "text", description: "text", span: "text",
  hr: "divider", separator: "divider", line: "divider",
  btn: "button",
  input: "text_input", textfield: "text_input", text_field: "text_input", string_input: "text_input",
  number: "number_input", numeric_input: "number_input", int_input: "number_input",
  range: "slider",
  dropdown: "select", combobox: "select",
  switch: "checkbox", toggle: "checkbox", check: "checkbox",
  stat: "metric", counter: "metric", display: "metric", card: "metric",
  progress_bar: "progress", progressbar: "progress",
  notification: "alert", banner: "alert", message: "alert",
  table: "list", items: "list",
  graph: "chart", plot: "chart",
};

let compCounter = 0;
const ComponentRaw = z.object({
  id: Id,
  type: z.enum(COMPONENT_TYPES),
  label: o(z.string().max(200)),
  text: o(z.string().max(500)),
  bind: o(Id),
  value: o(Expr),
  max: o(Expr),
  format: o(z.string().max(20)),
  visible_if: o(Expr),
  tone: o(z.enum(["info", "success", "warning", "error"])),
  action: o(Id),
  options: o(z.array(z.string().max(100)).max(30)),
  fields: o(z.array(Id).max(6)),
  removable: o(z.boolean()),
  chart: o(z.object({ from: z.number(), to: z.number(), y: Expr })),
});

export const Component = z.preprocess((val: any) => {
  if (!val || typeof val !== "object") return val;
  let type = typeof val.type === "string" ? val.type.toLowerCase().trim() : "text";
  if (COMPONENT_ALIASES[type]) type = COMPONENT_ALIASES[type];
  if (!COMPONENT_TYPES.includes(type as any)) type = "text";

  let id = val.id ?? val.key ?? val.name;
  if (typeof id === "string") {
    id = id.toLowerCase().trim().replace(/[\s-]+/g, "_").replace(/[^a-z0-9_]/g, "");
    if (/^[0-9_]/.test(id)) id = "c_" + id;
  }
  if (!id || typeof id !== "string") {
    id = `${type}_${++compCounter}_${Math.random().toString(36).slice(2, 6)}`;
  }
  id = id.slice(0, 32);

  let bind = typeof val.bind === "string" ? val.bind.toLowerCase().trim().replace(/[\s-]+/g, "_") : val.bind;
  let action = typeof val.action === "string" ? val.action.toLowerCase().trim().replace(/[\s-]+/g, "_") : val.action;

  let fields = Array.isArray(val.fields) ? val.fields.map((f: any) => {
    if (typeof f === "string") return f.toLowerCase().trim().replace(/[\s-]+/g, "_").replace(/[^a-z0-9_]/g, "");
    if (f && typeof f === "object") {
      const v = f.id || f.key || f.name || f.field || f.label;
      if (v != null) return String(v).toLowerCase().trim().replace(/[\s-]+/g, "_").replace(/[^a-z0-9_]/g, "");
    }
    return String(f);
  }) : val.fields;

  let options = Array.isArray(val.options) ? val.options.map((o: any) => {
    if (typeof o === "string") return o;
    if (o && typeof o === "object") {
      const v = o.value ?? o.label ?? o.name;
      if (v != null) return String(v);
    }
    return String(o);
  }) : val.options;

  return {
    ...val,
    id,
    type,
    bind,
    action,
    fields,
    options,
  };
}, ComponentRaw);

export const Rule = z.object({ when: Expr, message: z.string().max(300) });
export const Test = z.object({
  name: z.string().max(120),
  inputs: z.record(Id, z.any()),
  expect: z.record(Id, z.union([z.number(), z.boolean(), z.null(), z.string()])),
});

const ContractRaw = z.object({
  state: z.array(z.object({
    id: Id, label: o(z.string()), type: z.enum(STATE_TYPES), default: z.any(), min: o(z.number()), max: o(z.number()),
  })).max(12),
  outputs: z.array(z.object({ id: Id, label: o(z.string()), type: o(z.string()) })).max(14),
  actions: o(z.array(z.object({ id: Id, label: o(z.string()) })).max(12)).transform((v) => v ?? []),
});

export const Contract = z.preprocess((val: any) => {
  if (!val || typeof val !== "object") return val;
  if (Array.isArray(val.state)) {
    val = {
      ...val,
      state: val.state.map((s: any) => {
        if (!s || typeof s !== "object") return s;
        let type = typeof s.type === "string" ? s.type.toLowerCase().trim() : s.type;
        if (STATE_ALIASES[type]) type = STATE_ALIASES[type];
        let id = typeof s.id === "string" ? s.id.toLowerCase().trim().replace(/[\s-]+/g, "_") : s.id;
        return { ...s, id, type };
      }),
    };
  }
  return val;
}, ContractRaw);

export const AppSpec = z.object({
  meta: z.object({ name: z.string().max(60), theme: z.enum(["light", "dark"]).default("light") }),
  state: z.record(Id, StateDef),
  computed: z.record(Id, Expr),
  rules: z.array(Rule).max(20),
  components: z.array(Component).min(1).max(50),
  actions: z.preprocess((val: any) => {
    if (Array.isArray(val)) {
      const res: Record<string, any> = {};
      val.forEach((it, i) => {
        const id = it && typeof it === "object" && it.id ? it.id : `act_${i}`;
        res[id] = it;
      });
      return res;
    }
    return val;
  }, z.record(Id, Action)),
  tests: z.array(Test).max(12),
}).refine((s) => Object.keys(s.computed).length <= 40 && Object.keys(s.state).length <= 30, "spec too large")
  .refine((s) => JSON.stringify(s).length < 100_000, "spec exceeds 100 KB");

export type AppSpec = z.infer<typeof AppSpec>;
export type Contract = z.infer<typeof Contract>;
export type Action = z.infer<typeof Action>;
export type Component = z.infer<typeof Component>;
