# Autonomous Multi-Agent Research Analyst

A portfolio project demonstrating **LangChain Deep Agents** in a real, non-trivial application.  
Given a research topic, the system spawns multiple specialist AI subagents in parallel, gathers insights, fact-checks claims, and synthesises everything into a structured research report — all with Human-in-the-Loop control, real-time streaming, long-term memory, and a full audit log.

---

## What Makes This Interesting

This is **not** a chatbot. It is a fully orchestrated multi-agent pipeline where:

- The **Orchestrator** coordinates the entire workflow
- Three **specialist Subagents** run concurrently (Web Searcher, Insight Extractor, Fact Checker)
- The user **approves the plan** before any expensive LLM calls happen
- Responses **stream token-by-token** to the terminal in real time
- Prior research is **recalled from memory** and injected into new runs
- Every session is **saved to disk** as a timestamped JSON audit log
- Shared helper functions (**Skills**) are reused across agents

---

## Features

| # | Feature | What it demonstrates |
|---|---------|---------------------|
| 1 | Orchestrator + Parallel Subagents | Multi-agent coordination with `ThreadPoolExecutor` |
| 2 | Human-in-the-Loop (HITL) | Approval gate before any subagent cost is incurred |
| 3 | Streaming | Token-by-token output via `agent.stream()` |
| 4 | Long-Term Memory | JSON store with exact + fuzzy recall across runs |
| 5 | Filesystem Backend | Per-session JSON audit log in `sessions/` |
| 6 | Skills | Reusable tools (`format_citation`, `summarize`) shared across agents |

---

## Project Structure

```
research_analyst/
│
├── orchestrator.py          # Main entry point — wires all features together
├── streaming.py             # stream_agent() utility for token-by-token output
├── requirements.txt
├── demo.ipynb               # Full walkthrough notebook
│
├── subagents/
│   ├── web_searcher.py      # Fetches sources, formats citations
│   ├── insight_extractor.py # Pulls out breakthroughs, trends, key players
│   └── fact_checker.py      # Rates each claim HIGH / MEDIUM / LOW
│
├── memory/
│   ├── memory.py            # remember(), recall(), recall_related()
│   └── store.json           # Persistent knowledge store (auto-created)
│
├── backend/
│   └── filesystem.py        # save_session(), list_sessions(), load_session()
│
├── skills/
│   ├── citation_formatter.py  # format_citation() — APA, MLA, plain
│   └── summarizer.py          # summarize() — sentence-ranked compression
│
└── sessions/                # Auto-created — one JSON file per run
```

---

## Setup

### 1. Clone / open the project

```bash
cd "E:\Projects\exploring_ai\Deep Agent\research_analyst"
```

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
.\.venv\Scripts\activate        # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `deepagents` pulls in `langchain-anthropic` as a hard dependency even when using Groq. This is normal and expected.

### 4. Set your API key

Create a `.env` file in the **parent folder** (`Deep Agent/.env`):

```
GROQ_API_KEY=your_groq_key_here
```

Get a free key at [console.groq.com](https://console.groq.com).

---

## Running

### Standard run (interactive approval)

```bash
python orchestrator.py "Quantum Computing"
```

You will be shown a research plan and asked to approve, cancel, or redirect before any subagents are spawned.

### Auto-approve (non-interactive)

```bash
python orchestrator.py "Artificial Intelligence" --yes
```

### View session history

```bash
python orchestrator.py --history
python orchestrator.py --history "Quantum Computing"   # filter by topic
```

---

## Pipeline Flow

```
Input topic
    │
    ▼
[MEMORY CHECK]
  Exact recall + fuzzy keyword search across prior runs
    │
    ▼
[HITL GATE]  ← streaming pre-scan shows research plan
  y → proceed    n → cancel    r → redirect to new topic
    │
    ▼
[Web Searcher]  (sequential — output feeds the next two)
  Tools: web_search, format_citation (skill)
    │
    ├──────────────────────┐
    ▼                      ▼
[Insight Extractor]  [Fact Checker]   ← run in PARALLEL
  Tool: identify_themes    Tool: extract_claims
    │                      │
    └──────────┬───────────┘
               ▼
[Orchestrator]  ← memory context injected here
  Synthesises all outputs into a structured report (streaming)
               │
    ┌──────────┴──────────┐
    ▼                     ▼
[MEMORY UPDATE]    [BACKEND SAVE]
  store.json         sessions/<id>.json
```

---

## Output Structure

The final report follows this format:

```
## Executive Summary
## Key Findings
## Core Insights
## Reliability Assessment
## Next Steps
```

---

## Model

All agents use `groq:llama-3.3-70b-versatile` by default.

> **Free-tier note:** Groq's free tier has a 100,000 token/day limit on this model.  
> If you hit it, either wait for the daily reset or upgrade at `console.groq.com/settings/billing`.

To switch models, change the `model=` string in each subagent file and `orchestrator.py`.

---

## Tech Stack

| Library | Role |
|---------|------|
| `deepagents` | Deep Agent framework (LangChain-based) |
| `langchain-groq` | Groq LLM backend |
| `langgraph` | Agent graph execution (used internally by deepagents) |
| `python-dotenv` | Environment variable loading |
