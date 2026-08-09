"""
60-MIN BUILD: Prompting for control
======================================
5 experiments, ~10-12 min each. Run one at a time.

Fill in ask() once, every experiment reuses it.
"""

import json
from collections import Counter

def ask(prompt, system=None, temperature=0.7):
    # Plug in your Groq/Gemini/Ollama call here.
    # If your provider takes a separate system message, use `system`.
    raise NotImplementedError("Add your API call inside ask() first.")


# -----------------------------------------------------------
# 1. System prompt control (10 min)
#    Same question, different system prompts. Compare behavior.
# -----------------------------------------------------------
def experiment_1_system_prompt():
    question = "A user is angry their order is 3 days late. Reply to them."

    system_prompts = [
        None,  # no system prompt at all
        "You are a terse support bot. Max 1 sentence replies.",
        "You are a warm, empathetic support agent. Always apologize first.",
        "You are terse. Also always apologize first and explain empathetically.",  # conflicting on purpose
    ]

    for sp in system_prompts:
        answer = ask(question, system=sp, temperature=0.3)
        print(f"\nSystem: {sp}\n-> {answer}")

    print("\nCheck: did the conflicting system prompt (#4) pick one instruction and drop the other?")


# -----------------------------------------------------------
# 2. Few-shot vs zero-shot (10 min)
#    Same task, with and without examples. Compare format consistency.
# -----------------------------------------------------------
def experiment_2_few_shot():
    task = "Classify the sentiment of: 'The delivery guy was rude but the food was great.'"

    zero_shot = ask(f"{task} Answer with one word: positive, negative, or mixed.")

    few_shot_prompt = """Classify sentiment as one word: positive, negative, or mixed.

Text: "Loved the food, terrible service."
Sentiment: mixed

Text: "Best meal I've had all year."
Sentiment: positive

Text: '{}'
Sentiment:""".format("The delivery guy was rude but the food was great.")

    few_shot = ask(few_shot_prompt)

    print(f"\nZero-shot: {zero_shot}")
    print(f"Few-shot: {few_shot}")
    print("\nCheck: is the few-shot answer more consistently just the one word, no extra explanation?")


# -----------------------------------------------------------
# 3. Task decomposition (12 min)
#    One giant prompt vs. broken into steps. Compare reliability.
# -----------------------------------------------------------
def experiment_3_decomposition():
    review = "This laptop is fast but the battery dies in 2 hours and support never replied to my email."

    # One shot: everything at once
    one_shot = ask(f"""Read this review, extract the pros and cons, and rate it 1-5: "{review}" """)

    # Decomposed: separate steps
    pros_cons = ask(f'List pros and cons from this review as JSON: "{review}"')
    rating = ask(f"Given these pros and cons, rate 1-5: {pros_cons}")

    print(f"\nOne-shot (everything at once): {one_shot}")
    print(f"\nDecomposed step 1 (extract): {pros_cons}")
    print(f"Decomposed step 2 (rate using step 1's output): {rating}")
    print("\nCheck: is the decomposed rating easier to trust, since you can see exactly what it rated?")


# -----------------------------------------------------------
# 4. Self-consistency (12 min)
#    Ask the same question N times, vote on the most common answer.
# -----------------------------------------------------------
def experiment_4_self_consistency():
    question = "Is 8191 a prime number? Answer only yes or no."

    answers = [ask(question, temperature=0.8) for _ in range(5)]
    vote = Counter(a.strip().lower() for a in answers).most_common(1)[0]

    print(f"\nAll 5 answers: {answers}")
    print(f"Majority vote: {vote[0]} ({vote[1]}/5)")
    print("\nCheck: did any single sample disagree with the majority? That's the exact risk self-consistency catches.")


# -----------------------------------------------------------
# 5. Output contract (10 min)
#    Ask for JSON with a prose instruction, then validate it in code.
# -----------------------------------------------------------
def experiment_5_output_contract():
    prompt = 'Return ONLY JSON with keys "name" and "role" for: "Akshu is an AI Engineer."'
    raw = ask(prompt, temperature=0)

    try:
        data = json.loads(raw)
        has_required_fields = "name" in data and "role" in data
    except json.JSONDecodeError:
        data, has_required_fields = None, False

    print(f"\nRaw output: {raw}")
    print(f"Valid JSON with required fields: {has_required_fields}")

    if not has_required_fields:
        retry = ask(f"That wasn't valid. {prompt} Only output the JSON object, nothing else.")
        print(f"Retry: {retry}")

    print("\nCheck: did the model add any text before/after the JSON on the first try?")


# -----------------------------------------------------------
if __name__ == "__main__":
    experiment_1_system_prompt()

    # experiment_2_few_shot()
    # experiment_3_decomposition()
    # experiment_4_self_consistency()
    # experiment_5_output_contract()