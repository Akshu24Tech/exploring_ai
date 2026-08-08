"""
60-MIN BUILD: How LLMs actually behave
========================================
Companion to today's 30-min learning doc. Same day, hands on — five
timed experiments, ~10-15 min each. Run sections independently by
commenting/uncommenting the calls at the bottom.

SETUP (2 min):
  pip install tiktoken groq google-generativeai --break-system-packages
  Fill in ONE of the call_llm() backends below (Groq / Gemini / Ollama)
  to match your stack. Everything in EXPERIMENT 1 runs with zero API key.
"""

import time
import tiktoken

def call_llm(prompt: str, temperature: float = 0.7, model: str = "default") -> str:
    from groq import Groq
    client = Groq(api_key="")
    resp = client.chat.completions.create(
        model= "llama-3.1-8b-instant",
        messages= [{"role": "user", "content":prompt}],
        temperature=temperature,)
    return resp.choices[0].messge.content

    # --- Option A: Groq -----------------------------------------------
    # from groq import Groq
    # client = Groq(api_key="YOUR_KEY")
    # resp = client.chat.completions.create(
    #     model=model if model != "default" else "llama-3.1-8b-instant",
    #     messages=[{"role": "user", "content": prompt}],
    #     temperature=temperature,
    # )
    # return resp.choices[0].message.content

    # --- Option B: Gemini -----------------------------------------------
    # import google.generativeai as genai
    # genai.configure(api_key="YOUR_KEY")
    # m = genai.GenerativeModel(model if model != "default" else "gemini-1.5-flash")
    # resp = m.generate_content(prompt, generation_config={"temperature": temperature})
    # return resp.text

    # --- Option C: Ollama (local, no key needed) -------------------------
    # import requests
    # resp = requests.post("http://localhost:11434/api/generate", json={
    #     "model": model if model != "default" else "llama3.1",
    #     "prompt": prompt,
    #     "options": {"temperature": temperature},
    #     "stream": False,
    # })
    # return resp.json()["response"]

    raise NotImplementedError("Fill in call_llm() with one provider above before running experiments 2-5.")


# ---------------------------------------------------------------------------
# EXPERIMENT 1 (10 min) — Tokenizer playground. No API key needed.
# Goal: SEE tokenization happen so "1 token != 1 word" stops being abstract.
# ---------------------------------------------------------------------------

def _approx_encode(text: str):
    """Offline fallback if tiktoken can't download its vocab file (no internet).
    Crude subword-ish splitter — good enough to FEEL the effect, not byte-exact."""
    import re
    return re.findall(r"[A-Za-z]+|\d|[^\sA-Za-z\d]", text)


def experiment_1_tokenizer():
    try:
        enc = tiktoken.get_encoding("cl100k_base")  # same family as GPT-4-class tokenizers
        def encode(t): return enc.encode(t)
        def decode(ids): return [enc.decode([t]) for t in ids]
    except Exception:
        print("[tiktoken couldn't reach the internet to download its vocab — using an")
        print(" approximate offline tokenizer instead. Re-run with internet for exact counts.]\n")
        def encode(t): return _approx_encode(t)
        def decode(pieces): return pieces

    samples = [
        "The agent routes the request to the right tool.",
        "1234567890",                     # numbers split unpredictably
        "strawberry",                     # letter-counting failure source
        "श्रीमती अनीता शर्मा",             # non-English costs more tokens
        "def call_llm(prompt, temperature=0.7):",  # code tokenizes differently too
    ]

    print("=" * 70)
    print("EXPERIMENT 1: Tokenizer playground")
    print("=" * 70)
    for text in samples:
        tokens = encode(text)
        pieces = decode(tokens)
        print(f"\nText: {text!r}")
        print(f"  Token count: {len(tokens)}  (chars: {len(text)}, ratio: {len(text)/max(len(tokens),1):.1f} chars/token)")
        print(f"  Pieces: {pieces}")

    # Build-it task: measure YOUR actual system prompt
    your_system_prompt = """You are a helpful assistant for a school management system.
Always respond in JSON format with fields: status, message, data.
Never reveal internal implementation details to the user."""
    n = len(encode(your_system_prompt))
    print(f"\nYour sample system prompt costs {n} tokens EVERY SINGLE TURN.")
    print("Task: paste your actual agent's system prompt above and re-run. Note the number.")


# ---------------------------------------------------------------------------
# EXPERIMENT 2 (12 min) — "Lost in the middle": context window recall test.
# Goal: prove to yourself that position in context affects recall, not just length.
# ---------------------------------------------------------------------------

def experiment_2_lost_in_the_middle():
    filler = ("The company's cafeteria menu changes weekly. " * 40).strip()
    needle = "The secret project codename is BLUEHERON42."

    positions = {
        "start": needle + " " + filler,
        "middle": filler[:len(filler)//2] + " " + needle + " " + filler[len(filler)//2:],
        "end": filler + " " + needle,
    }

    print("=" * 70)
    print("EXPERIMENT 2: Lost in the middle")
    print("=" * 70)
    for pos, context in positions.items():
        prompt = f"{context}\n\nQuestion: What is the secret project codename? Answer with just the codename."
        answer = call_llm(prompt, temperature=0.0)
        hit = "BLUEHERON42" in answer
        print(f"\nNeedle at [{pos}]: {'HIT' if hit else 'MISS'}  -> model said: {answer.strip()[:80]}")

    print("\nTask: increase `filler` repeat count (40 -> 150) and re-run. Watch 'middle' degrade first.")


# ---------------------------------------------------------------------------
# EXPERIMENT 3 (12 min) — Temperature & sampling comparison.
# Goal: same prompt, different temperature -> see the distribution reshape in practice.
# ---------------------------------------------------------------------------

def experiment_3_temperature():
    prompt = "Write one sentence describing what a database index does."
    temps = [0.0, 0.5, 1.0, 1.3]

    print("=" * 70)
    print("EXPERIMENT 3: Temperature comparison")
    print("=" * 70)
    for t in temps:
        outputs = [call_llm(prompt, temperature=t) for _ in range(3)]
        unique = len(set(o.strip() for o in outputs))
        print(f"\nTemp {t}: {unique}/3 unique outputs")
        for o in outputs:
            print(f"    - {o.strip()[:90]}")

    print("\nTask: note at which temperature you start seeing factually different (not just")
    print("re-worded) claims. That's the point where sampling risk turns into hallucination risk.")


# ---------------------------------------------------------------------------
# EXPERIMENT 4 (12 min) — Grounded vs ungrounded: manufacture a hallucination.
# Goal: watch a model confidently answer something it can't know, then fix it with grounding.
# ---------------------------------------------------------------------------

def experiment_4_hallucination():
    obscure_question = "What was the exact attendance figure at the Gurugram University AI symposium on March 3rd this year?"

    ungrounded_prompt = obscure_question
    grounded_prompt = (
        "Context: No attendance data is available for this event in our records.\n\n"
        f"Question: {obscure_question}\n"
        "Instruction: Only answer from the context above. If the context doesn't contain "
        "the answer, say you don't have that information — do not guess."
    )

    print("=" * 70)
    print("EXPERIMENT 4: Grounded vs ungrounded")
    print("=" * 70)
    ungrounded = call_llm(ungrounded_prompt, temperature=0.7)
    grounded = call_llm(grounded_prompt, temperature=0.7)

    print(f"\nUngrounded answer:\n  {ungrounded.strip()}")
    print(f"\nGrounded (RAG-style) answer:\n  {grounded.strip()}")
    print("\nTask: check if the ungrounded version invented a specific number. That's a live")
    print("hallucination you just reproduced on demand — now you've seen the fix pattern too.")


# ---------------------------------------------------------------------------
# EXPERIMENT 5 (10 min) — Model selection: quality vs latency vs cost, same task.
# Goal: get real numbers instead of vibes for "which model should this node use".
# ---------------------------------------------------------------------------

def experiment_5_model_selection():
    task = "Extract the person's name and role from this text as JSON: 'Akshu is an AI Engineer building agentic systems.'"
    models_to_try = ["small-model-name", "large-model-name"]  # fill in real model strings for your provider

    print("=" * 70)
    print("EXPERIMENT 5: Model selection — same task, different models")
    print("=" * 70)
    for model in models_to_try:
        start = time.time()
        try:
            out = call_llm(task, temperature=0.0, model=model)
        except Exception as e:
            out = f"[error: {e}]"
        elapsed = time.time() - start
        print(f"\nModel: {model}")
        print(f"  Latency: {elapsed:.2f}s")
        print(f"  Output: {out.strip()[:120]}")

    print("\nTask: for a simple extraction task like this, did the bigger model actually")
    print("do better? If not, that's your routing signal — send this node to the small model.")


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    experiment_1_tokenizer()

    # Uncomment as you fill in call_llm() above:
    # experiment_2_lost_in_the_middle()
    # experiment_3_temperature()
    # experiment_4_hallucination()
    # experiment_5_model_selection()