"""
60-MIN BUILD: Agentic RAG
============================
4 experiments, ~15 min each. Experiments 2 and 3's core mechanics run
fully offline; experiments 1 and 4 need ask() filled in for the
planning/critique reasoning steps.

pip install rank_bm25
"""

import re
from collections import Counter

def tokenize(text):
    return re.findall(r"[a-z0-9]+", text.lower())

def ask(prompt, temperature=0.3):
    # Plug in your Groq/Gemini/Ollama call here.
    raise NotImplementedError("Add your API call inside ask() first.")


# -----------------------------------------------------------
# 1. Query planning (15 min)
#    Compound question -> atomic sub-queries, before any retrieval.
# -----------------------------------------------------------
def experiment_1_query_planning():
    question = "How did Acme's R&D spending as a percentage of revenue compare to last year?"

    prompt = f"""Break this question into the smallest set of independently-retrievable
    sub-queries needed to answer it. Return one sub-query per line, nothing else.

    Question: {question}"""

    plan = ask(prompt, temperature=0)
    sub_queries = [line.strip() for line in plan.strip().split("\n") if line.strip()]

    print(f"\nOriginal question: {question}")
    print(f"\nPlanned sub-queries ({len(sub_queries)}):")
    for q in sub_queries:
        print(f"  - {q}")

    print("\nCheck: does each sub-query stand alone as something a single retrieval pass could")
    print("actually answer? If any sub-query is still compound, the plan needs another pass.")


# -----------------------------------------------------------
# 2. Multi-hop retrieval (15 min)
#    Fully offline. Hop 1's answer becomes hop 2's search term.
# -----------------------------------------------------------
CORPUS = {
    "competitor": "Acme's biggest competitor is Globex Inc, based on market share data.",
    "acquisition": "Globex Inc was acquired by Initech Holdings in a 2024 merger.",
    "revenue": "Initech Holdings reported $890 million in annual revenue for 2024.",
    "unrelated_1": "Acme's headquarters relocated to a new office building in 2023.",
    "unrelated_2": "Globex Inc sponsors a regional youth sports league.",
}

def simple_retrieve(query, corpus):
    """Crude keyword-overlap retrieval — good enough to demo the HOP structure itself."""
    q_tokens = set(tokenize(query))
    scored = [(len(q_tokens & set(tokenize(text))), key, text) for key, text in corpus.items()]
    scored.sort(reverse=True)
    return scored[0][2]  # best match


def extract_entity_naive(text, after_word):
    """Extremely crude entity extraction for demo purposes: grab the capitalized
    phrase following a keyword. Real code should use structured output (Day 3)."""
    words = text.split()
    for i, w in enumerate(words):
        if w.lower().startswith(after_word) and i + 2 < len(words):
            return " ".join(words[i+1:i+3]).strip(",.")
    return None


def experiment_2_multi_hop():
    original_question = "What's the revenue of the company that acquired Acme's biggest competitor?"
    print(f"\nQuestion: {original_question}")

    # Hop 1: find Acme's biggest competitor
    hop1_result = simple_retrieve("Acme biggest competitor", CORPUS)
    print(f"\nHop 1 query: 'Acme biggest competitor'\n  -> retrieved: {hop1_result!r}")
    competitor = extract_entity_naive(hop1_result, "is")
    print(f"  -> extracted entity: {competitor}")

    # Hop 2: find who acquired that competitor — the query DEPENDS on hop 1's result
    hop2_query = f"{competitor} acquired by"
    hop2_result = simple_retrieve(hop2_query, CORPUS)
    print(f"\nHop 2 query: {hop2_query!r}\n  -> retrieved: {hop2_result!r}")
    acquirer = extract_entity_naive(hop2_result, "acquired")
    print(f"  -> extracted entity: {acquirer}")

    # Hop 3: find that acquirer's revenue
    hop3_query = f"{acquirer} revenue"
    hop3_result = simple_retrieve(hop3_query, CORPUS)
    print(f"\nHop 3 query: {hop3_query!r}\n  -> retrieved: {hop3_result!r}")

    print("\nCheck: hop 2's query literally could not have been written before hop 1 finished —")
    print("it contains hop 1's output as a search term. That dependency is the entire reason")
    print("this needs a loop instead of a query plan written upfront (experiment 1's approach).")


# -----------------------------------------------------------
# 3. Self-critique on weak evidence (15 min)
#    A checkable "is this evidence strong enough" function — no
#    API call needed for the check itself, only for the final answer.
# -----------------------------------------------------------
def evidence_strength(query, retrieved_text, min_overlap=2):
    """Crude but checkable: how many query terms actually appear in the evidence?
    A real system would combine this with rerank scores from Day 8."""
    q_tokens = set(tokenize(query)) - {"the", "a", "is", "of", "what", "how"}
    overlap = q_tokens & set(tokenize(retrieved_text))
    is_strong = len(overlap) >= min_overlap
    return is_strong, overlap


def experiment_3_self_critique():
    cases = [
        ("Acme biggest competitor", CORPUS["competitor"]),        # strong: directly on-topic
        ("Acme R&D spending percentage", CORPUS["unrelated_1"]),  # weak: query and evidence genuinely don't overlap
        ("Globex sponsorship activities", CORPUS["unrelated_2"]), # relevant evidence, but flagged weak anyway — see check below
    ]

    for query, evidence in cases:
        is_strong, overlap = evidence_strength(query, evidence)
        print(f"\nQuery: {query!r}")
        print(f"  Evidence: {evidence!r}")
        print(f"  Overlapping terms: {overlap}")
        print(f"  Strong enough to answer from: {is_strong}")

        if not is_strong:
            print("  -> Action: re-query with broader/different terms rather than answering from this.")

    print("\nCheck: for the R&D-spending query, the evidence about office relocation is")
    print("completely irrelevant, but a plain retrieval pass would still return SOMETHING —")
    print("this is exactly the case where a system without self-critique generates a")
    print("plausible-sounding but ungrounded answer instead of recognizing the miss.")
    print("\nAlso notice: the Globex sponsorship case was flagged WEAK even though the evidence")
    print("genuinely is about sponsorship — 'sponsorship' and 'sponsors' don't share a token,")
    print("so plain word-overlap misses the match. This crude check has real false negatives;")
    print("a production self-critique step should ask a model 'does this evidence answer the")
    print("question' rather than count overlapping words — which is exactly why this experiment's")
    print("mechanism is a stand-in, not the real technique.")


# -----------------------------------------------------------
# 4. Full loop: plan -> retrieve -> critique -> re-query or answer (15 min)
# -----------------------------------------------------------
def experiment_4_full_agentic_loop(question, max_hops=3):
    scratchpad = []

    for hop in range(1, max_hops + 1):
        query_prompt = f"""Question: {question}
        What you know so far: {scratchpad if scratchpad else '(nothing yet)'}
        What is the single next thing you need to look up? Reply with just a short search query."""
        query = ask(query_prompt, temperature=0)

        evidence = simple_retrieve(query, CORPUS)
        is_strong, overlap = evidence_strength(query, evidence)

        scratchpad.append({"hop": hop, "query": query, "evidence": evidence, "strong": is_strong})
        print(f"\nHop {hop}: query={query!r} -> strong={is_strong}")

        if not is_strong:
            print("  Weak evidence — would reformulate query here rather than proceeding.")
            continue  # in a real loop: reformulate before retrying, don't just repeat

        decide_prompt = f"""Question: {question}
        Evidence gathered so far: {scratchpad}
        Do you have enough to answer confidently? Reply YES or NO."""
        decision = ask(decide_prompt, temperature=0)
        if "yes" in decision.lower():
            break

    if any(not h["strong"] for h in scratchpad[-1:]):
        print(f"\nStopped after {len(scratchpad)} hops without strong evidence for the final step.")
        print("Honest output: 'I wasn't able to find sufficient evidence to answer confidently.'")
    else:
        print(f"\nProceeding to generate a final grounded answer from {len(scratchpad)} hop(s) of evidence.")


if __name__ == "__main__":
    experiment_2_multi_hop()
    experiment_3_self_critique()

    # experiment_1_query_planning()
    # experiment_4_full_agentic_loop("What's the revenue of the company that acquired Acme's biggest competitor?")