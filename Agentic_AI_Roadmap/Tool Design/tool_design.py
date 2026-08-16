"""
60-MIN BUILD: Tool design principles
========================================
4 experiments, ~15 min each. Run one at a time.

Fill in ask() once, every experiment reuses it.
"""

import json

def ask(prompt, temperature=0.3):
    # Plug in your Groq/Gemini/Ollama call here.
    raise NotImplementedError("Add your API call inside ask() first.")


# -----------------------------------------------------------
# 1. Granularity: coarse vs. right-sized tool (15 min)
#    A bundled tool that fails all-or-nothing, vs. split steps
#    where partial success is visible.
# -----------------------------------------------------------
def process_order_coarse(order_id, should_fail_at="none"):
    """Everything in one call. If it fails, you don't know what already happened."""
    steps_done = []
    steps_done.append("validated")
    if should_fail_at == "charge":
        return {"success": False, "error": "payment failed", "steps_done": steps_done}
    steps_done.append("charged")
    if should_fail_at == "email":
        return {"success": False, "error": "email service down", "steps_done": steps_done}
    steps_done.append("email_sent")
    return {"success": True, "steps_done": steps_done}


def validate_order(order_id):
    return {"success": True}

def charge_payment(order_id, should_fail=False):
    if should_fail:
        return {"success": False, "error": "payment failed, card declined"}
    return {"success": True}

def send_confirmation(order_id, should_fail=False):
    if should_fail:
        return {"success": False, "error": "email service temporarily down"}
    return {"success": True}


def experiment_1_granularity():
    print("\nCoarse tool, failing at the email step:")
    result = process_order_coarse("ORD-1", should_fail_at="email")
    print(f"  {result}")
    print("  -> Was the customer charged? You can only tell by reading steps_done carefully.")

    print("\nGranular tools, same scenario:")
    v = validate_order("ORD-1")
    c = charge_payment("ORD-1", should_fail=False)
    e = send_confirmation("ORD-1", should_fail=True)
    print(f"  validate: {v}\n  charge: {c}\n  confirm_email: {e}")
    print("  -> Immediately clear: order was validated AND charged, only email failed.")
    print("     A retry only needs to re-run send_confirmation, not the whole order.")


# -----------------------------------------------------------
# 2. Idempotency: same call twice, with and without protection (15 min)
# -----------------------------------------------------------
CHARGES = []  # simulates a payment ledger

def charge_card_unsafe(order_id, amount):
    CHARGES.append({"order_id": order_id, "amount": amount})
    return {"success": True, "charge_count_for_order": sum(1 for c in CHARGES if c["order_id"] == order_id)}


CHARGED_ORDERS = set()  # simulates tracking what's already been charged

def charge_card_idempotent(order_id, amount):
    if order_id in CHARGED_ORDERS:
        return {"success": True, "note": "already charged, no-op", "charge_count_for_order": 1}
    CHARGED_ORDERS.add(order_id)
    return {"success": True, "charge_count_for_order": 1}


def experiment_2_idempotency():
    print("\nUnsafe version, called twice (simulating an agent retry):")
    r1 = charge_card_unsafe("ORD-1", 50)
    r2 = charge_card_unsafe("ORD-1", 50)
    print(f"  1st call: {r1}\n  2nd call: {r2}")
    print(f"  -> Customer charged {r2['charge_count_for_order']} times for one order.")

    print("\nIdempotent version, called twice:")
    r1 = charge_card_idempotent("ORD-2", 50)
    r2 = charge_card_idempotent("ORD-2", 50)
    print(f"  1st call: {r1}\n  2nd call: {r2}")
    print(f"  -> Customer charged {r2['charge_count_for_order']} time, second call was a safe no-op.")


# -----------------------------------------------------------
# 3. Permissions: tiered tools instead of one unbounded tool (15 min)
# -----------------------------------------------------------
def issue_refund_unbounded(order_id, amount):
    """No ceiling at all — whatever the model generates, goes through."""
    return {"success": True, "refunded": amount}


def issue_refund_capped(order_id, amount, cap=100):
    """Schema-level permission boundary: can't refund more than the cap in one call."""
    if amount > cap:
        return {
            "success": False,
            "error": f"amount {amount} exceeds this tool's cap of {cap}. "
                      f"Use request_large_refund_approval for amounts over {cap}.",
        }
    return {"success": True, "refunded": amount}


def experiment_3_permissions():
    print("\nUnbounded tool, model asked to refund an unusually large amount:")
    print(f"  {issue_refund_unbounded('ORD-1', 5000)}")
    print("  -> Went through with zero friction, whatever the model generated.")

    print("\nCapped tool, same request:")
    print(f"  {issue_refund_capped('ORD-1', 5000)}")
    print("  -> Rejected at the schema/logic level with a path to the right escalation tool.")


# -----------------------------------------------------------
# 4. Error messages: generic vs. recoverable (15 min)
#    Feed both kinds back to the model and compare what it does next.
# -----------------------------------------------------------
def experiment_4_error_messages():
    task = "Look up the status of order ORD-99999."

    generic_error = {"success": False, "error": "Error: 500"}
    good_error = {
        "success": False,
        "error": "order_id 'ORD-99999' not found. Order IDs are 5 digits after 'ORD-'. "
                  "Ask the user to confirm the ID, or look up by customer name instead.",
    }

    for label, observation in [("generic", generic_error), ("recoverable", good_error)]:
        prompt = f"""Task: {task}
        Tool result: {json.dumps(observation)}
        What do you do next? Either propose a specific next action, or explain what you'd ask the user."""
        response = ask(prompt, temperature=0.3)
        print(f"\n[{label} error] model's next step:\n  {response}")

    print("\nCheck: did the generic error produce a vague 'let me try again' response,")
    print("while the recoverable error produced a specific, useful next step?")


# -----------------------------------------------------------
if __name__ == "__main__":
    experiment_1_granularity()
    experiment_2_idempotency()
    experiment_3_permissions()

    # experiment_4_error_messages()