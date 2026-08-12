"""
60-MIN BUILD: The agent loop (ReAct)
========================================
4 experiments, ~15 min each. Run one at a time.

pip install pydantic
Fill in ask() once, every experiment reuses it.
"""

import json
import os
from dotenv import load_dotenv, find_dotenv
from groq import Groq
from pydantic import BaseModel

load_dotenv(find_dotenv(usecwd=True))
client = Groq()

def ask(prompt, temperature=0.3):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content


# A tiny fake tool for the whole file to reuse.
FAKE_ORDER_DB = {"ORD-88213": "shipped", "ORD-11111": "processing"}

def get_order_status(order_id: str) -> str:
    if order_id not in FAKE_ORDER_DB:
        raise ValueError(f"no order found with id {order_id}")
    return FAKE_ORDER_DB[order_id]


# -----------------------------------------------------------
# 1. Reason step alone (15 min)
#    Ask the model to think before acting. Check if the thought
#    actually constrains the next step, or is just filler.
# -----------------------------------------------------------
def experiment_1_reason():
    task = "What's the status of order ORD-88213?"

    prompt = f"""Task: {task}
    Available tool: get_order_status(order_id)

    First write a Thought explaining what you need to do and why.
    Then write an Action: either "get_order_status(<id>)" or "final_answer(<text>)"."""

    response = ask(prompt)
    print(f"\nModel's reasoning + action:\n{response}")
    print("\nCheck: does the Thought actually explain WHY this action, or is it generic filler")
    print("like 'I will help the user' that could precede any action at all?")


# -----------------------------------------------------------
# 2. One full reason -> act -> observe cycle (15 min)
#    Wire the three steps together manually, once.
# -----------------------------------------------------------
def experiment_2_one_cycle():
    task = "What's the status of order ORD-99999?"  # doesn't exist — forces a failure observation

    reason_act_prompt = f"""Task: {task}
    Available tool: get_order_status(order_id)
    Write a Thought, then an Action as JSON: {{"tool": "get_order_status", "order_id": "..."}}"""

    reasoning = ask(reason_act_prompt)
    print(f"\nReasoning + action:\n{reasoning}")

    # Pretend we parsed an order_id out of the model's action (kept manual/simple on purpose here)
    order_id = "ORD-99999"
    try:
        result = get_order_status(order_id)
        observation = {"success": True, "data": result}
    except ValueError as e:
        observation = {"success": False, "error": str(e)}

    final_prompt = f"""Task: {task}
    You took action get_order_status(order_id="{order_id}").
    Observation: {json.dumps(observation)}
    Write your final answer to the user."""
    final_answer = ask(final_prompt, temperature=0.5)

    print(f"\nObservation: {observation}")
    print(f"Final answer: {final_answer}")
    print("\nCheck: when the observation was a failure, did the final answer say so honestly?")


# -----------------------------------------------------------
# 3. Multi-step loop with an iteration cap (15 min)
#    The real ReAct loop: repeat until done or capped.
# -----------------------------------------------------------
def run_react_loop(task, max_iterations=4):
    scratchpad = []

    for i in range(1, max_iterations + 1):
        history = "\n".join(scratchpad) if scratchpad else "(none yet)"
        prompt = f"""Task: {task}
        Available tool: get_order_status(order_id)
        History so far:
        {history}

        Write a Thought, then either:
        Action: get_order_status(<id>)
        or
        Action: final_answer(<your answer>)"""

        response = ask(prompt, temperature=0.3)
        scratchpad.append(f"Step {i}: {response}")
        print(f"\n--- Iteration {i} ---\n{response}")

        if "final_answer" in response.lower():
            return response, scratchpad, "completed"

        # crude extraction for demo purposes — real code should parse this properly (see Day 4)
        order_id = "ORD-88213"  # stand-in: pretend we parsed this from the response
        try:
            result = get_order_status(order_id)
            observation = {"success": True, "data": result}
        except ValueError as e:
            observation = {"success": False, "error": str(e)}
        scratchpad.append(f"Observation: {json.dumps(observation)}")

    return None, scratchpad, "iteration_cap_reached"


def experiment_3_full_loop():
    answer, scratchpad, status = run_react_loop("What's the status of order ORD-88213?")
    print(f"\nLoop ended: {status}")
    if status == "iteration_cap_reached":
        print("Returning an honest partial result instead of pretending we're done:")
        print(f"  'I wasn't able to finish within the step limit. Here's what happened: {scratchpad[-2:]}'")
    else:
        print(f"Final answer: {answer}")


# -----------------------------------------------------------
# 4. Scratchpad growth and compression (15 min)
#    Watch the scratchpad grow, then compress the old parts.
# -----------------------------------------------------------
def compress_scratchpad(scratchpad, keep_recent=2):
    if len(scratchpad) <= keep_recent:
        return scratchpad
    older = scratchpad[:-keep_recent]
    recent = scratchpad[-keep_recent:]
    summary = f"[Summary of {len(older)} earlier steps: {len(older)} tool calls made, see recent steps for detail]"
    return [summary] + recent


def experiment_4_scratchpad():
    fake_scratchpad = [f"Step {i}: thought + action + observation text..." for i in range(1, 9)]

    print(f"\nFull scratchpad ({len(fake_scratchpad)} entries):")
    for entry in fake_scratchpad:
        print(f"  {entry}")

    compressed = compress_scratchpad(fake_scratchpad, keep_recent=2)
    print(f"\nCompressed scratchpad ({len(compressed)} entries):")
    for entry in compressed:
        print(f"  {entry}")

    print("\nCheck: at what scratchpad length would this compression have started saving")
    print("meaningful tokens in your actual agent? Try it with your real system prompt size.")


# -----------------------------------------------------------
if __name__ == "__main__":
    print("=== Experiment 1: Reason ===")
    experiment_1_reason()

    print("\n=== Experiment 2: One Cycle ===")
    experiment_2_one_cycle()

    print("\n=== Experiment 3: Full ReAct Loop ===")
    experiment_3_full_loop()

    print("\n=== Experiment 4: Scratchpad Compression ===")
    experiment_4_scratchpad()