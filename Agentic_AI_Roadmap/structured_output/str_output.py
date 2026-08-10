"""
60-MIN BUILD: Structured outputs
===================================
4 experiments, ~15 min each. Run one at a time.

pip install pydantic
Fill in ask() once, every experiment reuses it.
"""

import json
import os
from groq import Groq
from dotenv import load_dotenv
from pydantic import BaseModel, field_validator, ValidationError

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def ask(prompt, temperature=0.7):
    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content


# -----------------------------------------------------------
# 1. JSON schema: prompt-level vs strict instruction (15 min)
#    Same task, weak instruction vs a strict one. Compare how
#    often the output is clean, parseable JSON.
# -----------------------------------------------------------
def experiment_1_json_schema():
    weak_prompt = "Give me info about a laptop: name, price, in stock."

    strict_prompt = """Return ONLY a JSON object, no other text, matching exactly:
{"name": string, "price": number, "in_stock": boolean}

Task: Give me info about a laptop."""

    weak = ask(weak_prompt, temperature=0.5)
    strict = ask(strict_prompt, temperature=0.5)

    def is_clean_json(text):
        try:
            json.loads(text)
            return True
        except json.JSONDecodeError:
            return False

    print(f"\nWeak prompt output: {weak}\n-> clean JSON: {is_clean_json(weak)}")
    print(f"\nStrict prompt output: {strict}\n-> clean JSON: {is_clean_json(strict)}")
    print("\nCheck: did the weak prompt add commentary before/after the JSON?")


# -----------------------------------------------------------
# 2. Pydantic validation (15 min)
#    Parse the model's output into a typed object. Catch bad values.
# -----------------------------------------------------------
class Invoice(BaseModel):
    vendor: str
    amount: float
    currency: str

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("amount must be positive")
        return v


def experiment_2_pydantic():
    prompt = """Return ONLY JSON: {"vendor": string, "amount": number, "currency": string}
    Task: Extract from "Invoice from Acme Corp for -50 USD" """

    raw = ask(prompt, temperature=0)
    print(f"\nRaw output: {raw}")

    try:
        invoice = Invoice.model_validate_json(raw)
        print(f"Parsed OK: {invoice}")
    except ValidationError as e:
        print(f"Validation failed: {e}")

    print("\nCheck: did the negative amount in the source text slip through, or did Pydantic catch it?")


# -----------------------------------------------------------
# 3. Retry on parse failure (15 min)
#    On validation failure, feed the actual error back and try again.
# -----------------------------------------------------------
def experiment_3_retry():
    prompt = """Return ONLY JSON: {"vendor": string, "amount": number, "currency": string}
    Task: Extract from "Invoice from Acme Corp for -50 USD" """

    for attempt in range(1, 4):
        raw = ask(prompt, temperature=0)
        try:
            invoice = Invoice.model_validate_json(raw)
            print(f"\nAttempt {attempt}: SUCCESS -> {invoice}")
            return invoice
        except ValidationError as e:
            print(f"\nAttempt {attempt}: FAILED -> {e}")
            prompt = f"{prompt}\n\nYour last output failed validation: {e}\nFix it and return only valid JSON."

    print("\nGave up after 3 attempts.")
    print("Check: did the error-specific feedback change the output, or did it repeat the same mistake?")


# -----------------------------------------------------------
# 4. Tool/function schema (15 min)
#    Describe a fake tool, ask the model to produce matching arguments.
# -----------------------------------------------------------
def experiment_4_tool_schema():
    tool_schema = {
        "name": "book_flight",
        "parameters": {
            "origin": "airport code, e.g. DEL",
            "destination": "airport code, e.g. JFK",
            "date": "date in YYYY-MM-DD format, must be in the future",
        },
    }

    prompt = f"""Given this tool schema: {json.dumps(tool_schema)}
    Return ONLY JSON matching the parameters for: "Book me a flight from Delhi to New York next Friday." """

    raw = ask(prompt, temperature=0)
    print(f"\nModel's tool call arguments: {raw}")

    try:
        args = json.loads(raw)
        has_all = all(k in args for k in tool_schema["parameters"])
        print(f"All required parameters present: {has_all}")
    except json.JSONDecodeError:
        print("Not valid JSON — the model didn't follow the tool schema.")

    print("\nCheck: did it resolve 'next Friday' into an actual date, or leave it vague?")


# -----------------------------------------------------------
if __name__ == "__main__":
    print("==========================================")
    print("1. experiment_1_json_schema()")
    print("==========================================")
    experiment_1_json_schema()

    print("\n==========================================")
    print("2. experiment_2_pydantic()")
    print("==========================================")
    experiment_2_pydantic()

    print("\n==========================================")
    print("3. experiment_3_retry()")
    print("==========================================")
    experiment_3_retry()

    print("\n==========================================")
    print("4. experiment_4_tool_schema()")
    print("==========================================")
    experiment_4_tool_schema()