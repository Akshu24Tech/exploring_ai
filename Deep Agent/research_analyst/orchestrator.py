"""
Autonomous Multi-Agent Research Analyst
========================================
Features:
  - Parallel subagent coordination (Web Searcher -> Insight Extractor + Fact Checker)
  - Human-in-the-Loop: approval gate before expensive subagent work starts
  - Long-Term Memory: recall prior research, inject as context, update after each run
  - Filesystem Backend: save every session (subagent outputs + report) as a JSON audit log

Long-Term Memory pattern:
  Before any subagent work, memory is checked for this topic (exact) and
  related topics (fuzzy keyword overlap). Any prior knowledge is injected
  into the orchestrator's synthesis prompt so the final report builds on
  what was already known, not just the current run's findings.
  After the report is generated, a compressed summary is written back to memory.

Flow:
    topic
      │
      ▼
  [MEMORY CHECK] ← recall exact + related topics
      │
      ▼
  [HITL GATE] ← pre-scan (+ prior knowledge shown) -> user approves?
      │ yes
      ▼
  Web Searcher ──--raw ────┬────────────────┐
                            ▼                ▼
                   Insight Extractor    Fact Checker   (parallel)
                            │                │
                            └──────┬─────────┘
                                   ▼
                        Orchestrator (+ memory context) -> Final Report
                                   │
                                   ▼
                            [MEMORY UPDATE]
                                   │
                                   ▼
                            [BACKEND SAVE] -> sessions/<id>.json
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from deepagents import create_deep_agent

# Windows terminals default to cp1252 — force UTF-8 so Unicode in LLM output
# doesn't crash the process.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from subagents import web_searcher, insight_extractor, fact_checker
from streaming import stream_agent
from memory import memory
from backend import filesystem

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "../.env"))


# --Pre-scan agent (cheap — used for HITL preview only) ───────────────────────
def build_prescan_agent() -> object:
    return create_deep_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[],
        system_prompt=(
            "You are a research planning assistant. "
            "Given a topic, produce a brief research plan in this exact format:\n\n"
            "TOPIC INTERPRETATION: one sentence on how you understand the topic.\n"
            "SUBAGENTS TO SPAWN: Web Searcher, Insight Extractor, Fact Checker\n"
            "KEY QUESTIONS:\n"
            "  - question 1\n"
            "  - question 2\n"
            "  - question 3\n"
            "ESTIMATED SCOPE: Narrow / Medium / Broad\n\n"
            "Be concise. This is shown to the user before any heavy work begins."
        ),
    )


# --Human-in-the-Loop gate --------------------------------------------------───
def hitl_gate(topic: str, auto_approve: bool = False) -> str | None:
    """
    Generates a research plan preview and asks the user to approve it.

    Returns:
      - the approved topic (str) if user says yes
      - a redirected topic (str) if user says redirect
      - None if user cancels
    """
    print("\n--Research Plan Preview ───────────────────────────────")
    print("  Generating plan (no subagents spawned yet)...\n")

    agent = build_prescan_agent()
    plan = stream_agent(agent, f"Plan research on: {topic}", label="Research Plan")

    print("\n--Approval Required -----------------------------------------------")
    print("  This will spawn 3 subagents and make multiple LLM calls.")
    print("  [y] Approve and run    [n] Cancel    [r] Redirect to new topic")
    print("-------------------------------------------------------------------")

    if auto_approve:
        print("  Your choice: y  (--yes flag)")
        return topic

    while True:
        choice = input("  Your choice: ").strip().lower()

        if choice == "y":
            print(f"  [OK]Approved. Starting research on: {topic}\n")
            return topic

        elif choice == "n":
            print("  [NO]Cancelled. No subagents were spawned.")
            return None

        elif choice == "r":
            new_topic = input("  Enter new topic: ").strip()
            if new_topic:
                print(f"  [->] Redirected to: {new_topic}\n")
                return new_topic
            print("  Topic cannot be empty. Try again.")

        else:
            print("  Please enter y, n, or r.")


# --Orchestrator agent (synthesises subagent outputs) ─────────────────────────
def build_orchestrator() -> object:
    return create_deep_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[],
        system_prompt=(
            "You are the lead research orchestrator. "
            "You receive outputs from three specialist subagents and your sole job "
            "is to synthesise them into one polished research report.\n\n"
            "Use this exact structure:\n\n"
            "## Executive Summary\n"
            "2-3 sentence overview.\n\n"
            "## Key Findings\n"
            "What the web searcher found (bullet points).\n\n"
            "## Core Insights\n"
            "Breakthroughs, trends, key players, open problems.\n\n"
            "## Reliability Assessment\n"
            "What the fact checker concluded.\n\n"
            "## Next Steps\n"
            "3-5 actionable recommendations.\n\n"
            "Be precise. Do not pad. Use the subagent outputs as your only source."
        ),
    )


# --Parallel subagent runner --------------------------------------------------─
def run_subagents(topic: str) -> dict[str, str]:
    print("--Subagents starting ──────────────────────────────────")

    print("  [1/3] Web Searcher       -> running...")
    t0 = time.time()
    raw = web_searcher.run(topic)
    print(f"  [1/3] Web Searcher       done ({time.time()-t0:.1f}s)")

    print("  [2/3] Insight Extractor  -> running (parallel)")
    print("  [3/3] Fact Checker       -> running (parallel)")

    # Truncate to ~800 words before handing off to parallel subagents —
    # keeps requests well within the free-tier TPM limits.
    raw_truncated = " ".join(raw.split()[:800])

    results = {"web_searcher": raw}
    t1 = time.time()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(insight_extractor.run, raw_truncated): "insight_extractor",
            pool.submit(fact_checker.run, raw_truncated):       "fact_checker",
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
            label = "Insight Extractor" if name == "insight_extractor" else "Fact Checker     "
            idx   = "2/3"               if name == "insight_extractor" else "3/3"
            print(f"  [{idx}] {label} done ({time.time()-t1:.1f}s)")

    print(f"--All done ({time.time()-t0:.1f}s total) ─────────────────────\n")
    return results


# --Main pipeline --------------------------------------------------────────────
def run(topic: str, auto_approve: bool = False) -> None:
    print(f"\n{'='*58}")
    print(f"  Research Analyst  |  Topic: {topic}")
    print(f"{'='*58}")

    # --LONG-TERM MEMORY: recall what we already know ─────────────────────────
    prior        = memory.recall(topic)
    related      = memory.recall_related(topic)
    memory_context = ""

    if prior:
        print(f"\n[memory] Found prior research on '{topic}' "
              f"({prior['research_count']}x, last: {prior['last_updated']})")
        memory_context += memory.format_for_context(prior) + "\n\n"

    if related:
        print(f"[memory] Found {len(related)} related topic(s): "
              + ", ".join(f"'{e['topic']}'" for e in related))
        for entry in related:
            memory_context += memory.format_for_context(entry) + "\n\n"

    if not prior and not related:
        print("[memory] No prior knowledge found — starting fresh.")

    # --HUMAN-IN-THE-LOOP: show plan, wait for approval ───────────────────────
    approved_topic = hitl_gate(topic, auto_approve=auto_approve)
    if approved_topic is None:
        return  # user cancelled — no subagents spawned, no cost incurred

    topic = approved_topic  # may have been redirected

    # --Parallel subagent execution ───────────────────────────────────────────
    outputs = run_subagents(topic)

    # --Orchestrator synthesis (memory context injected here) ─────────────────
    memory_block = (
        f"\n=== PRIOR KNOWLEDGE FROM MEMORY ===\n{memory_context}"
        if memory_context else ""
    )

    synthesis_input = f"""
Research topic: {topic}
{memory_block}
=== WEB SEARCHER OUTPUT ===
{outputs['web_searcher']}

=== INSIGHT EXTRACTOR OUTPUT ===
{outputs['insight_extractor']}

=== FACT CHECKER OUTPUT ===
{outputs['fact_checker']}

Note: If prior knowledge is present, reference it where relevant and highlight
what is NEW compared to what was already known.
""".strip()

    orchestrator = build_orchestrator()
    report = stream_agent(orchestrator, synthesis_input, label="Final Report")

    # --LONG-TERM MEMORY: save compressed summary ─────────────────────────────
    memory.remember(topic, report)

    # --FILESYSTEM BACKEND: save full session audit log ───────────────────────
    filesystem.save_session(
        topic=topic,
        subagent_outputs=outputs,
        report=report,
    )

    print(f"{'='*58}\n")


# --CLI --------------------------------------------------──────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--history":
        # List all saved sessions, optionally filtered by topic
        filter_topic = " ".join(sys.argv[2:]) or None
        sessions = filesystem.list_sessions(filter_topic)
        if not sessions:
            print("No sessions saved yet.")
        else:
            label = f"for '{filter_topic}'" if filter_topic else "(all topics)"
            print(f"\n--Session History {label} ─────────────────────────")
            for s in sessions:
                print(f"  [{s['timestamp']}]  {s['topic']}")
                print(f"    id: {s['id']}")
            print()
    else:
        args = [a for a in sys.argv[1:] if a != "--yes"]
        yes  = "--yes" in sys.argv
        topic = " ".join(args) if args else "Quantum Computing"
        run(topic, auto_approve=yes)
