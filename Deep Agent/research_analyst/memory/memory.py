"""
Long-Term Memory for the Research Analyst
==========================================
Stores compressed research summaries that persist across runs.
Each entry records what the agent already knows about a topic so
future runs can build on prior knowledge instead of starting cold.

Storage format  (memory/store.json):
{
  "quantum computing": {
    "topic":          "Quantum Computing",
    "summary":        "Compact summary of everything researched so far...",
    "research_count": 2,
    "last_updated":   "2026-06-10T11:45:00",
    "keywords":       ["qubit", "decoherence", "IBM", "Google", ...]
  },
  ...
}
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path

_STORE_PATH = Path(__file__).parent / "store.json"


# ── Internal helpers ───────────────────────────────────────────────────────────

def _load() -> dict:
    if _STORE_PATH.exists():
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    return {}


def _save(store: dict) -> None:
    _STORE_PATH.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")


def _key(topic: str) -> str:
    return topic.lower().strip()


def _keywords(text: str) -> list[str]:
    words = re.findall(r'\b[A-Za-z]{4,}\b', text)
    freq: dict[str, int] = {}
    for w in words:
        freq[w.lower()] = freq.get(w.lower(), 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])][:20]


# ── Public API ─────────────────────────────────────────────────────────────────

def remember(topic: str, summary: str) -> None:
    """
    Save or update a research summary for a topic.
    If the topic already exists, merges the new summary with the old one
    and increments the research count.
    """
    store = _load()
    key   = _key(topic)
    now   = datetime.now().isoformat(timespec="seconds")

    if key in store:
        existing = store[key]["summary"]
        merged   = f"{existing}\n\n[Updated {now}]\n{summary}"
        store[key]["summary"]        = merged
        store[key]["research_count"] += 1
        store[key]["last_updated"]   = now
        store[key]["keywords"]       = _keywords(merged)
    else:
        store[key] = {
            "topic":          topic,
            "summary":        summary,
            "research_count": 1,
            "last_updated":   now,
            "keywords":       _keywords(summary),
        }

    _save(store)
    count = store[key]["research_count"]
    print(f"[memory] Saved -> '{topic}'  (research count: {count})")


def recall(topic: str) -> dict | None:
    """
    Exact-match lookup for a topic.
    Returns the memory entry dict, or None if not found.
    """
    return _load().get(_key(topic))


def recall_related(topic: str, max_results: int = 2) -> list[dict]:
    """
    Fuzzy lookup — returns entries whose keywords overlap with the topic words.
    Useful for surfacing adjacent knowledge (e.g. 'AI Safety' when researching 'LLMs').
    """
    store   = _load()
    t_words = set(re.findall(r'\b[A-Za-z]{4,}\b', topic.lower()))
    scored  = []

    for key, entry in store.items():
        if key == _key(topic):
            continue  # skip exact match, handled by recall()
        overlap = t_words & set(entry["keywords"])
        if overlap:
            scored.append((len(overlap), entry))

    scored.sort(key=lambda x: -x[0])
    return [e for _, e in scored[:max_results]]


def list_all() -> list[dict]:
    """Return all memory entries as a list, sorted by last_updated descending."""
    store = _load()
    entries = list(store.values())
    entries.sort(key=lambda e: e["last_updated"], reverse=True)
    return entries


def format_for_context(entry: dict) -> str:
    """Format a memory entry as a context block for injection into a prompt."""
    return (
        f"[PRIOR KNOWLEDGE — '{entry['topic']}' "
        f"(researched {entry['research_count']}x, last: {entry['last_updated']})]\n"
        f"{entry['summary']}"
    )
