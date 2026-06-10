"""
Subagent: Insight Extractor
Responsibility: given raw source content, pull out the most important insights,
trends, breakthroughs, and key players.
Skills used: summarizer skill is applied by the orchestrator before this agent
             runs, so content arrives pre-compressed.
"""

from deepagents import create_deep_agent


def identify_themes(content: str) -> str:
    """
    Scan research content and return metadata about what types of information
    are present: statistics, named entities, trend signals, and future projections.
    """
    has_stats    = any(c in content for c in ["%", "$", "billion", "million"])
    has_names    = any(c in content for c in ["Google", "Microsoft", "OpenAI", "MIT", "Stanford", "DeepMind"])
    has_trends   = any(c in content for c in ["growing", "projected", "increase", "decline", "shift"])
    has_problems = any(c in content for c in ["challenge", "problem", "unsolved", "limitation", "risk"])

    flags = []
    if has_stats:    flags.append("quantitative data present")
    if has_names:    flags.append("key organisations named")
    if has_trends:   flags.append("trend signals detected")
    if has_problems: flags.append("open problems mentioned")

    return "Content scan: " + (", ".join(flags) if flags else "general descriptive content only")


def build() -> object:
    return create_deep_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[identify_themes],
        system_prompt=(
            "You are an insight extraction agent. "
            "Call identify_themes on the content to understand what is present, "
            "then return a structured analysis under exactly these four headings:\n\n"
            "KEY BREAKTHROUGHS\n"
            "MAJOR TRENDS\n"
            "KEY PLAYERS\n"
            "OPEN PROBLEMS\n\n"
            "Keep each section to 2-3 concise bullet points. No padding."
        ),
    )


def run(raw_content: str) -> str:
    agent = build()
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Extract insights from this:\n\n{raw_content}"}]
    })
    return result["messages"][-1].content
