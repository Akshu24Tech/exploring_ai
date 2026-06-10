"""
Skill: Summarizer
==================
Reusable tool that compresses a long block of text into a tight summary
at a chosen detail level.

Why a skill and not inline code:
  Both the Insight Extractor (pre-processing raw sources) and the Orchestrator
  (compressing subagent outputs before synthesis) may need to shrink text.
  One definition, used by many agents.
"""

import re


def summarize(text: str, max_sentences: int = 5, focus: str = "") -> str:
    """
    Compress text into a concise summary.

    Args:
        text:           The text to summarise.
        max_sentences:  Maximum number of sentences to keep (default 5).
        focus:          Optional keyword — sentences containing this word
                        are ranked higher (e.g. 'breakthrough', 'risk').

    Returns a shorter version of the text.
    """
    # Split into sentences
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]

    if len(sentences) <= max_sentences:
        return text  # already short enough

    # Score each sentence: longer sentences and focus-keyword hits score higher
    def score(s: str) -> float:
        base  = min(len(s.split()) / 20, 1.0)          # length bonus (up to 1.0)
        bonus = 0.5 if focus and focus.lower() in s.lower() else 0.0
        return base + bonus

    ranked     = sorted(enumerate(sentences), key=lambda x: -score(x[1]))
    keep_idxs  = sorted(i for i, _ in ranked[:max_sentences])
    summary    = " ".join(sentences[i] for i in keep_idxs)

    word_in  = len(text.split())
    word_out = len(summary.split())
    return f"[summarized {word_in}->{word_out} words]\n{summary}"
