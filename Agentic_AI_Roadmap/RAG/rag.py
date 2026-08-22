"""
60-MIN BUILD: RAG that actually works
=========================================
4 experiments, ~15 min each. Runs fully offline — no API key needed.

pip install rank_bm25
"""

import math
import re
from collections import Counter
from rank_bm25 import BM25Okapi

def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())

def fake_embed(text, vocab):
    counts = Counter(tokenize(text))
    return [counts.get(word, 0) for word in vocab]

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    return dot / (mag_a * mag_b) if mag_a and mag_b else 0.0


# -----------------------------------------------------------
# 1. Reranker (15 min)
#    A crude "cross-encoder" stand-in: score each (query, chunk)
#    pair jointly by exact-phrase + term-overlap, not independent
#    vectors. Compare its top pick against plain vector similarity.
# -----------------------------------------------------------
CHUNKS = [
    "Acme Corp Q3 2025 revenue was $4.2 million, up 12% year over year.",
    "Acme Corp Q2 2025 revenue grew steadily, matching internal forecasts.",
    "Acme Corp's overall 2025 fiscal year revenue trends were strong across all quarters.",
]

def crude_rerank_score(query, chunk):
    """Stand-in for a real cross-encoder: rewards exact phrase overlap
    between query and chunk, not just shared vocabulary."""
    q_tokens = tokenize(query)
    c_tokens = tokenize(chunk)
    exact_phrase_bonus = 2.0 if "q3" in q_tokens and "q3" in c_tokens else 0.0
    overlap = len(set(q_tokens) & set(c_tokens))
    return overlap + exact_phrase_bonus


def experiment_1_reranker():
    query = "What was Acme's Q3 2025 revenue?"
    vocab = sorted(set(tokenize(query + " " + " ".join(CHUNKS))))

    vector_scores = [(cosine_similarity(fake_embed(query, vocab), fake_embed(c, vocab)), c) for c in CHUNKS]
    vector_scores.sort(key=lambda x: -x[0])

    rerank_scores = [(crude_rerank_score(query, c), c) for c in CHUNKS]
    rerank_scores.sort(key=lambda x: -x[0])

    print(f"\nQuery: {query!r}")
    print("\nVector similarity ranking:")
    for score, c in vector_scores:
        print(f"  {score:.3f}  {c}")

    print("\nReranker ranking (rewards the exact 'Q3' match):")
    for score, c in rerank_scores:
        print(f"  {score:.1f}  {c}")

    print("\nCheck: did vector similarity treat the three chunks as nearly tied (all about")
    print("Acme revenue), while the reranker clearly separated the Q3-specific chunk from")
    print("the Q2 and full-year ones that only sound similar?")


# -----------------------------------------------------------
# 2. Context ordering (15 min)
#    Same set of chunks, three different orderings. Just LOOK at
#    where the most-relevant chunk ends up.
# -----------------------------------------------------------
def order_by_score_descending(scored_chunks):
    return [c for _, c in sorted(scored_chunks, key=lambda x: -x[0])]

def order_most_relevant_last(scored_chunks):
    ranked = sorted(scored_chunks, key=lambda x: x[0])  # ascending, so best ends up last
    return [c for _, c in ranked]

def order_best_first_and_last(scored_chunks):
    ranked = sorted(scored_chunks, key=lambda x: -x[0])
    if len(ranked) <= 2:
        return [c for _, c in ranked]
    best, *middle, second_best = ranked
    return [c for _, c in [best] + middle + [second_best]]


def experiment_2_context_ordering():
    scored = [(3.0, "MOST RELEVANT: Acme Q3 2025 revenue was $4.2 million."),
              (1.0, "less relevant: Acme's office relocated in 2025."),
              (0.8, "less relevant: Acme sponsors a local youth sports team."),
              (0.5, "least relevant: Acme was founded in 1998.")]

    print("\nRetrieval-score order (as returned by the retriever):")
    for c in order_by_score_descending(scored):
        print(f"  {c}")

    print("\nMost-relevant-last order (closest to the question):")
    for c in order_most_relevant_last(scored):
        print(f"  {c}")

    print("\nCheck: in retrieval-score order, the MOST RELEVANT chunk sits at position 1 of 4 —")
    print("not necessarily bad here, but in a 10-chunk context that same position 1 could land")
    print("deep in the 'lost in the middle' zone once more chunks are added in front of it")
    print("by a later pipeline stage (e.g. a system prompt or few-shot examples).")


# -----------------------------------------------------------
# 3. Grounded citations (15 min)
#    Given an answer with citation markers, verify each citation
#    actually supports the claim — don't just check citations exist.
# -----------------------------------------------------------
SOURCE_CHUNKS = {
    "[1]": "Acme Corp Q3 2025 revenue was $4.2 million, up 12% year over year.",
    "[2]": "Support hours are 9am to 5pm, Monday through Friday.",
}

def verify_citation(claim_text, citation_marker):
    source = SOURCE_CHUNKS.get(citation_marker, "")
    # Strip the citation marker itself out first — otherwise "[1]" tokenizes into
    # a stray "1" that gets mistaken for part of the claim's content.
    claim_without_marker = claim_text.replace(citation_marker, "")

    claim_tokens = set(tokenize(claim_without_marker))
    source_tokens = set(tokenize(source))

    claim_numbers = {t for t in claim_tokens if t.isdigit()}
    source_numbers = {t for t in source_tokens if t.isdigit()}
    numbers_match = claim_numbers.issubset(source_numbers) if claim_numbers else True

    overlap_ratio = len(claim_tokens & source_tokens) / max(len(claim_tokens), 1)
    is_grounded = overlap_ratio > 0.5 and numbers_match
    return is_grounded, source


def experiment_3_grounded_citations():
    answers = [
        ("Acme's Q3 2025 revenue was $4.2 million [1].", "[1]"),          # accurate, real citation
        ("Acme's Q3 2025 revenue was $6.8 million [1].", "[1]"),          # WRONG number, but cites a real chunk — this is the dangerous one
        ("Support is available 24/7 [2].", "[2]"),                        # citation exists but doesn't actually say this
    ]

    for claim, marker in answers:
        is_grounded, source = verify_citation(claim, marker)
        print(f"\nClaim: {claim!r}")
        print(f"  Cited source: {source!r}")
        print(f"  Passes 'has a citation' check: True (marker {marker} exists)")
        print(f"  Passes 'citation actually supports claim' check: {is_grounded}")

    print("\nCheck: the second claim (wrong revenue number) HAS a real citation, and shares most")
    print("of its WORDS with the source — a plain word-overlap check alone would wrongly call it")
    print("grounded. Only explicitly comparing the numeric tokens catches that 6.8 isn't in the")
    print("source at all. This is the general lesson: word overlap and factual support are not")
    print("the same check, especially for numbers, dates, and identifiers.")


# -----------------------------------------------------------
# 4. Measuring retrieval quality (15 min)
#    precision@k, recall@k, and MRR against a small labeled set.
# -----------------------------------------------------------
def precision_at_k(retrieved, relevant, k):
    top_k = retrieved[:k]
    hits = sum(1 for c in top_k if c in relevant)
    return hits / k

def recall_at_k(retrieved, relevant, k):
    top_k = retrieved[:k]
    hits = sum(1 for c in top_k if c in relevant)
    return hits / len(relevant) if relevant else 0.0

def reciprocal_rank(retrieved, relevant):
    for i, c in enumerate(retrieved):
        if c in relevant:
            return 1 / (i + 1)
    return 0.0


def experiment_4_measuring_quality():
    # A tiny hand-labeled eval set: query -> retrieved order -> which are actually relevant
    eval_cases = [
        {
            "query": "Acme Q3 revenue",
            "retrieved": ["Q2 revenue chunk", "Q3 revenue chunk", "office news chunk", "founding date chunk"],
            "relevant": {"Q3 revenue chunk"},
        },
        {
            "query": "Acme support hours",
            "retrieved": ["support hours chunk", "revenue chunk", "office news chunk"],
            "relevant": {"support hours chunk"},
        },
    ]

    for case in eval_cases:
        p_at_2 = precision_at_k(case["retrieved"], case["relevant"], k=2)
        r_at_2 = recall_at_k(case["retrieved"], case["relevant"], k=2)
        rr = reciprocal_rank(case["retrieved"], case["relevant"])

        print(f"\nQuery: {case['query']!r}")
        print(f"  Retrieved order: {case['retrieved']}")
        print(f"  Precision@2: {p_at_2:.2f}   Recall@2: {r_at_2:.2f}   Reciprocal rank: {rr:.2f}")

    print("\nCheck: for the first query, the relevant chunk was retrieved but at rank 2, not rank 1.")
    print("Precision@2 still counts it as a 'hit', but reciprocal rank (0.5) reflects that it")
    print("wasn't the top result — this is exactly the distinction MRR is for.")
    print("\nTask: build a real 20-30 query eval set for one of your own projects using this pattern.")


# -----------------------------------------------------------
if __name__ == "__main__":
    experiment_1_reranker()
    experiment_2_context_ordering()
    experiment_3_grounded_citations()
    experiment_4_measuring_quality()