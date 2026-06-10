"""
Filesystem Backend
==================
Saves every research session as a JSON file under sessions/.
Each file is a complete, self-contained record of one run:
  - topic and timestamp
  - every subagent's raw output
  - the final synthesised report

This is separate from long-term memory:
  memory/   = compressed knowledge that accumulates across runs
  sessions/ = full audit log, one file per run, nothing discarded

Session filename:  sessions/<topic-slug>_<YYYYMMDD_HHMMSS>.json

Session schema:
{
  "id":         "quantum-computing_20260610_114500",
  "topic":      "Quantum Computing",
  "timestamp":  "2026-06-10T11:45:00",
  "subagents": {
    "web_searcher":       "...",
    "insight_extractor":  "...",
    "fact_checker":       "..."
  },
  "report": "Final report text..."
}
"""

import json
import re
from datetime import datetime
from pathlib import Path

_SESSIONS_DIR = Path(__file__).parent.parent / "sessions"
_SESSIONS_DIR.mkdir(exist_ok=True)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _slug(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def _session_path(session_id: str) -> Path:
    return _SESSIONS_DIR / f"{session_id}.json"


# ── Public API ─────────────────────────────────────────────────────────────────

def save_session(topic: str, subagent_outputs: dict[str, str], report: str) -> str:
    """
    Persist a completed research session to disk.
    Returns the session_id (use it to reload with load_session).
    """
    ts         = datetime.now()
    session_id = f"{_slug(topic)}_{ts.strftime('%Y%m%d_%H%M%S')}"
    data = {
        "id":        session_id,
        "topic":     topic,
        "timestamp": ts.isoformat(timespec="seconds"),
        "subagents": subagent_outputs,
        "report":    report,
    }
    _session_path(session_id).write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[backend] Session saved -> sessions/{session_id}.json")
    return session_id


def load_session(session_id: str) -> dict:
    """Load a session by ID. Raises FileNotFoundError if it doesn't exist."""
    path = _session_path(session_id)
    if not path.exists():
        raise FileNotFoundError(f"Session not found: {session_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def list_sessions(topic: str | None = None) -> list[dict]:
    """
    Return session summaries (id, topic, timestamp), newest first.
    Pass topic to filter to a specific subject.
    """
    summaries = []
    for path in sorted(_SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if topic and _slug(topic) not in data["id"]:
                continue
            summaries.append({
                "id":        data["id"],
                "topic":     data["topic"],
                "timestamp": data["timestamp"],
            })
        except (json.JSONDecodeError, KeyError):
            continue
    return summaries


def load_latest(topic: str) -> dict | None:
    """Return the most recent session for a topic, or None if none exist."""
    sessions = list_sessions(topic)
    if not sessions:
        return None
    return load_session(sessions[0]["id"])
