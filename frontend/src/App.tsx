import { useState, useRef, useEffect } from "react";
import Runtime from "./Runtime";
import { post, stream } from "./api";
import { useStore, type Version } from "./store";

const AGENTS: [string, string, string][] = [
  ["orchestrator", "Orchestrator", "🎯"],
  ["product", "Product", "📋"],
  ["logic", "Logic", "⚙️"],
  ["ux", "UX", "🎨"],
  ["tests", "Test Author", "🧪"],
  ["integrator", "Integrator", "🧩"],
  ["critic", "Critic", "🔍"],
  ["verifier", "Verifier", "🛡️"],
];

const PRESETS = [
  { label: "Attendance Bunk Calculator", prompt: "Tell me if I can bunk tomorrow and still keep 75% attendance" },
  { label: "Trip Expense Splitter", prompt: "Split Goa trip expenses between friends and show balances" },
  { label: "Water Intake Tracker", prompt: "Water tracker with a daily goal in ml and quick add buttons" },
  { label: "Daily Habit Streaks", prompt: "Daily habit tracker with streak count, goal percentage, and reset" },
];

type AgentStatus = { s: "idle" | "running" | "done" | "skipped"; ms?: number };

export default function App() {
  const { versions, currentId, add, select, clear } = useStore();
  const current = versions.find((v) => v.id === currentId);

  const [prompt, setPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<Record<string, AgentStatus>>({});
  const [log, setLog] = useState<string[]>([]);
  const [plan, setPlan] = useState<any>(null);
  const [results, setResults] = useState<any[]>([]);
  const [criticIssues, setCriticIssues] = useState<any[]>([]);
  const [criticApproved, setCriticApproved] = useState<boolean | null>(null);
  const [sandboxTab, setSandboxTab] = useState<"preview" | "stream" | "spec">("preview");
  const [rightDrawerOpen, setRightDrawerOpen] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [soloData, setSoloData] = useState<any>(null);
  const [lastPrompt, setLastPrompt] = useState<string>("");

  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-select latest version from local history on load
  useEffect(() => {
    if (versions.length > 0) {
      const target = versions.find((v) => v.id === currentId) || versions[versions.length - 1];
      selectVersion(target);
    }
  }, []);

  const selectVersion = (v: Version) => {
    select(v.id);
    setLastPrompt(v.prompt || v.summary || "");
    setErrorMessage(null);
    if (v.plan) setPlan(v.plan);
    if (v.results) setResults(v.results);
    if (v.criticIssues) setCriticIssues(v.criticIssues);
    if (v.criticApproved !== undefined) setCriticApproved(v.criticApproved);
  };

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [log, busy, current]);

  const say = (msg: string) => setLog((prev) => [...prev.slice(-80), msg]);

  const eventHandler = (summary: string, userPrompt: string) => (e: any) => {
    switch (e.type) {
      case "route":
        setStatus((prev) => {
          const next: Record<string, AgentStatus> = { ...prev };
          next["orchestrator"] = { s: "done", ms: 300 };
          for (const a of e.agents || []) next[a] = { s: "idle" };
          for (const a of e.skipped || []) next[a] = { s: "skipped" };
          return next;
        });
        say(`route → ${e.agents?.join(", ")}`);
        break;

      case "agent_start":
        setStatus((prev) => ({ ...prev, [e.agent]: { s: "running" } }));
        break;

      case "agent_done":
        setStatus((prev) => ({ ...prev, [e.agent]: { s: "done", ms: e.ms } }));
        break;

      case "plan":
        setPlan(e);
        break;

      case "critic":
        setCriticApproved(e.approved);
        setCriticIssues(e.issues || []);
        say(e.approved ? "critic: approved spec" : `critic: found ${e.issues?.length} issue(s)`);
        break;

      case "tests":
        setResults(e.results || []);
        setStatus((prev) => ({ ...prev, verifier: { s: "done" } }));
        break;

      case "error":
        setErrorMessage(e.message || "An unexpected error occurred during synthesis.");
        say("✗ " + e.message);
        break;

      case "done":
        setErrorMessage(null);
        setResults(e.results || []);
        add(summary, e.spec, {
          prompt: userPrompt,
          plan: plan,
          results: e.results || [],
          criticIssues: criticIssues,
          criticApproved: criticApproved,
        });
        say(e.demo ? "demo mode: showing verified offline app" : "✓ mini-app ready");
        break;
    }
  };

  async function executeForge(query: string) {
    if (!query.trim() || busy) return;
    setBusy(true);
    setErrorMessage(null);
    setStatus({ orchestrator: { s: "running" } });
    setLog([]);
    setResults([]);
    setCriticIssues([]);
    setCriticApproved(null);
    setSoloData(null);
    setLastPrompt(query);
    setPrompt("");

    try {
      if (current) {
        // App exists: Orchestrator routes modification
        await stream("/api/modify", { prompt: query, spec: current.spec }, eventHandler(query.slice(0, 50), query));
      } else {
        // New app: Product -> Logic & UX -> Verifier
        await stream("/api/forge", { prompt: query }, eventHandler(query.slice(0, 50), query));
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Connection failed to backend server.");
      say("✗ " + err.message);
    } finally {
      setBusy(false);
    }
  }

  async function runSoloBenchmark() {
    const targetPrompt = lastPrompt || current?.summary || "Attendance tracker";
    setSoloData({ loading: true });
    try {
      const res = await post("/api/solo", { prompt: targetPrompt });
      setSoloData(res);
    } catch (err: any) {
      setSoloData({ ok: false, error: err.message });
    }
  }

  const passedTestsCount = results.filter((r) => r.pass).length;

  return (
    <div className="app-layout">
      {/* ========================================================
          LEFT SIDEBAR: Projects and Local Storage History
          ======================================================== */}
      <aside className="sidebar-left">
        <div className="sidebar-brand">
          <div className="brand-title">
            <div className="brand-icon">⚡</div>
            <span>AppForge Studio</span>
          </div>
        </div>

        {/* New App Button */}
        <button
          className="sidebar-new-btn"
          onClick={() => {
            select("");
            setLastPrompt("");
            setResults([]);
            setPlan(null);
            setLog([]);
            setStatus({});
          }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Create New App</span>
        </button>

        <div className="sidebar-section-title">PROJECTS HISTORY ({versions.length})</div>

        {/* Local History List */}
        <div className="version-list">
          {versions.length === 0 ? (
            <div style={{ fontSize: "12px", color: "var(--text-muted)", padding: "16px 4px", lineHeight: "1.5" }}>
              No apps created yet.<br />Click a starter option below or enter a prompt!
            </div>
          ) : (
            versions.map((v) => (
              <div
                key={v.id}
                className={`version-item ${v.id === currentId ? "active" : ""}`}
                onClick={() => selectVersion(v)}
              >
                <div className="version-item-icon">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                    <polyline points="14 2 14 8 20 8" />
                  </svg>
                </div>
                <div className="version-meta">
                  <div className="version-title">{v.spec.meta.name || v.summary}</div>
                  <div className="version-status">
                    <div className="status-dot" />
                    <span>Saved in Local · {v.id.toUpperCase()}</span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {versions.length > 0 && (
          <div className="sidebar-footer">
            <button className="btn-clear-history" onClick={clear}>
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
              <span>Clear local history</span>
            </button>
          </div>
        )}
      </aside>

      {/* ========================================================
          CENTER STAGE: AI Researcher & Lovable Sandbox
          ======================================================== */}
      <main className="main-center">
        {/* Top Navbar */}
        <header className="top-navbar">
          <div className="top-navbar-title">
            <div className="ai-badge-icon">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
            </div>
            <span>AI AppForge Swarm</span>
          </div>

          <div className="top-navbar-actions">
            <button className="btn-toggle-sources" onClick={() => setRightDrawerOpen((prev) => !prev)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </svg>
              <span>{rightDrawerOpen ? "Hide Brain" : "Show Brain"}</span>
            </button>
          </div>
        </header>

        {/* Scrollable Workspace */}
        <div className="workspace-scroll" ref={scrollRef}>
          {/* User Prompt Message */}
          {lastPrompt && (
            <div className="message-user">
              <span className="message-author">You</span>
              <div className="message-user-bubble">{lastPrompt}</div>
            </div>
          )}

          {/* AI Swarm Response & Pipeline Card */}
          {(current || busy || log.length > 0) && (
            <div className="message-agent">
              <div className="agent-header-row">
                <span className="message-author">AI AppForge Swarm</span>
                {busy && (
                  <span style={{ fontSize: "12px", color: "var(--primary)", fontWeight: 600 }}>
                    ⚡ Orchestrating Swarm Agents...
                  </span>
                )}
              </div>

              <div className="agent-title">App Synthesis & Pipeline</div>
              <p className="agent-narrative">
                {current
                  ? `Application "${current.spec.meta.name}" constructed through multi-agent contract negotiation, verified by deterministic AST rules.`
                  : "The multi-agent swarm is negotiating the state contract and running invariant checks."}
              </p>

              {/* ========================================================
                  VISUAL ORCHESTRATOR PIPELINE DIAGRAM
                  ======================================================== */}
              <div className="orchestrator-pipeline-container">
                <div className="pipeline-header">
                  <span className="pipeline-title">
                    <span>⚡</span> Orchestrator Pipeline Flow
                  </span>
                  <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>
                    {busy ? "Active Step Executing" : "Pipeline Completed"}
                  </span>
                </div>

                <div className="pipeline-flow">
                  {AGENTS.map(([id, label, icon], index) => {
                    const s = status[id];
                    return (
                      <div key={id} style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <div className={`pipeline-node ${s?.s || "idle"}`}>
                          <div className="node-icon">{icon}</div>
                          <div className="node-label">{label}</div>
                          <div className="node-time">
                            {s?.s === "done" ? (s.ms ? `${(s.ms / 1000).toFixed(1)}s` : "✓ Done") : s?.s === "running" ? "Running..." : s?.s === "skipped" ? "Skipped" : "Ready"}
                          </div>
                        </div>
                        {index < AGENTS.length - 1 && <span className="pipeline-arrow">→</span>}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Error Notice Banner */}
              {errorMessage && (
                <div style={{
                  background: "#fef2f2",
                  border: "1px solid #f87171",
                  color: "#991b1b",
                  padding: "12px 16px",
                  borderRadius: "10px",
                  marginBottom: "16px",
                  fontSize: "13px",
                  display: "flex",
                  alignItems: "center",
                  gap: "10px",
                  boxShadow: "0 2px 4px rgba(239, 68, 68, 0.08)"
                }}>
                  <span style={{ fontSize: "18px" }}>⚠️</span>
                  <div>
                    <div style={{ fontWeight: 600 }}>Swarm Execution Notice</div>
                    <div style={{ fontSize: "12px", color: "#b91c1c", marginTop: "2px" }}>{errorMessage}</div>
                  </div>
                </div>
              )}

              {/* Interactive Sandbox Container */}
              <div className="sandbox-card">
                <div className="sandbox-toolbar">
                  <div className="sandbox-tabs">
                    <button
                      className={`tab-btn ${sandboxTab === "preview" ? "active" : ""}`}
                      onClick={() => setSandboxTab("preview")}
                    >
                      🎮 Interactive Sandbox
                    </button>
                    <button
                      className={`tab-btn ${sandboxTab === "stream" ? "active" : ""}`}
                      onClick={() => setSandboxTab("stream")}
                    >
                      ⚡ Swarm Logs ({log.length})
                    </button>
                    <button
                      className={`tab-btn ${sandboxTab === "spec" ? "active" : ""}`}
                      onClick={() => setSandboxTab("spec")}
                    >
                      📋 Spec JSON
                    </button>
                  </div>
                </div>

                <div className="sandbox-viewport">
                  {sandboxTab === "preview" && (
                    current ? (
                      <Runtime key={current.id} spec={current.spec} />
                    ) : (
                      <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "40px 20px" }}>
                        {busy ? "Swarm agents are assembling your sandbox components..." : "Your live mini-app will appear here."}
                      </div>
                    )
                  )}

                  {sandboxTab === "stream" && (
                    <pre style={{ fontSize: "12px", fontFamily: "'JetBrains Mono', monospace", color: "var(--text-secondary)", whiteSpace: "pre-wrap", maxHeight: "360px", overflowY: "auto" }}>
                      {log.join("\n") || "No streaming events yet."}
                    </pre>
                  )}

                  {sandboxTab === "spec" && (
                    <pre style={{ fontSize: "11.5px", fontFamily: "'JetBrains Mono', monospace", color: "#334155", background: "#f8fafc", padding: "12px", borderRadius: "8px", maxHeight: "360px", overflowY: "auto" }}>
                      {current ? JSON.stringify(current.spec, null, 2) : "—"}
                    </pre>
                  )}
                </div>
              </div>

              {/* Source verification pills at the bottom */}
              <div className="source-pills-row">
                <span className="source-pill">⚡ Auto mode</span>
                {criticApproved !== null && (
                  <span className="source-pill" style={{ color: criticApproved ? "var(--success)" : "var(--warning)" }}>
                    {criticApproved ? "✓ Critic approved" : `⚠ Critic: ${criticIssues.length} issue(s)`}
                  </span>
                )}
                {results.length > 0 && (
                  <span className="source-pill" style={{ color: "var(--success)" }}>
                    🛡 {passedTestsCount}/{results.length} checks verified
                  </span>
                )}
                <span className="source-pill">Groq Llama 3.3</span>
              </div>
            </div>
          )}
        </div>

        {/* ========================================================
            BOTTOM DOCKED INPUT BAR WITH PRESET OPTIONS (IMAGE 2)
            ======================================================== */}
        <div className="docked-input-container">
          <div className="docked-input-inner">
            {/* Preset Options shown near the bottom writing part (matching user's 2nd image) */}
            <div className="bottom-preset-chips">
              {PRESETS.map((p) => (
                <button
                  key={p.label}
                  className="preset-chip-btn"
                  disabled={busy}
                  onClick={() => executeForge(p.prompt)}
                >
                  <span>•</span>
                  <span>{p.label}</span>
                </button>
              ))}
            </div>

            <div className="input-box-wrapper">
              <input
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && executeForge(prompt)}
                placeholder={current ? "Ask AppForge to change something in this app..." : "Ask AppForge to build any small mini-app..."}
                disabled={busy}
              />
              <button
                className={`btn-send ${prompt.trim() && !busy ? "active" : ""}`}
                disabled={!prompt.trim() || busy}
                onClick={() => executeForge(prompt)}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <line x1="12" y1="19" x2="12" y2="5" />
                  <polyline points="5 12 12 5 19 12" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </main>

      {/* ========================================================
          RIGHT DRAWER: Sources & Swarm Brain
          ======================================================== */}
      <aside className={`sidebar-right ${rightDrawerOpen ? "" : "collapsed"}`}>
        <div className="drawer-header">
          <span className="drawer-title">Sources & Swarm Brain</span>
          <button className="btn-close-drawer" onClick={() => setRightDrawerOpen(false)}>
            ✕
          </button>
        </div>

        <div className="drawer-content">
          <div className="sidebar-section-title">DOCUMENTS & ARTIFACTS</div>

          {/* Card 1: Product Contract */}
          <div className="source-card">
            <div className="source-card-header">
              <span className="source-badge">[1] Product_Contract.json</span>
              <span className="source-tag">Contract</span>
            </div>
            {plan ? (
              <div className="source-snippet">
                {`Problem: ${plan.plan.problem}\nPrimary Q: ${plan.plan.primary_question}\nFeatures: ${plan.plan.features.join(", ")}\n\nState Inputs:\n${plan.contract.state.map((s: any) => `• ${s.id} (${s.type}, default: ${s.default})`).join("\n")}`}
              </div>
            ) : (
              <div style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                Contract appears after a build begins.
              </div>
            )}
          </div>

          {/* Card 2: Verification Suite */}
          <div className="source-card">
            <div className="source-card-header">
              <span className="source-badge">[2] Verification_Suite.spec</span>
              <span className="source-tag">Verifier</span>
            </div>
            {results.length > 0 ? (
              <div className="source-snippet">
                {results.map((r) => `${r.pass ? "✓" : "✗"} [${r.layer}] ${r.name}${r.detail ? ` (${r.detail})` : ""}`).join("\n")}
              </div>
            ) : (
              <div style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                Invariants, unit tests, and fuzzing run automatically.
              </div>
            )}
          </div>

          {/* Card 3: Critic Review */}
          <div className="source-card">
            <div className="source-card-header">
              <span className="source-badge">[3] Critic_Review_Audit.log</span>
              <span className="source-tag">QA</span>
            </div>
            {criticIssues.length > 0 ? (
              <div className="source-snippet">
                {criticIssues.map((issue) => `[${issue.severity.toUpperCase()}] ${issue.agent}: ${issue.problem}`).join("\n\n")}
              </div>
            ) : (
              <div style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                {criticApproved ? "✓ All safety and edge-case checks approved." : "Critic reviews all integrated drafts."}
              </div>
            )}
          </div>

          {/* Card 4: Solo vs Swarm Benchmark */}
          <div className="source-card">
            <div className="source-card-header">
              <span className="source-badge">[4] Solo_vs_Swarm.benchmark</span>
              <span className="source-tag">Comparison</span>
            </div>
            {soloData ? (
              soloData.loading ? (
                <div style={{ fontSize: "11.5px", color: "var(--primary)" }}>Running 1-shot baseline...</div>
              ) : soloData.ok ? (
                <div className="source-snippet">
                  {`Solo Baseline:\n• Passed: ${soloData.passed}/${soloData.total}\n• Issues: ${soloData.issues?.length || 0}\n• Calls: 1 (Monolithic)\n• Time: ${soloData.ms}ms`}
                </div>
              ) : (
                <div style={{ fontSize: "11.5px", color: "var(--danger)" }}>Error: {soloData.error}</div>
              )
            ) : (
              <div style={{ fontSize: "11.5px", color: "var(--text-muted)" }}>
                Click below to benchmark 1-shot vs Swarm:
                <button
                  className="preset-chip-btn"
                  onClick={runSoloBenchmark}
                  style={{ marginTop: "8px", width: "100%", justifyContent: "center" }}
                >
                  ⚖ Run Solo Benchmark
                </button>
              </div>
            )}
          </div>
        </div>
      </aside>
    </div>
  );
}
