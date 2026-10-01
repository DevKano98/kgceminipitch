# 🚀 AppForge Swarm

> **A collaborative Multi-Agent AI system that builds interactive, bug-free mini-applications from natural language prompts.**

Unlike typical AI code generators that output raw, hallucination-prone React/JavaScript files, **AppForge never asks the LLM to write executable code**. Instead, a coordinated swarm of specialized AI agents designs a **declarative application specification (`AppSpec`)** in structured JSON. The browser then interprets this specification using an in-memory, sandboxed AST engine with **zero arbitrary code execution (`no eval`)**.

---

## 📑 Table of Contents

- [The Big Picture](#-the-big-picture)
- [How It Works: Step-by-Step](#-how-it-works-step-by-step)
- [The Agent Swarm (Separation of Concerns)](#-the-agent-swarm-separation-of-concerns)
- [Project Architecture & Directory Structure](#-project-architecture--directory-structure)
- [Quickstart: Running Locally](#-quickstart-running-locally)
- [Core Concepts for Students](#-core-concepts-for-students)
- [Testing & Quality Verification](#-testing--quality-verification)
- [Student Challenges & Extensions](#-student-challenges--extensions)

---

## 🌟 The Big Picture

### Why Not Just Ask an LLM to Write React Code?
1. **Hallucination & Breakages**: Large models frequently hallucinate missing imports, mismatched state hooks, or invalid syntax.
2. **Security Vulnerabilities**: Executing LLM-generated JavaScript (`eval()` or `<script>`) inside a browser creates severe XSS and arbitrary code execution vulnerabilities.
3. **Hard to Mathematically Verify**: Proving that arbitrary JavaScript code handles division-by-zero, bounds checking, or invalid inputs requires running full headless browser sandboxes.

### The AppForge Solution: Declarative DSL + In-Memory Sandbox
AppForge uses a **Domain-Specific Language (DSL)**. The AI agents only emit a validated JSON schema containing:
* **`state`**: Variables stored in browser memory (numbers, text, booleans, lists).
* **`computed`**: Pure mathematical formulas evaluated reactively.
* **`rules`**: Validation constraints that flag invalid user inputs.
* **`actions`**: Deterministic state transitions (`set`, `increment`, `add_item`, `remove_item`, `toggle`, `reset`).
* **`components`**: Pre-built UI widgets (`heading`, `text_input`, `button`, `metric`, `list`, `slider`, `alert`).

The browser renders these components natively and evaluates formulas using a custom, safe **Pratt Parser** (`formula.ts`) — completely isolated from the DOM and system APIs.

---

## 🔄 How It Works: Step-by-Step

```
User Prompt: "Create a Todo App with add, complete, and delete"
                             │
                             ▼
                 ┌───────────────────────┐
                 │     Product Agent     │ ◄── Defines the Contract (IDs & Goals)
                 └───────────┬───────────┘
                             │
            ┌────────────────┴────────────────┐
            ▼                                 ▼
┌───────────────────────┐         ┌───────────────────────┐
│      Logic Agent      │         │       UX Agent        │
│ (Formulas & Actions)  │         │ (Layout & Components) │
└───────────┬───────────┘         └───────────┬───────────┘
            │                                 │
            │   ┌─────────────────────────┐   │
            └──►│   Test Author Agent     │◄──┘
                │ (Independent Unit Tests)│
                └───────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │  Deterministic Integrator │ ◄── Pure Python Code (No LLM!)
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │       Critic Agent        │ ◄── Reviews Edge Cases & Bugs
              └─────────────┬─────────────┘
                            │
                            ▼
              ┌───────────────────────────┐
              │   Deterministic Verifier  │ ◄── Executes Invariant & Fuzz Checks
              └─────────────┬─────────────┘
                            │ (Passes All Checks)
                            ▼
           Client Streamed via Server-Sent Events (SSE)
                            │
                            ▼
              ┌───────────────────────────┐
              │   Browser React Runtime   │ ◄── Interprets AppSpec (No eval!)
              └───────────────────────────┘
```

---

## 👥 The Agent Swarm (Separation of Concerns)

Instead of a single "mega-prompt", AppForge uses a swarm of specialized agents behaving like a professional software engineering team:

| Agent | Real-World Role | What It Does |
|---|---|---|
| **Product Agent** | Product Manager | Analyzes the user's intent, identifies core features, and establishes a strict **Contract** (agreed IDs for state, outputs, and actions). |
| **Logic Agent** | Backend Developer | Writes math formulas for computed values, defines validation rules, and designs state-changing actions. Never touches CSS or UI. |
| **UX Agent** | Frontend Designer | Organizes UI components (`heading`, `list`, `button`, `metric`) bound strictly to the IDs agreed upon in the Product Contract. |
| **Test Author** | QA Engineer | Writes independent unit tests (`inputs` and expected `outputs`). Runs with list schema awareness without seeing the formulas to prevent confirmation bias. |
| **Deterministic Integrator** | Software Architect | **Pure deterministic code (Not an LLM!)**. Merges the outputs of Product, Logic, UX, and Tests into a single unified `AppSpec`. |
| **Critic Agent** | Senior Code Reviewer | Audits the draft for flaws (e.g., division by zero, unbounded sliders, missing fields). High-severity flaws trigger a targeted revision loop. |
| **Verifier** | Automated CI/CD Engine | Executes 3 tiers of automated tests: Mathematical Invariants, Unit Tests, and 100 random Fuzzing permutations. |
| **Orchestrator** | Tech Lead (Router) | When modifying an existing app, routes work *only* to the agents that need to change (e.g., UI only vs Logic only), conserving API budget. |

---

## 📂 Project Architecture & Directory Structure

```text
appforge/
├── backend/                   # FastAPI Backend (Python)
│   ├── main.py                # REST & SSE streaming endpoints (/api/forge, /api/modify)
│   ├── config.py              # Environment variables & LLM concurrency limits
│   ├── llm.py                 # Async Groq client with exponential backoff & rate-limit handling
│   ├── pipeline.py            # Orchestrator & agent execution coordinator
│   ├── verifier.py            # Safe AST formula evaluator & 3-tier check runner
│   ├── models/spec.py         # Pydantic v2 schemas for AppSpec, Action, Component, etc.
│   └── agents/                # Individual agent prompt definitions
│       ├── base.py            # Shared runtime vocabulary (GUIDE)
│       ├── product.py         # Product planning agent
│       ├── logic.py           # Formulas and state transition logic
│       ├── ux.py              # User interface design agent
│       ├── tests.py           # Independent test generator
│       ├── critic.py          # Quality and edge-case auditor
│       ├── orchestrator.py    # Modification routing agent
│       └── solo.py            # Monolithic baseline agent (for benchmarking)
│
├── frontend/                  # React + Vite (TypeScript)
│   ├── src/
│   │   ├── App.tsx            # Main UI, agent activity badges, timeline, prompt bar
│   │   ├── Runtime.tsx        # In-browser declarative spec renderer (reactive React state)
│   │   ├── store.ts           # Zustand store with persistent browser history (localStorage)
│   │   └── api.ts             # Server-Sent Events (SSE) stream listener
│   └── vite.config.ts         # Vite configuration with proxy to FastAPI backend
│
└── packages/app-spec/         # Shared TypeScript Spec & Runtime Package
    ├── src/
    │   ├── formula.ts         # Hand-written Pratt parser & safe AST evaluator (Zero eval!)
    │   ├── runtime.ts         # Action execution engine (`applyAction`) & text interpolation
    │   ├── schema.ts          # Zod validation schemas matching the backend models
    │   ├── verify.ts          # Client-side verification utilities
    │   └── selftest.ts        # Unit test suite verifying runtime safety & parsing
```

---

## ⚡ Quickstart: Running Locally

### 1. Prerequisites
* **Node.js** (v18 or higher)
* **Python** (v3.10 or higher)
* A free **Groq API Key** (from [console.groq.com](https://console.groq.com))

### 2. Installation
Clone the repository and install dependencies:
```bash
# Clone the repository
git clone https://github.com/DevKano98/kgceminipitch.git
cd kgceminipitch

# Install Node workspace dependencies
npm install

# Install Python backend dependencies
cd backend
pip install -r requirements.txt
cd ..
```

### 3. Setup Environment Variables
Copy the example environment configuration:
```bash
cp .env.example .env
```
Open `.env` and paste your Groq API key:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
LLM_CONCURRENCY=2
PORT=8787
```
*(Note: If you run without an API key, the system defaults to offline demo mode using a cached attendance calculator).*

### 4. Start the Application
Run both frontend and backend concurrently with a single command:
```bash
npm run dev
```

Open your browser at:
* **Frontend**: [http://localhost:5173](http://localhost:5173)
* **Backend API Docs**: [http://localhost:8787/docs](http://localhost:8787/docs)

---

## 🧠 Core Concepts for Students

### 1. Zero `eval()` Pratt Parsing
In `packages/app-spec/src/formula.ts`, mathematical formulas like `clamp(attended / conducted * 100, 0, 100)` are tokenized and parsed into an Abstract Syntax Tree (AST). The evaluator only understands an allowlisted set of operations (`+`, `-`, `*`, `/`, `min`, `max`, `sumOf`, `len`). JavaScript keywords like `window`, `document`, `fetch`, or `__proto__` are immediately rejected.

### 2. Deterministic Code Integration
Large Language Models struggle with copying large JSON structures accurately. Instead of asking another LLM to merge agent outputs, the `integrate()` function in `backend/pipeline.py` is written in standard Python:
```python
def integrate(contract: Contract, logic: LogicOut, ux: UxOut, tests: list) -> AppSpec:
    # Deterministic code stitches the contract, logic formulas, UI components, and tests
    ...
```
This guarantees that IDs are never lost, renamed, or accidentally dropped during assembly.

### 3. Hard Budget Enforcement
To prevent runaway billing or infinite refinement loops, the `CallTracker` in `backend/pipeline.py` enforces a strict ceiling of **12 LLM calls per build**.

---

## 🧪 Testing & Quality Verification

You can verify the runtime, parser, and verification engine anytime without consuming LLM API credits:

```bash
# Run the 22-test TypeScript safety & parser suite
npm test

# Run the TypeScript type checker across all packages
npm run typecheck
```

---

## 🚀 Student Challenges & Extensions

If you are using this project to learn agentic architectures, here are great hands-on features to build:

1. **Add a New Component**: Extend `packages/app-spec/src/schema.ts` and `frontend/src/Runtime.tsx` to support a `toggle_switch` or `color_picker` component.
2. **Add a Timer Action**: Create a new action type `set_interval` so applications can implement countdown timers or stopwatches.
3. **Multi-Model Support**: Update `backend/llm.py` to allow users to switch between Groq, OpenAI, Anthropic, or local Ollama models.
4. **Visual Swarm Graph**: Use React Flow to render a live animated graph showing tokens flowing between agents in real time.

---

## 📄 License
MIT License. Built for learning, experimentation, and teaching modern multi-agent systems.
