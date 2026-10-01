// Safe formula language: a hand-written Pratt parser + tree-walking evaluator.
// No eval, no new Function, no property access, bounded work.
export type Val = number | string | boolean | null | Val[] | { [k: string]: Val };
export type Env = Record<string, Val>;
export class FormulaError extends Error {}
export class UnknownId extends FormulaError {
  constructor(public id: string) { super(`Unknown identifier: ${id}`); }
}
type Node =
  | { t: "lit"; v: number | string | boolean | null }
  | { t: "id"; n: string }
  | { t: "un"; op: string; a: Node }
  | { t: "bin"; op: string; l: Node; r: Node }
  | { t: "call"; n: string; args: Node[] };
type Tok = { k: "num" | "id" | "str" | "op"; v: string };

const TOKEN = /\s*(?:(\d+\.?\d*)|([A-Za-z_][A-Za-z0-9_]*)|("[^"]*"|'[^']*')|(<=|>=|==|!=|[-+*/%<>(),]))/y;

function tokenize(src: string): Tok[] {
  const out: Tok[] = [];
  let pos = 0;
  while (pos < src.length) {
    if (/^\s*$/.test(src.slice(pos))) break;
    TOKEN.lastIndex = pos;
    const m = TOKEN.exec(src);
    if (!m) throw new FormulaError(`Unexpected character near "${src.slice(pos, pos + 8)}"`);
    pos = TOKEN.lastIndex;
    if (m[1] !== undefined) out.push({ k: "num", v: m[1] });
    else if (m[2] !== undefined) out.push({ k: "id", v: m[2] });
    else if (m[3] !== undefined) out.push({ k: "str", v: m[3].slice(1, -1) });
    else out.push({ k: "op", v: m[4] });
  }
  return out;
}

const PREC: Record<string, number> = {
  "==": 3, "!=": 3, "<": 3, "<=": 3, ">": 3, ">=": 3, "+": 4, "-": 4, "*": 5, "/": 5, "%": 5,
};

function parse(src: string): Node {
  if (src.length > 400) throw new FormulaError("Formula too long");
  const toks = tokenize(src);
  let i = 0;
  const isOp = (v: string) => toks[i]?.k === "op" && toks[i].v === v;
  const expect = (v: string) => { if (!isOp(v)) throw new FormulaError(`Expected "${v}"`); i++; };
  const prec = (t?: Tok) => {
    if (!t) return 0;
    if (t.k === "id") return t.v === "or" ? 1 : t.v === "and" ? 2 : 0;
    return t.k === "op" ? PREC[t.v] ?? 0 : 0;
  };
  function expr(min: number, depth: number): Node {
    if (depth > 40) throw new FormulaError("Formula nested too deeply");
    let left = unary(depth);
    for (;;) {
      const t = toks[i];
      const p = prec(t);
      if (p === 0 || p < min) break;
      i++;
      const right = expr(p + 1, depth + 1);
      left = { t: "bin", op: t.v, l: left, r: right };
    }
    return left;
  }
  function unary(depth: number): Node {
    const t = toks[i];
    if (t?.k === "op" && t.v === "-") { i++; return { t: "un", op: "-", a: unary(depth + 1) }; }
    if (t?.k === "id" && t.v === "not") { i++; return { t: "un", op: "not", a: unary(depth + 1) }; }
    return primary(depth);
  }
  function primary(depth: number): Node {
    const t = toks[i++];
    if (!t) throw new FormulaError("Unexpected end of formula");
    if (t.k === "num") return { t: "lit", v: Number(t.v) };
    if (t.k === "str") return { t: "lit", v: t.v };
    if (t.k === "op" && t.v === "(") { const e = expr(1, depth + 1); expect(")"); return e; }
    if (t.k === "id") {
      if (t.v === "true") return { t: "lit", v: true };
      if (t.v === "false") return { t: "lit", v: false };
      if (t.v === "null") return { t: "lit", v: null };
      if (isOp("(")) {
        i++;
        const args: Node[] = [];
        if (!isOp(")")) for (;;) { args.push(expr(1, depth + 1)); if (isOp(",")) { i++; continue; } break; }
        expect(")");
        return { t: "call", n: t.v, args };
      }
      return { t: "id", n: t.v };
    }
    throw new FormulaError(`Unexpected token "${t.v}"`);
  }
  const root = expr(1, 0);
  if (i < toks.length) throw new FormulaError(`Unexpected token "${toks[i].v}"`);
  return root;
}

const cache = new Map<string, Node>();
function compile(src: string): Node {
  let n = cache.get(src);
  if (!n) { n = parse(src); if (cache.size > 500) cache.clear(); cache.set(src, n); }
  return n;
}

const num = (v: Val): number | null => {
  if (v === null) return null;
  if (typeof v === "number") return v;
  if (typeof v === "boolean") return v ? 1 : 0;
  throw new FormulaError("Expected a number");
};
const truthy = (v: Val) => v !== null && v !== false && v !== 0 && v !== "";
const CMP = ["<", "<=", ">", ">="];

export function evaluate(src: string, env: Env): Val {
  const root = compile(src);
  let ops = 0;
  const has = (n: string) => Object.prototype.hasOwnProperty.call(env, n);
  function ev(n: Node): Val {
    if (++ops > 10000) throw new FormulaError("Formula too expensive");
    switch (n.t) {
      case "lit": return n.v;
      case "id": if (!has(n.n)) throw new UnknownId(n.n); return env[n.n];
      case "un": {
        const a = ev(n.a);
        if (n.op === "not") return !truthy(a);
        const x = num(a); return x === null ? null : -x;
      }
      case "bin": {
        if (n.op === "and") return truthy(ev(n.l)) ? truthy(ev(n.r)) : false;
        if (n.op === "or") return truthy(ev(n.l)) ? true : truthy(ev(n.r));
        const l = ev(n.l), r = ev(n.r);
        if (n.op === "==") return l === r;
        if (n.op === "!=") return l !== r;
        if (n.op === "+" && (typeof l === "string" || typeof r === "string")) return String(l ?? "") + String(r ?? "");
        const a = num(l), b = num(r);
        if (a === null || b === null) return CMP.includes(n.op) ? false : null;
        switch (n.op) {
          case "+": return a + b;
          case "-": return a - b;
          case "*": return a * b;
          case "/": return b === 0 ? null : a / b;
          case "%": return b === 0 ? null : a % b;
          case "<": return a < b;
          case "<=": return a <= b;
          case ">": return a > b;
          default: return a >= b;
        }
      }
      case "call": return call(n);
    }
  }
  function call(n: Extract<Node, { t: "call" }>): Val {
    const f = n.n;
    if (f === "if") {
      if (n.args.length !== 3) throw new FormulaError("if() needs 3 arguments");
      return truthy(ev(n.args[0])) ? ev(n.args[1]) : ev(n.args[2]);
    }
    const a = n.args.map(ev);
    const x = a.length ? num(a[0]) : null;
    switch (f) {
      case "min": case "max": {
        const xs = a.map(num);
        if (!xs.length || xs.includes(null)) return null;
        return f === "min" ? Math.min(...(xs as number[])) : Math.max(...(xs as number[]));
      }
      case "abs": case "floor": case "ceil": case "sqrt":
        return x === null ? null : (Math as any)[f](x);
      case "round": {
        const d = a.length > 1 ? num(a[1]) ?? 0 : 0;
        return x === null ? null : Math.round(x * 10 ** d) / 10 ** d;
      }
      case "clamp": {
        const lo = num(a[1]), hi = num(a[2]);
        return x === null || lo === null || hi === null ? null : Math.min(hi, Math.max(lo, x));
      }
      case "pow": { const y = num(a[1]); return x === null || y === null ? null : Math.pow(x, y); }
      case "len": return Array.isArray(a[0]) ? a[0].length : 0;
      case "sumOf": case "avgOf": {
        const list = Array.isArray(a[0]) ? a[0] : [];
        const field = String(a[1]);
        const vals = list.map((it) => (it && typeof it === "object" && !Array.isArray(it) ? num(it[field] as Val) ?? 0 : 0));
        const s = vals.reduce((p, c) => p + c, 0);
        return f === "sumOf" ? s : vals.length ? s / vals.length : null;
      }
      default: throw new FormulaError(`Unknown function: ${f}`);
    }
  }
  return ev(root);
}

/** Identifiers a formula reads (function names excluded). */
export function idsOf(src: string): string[] {
  const out = new Set<string>();
  (function walk(n: Node) {
    if (n.t === "id") out.add(n.n);
    else if (n.t === "un") walk(n.a);
    else if (n.t === "bin") { walk(n.l); walk(n.r); }
    else if (n.t === "call") n.args.forEach(walk);
  })(compile(src));
  return [...out];
}

export const templateExprs = (text: string) => [...text.matchAll(/\{\{(.+?)\}\}/g)].map((m) => m[1]);
