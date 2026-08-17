"""
60-MIN BUILD: Embeddings & vector search
============================================
4 experiments, ~15 min each. Runs fully offline — no API key needed.

pip install rank_bm25
(Vector search uses a small hand-rolled TF-IDF + cosine similarity
function as a stand-in for real embeddings, so this runs with zero
setup. Swap `fake_embed()` for a real embedding API call when ready.)
"""

import math
import re
from collections import Counter
from rank_bm25 import BM25Okapi


# -----------------------------------------------------------
# 1. Chunking strategies (15 min)
#    Compare fixed-size vs. sentence-based vs. overlapping chunking
#    on the same document. Watch where a fact gets split.
# -----------------------------------------------------------
DOC = (
    "Acme Corp reported Q3 revenue of $4.2 million, up 12% year over year. "
    "The increase was driven mainly by the new enterprise product line. "
    "Operating costs also rose, largely due to hiring in the sales team. "
    "Net profit margin held steady at 18%, matching analyst expectations. "
    "The board approved a $500,000 investment in R&D for next quarter."
)

def chunk_fixed_size(text, size = 60):
    return [text[i:i+size] for i in range(0, len(text), size)]

def chunk_by_sentence(text):
    return [s.strip() + "." for s in text.split(".") if s.strip()]

def chunk_overlapping(text, size=60, overlap=15):
    chunks = []
    step = size - overlap
    for i in range(0, len(text), step):
        chunks.append(text[i:i + size])
    return chunks


def experiment_1_chunking():
    print("\nFixed-size (60 chars, no overlap):")
    for c in chunk_fixed_size(DOC):
        print(f"  {c!r}")

    print("\nSentence-based:")
    for c in chunk_by_sentence(DOC):
        print(f"  {c!r}")

    print("\nOverlapping (60 chars, 15 overlap):")
    for c in chunk_overlapping(DOC):
        print(f"  {c!r}")

    print("\nCheck: in the fixed-size version, is '$4.2 million' split across two chunks?")
    print("Does the overlapping version keep it intact in at least one chunk?")


# -----------------------------------------------------------
# 2. Vector search basics (15 min)
#    A tiny hand-rolled TF-IDF + cosine similarity "embedding" —
#    enough to see the mechanics without needing a real API key.
# -----------------------------------------------------------
def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())

def fake_embed(text, vocab):
    """Stand-in for a real embedding call. Swap this for your
    Groq/Gemini/Ollama embedding endpoint when ready."""
    counts = Counter(tokenize(text))
    return [counts.get(word, 0) for word in vocab]

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(y * y for y in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def experiment_2_vector_search():
    chunks = chunk_by_sentence(DOC)
    query = "How much did the company earn this quarter?"

    vocab = sorted(set(tokenize(DOC + " " + query)))
    query_vec = fake_embed(query, vocab)
    chunk_vecs = [fake_embed(c, vocab) for c in chunks]

    scores = [(cosine_similarity(query_vec, cv), c) for cv, c in zip(chunk_vecs, chunks)]
    scores.sort(reverse=True)

    print(f"\nQuery: {query!r}")
    for score, chunk in scores:
        print(f"  {score:.3f}  {chunk}")

    print("\nCheck: did the revenue sentence rank highest even though the query used")
    print("different words ('earn' vs 'revenue')? If not, this crude embedding is too literal —")
    print("a real embedding model handles that synonym gap much better.")


# -----------------------------------------------------------
# 3. Metadata filters (15 min)
#    Same query, but chunks now carry metadata. Compare
#    unfiltered vs. pre-filtered retrieval.
# -----------------------------------------------------------
CHUNKS_WITH_METADATA = [
    {"text": "Acme Corp Q3 2025 revenue was $4.2 million.", "year": 2025, "quarter": "Q3"},
    {"text": "Acme Corp Q3 2024 revenue was $3.6 million.", "year": 2024, "quarter": "Q3"},
    {"text": "Acme Corp Q1 2025 revenue was $2.9 million.", "year": 2025, "quarter": "Q1"},
]

def experiment_3_metadata_filters():
    query = "What was Acme's revenue?"
    vocab = sorted(set(tokenize(query + " " + " ".join(c["text"] for c in CHUNKS_WITH_METADATA))))
    query_vec = fake_embed(query, vocab)

    print(f"\nQuery: {query!r} (ambiguous — could match any year/quarter)")

    print("\nUnfiltered (vector similarity only):")
    scores = [(cosine_similarity(query_vec, fake_embed(c["text"], vocab)), c) for c in CHUNKS_WITH_METADATA]
    scores.sort(key=lambda x: -x[0])
    for score, c in scores:
        print(f"  {score:.3f}  {c['text']}")

    print("\nPre-filtered to year=2025, quarter=Q3, THEN ranked:")
    filtered = [c for c in CHUNKS_WITH_METADATA if c["year"] == 2025 and c["quarter"] == "Q3"]
    for c in filtered:
        print(f"  {c['text']}")

    print("\nCheck: without the filter, could the wrong year's revenue have been the top result")
    print("just because it's textually similar? The filter removes that risk entirely.")


# -----------------------------------------------------------
# 4. Hybrid retrieval: BM25 + vector, combined with rank fusion (15 min)
# -----------------------------------------------------------
def reciprocal_rank_fusion(ranked_lists, k=60):
    """ranked_lists: list of ranked chunk-index lists (best first). Returns fused ranking."""
    scores = {}
    for ranked in ranked_lists:
        for rank, idx in enumerate(ranked):
            scores[idx] = scores.get(idx, 0) + 1 / (k + rank + 1)
    return sorted(scores, key=lambda idx: -scores[idx])


def experiment_4_hybrid():
    chunks = [
        "Invoice INV-88213 was paid on time.",
        "Customers can cancel their subscription anytime from account settings.",
        "To terminate your membership, go to billing preferences.",
        "The Q3 report mentions invoice INV-88213 as fully settled.",
    ]

    # Query 1: exact identifier — favors BM25
    query_exact = "INV-88213 status"
    # Query 2: true paraphrase, zero shared words with the target chunk on purpose
    query_paraphrase = "how do I stop paying for this service"

    tokenized_chunks = [tokenize(c) for c in chunks]
    bm25 = BM25Okapi(tokenized_chunks)

    vocab = sorted(set(tokenize(" ".join(chunks) + " " + query_exact + " " + query_paraphrase)))

    for label, query in [("exact identifier", query_exact), ("paraphrase", query_paraphrase)]:
        bm25_scores = bm25.get_scores(tokenize(query))
        bm25_ranked = sorted(range(len(chunks)), key=lambda i: -bm25_scores[i])

        query_vec = fake_embed(query, vocab)
        vec_scores = [cosine_similarity(query_vec, fake_embed(c, vocab)) for c in chunks]
        vec_ranked = sorted(range(len(chunks)), key=lambda i: -vec_scores[i])

        fused = reciprocal_rank_fusion([bm25_ranked, vec_ranked])

        print(f"\nQuery ({label}): {query!r}")
        print(f"  BM25 top result:   {chunks[bm25_ranked[0]]!r}")
        print(f"  Vector top result: {chunks[vec_ranked[0]]!r}")
        print(f"  Hybrid top result: {chunks[fused[0]]!r}")

    print("\nCheck: for the exact-identifier query, both retrievers likely nailed it since the ID")
    print("string is a rare, exact token — that's the case BM25 is built for.")
    print("For the true paraphrase query (zero shared words with 'cancel your subscription'),")
    print("did EITHER retriever find the right chunk? Likely not — fake_embed() here is just a")
    print("word-count vector, not a real semantic embedding. This is the honest limitation to notice:")
    print("only a real embedding model (trained to place synonyms near each other in vector space)")
    print("closes this gap. Swap fake_embed() for a real embedding API call to see the difference.")


# -----------------------------------------------------------
if __name__ == "__main__":
    experiment_1_chunking()
    experiment_2_vector_search()
    experiment_3_metadata_filters()
    experiment_4_hybrid()