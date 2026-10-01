# APPFORGE SWARM v2

One sentence → AI team → validated spec → deterministic checks → working mini-app.
The LLM never writes code. It emits JSON that is Zod-validated and interpreted by a small runtime.

## Run
```bash
npm install
cp .env.example .env     # add GROQ_API_KEY (free at console.groq.com). Without it: demo mode.
npm run dev              # web http://localhost:5173, server :8787
npm test                 # runtime + verifier self-test (no API key needed)
```

## Architecture
```
Intent router (code) ─► PRODUCT ─► CONTRACT (shared ids)
                          ├─► LOGIC ──┐
                          ├─► UX ─────┼─► INTEGRATOR (code) ─► validator ─► CRITIC (max 2 rounds, HIGH blocks)
                          └─► TEST AUTHOR (blind to Logic) ─┘                     │
                                                          verifier: invariants + example tests + fuzz
                                                          failure → routed to Logic/UX (max 2 rounds, 12-call budget)
                                                                              ▼
                                                                  React runtime renders the AppSpec
```
Modifications: the **Orchestrator** picks Logic and/or UX; they rewrite only their sections, old tests are replayed, existing state ids are never dropped, and each change adds a node to the version **tree**.

| Package | What it is |
|---|---|
| `packages/app-spec` | Zod schema, safe formula parser/evaluator, verifier, action engine, demo spec. Shared by server and web |
| `apps/server` | Fastify + Groq. Agents, pipeline, concurrency queue, 429 backoff, SSE streaming, `/api/solo` baseline |
| `apps/web` | React/Vite UI: Swarm · Preview · Brain, version tree, Solo vs Swarm comparison |

## Safety model
Specs can only use the runtime's vocabulary: 14 components, 9 action types, allowlisted formula functions. Formulas go through a custom parser (no `eval`), capped at 10,000 operations and 400 chars. Ids are `^[a-z][a-z0-9_]{0,31}$`, lists are capped at 200 items, specs at 100 KB, and all text is rendered as text, never HTML.

## Honest limits
"Checks passed" means *consistent*, not *correct*: a quiz with wrong answers can still pass. Not built yet: timers, tabs, `settle()`, React Flow swarm graph, Framer Motion, per-session throttling. Good next steps.
"# kgceminipitch" 
