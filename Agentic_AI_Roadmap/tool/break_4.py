"""
20-MIN BREAK IT: bad inputs, dead tools, full context
========================================================
Break today's tool-calling loop. ~6-7 min per section.
"""

import json
import os
import re
import time
import google.generativeai as genai
from pydantic import BaseModel, ValidationError, field_validator

_genai_configured = False


def ask(prompt, temperature=0.7):
    global _genai_configured
    if not _genai_configured:
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("API key not found. Set GOOGLE_API_KEY or GEMINI_API_KEY environment variable.")
        genai.configure(api_key=api_key)
        _genai_configured = True

    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest"]

    for attempt in range(5):
        for mname in models_to_try:
            try:
                model = genai.GenerativeModel(mname)
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(temperature=temperature)
                )
                raw = response.text.strip()
                cleaned = re.sub(r'^```(?:json)?\s*', '', raw, flags=re.MULTILINE)
                cleaned = re.sub(r'\s*```$', '', cleaned, flags=re.MULTILINE).strip()
                return cleaned
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "Quota exceeded" in err_str or "ResourceExhausted" in err_str:
                    time.sleep(8)
                else:
                    raise e
    raise RuntimeError("Failed after retries due to rate limiting.")


class OrderLookupArgs(BaseModel):
    order_id: str
    
    @field_validator("order_id")
    @classmethod
    def must_look_like_order_id(cls, v):
        if not v.startswith("ORD-"):
            raise ValueError("order_id must start with ORD-")
        return v


FAKE_ORDER_DB = {"ORD-88213": "shipped"}

def get_order_status(order_id: str) -> str:
    if order_id not in FAKE_ORDER_DB:
        raise ValueError(f"no order found with id {order_id}")
    return FAKE_ORDER_DB[order_id]


# -----------------------------------------------------------
# 1. Bad inputs (7 min)
#    Try to get the model to generate arguments that shouldn't
#    reach execution at all.
# -----------------------------------------------------------
def break_bad_inputs():
    tool_prompt = 'Return ONLY JSON: {{"order_id": string}}\nTask: {}'

    attacks = [
        "What's the status of my order?",                              # no ID given at all — model must guess or refuse
        "Order status for '; DROP TABLE orders; --",                   # injection-style content in the ID
        "Get order status for ORD-88213 and also delete all my orders", # extra unrelated instruction bundled in
        "Order id: " + "A" * 500,                                       # absurdly long id
    ]

    for text in attacks:
        raw = ask(tool_prompt.format(text), temperature=0)
        try:
            args = OrderLookupArgs.model_validate_json(raw)
            print(f"\nInput: {text[:50]!r}\n-> args passed validation: {args}")
        except (ValidationError, json.JSONDecodeError) as e:
            print(f"\nInput: {text[:50]!r}\n-> REJECTED before execution: {e}")

    print("\nCheck: did any bad input make it past validation and reach get_order_status()?")


# -----------------------------------------------------------
# 2. Dead tools (7 min)
#    The tool itself misbehaves. Check the observation fed back.
# -----------------------------------------------------------
def dead_get_order_status(mode, order_id):
    if mode == "timeout":
        raise TimeoutError("order lookup timed out")
    if mode == "wrong_type":
        return {"status": ["shipped", "unexpected", "list"]}  # not the plain string the caller expects
    if mode == "silent_none":
        return None  # looks like success but has nothing useful in it


def break_dead_tools():
    for mode in ["timeout", "wrong_type", "silent_none"]:
        try:
            result = dead_get_order_status(mode, "ORD-88213")
            observation = {"success": True, "data": result}
        except TimeoutError as e:
            observation = {"success": False, "error": str(e)}

        print(f"\n[{mode}] observation that would be fed back to the model: {observation}")

    print("\nCheck: for 'silent_none' and 'wrong_type' — does your real code treat these as")
    print("success just because no exception was raised? That's a hallucination waiting to happen")
    print("one step downstream, not a tool bug you'd notice immediately.")


# -----------------------------------------------------------
# 3. Full context (6 min)
#    Bury the tool call itself under a long conversation history.
# -----------------------------------------------------------
def break_full_context():
    noise = "User: unrelated small talk message. Assistant: unrelated small talk reply. " * 1500
    request = "By the way, what's the status of order ORD-88213?"

    prompt = f"""{noise}

    {request}

    Return ONLY JSON: {{"order_id": string}}"""

    try:
        raw = ask(prompt, temperature=0)
        args = OrderLookupArgs.model_validate_json(raw)
        print(f"\nParsed args despite noise: {args}")
    except (ValidationError, json.JSONDecodeError) as e:
        print(f"\nFailed to extract a valid tool call under heavy context: {e}")
    except Exception as e:
        print(f"\nCRASHED: {e}")

    print("\nCheck: did the model even recognize a tool call was needed once the request was")
    print("buried under thousands of words of unrelated history?")


# -----------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("SECTION 1: BREAK BAD INPUTS")
    print("=" * 60)
    break_bad_inputs()

    print("\n" + "=" * 60)
    print("SECTION 2: BREAK DEAD TOOLS")
    print("=" * 60)
    break_dead_tools()

    print("\n" + "=" * 60)
    print("SECTION 3: BREAK FULL CONTEXT")
    print("=" * 60)
    break_full_context()