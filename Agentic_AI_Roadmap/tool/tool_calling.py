"""
60-MIN BUILD: Tool calling from scratch
==========================================
4 experiments, ~15 min each. Run one at a time.

pip install pydantic
Fill in ask() once, every experiment reuses it.
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


# -----------------------------------------------------------
# 1. Expose a function (15 min)
#    Write a good tool description. Compare against a bad one.
# -----------------------------------------------------------
def experiment_1_expose():
    bad_tool = {"name": "get_data", "parameters": {"id": "the id"}}

    good_tool = {
        "name": "get_order_status",
        "description": "Look up the current shipping status of a customer order by its order ID.",
        "parameters": {
            "order_id": "string, format ORD-XXXXX, required",
        },
    }

    request = "What's the status of order ORD-88213?"

    for tool in [bad_tool, good_tool]:
        prompt = f"""Tool available: {json.dumps(tool)}
        Return ONLY JSON with the arguments to call this tool for: "{request}" """
        answer = ask(prompt, temperature=0)
        print(f"\nTool: {tool['name']}\n-> {answer}")

    print("\nCheck: did the vague tool ('get_data', 'id: the id') produce the right argument value anyway,")
    print("or did the ambiguity show up in a wrong/missing order_id?")


# -----------------------------------------------------------
# 2. Parse arguments into a validated shape (15 min)
#    Never trust the raw dict — parse into Pydantic first.
# -----------------------------------------------------------
class OrderLookupArgs(BaseModel):
    order_id: str

    @field_validator("order_id")
    @classmethod
    def must_look_like_order_id(cls, v):
        if not v.startswith("ORD-"):
            raise ValueError("order_id must start with ORD-")
        return v


def experiment_2_parse():
    prompt = """Return ONLY JSON: {"order_id": string}
    Task: get the order status for "my last order, I think it started with ORD" """

    raw = ask(prompt, temperature=0)
    print(f"\nRaw model output: {raw}")

    try:
        args = OrderLookupArgs.model_validate_json(raw)
        print(f"Parsed and validated: {args}")
    except ValidationError as e:
        print(f"Rejected before execution: {e}")

    print("\nCheck: did the model guess a plausible-looking but incomplete order_id,")
    print("and did validation catch it before it reached a real function call?")


# -----------------------------------------------------------
# 3. Execute safely (15 min)
#    A tool with validation, a scope limit, and a timeout — not a blank check.
# -----------------------------------------------------------
FAKE_ORDER_DB = {"ORD-88213": "shipped", "ORD-11111": "processing"}

def get_order_status(order_id: str) -> str:
    # Scoped: only reads from this fixed lookup, never writes, never takes free-form queries.
    if order_id not in FAKE_ORDER_DB:
        raise ValueError(f"no order found with id {order_id}")
    return FAKE_ORDER_DB[order_id]


def execute_tool_safely(args: OrderLookupArgs):
    try:
        result = get_order_status(args.order_id)
        return {"success": True, "data": result}
    except ValueError as e:
        return {"success": False, "error": str(e)}


def experiment_3_execute():
    test_ids = ["ORD-88213", "ORD-99999", "'; DROP TABLE orders; --"]

    for order_id in test_ids:
        try:
            args = OrderLookupArgs(order_id=order_id)
            result = execute_tool_safely(args)
        except ValidationError as e:
            result = {"success": False, "error": f"validation rejected input: {e}"}
        print(f"\norder_id={order_id!r} -> {result}")

    print("\nCheck: did the injection-style input ever reach get_order_status(),")
    print("or did validation stop it before execution?")


# -----------------------------------------------------------
# 4. Feed the observation back (15 min)
#    Success and failure both need to go back to the model clearly.
# -----------------------------------------------------------
def experiment_4_observation_loop():
    user_request = "What's the status of order ORD-99999?"

    tool_prompt = f"""Return ONLY JSON: {{"order_id": string}}
    Task: {user_request}"""
    raw = ask(tool_prompt, temperature=0)
    args = OrderLookupArgs.model_validate_json(raw)
    observation = execute_tool_safely(args)

    followup_prompt = f"""User asked: {user_request}
    Tool result: {json.dumps(observation)}
    Reply to the user based on the tool result above."""
    final_answer = ask(followup_prompt, temperature=0.5)

    print(f"\nObservation fed back to model: {observation}")
    print(f"Final answer to user: {final_answer}")
    print("\nCheck: when the order wasn't found, did the model tell the user honestly,")
    print("or did it make up a plausible-sounding status anyway?")


# -----------------------------------------------------------
if __name__ == "__main__":
    print("=" * 60)
    print("EXPERIMENT 1: EXPOSE A FUNCTION")
    print("=" * 60)
    experiment_1_expose()

    print("\n" + "=" * 60)
    print("EXPERIMENT 2: PARSE ARGUMENTS INTO A VALIDATED SHAPE")
    print("=" * 60)
    experiment_2_parse()

    print("\n" + "=" * 60)
    print("EXPERIMENT 3: EXECUTE SAFELY")
    print("=" * 60)
    experiment_3_execute()

    print("\n" + "=" * 60)
    print("EXPERIMENT 4: FEED THE OBSERVATION BACK")
    print("=" * 60)
    experiment_4_observation_loop()