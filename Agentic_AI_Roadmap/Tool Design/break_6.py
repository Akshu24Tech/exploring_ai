"""
20-MIN BREAK IT: bad inputs, dead tools, full context
========================================================
Break today's tool design choices. ~6-7 min per section.
"""

import json

def ask(prompt, temperature=0.3):
    raise NotImplementedError("Add your API call inside ask() first.")


# -----------------------------------------------------------
# 1. Bad inputs (7 min)
#    Try to push a permission-capped tool past its boundary
#    through the arguments themselves, not just a plain over-cap amount.
# -----------------------------------------------------------
def issue_refund_capped(order_id, amount, cap=100):
    if amount > cap:
        return {"success": False, "error": f"amount {amount} exceeds cap of {cap}"}
    return {"success": True, "refunded": amount}


def break_bad_inputs():
    attacks = [
        50,           # normal, should pass
        100.0001,     # just barely over, tests boundary handling not just obvious abuse
        -50,          # negative "refund" — an unintended way to move money the other direction
        "100",        # string instead of number — does the comparison even work safely?
    ]

    for amount in attacks:
        try:
            result = issue_refund_capped("ORD-1", amount)
            print(f"\namount={amount!r} -> {result}")
        except TypeError as e:
            print(f"\namount={amount!r} -> CRASHED comparing types: {e}")

    print("\nCheck: did the negative amount get silently accepted as 'under the cap'?")
    print("A permission cap that only checks an upper bound has a lower-bound hole.")


# -----------------------------------------------------------
# 2. Dead tools (7 min)
#    A tool that's non-idempotent AND flaky at the same time —
#    the worst combination for an agent loop that retries on failure.
# -----------------------------------------------------------
CHARGES = []

def flaky_non_idempotent_charge(order_id, amount, attempt):
    CHARGES.append({"order_id": order_id, "amount": amount})
    if attempt == 1:
        # looks like it failed to the caller...
        raise ConnectionError("timeout waiting for payment gateway response")
    # ...but the charge above already went through on attempt 1 regardless.
    return {"success": True}


def break_dead_tools():
    CHARGES.clear()
    for attempt in (1, 2):
        try:
            result = flaky_non_idempotent_charge("ORD-1", 50, attempt)
            print(f"\nAttempt {attempt}: {result}")
        except ConnectionError as e:
            print(f"\nAttempt {attempt}: appeared to fail -> {e}")
            print("  (An agent would reasonably retry here, believing nothing happened.)")

    print(f"\nActual charges recorded: {CHARGES}")
    print(f"Check: the 'failed' first attempt still recorded a charge. Total charges: {len(CHARGES)}")
    print("This is the exact scenario idempotency design is meant to prevent —")
    print("a tool that looks safe to retry but isn't.")


# -----------------------------------------------------------
# 3. Full context (6 min)
#    A long error message vs. a long, noisy tool result — which
#    survives being pushed toward the end of a big prompt.
# -----------------------------------------------------------
def break_full_context():
    noise = "Unrelated prior tool call and result, repeated. " * 2000
    good_error = ("order_id 'ORD-99999' not found. Order IDs are 5 digits after 'ORD-'. "
                  "Ask the user to confirm the ID.")

    prompt = f"""{noise}

    Tool result: {{"success": false, "error": "{good_error}"}}

    What should you do next?"""

    try:
        response = ask(prompt, temperature=0.3)
        print(f"\nResponse after a well-designed error was buried in noise:\n{response}")
    except Exception as e:
        print(f"\nCRASHED: {e}")

    print("\nCheck: even a well-designed, recoverable error message only helps if it survives")
    print("the context budget — a great error buried at position 2000 of 2000 can still get ignored.")


# -----------------------------------------------------------
if __name__ == "__main__":
    break_bad_inputs()
    break_dead_tools()

    # break_full_context()