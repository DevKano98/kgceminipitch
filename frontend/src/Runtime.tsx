import { useMemo, useState } from "react";
import { applyAction, compute, defaultState, evaluate, fmt, interpolate, type AppSpec, type Env } from "@appforge/app-spec";

// The renderer only knows the component vocabulary. There is no code path that executes spec-provided JS.
export default function Runtime({ spec }: { spec: AppSpec }) {
  const [state, setState] = useState<Env>(() => defaultState(spec));
  const env = useMemo(() => compute(spec, state), [spec, state]);
  const truthy = (expr?: string | null) => {
    if (!expr) return true;
    try { const v = evaluate(expr, env); return v !== null && v !== false && v !== 0 && v !== ""; } catch { return false; }
  };
  const val = (expr?: string | null) => { if (!expr) return null; try { return evaluate(expr, env); } catch { return null; } };
  const set = (id: string, raw: any) => {
    const d = spec.state[id];
    let v = raw;
    if (d && (d.type === "int" || d.type === "number" || d.type === "percent")) {
      v = raw === "" ? 0 : Number(raw);
      if (!Number.isFinite(v)) v = 0;
      if (d.type === "int") v = Math.round(v);
      if (d.min != null) v = Math.max(d.min, v);
      if (d.max != null) v = Math.min(d.max, v);
    }
    setState((s) => ({ ...s, [id]: v }));
  };
  const run = (id?: string | null) => { const a = id ? spec.actions[id] : null; if (a) setState((s) => applyAction(spec, a, s)); };

  return (
    <div className={`app ${spec.meta.theme}`}>
      <h2>{spec.meta.name}</h2>
      {spec.rules.filter((r) => truthy(r.when)).map((r, i) => <div key={i} className="alert error">⚠ {r.message}</div>)}
      {spec.components.map((c) => {
        if (!truthy(c.visible_if)) return null;
        const label = c.label ? interpolate(c.label, env) : "";
        const d = c.bind ? spec.state[c.bind] : undefined;
        switch (c.type) {
          case "heading": return <h3 key={c.id}>{interpolate(c.text ?? "", env)}</h3>;
          case "text": return <p key={c.id}>{interpolate(c.text ?? "", env)}</p>;
          case "divider": return <hr key={c.id} />;
          case "button": return <button key={c.id} className="btn" onClick={() => run(c.action)}>{label}</button>;
          case "number_input": return <label key={c.id} className="field"><span>{label}</span><input type="number" value={String(env[c.bind!] ?? "")} onChange={(e) => set(c.bind!, e.target.value)} /></label>;
          case "text_input": return <label key={c.id} className="field"><span>{label}</span><input type="text" maxLength={200} value={String(env[c.bind!] ?? "")} onChange={(e) => set(c.bind!, e.target.value)} /></label>;
          case "slider": return <label key={c.id} className="field"><span>{label}: <b>{fmt(env[c.bind!] as any)}</b></span><input type="range" min={d?.min ?? 0} max={d?.max ?? 100} value={Number(env[c.bind!]) || 0} onChange={(e) => set(c.bind!, e.target.value)} /></label>;
          case "select": return <label key={c.id} className="field"><span>{label}</span><select value={String(env[c.bind!] ?? "")} onChange={(e) => set(c.bind!, e.target.value)}>{(c.options ?? []).map((o) => <option key={o}>{o}</option>)}</select></label>;
          case "checkbox": return <label key={c.id} className="check"><input type="checkbox" checked={!!env[c.bind!]} onChange={(e) => set(c.bind!, e.target.checked)} />{label}</label>;
          case "metric": return <div key={c.id} className="metric"><small>{label}</small><strong>{fmt(val(c.value) as any, c.format)}</strong></div>;
          case "progress": {
            const v = Number(val(c.value)), m = Number(val(c.max) ?? 100) || 100;
            const pct = Number.isFinite(v) ? Math.max(0, Math.min(100, (v / m) * 100)) : 0;
            return <div key={c.id} className="bar" title={label}><div style={{ width: pct + "%" }} /></div>;
          }
          case "alert": return <div key={c.id} className={`alert ${c.tone ?? "info"}`}>{interpolate(c.text ?? "", env)}</div>;
          case "list": {
            const items = Array.isArray(env[c.bind!]) ? (env[c.bind!] as any[]) : [];
            const fields = c.fields ?? (items[0] ? Object.keys(items[0]) : []);
            return (
              <div key={c.id} className="list"><small>{label}</small>
                {items.length === 0 && <em>Nothing here yet</em>}
                {items.map((it, i) => (
                  <div key={i} className="row">{fields.map((f) => <span key={f}>{fmt(it?.[f])}</span>)}
                    {c.removable && <button className="x" onClick={() => setState((s) => applyAction(spec, { type: "remove_item", target: c.bind!, amount: String(i) }, s))}>✕</button>}
                  </div>
                ))}
              </div>
            );
          }
          case "chart": return <Chart key={c.id} label={label} cfg={c.chart} env={env} />;
        }
      })}
      <button className="btn ghost" onClick={() => setState(defaultState(spec))}>Reset</button>
    </div>
  );
}

function Chart({ label, cfg, env }: { label: string; cfg: any; env: Env }) {
  if (!cfg) return null;
  const pts: { x: number; y: number }[] = [];
  for (let x = cfg.from; x <= cfg.to && pts.length < 500; x++) {
    try { const y = evaluate(cfg.y, { ...env, i: x }); if (typeof y === "number" && Number.isFinite(y)) pts.push({ x, y }); } catch { /* skip point */ }
  }
  if (pts.length < 2) return <div className="chart"><small>{label}</small><em>No data</em></div>;
  const ys = pts.map((p) => p.y), lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 1;
  const X = (x: number) => 10 + ((x - cfg.from) / (cfg.to - cfg.from || 1)) * 280;
  const Y = (y: number) => 90 - ((y - lo) / span) * 70;
  return (
    <div className="chart"><small>{label}</small>
      <svg viewBox="0 0 300 110">
        <polyline fill="none" stroke="currentColor" strokeWidth="2" points={pts.map((p) => `${X(p.x)},${Y(p.y)}`).join(" ")} />
        {pts.map((p) => <circle key={p.x} cx={X(p.x)} cy={Y(p.y)} r="2.5" fill="currentColor" />)}
        <text x="10" y="106" fontSize="9" fill="currentColor">{fmt(lo)} → {fmt(hi)}</text>
      </svg>
    </div>
  );
}
