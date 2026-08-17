"""
20-MIN BREAK IT: bad inputs, dead tools, full context
========================================================
Break today's retrieval pipeline. Fully offline. ~6-7 min per section.
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


CHUNKS = [
    "Acme Corp Q3 2025 revenue was $4.2 million.",
    "Acme Corp Q1 2025 revenue was $2.9 million.",
    "Support hours are 9am to 5pm, Monday through Friday.",
]


# -----------------------------------------------------------
# 1. Bad inputs (7 min)
#    Queries designed to confuse retrieval.
# -----------------------------------------------------------
def break_bad_inputs():
    vocab = sorted(set(tokenize(" ".join(CHUNKS))))
    bad_queries = [
        "",                              # empty query
        "the the the the the",          # all stopwords, no real content
        "revenue revenue revenue revenue revenue revenue revenue revenue",  # keyword-stuffed
        "🎉📊💰",                          # no alphanumeric tokens at all
    ]

    for q in bad_queries:
        q_vec = fake_embed(q, vocab)
        scores = [(cosine_similarity(q_vec, fake_embed(c, vocab)), c) for c in CHUNKS]
        scores.sort(key=lambda x: -x[0])
        print(f"\nQuery: {q!r}\n  top result: {scores[0]}")

    print("\nCheck: for the empty query and the emoji-only query, is the top result meaningless")
    print("(a tie broken arbitrarily) rather than an honest 'no relevant match' signal?")
    print("Real retrieval code should have a minimum-score threshold below which it returns nothing.")


# -----------------------------------------------------------
# 2. Dead tools (7 min)
#    The vector index is down. Does retrieval fail completely,
#    or degrade gracefully to BM25-only?
# -----------------------------------------------------------
def vector_search(query, chunks, simulate_down=False):
    if simulate_down:
        raise ConnectionError("vector index unreachable")
    vocab = sorted(set(tokenize(query + " " + " ".join(chunks))))
    q_vec = fake_embed(query, vocab)
    scores = [(cosine_similarity(q_vec, fake_embed(c, vocab)), c) for c in chunks]
    return sorted(scores, key=lambda x: -x[0])


def bm25_search(query, chunks):
    bm25 = BM25Okapi([tokenize(c) for c in chunks])
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(zip(scores, chunks), key=lambda x: -x[0])
    return ranked


def break_dead_tools():
    query = "Acme Q3 revenue"

    print("\nNormal hybrid retrieval:")
    try:
        v = vector_search(query, CHUNKS)
        b = bm25_search(query, CHUNKS)
        print(f"  vector top: {v[0][1]}\n  bm25 top: {b[0][1]}")
    except ConnectionError as e:
        print(f"  CRASHED: {e}")

    print("\nVector index down, no fallback:")
    try:
        v = vector_search(query, CHUNKS, simulate_down=True)
        print(f"  vector top: {v[0][1]}")
    except ConnectionError as e:
        print(f"  Retrieval CRASHED entirely: {e}")

    print("\nVector index down, WITH fallback to BM25-only:")
    try:
        v = vector_search(query, CHUNKS, simulate_down=True)
        results = v
    except ConnectionError:
        results = bm25_search(query, CHUNKS)
        print("  (fell back to BM25-only)")
    print(f"  top result: {results[0][1] if isinstance(results[0], tuple) else results[0]}")

    print("\nCheck: without the fallback, does one dead component take down retrieval entirely,")
    print("even though BM25 alone could still have answered this query fine?")


# -----------------------------------------------------------
# 3. Full context (6 min)
#    Retrieve way too many chunks and see what it costs.
# -----------------------------------------------------------
def break_full_context():
    big_corpus = CHUNKS * 500  # 1500 near-duplicate chunks
    query = "Acme revenue"

    vocab = sorted(set(tokenize(query + " " + " ".join(set(big_corpus)))))
    q_vec = fake_embed(query, vocab)
    scores = [(cosine_similarity(q_vec, fake_embed(c, vocab)), c) for c in big_corpus]
    scores.sort(key=lambda x: -x[0])

    top_20 = scores[:20]
    approx_tokens = sum(len(c.split()) for _, c in top_20) * 1.3  # rough words-to-tokens estimate

    print(f"\nCorpus size: {len(big_corpus)} chunks (mostly duplicates)")
    print(f"Top 20 results retrieved -> approx {approx_tokens:.0f} tokens of context")
    print("Sample of what got retrieved (all near-identical):")
    for score, chunk in top_20[:5]:
        print(f"  {score:.3f}  {chunk}")

    print("\nCheck: retrieving top-20 from a corpus full of near-duplicates burns a large token")
    print("budget (Day 1) on repeated information. Would top-3 with a diversity/dedup step have")
    print("given the model just as much signal for a fraction of the tokens?")


# -----------------------------------------------------------
if __name__ == "__main__":
    break_bad_inputs()
    break_dead_tools()
    break_full_context()