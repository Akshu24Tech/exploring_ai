"""
60-MIN BUILD: How LLMs actually behave
=========================================
5 small experiments, ~10 min each. Run one at a time.

STEP 1: pip install tiktoken
STEP 2: Fill in the ask() function below with your LLM (Groq/Gemini/Ollama).
STEP 3: Uncomment one experiment at the bottom and run the file.
"""

import tiktoken
import time
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# -----------------------------------------------------------
# Fill this in once. Every experiment below just calls ask().
# -----------------------------------------------------------
def ask(prompt, temperature=0.7, model="llama-3.1-8b-instant"):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content


# -----------------------------------------------------------
# 1. See how text turns into tokens (no API needed)
# -----------------------------------------------------------
def experiment_1_tokens():
    enc = tiktoken.get_encoding("cl100k_base")

    texts = [
        "The agent routes the request to the right tool.",
        "1234567890",
        "strawberry",
    ]

    for text in texts:
        tokens = enc.encode(text)
        print(f"\n'{text}'")
        print(f"-> {len(tokens)} tokens: {[enc.decode([t]) for t in tokens]}")


# -----------------------------------------------------------
# 2. Put a fact at the start, middle, and end of a long text.
#    See where the model actually finds it.
# -----------------------------------------------------------
def experiment_2_context_window():
    filler = "The office wifi password changes every month. " * 50
    fact = "The secret code is BLUEHERON42."

    tests = {
        "fact at start": fact + filler,
        "fact in middle": filler[:500] + fact + filler[500:],
        "fact at end": filler + fact,
    }

    for label, text in tests.items():
        prompt = f"{text}\n\nWhat is the secret code?"
        answer = ask(prompt, temperature=0)
        print(f"\n{label}: {answer}")


# -----------------------------------------------------------
# 3. Same question, different temperatures. Compare answers.
# -----------------------------------------------------------
def experiment_3_temperature():
    question = "Describe what a database index does, in one sentence."

    for temp in [0, 0.7, 1.3]:
        answer = ask(question, temperature=temp)
        print(f"\ntemperature {temp}: {answer}")


# -----------------------------------------------------------
# 4. Ask something the model can't know. Then give it context
#    and tell it to say "I don't know" if it's not there.
# -----------------------------------------------------------
def experiment_4_hallucination():
    question = "How many people attended the XYZ conference on March 3rd?"

    no_context = ask(question)
    with_context = ask(
        f"Context: no attendance number is recorded.\n"
        f"Question: {question}\n"
        f"If the answer isn't in the context, say you don't know."
    )

    print(f"\nWithout grounding: {no_context}")
    print(f"With grounding: {with_context}")


# -----------------------------------------------------------
# 5. Same task, small model vs big model. Compare speed + quality.
# -----------------------------------------------------------
def experiment_5_model_choice():
    task = "Return JSON with name and role from: 'Akshu is an AI Engineer.'"

    for model_name, model in [("small model (llama-3.1-8b-instant)", "llama-3.1-8b-instant"), ("big model (llama-3.3-70b-versatile)", "llama-3.3-70b-versatile")]:
        start = time.time()
        answer = ask(task, model=model)
        print(f"\n{model_name} ({time.time() - start:.1f}s): {answer}")


# -----------------------------------------------------------
# Run all experiments
# -----------------------------------------------------------
if __name__ == "__main__":
    print("==========================================")
    print("1. experiment_1_tokens()")
    print("==========================================")
    experiment_1_tokens()

    print("\n==========================================")
    print("2. experiment_2_context_window()")
    print("==========================================")
    experiment_2_context_window()

    print("\n==========================================")
    print("3. experiment_3_temperature()")
    print("==========================================")
    experiment_3_temperature()

    print("\n==========================================")
    print("4. experiment_4_hallucination()")
    print("==========================================")
    experiment_4_hallucination()

    print("\n==========================================")
    print("5. experiment_5_model_choice()")
    print("==========================================")
    experiment_5_model_choice()