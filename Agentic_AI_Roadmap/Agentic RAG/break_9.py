"""
20-MIN BREAK IT: bad inputs, dead tools, full context
========================================================
Break today's plan/multi-hop/self-critique pipeline. Fully offline. ~6-7 min per section.
"""

import re

def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())

def ask(prompt, temperature=0.3):
    raise NotImplementedError("Add your API call inside ask() first.")


CORPUS = {
    "competitor": "Acme's biggest competitor is Globex Inc, based on market share data.",
    "acquisition": "Globex Inc was acquired by Initech Holdings in a 2024 merger.",
    "revenue": "Initech Holdings reported $890 million in annual revenue for 2024.",
}

def simple_retrieve(query, corpus):
    q_tokens = set(tokenize(query))
    scored = [(len(q_tokens & set(tokenize(text))), key, text) for key, text in corpus.items()]
    scored.sort(reverse=True)
    return scored[0][2]


def evidence_strength(query, retrieved_text, min_overlap=2):
    q_tokens = set(tokenize(query)) - {"the", "a", "is", "of", "what", "how"}
    overlap = q_tokens & set(tokenize(retrieved_text))
    return len(overlap) >= min_overlap, overlap


# -----------------------------------------------------------
# 1. Bad inputs (7 min)
#    Questions designed to break query planning and multi-hop chaining.
# -----------------------------------------------------------
def break_bad_inputs():
    bad_questions = [
        "Tell me everything about Acme.",                                     # unboundedly broad, no natural sub-query set
        "What's the revenue of the company that acquired the company that acquired the company that acquired Acme's competitor?",  # chained hops beyond what the corpus can support
        "Compare Acme's numbers to their numbers.",                           # ambiguous referents, nothing concrete to plan sub-queries around
    ]

    for q in bad_questions:
        prompt = f"""Break this question into independently-retrievable sub-queries, one per line.
        If the question is too broad or ambiguous to decompose meaningfully, say so instead.
        Question: {q}"""
        try:
            response = ask(prompt, temperature=0)
            print(f"\nQuestion: {q}\n-> {response}")
        except NotImplementedError as e:
            print(f"\nQuestion: {q}\n-> (needs ask() filled in: {e})")

    print("\nCheck: did the model recognize the unboundedly broad and over-chained questions as")
    print("undecomposable, or did it confidently produce a plan for something the corpus")
    print("can't actually support that many hops into?")


# -----------------------------------------------------------
# 2. Dead tools: retrieval fails mid-hop (7 min)
#    Hop 2 depends on hop 1's entity — what happens if hop 2's
#    lookup comes back empty?
# -----------------------------------------------------------
def break_dead_tools():
    hop1 = simple_retrieve("Acme biggest competitor", CORPUS)
    print(f"\nHop 1: {hop1!r}")

    # Simulate hop 2 searching for an entity that doesn't actually exist in the corpus —
    # e.g. entity extraction from hop 1 went wrong and produced an unrelated name.
    wrong_entity = "Vertex Dynamics"  # no token overlap with the corpus's actual "Globex Inc" at all
    hop2_query = f"{wrong_entity} acquired by"
    hop2 = simple_retrieve(hop2_query, CORPUS)
    is_strong, overlap = evidence_strength(hop2_query, hop2)

    print(f"\nHop 2 query (using a completely wrong entity name): {hop2_query!r}")
    print(f"  -> best match found anyway: {hop2!r}")
    print(f"  -> flagged strong: {is_strong}, overlap: {overlap}")

    print("\nCheck: notice the overlap is just {'acquired', 'by'} — generic query words that")
    print("would appear in ANY acquisition-related sentence, regardless of which company is")
    print("actually named. The entity name itself ('Vertex Dynamics') contributed ZERO overlap")
    print("and was silently ignored. This crude strength check would pass hop 2 as confident")
    print("evidence about the WRONG company, purely because the sentence shape matched — the")
    print("exact compounding-error failure mode from today's doc, and it happened on the first")
    print("wrong-entity name tried, not an unusual edge case. A real check needs to verify the")
    print("SPECIFIC entity is present, not just that the sentence is topically shaped right.")


# -----------------------------------------------------------
# 3. Full context: scratchpad across many hops (6 min)
# -----------------------------------------------------------
def break_full_context():
    huge_scratchpad = [
        {"hop": i, "query": f"query {i}", "evidence": f"evidence text for hop {i}..." * 20}
        for i in range(1, 15)
    ]

    approx_tokens = sum(len(str(h).split()) for h in huge_scratchpad) * 1.3
    print(f"\nScratchpad after 14 hops: approx {approx_tokens:.0f} tokens")
    print("(this is per-hop full evidence text kept verbatim, uncompressed)")

    print("\nCheck: at 14 hops with full evidence text kept every time, this scratchpad alone")
    print("could be competing hard with the actual system prompt and final-answer generation")
    print("for context budget (Day 1). Would compressing hops older than the last 2-3")
    print("(Day 5's scratchpad compression) keep this usable at hop 30 instead of hop 14?")


# -----------------------------------------------------------
if __name__ == "__main__":
    break_dead_tools()
    break_full_context()

    # break_bad_inputs()