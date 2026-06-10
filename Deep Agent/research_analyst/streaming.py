"""
Streaming utility for Deep Agents.

stream_agent() is a drop-in replacement for agent.invoke() that:
  - prints tokens to stdout in real-time as the model generates them
  - returns the full response text when done (same usage pattern as invoke)

Usage:
    text = stream_agent(agent, "your prompt here", label="Orchestrator")
"""

import sys


def stream_agent(agent, prompt: str, label: str = "Agent") -> str:
    """
    Stream an agent's response token-by-token to stdout.
    Returns the complete response text.

    Args:
        agent:  a create_deep_agent() instance
        prompt: the user message string
        label:  display name shown in the header line
    """
    print(f"\n-- {label} " + "-" * max(0, 50 - len(label)))

    full_text = ""
    input_payload = {"messages": [{"role": "user", "content": prompt}]}

    for chunk in agent.stream(
        input_payload,
        stream_mode="messages",
        subgraphs=True,
        version="v2",
    ):
        if chunk.get("type") == "messages":
            token, metadata = chunk["data"]
            content = token.content if isinstance(token.content, str) else ""
            if content:
                print(content, end="", flush=True)
                full_text += content

    print()  # newline after stream ends
    return full_text
