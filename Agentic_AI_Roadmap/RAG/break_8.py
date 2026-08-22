"""
20-MIN BREAK IT: bad inputs, dead tools, full context
========================================================
Break today's rerank/order/cite/measure pipeline. Fully offline. ~6-7 min per section.
"""

import re
from collections import Counter

def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())


SOURCE_CHUNKS = {
    "[1]": "Acme Corp Q3 2025 revenue was $4.2 million.",
    "[2]": "Support hours are 9am to 5pm, Monday through Friday.",
}


# -----------------------------------------------------------
# 1. Bad inputs (7 min)
#    Citations designed to slip past a naive grounding check.
# -----------------------------------------------------------
def verify_citation(claim_text, citation_marker):
    source = SOURCE_CHUNKS.get(citation_marker)
    if source is None:
        return False, None
    claim_without_marker = claim_text.replace(citation_marker, "")
    claim_tokens = set(tokenize(claim_without_marker))
    source_tokens = set(tokenize(source))
    claim_numbers = {t for t in claim_tokens if t.isdigit()}
    source_numbers = {t for t in source_tokens if t.isdigit()}
    numbers_match = claim_numbers.issubset(source_numbers) if claim_numbers else True
    overlap_ratio = len(claim_tokens & source_tokens) / max(len(claim_tokens), 1)
    return (overlap_ratio > 0.5 and numbers_match), source


def break_bad_inputs():
    attacks = [
        ("Acme's Q3 revenue was $4.2 million, roughly [1].", "[1]"),         # hedge word "roughly" — should still pass, real number matches
        ("Acme's Q3 revenue was between $4.2 and $42 million [1].", "[1]"),  # sneaks an extra plausible-looking number in alongside the real one
        ("Acme's Q3 revenue was $4.2 million [3].", "[3]"),                  # citation marker that doesn't exist at all
        ("", "[1]"),                                                         # empty claim, real marker
    ]

    for claim, marker in attacks:
        is_grounded, source = verify_citation(claim, marker)
        print(f"\nClaim: {claim!r} citing {marker}\n  source found: {source!r}\n  grounded: {is_grounded}")

    print("\nCheck: did the 'between $4.2 and $42 million' claim slip through as grounded")
    print("because $4.2 is technically present, even though the claim as a whole is misleading?")
    print("A real hallucination check needs to catch invented numbers ADDED alongside real ones,")
    print("not just verify that at least one number happens to match.")


# -----------------------------------------------------------
# 2. Dead tools (7 min)
#    The reranker is unavailable. Does the pipeline fail closed
#    (no results) or fail open (skip reranking silently)?
# -----------------------------------------------------------
def rerank(query, candidates, simulate_down=False):
    if simulate_down:
        raise RuntimeError("reranker service unavailable")
    return sorted(candidates, key=lambda c: -len(set(tokenize(query)) & set(tokenize(c))))


def break_dead_tools():
    query = "Acme Q3 revenue"
    candidates = ["Q2 chunk", "Q3 chunk", "office news chunk"]

    print("\nNo fallback — reranker failure propagates up:")
    try:
        result = rerank(query, candidates, simulate_down=True)
        print(f"  {result}")
    except RuntimeError as e:
        print(f"  Pipeline CRASHED: {e}")
        print("  (the whole RAG answer fails, even though plain retrieval order was still usable)")

    print("\nWith fallback — skip reranking, use retrieval order as-is:")
    try:
        result = rerank(query, candidates, simulate_down=True)
    except RuntimeError:
        result = candidates  # fall back to unranked retrieval order
        print("  (reranker down — fell back to original retrieval order, answer still possible)")
    print(f"  {result}")

    print("\nCheck: is 'reranker down, use retrieval order' an acceptable degraded mode for your")
    print("use case, or does answer quality drop enough that you'd rather fail closed and tell")
    print("the user retrieval is temporarily degraded? Different products should choose differently.")


# -----------------------------------------------------------
# 3. Full context (6 min)
#    A citation-heavy answer where the source text is pushed far
#    from its citation marker by unrelated content in between.
# -----------------------------------------------------------
def break_full_context():
    noise_between = "Unrelated filler paragraph. " * 800
    prompt = f"""Source [1]: {SOURCE_CHUNKS['[1]']}

    {noise_between}

    Question: What was Acme's Q3 revenue? Answer with a citation to [1]."""

    approx_tokens = len(prompt.split()) * 1.3
    print(f"\nPrompt size with noise between the source and the question: ~{approx_tokens:.0f} tokens")
    print("Simulating: even if the model still produces a citation marker [1] correctly,")
    print("does the VALUE it cites still match the source now that ~800 filler lines sit")
    print("between the source text and the question asking about it?")

    print("\nCheck: this is exactly why grounded-citation verification (experiment 3 above) matters")
    print("more, not less, as context grows — the citation marker being present tells you nothing")
    print("about whether the model actually re-read that specific source before answering.")


# -----------------------------------------------------------
if __name__ == "__main__":
    break_bad_inputs()
    break_dead_tools()
    break_full_context()