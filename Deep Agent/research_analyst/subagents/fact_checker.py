"""
Subagent: Fact Checker
Responsibility: identify specific claims in the content and rate each one
as HIGH / MEDIUM / LOW confidence.
"""

from deepagents import create_deep_agent


def extract_claims(content: str) -> str:
    """
    Parse research content and return a numbered list of specific,
    verifiable claims (statistics, attributed findings, named dates).
    """
    claim_markers = ["%", "$", "study", "report", "found", "shows",
                     "projected", "published", "2024", "2025", "2030"]
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    claims = [l for l in lines if any(m in l for m in claim_markers)][:6]

    if not claims:
        return "No specific verifiable claims found — content is general."

    return "Claims to verify:\n" + "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))


def build() -> object:
    return create_deep_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[extract_claims],
        system_prompt=(
            "You are a fact-checking agent. "
            "Call extract_claims to isolate specific statements, then rate each one:\n\n"
            "  ✅ HIGH   — well-established, widely corroborated\n"
            "  ⚠️  MEDIUM — plausible but needs primary source\n"
            "  ❌ LOW    — speculative or unsubstantiated\n\n"
            "One line of reasoning per claim. "
            "End with OVERALL RELIABILITY: High / Medium / Low."
        ),
    )


def run(raw_content: str) -> str:
    agent = build()
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Fact-check this:\n\n{raw_content}"}]
    })
    return result["messages"][-1].content
