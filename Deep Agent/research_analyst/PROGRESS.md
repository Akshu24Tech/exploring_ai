# Project Progress & Technical Deep-Dive

## Autonomous Multi-Agent Research Analyst

---

## What This Project Is

A fully working **LangChain Deep Agent** application that demonstrates every major concept in the deep agents framework — in a single, coherent, portfolio-grade project.

**Core idea:** Give it a research topic. It spins up multiple AI subagents that work in parallel, gathers web findings, extracts insights, fact-checks claims, and delivers a structured research report — with Human-in-the-Loop control, live streaming, memory that persists across runs, a filesystem audit log, and shared reusable skills.

This is built to show:
- You understand how to **architect** a multi-agent system, not just call an API
- You know how to handle **real-world constraints** (rate limits, token budgets, Windows encoding)
- You can apply **every major deep agent pattern** in one coherent project

---

## Deep Agent Concepts Covered

| Concept | Where It Lives | What It Does |
|---------|---------------|--------------|
| `create_deep_agent()` | All agent files | Core framework call — wraps an LLM + tools into an agent graph |
| Orchestrator pattern | `orchestrator.py` | Coordinates all subagents; no tools of its own — pure synthesis |
| Parallel subagents | `orchestrator.py:run_subagents()` | `ThreadPoolExecutor(max_workers=2)` runs Insight Extractor + Fact Checker simultaneously |
| Human-in-the-Loop | `orchestrator.py:hitl_gate()` | Shows a streaming plan preview; blocks until user approves/cancels/redirects |
| Streaming | `streaming.py:stream_agent()` | Hooks into `agent.stream()` with `stream_mode="messages"` for token-by-token output |
| Long-Term Memory | `memory/memory.py` | JSON-backed store; exact + fuzzy recall; injected into synthesis prompt |
| Filesystem Backend | `backend/filesystem.py` | Timestamped JSON audit log, one file per run, separate from memory |
| Skills (shared tools) | `skills/` | `format_citation`, `summarize` — defined once, callable by any agent |

---

## What Was Built — Feature by Feature

### Feature 1: Orchestrator + Parallel Subagents

**The core architecture.** The Orchestrator does not do research itself — it delegates.

Three specialist subagents:

- **Web Searcher** — given a topic, calls `web_search` (simulated) + `format_citation` (skill) to return sourced findings
- **Insight Extractor** — calls `identify_themes` to scan content type, then returns structured analysis under four headings: Key Breakthroughs, Major Trends, Key Players, Open Problems
- **Fact Checker** — calls `extract_claims` to isolate verifiable statements, then rates each claim HIGH / MEDIUM / LOW confidence

**Parallel execution:**

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    futures = {
        pool.submit(insight_extractor.run, raw_truncated): "insight_extractor",
        pool.submit(fact_checker.run, raw_truncated):       "fact_checker",
    }
    for future in as_completed(futures):
        results[futures[future]] = future.result()
```

Web Searcher runs first (its output feeds both parallel agents). Insight Extractor and Fact Checker then run concurrently, cutting wall-clock time roughly in half.

Raw content is truncated to ~800 words before the parallel stage to stay within free-tier token limits.

---

### Feature 2: Human-in-the-Loop (HITL)

**No subagents spawn until the user approves.**

A cheap pre-scan agent (no tools) generates a research plan preview — streaming it to the terminal. The user sees:

```
TOPIC INTERPRETATION: ...
SUBAGENTS TO SPAWN: Web Searcher, Insight Extractor, Fact Checker
KEY QUESTIONS:
  - question 1
  - question 2
  - question 3
ESTIMATED SCOPE: Broad
```

Then a gate appears:

```
[y] Approve and run    [n] Cancel    [r] Redirect to new topic
```

- `y` → continue with original or redirected topic
- `n` → pipeline exits, zero subagent cost incurred
- `r` → user types a new topic; pipeline restarts from HITL with the new topic

`--yes` flag skips this gate for non-interactive / scripted runs.

---

### Feature 3: Streaming

**Every LLM response prints token-by-token in real time** instead of appearing all at once after a long wait.

`stream_agent()` in `streaming.py` is a drop-in replacement for `agent.invoke()`:

```python
for chunk in agent.stream(
    {"messages": [{"role": "user", "content": prompt}]},
    stream_mode="messages",
    subgraphs=True,
    version="v2",
):
    if chunk.get("type") == "messages":
        token, metadata = chunk["data"]
        content = token.content if isinstance(token.content, str) else ""
        if content:
            print(content, end="", flush=True)
            full_text += content
```

Used for both the HITL pre-scan and the final report. Makes long responses feel immediate.

---

### Feature 4: Long-Term Memory

**The system remembers what it already knows about a topic across separate runs.**

Storage: `memory/store.json` — a flat JSON dict keyed by normalised topic name.

Each entry:
```json
{
  "artificial intelligence": {
    "topic": "Artificial Intelligence",
    "summary": "Compressed findings from prior runs...",
    "research_count": 3,
    "last_updated": "2026-06-10T14:30:00",
    "keywords": ["neural", "transformer", "openai", "benchmark", ...]
  }
}
```

Two recall modes:

- **Exact match** — `memory.recall("Artificial Intelligence")` — precise lookup
- **Fuzzy / related** — `memory.recall_related("AI Safety")` — keyword overlap scoring, returns up to 2 adjacent entries

Prior knowledge is injected into the Orchestrator's synthesis prompt:

```
=== PRIOR KNOWLEDGE FROM MEMORY ===
[PRIOR KNOWLEDGE — 'Artificial Intelligence' (researched 2x, last: ...)]
<compressed summary of prior runs>
```

The Orchestrator is instructed to reference prior knowledge and highlight what is **new** compared to what was already known.

After every run, `memory.remember(topic, report)` saves a compressed summary back to the store, merging with any existing entry.

---

### Feature 5: Filesystem Backend

**Every run is saved as a complete, self-contained JSON audit log.**

Separate from memory:
- `memory/` = compressed knowledge that accumulates
- `sessions/` = raw, full-detail record of each individual run

Session file: `sessions/<topic-slug>_<YYYYMMDD_HHMMSS>.json`

```json
{
  "id": "artificial-intelligence_20260610_143022",
  "topic": "Artificial Intelligence",
  "timestamp": "2026-06-10T14:30:22",
  "subagents": {
    "web_searcher": "...",
    "insight_extractor": "...",
    "fact_checker": "..."
  },
  "report": "## Executive Summary\n..."
}
```

CLI access:
```bash
python orchestrator.py --history                         # all sessions
python orchestrator.py --history "Artificial Intelligence"  # filtered
```

---

### Feature 6: Skills

**Shared helper functions that any agent can call as a tool.**

Why skills instead of inline code:
- The same logic (e.g. citation formatting) may be needed by multiple agents
- Define once, import anywhere — consistent output, no duplication

Two skills implemented:

**`skills/citation_formatter.py`**
```python
format_citation(title, url, author, year, style="apa") -> str
```
Formats a web source into APA, MLA, or plain-text citation. Used by Web Searcher.

**`skills/summarizer.py`**
```python
summarize(text, max_sentences=5, focus="") -> str
```
Sentence-ranked compression. Scores sentences by length and optional focus keyword, keeps the top N. Used for pre-processing raw content.

---

## Full System Flowchart

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESEARCH ANALYST PIPELINE                    │
└─────────────────────────────────────────────────────────────────┘

  User Input: "Artificial Intelligence"
        │
        ▼
┌──────────────────┐
│  MEMORY CHECK    │  recall("Artificial Intelligence")
│                  │  recall_related("AI", "machine learning")
│  memory.py       │
└────────┬─────────┘
         │  prior knowledge found? → inject into context block
         │  nothing found? → "starting fresh"
         ▼
┌──────────────────────────────────────────────────────┐
│  HUMAN-IN-THE-LOOP GATE           streaming.py       │
│                                                      │
│  Pre-scan agent (no tools, cheap)                    │
│  Streams research plan preview to terminal           │
│                                                      │
│  TOPIC INTERPRETATION: ...                           │
│  KEY QUESTIONS:                                      │
│    - What are the latest breakthroughs?              │
│    - Who are the key players?                        │
│    - What problems remain unsolved?                  │
│  ESTIMATED SCOPE: Broad                              │
│                                                      │
│  [y] Approve  [n] Cancel  [r] Redirect               │
└──────────┬───────────────────────────────────────────┘
           │  n → EXIT (no cost incurred)
           │  r → loop back with new topic
           │  y → continue
           ▼
┌──────────────────────────────────────────────────────┐
│  WEB SEARCHER  (sequential)        subagents/        │
│                                    web_searcher.py   │
│  Tools:                                              │
│    web_search(topic) → raw source summaries          │
│    format_citation(title, url, ...) → APA citation   │
│       └── skill from skills/citation_formatter.py    │
│                                                      │
│  Output: bullet-point findings + numbered refs       │
└──────────┬───────────────────────────────────────────┘
           │  raw text truncated to ~800 words
           ├──────────────────────┐
           ▼                      ▼
┌───────────────────┐    ┌────────────────────┐
│ INSIGHT EXTRACTOR │    │   FACT CHECKER     │  PARALLEL
│                   │    │                    │  (ThreadPoolExecutor
│ Tool:             │    │  Tool:             │   max_workers=2)
│  identify_themes  │    │   extract_claims   │
│  → scans content  │    │   → isolates       │
│    for stats,     │    │     verifiable     │
│    named orgs,    │    │     statements     │
│    trends,        │    │                    │
│    problems       │    │  Rates each:       │
│                   │    │  HIGH / MEDIUM /   │
│ Output:           │    │  LOW confidence    │
│  KEY BREAKTHROUGHS│    │                    │
│  MAJOR TRENDS     │    │  OVERALL           │
│  KEY PLAYERS      │    │  RELIABILITY score │
│  OPEN PROBLEMS    │    │                    │
└─────────┬─────────┘    └────────┬───────────┘
          └──────────┬────────────┘
                     ▼
┌──────────────────────────────────────────────────────┐
│  ORCHESTRATOR  (synthesis)          streaming.py     │
│                                                      │
│  Input:                                              │
│    [prior memory context]  ← injected if exists      │
│    [web searcher output]                             │
│    [insight extractor output]                        │
│    [fact checker output]                             │
│                                                      │
│  Streams final report token-by-token:                │
│                                                      │
│    ## Executive Summary                              │
│    ## Key Findings                                   │
│    ## Core Insights                                  │
│    ## Reliability Assessment                         │
│    ## Next Steps                                     │
└──────────┬───────────────────────────────────────────┘
           ├──────────────────────┐
           ▼                      ▼
┌───────────────────┐    ┌────────────────────────────┐
│  MEMORY UPDATE    │    │  FILESYSTEM BACKEND         │
│                   │    │                             │
│  memory.py        │    │  backend/filesystem.py      │
│                   │    │                             │
│  remember(topic,  │    │  save_session(              │
│    report)        │    │    topic,                   │
│                   │    │    subagent_outputs,        │
│  Merges with      │    │    report                   │
│  existing entry   │    │  )                          │
│  or creates new   │    │                             │
│                   │    │  sessions/                  │
│  memory/          │    │    ai_20260610_143022.json   │
│    store.json     │    │                             │
└───────────────────┘    └─────────────────────────────┘

                     END
```

---

## File-by-File Summary

| File | Role | Key Functions |
|------|------|--------------|
| `orchestrator.py` | Entry point, pipeline coordinator | `run()`, `hitl_gate()`, `run_subagents()`, `build_orchestrator()` |
| `streaming.py` | Real-time token streaming | `stream_agent()` |
| `subagents/web_searcher.py` | Source gathering + citations | `run()`, `web_search()`, uses `format_citation` skill |
| `subagents/insight_extractor.py` | Theme + trend analysis | `run()`, `identify_themes()` |
| `subagents/fact_checker.py` | Claim verification + confidence rating | `run()`, `extract_claims()` |
| `memory/memory.py` | Persistent knowledge store | `remember()`, `recall()`, `recall_related()`, `format_for_context()` |
| `memory/store.json` | JSON knowledge database | Auto-managed by `memory.py` |
| `backend/filesystem.py` | Session audit log | `save_session()`, `load_session()`, `list_sessions()`, `load_latest()` |
| `skills/citation_formatter.py` | Shared citation tool | `format_citation()` |
| `skills/summarizer.py` | Shared text compression tool | `summarize()` |
| `demo.ipynb` | Interactive notebook walkthrough | Covers all 6 features with commentary |

---

## Technical Challenges Solved

### 1. Windows UTF-8 Encoding
LLM output contains Unicode characters (arrows, checkmarks, box-drawing). Windows terminals default to `cp1252` which crashes on these.

**Fix:**
```python
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
```
Plus replacing all Unicode symbols in our own print statements with ASCII equivalents.

### 2. Tool-Call Schema Bug (llama-3.3-70b-versatile)
The model occasionally generates an extra `params: {}` field in tool calls, causing Groq to return a `400 Bad Request`.

**Fix:** Keep tool signatures simple (single-argument tools). Removed `summarize` from `insight_extractor`'s tools list — the tool still exists as a skill but is not exposed to this particular agent.

### 3. Free-Tier Token Limits
`deepagents` adds ~8,000 tokens of framework overhead per call (subagent middleware, summarization pipeline, prompt caching layer). This makes small-TPM models like `llama-3.1-8b-instant` (6,000 TPM) unusable — the framework overhead alone exceeds the limit.

**Design decision:** Truncate raw web search output to ~800 words before passing to parallel subagents. This keeps each parallel call well within the 6,000 TPM window of the model.

### 4. `langchain-anthropic` as Hard Dependency
Even when using Groq exclusively, `deepagents` imports `langchain_anthropic.middleware.prompt_caching` internally. Uninstalling it breaks the framework.

**Accepted trade-off:** Keep it installed, ignore the import noise in tracebacks.

### 5. Decommissioned Models
`llama3-70b-8192` was removed from Groq's API mid-development.

**Fix:** Tested available models and switched to `meta-llama/llama-4-scout-17b-16e-instruct` as fallback, then reverted to `llama-3.3-70b-versatile` per project spec once quota reset.

---

## Current Status

| Component | Status |
|-----------|--------|
| Orchestrator | Complete |
| Parallel subagents | Complete |
| HITL gate | Complete |
| Streaming | Complete |
| Long-term memory | Complete |
| Filesystem backend | Complete |
| Skills | Complete |
| Demo notebook | Complete |
| End-to-end run | Ready — pending Groq daily quota reset |

The full pipeline runs correctly. The only blocker is the Groq free-tier 100K token/day limit being exhausted from development and debugging runs. Once the daily quota resets, run:

```bash
python orchestrator.py "Artificial Intelligence" --yes
```

---

## Tech Stack

| Library | Version | Role |
|---------|---------|------|
| `deepagents` | latest | Deep Agent framework |
| `langchain-groq` | latest | Groq LLM integration |
| `langchain-anthropic` | latest | Hard dep of deepagents (framework internal use) |
| `langgraph` | latest | Agent graph execution engine (deepagents internals) |
| `python-dotenv` | latest | `.env` file loading |
| Python | 3.12 | Runtime |
| Groq API | — | LLM provider (`llama-3.3-70b-versatile`) |
