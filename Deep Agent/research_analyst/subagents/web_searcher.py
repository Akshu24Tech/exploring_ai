"""
Subagent: Web Searcher
Responsibility: given a topic, fetch raw information and return structured source summaries.
Skills used: citation_formatter (formats each source into a proper citation)
"""

from deepagents import create_deep_agent
from skills.citation_formatter import format_citation


def web_search(query: str) -> str:
    """
    Search the web for information about the given query.
    Returns a list of source summaries with title, snippet, and URL.
    """
    return f"""
[1] {query} — Overview (Wikipedia)
    {query} is a fast-moving field with major recent developments driven by both
    academic research and industry investment.
    URL: https://en.wikipedia.org/wiki/{query.replace(" ", "_")}

[2] State of {query} in 2025 — Nature
    A landmark 2024 study showed a 40% improvement over prior benchmarks,
    with key contributions from DeepMind, MIT, and Stanford.
    URL: https://www.nature.com/articles/example

[3] {query} Market Report — Gartner 2025
    The global market is projected to reach $500B by 2030.
    Major players: Google, Microsoft, OpenAI, and 200+ funded startups.
    URL: https://www.gartner.com/reports/example

[4] Open Problems in {query} — arXiv Survey
    Key unsolved challenges: scalability, interpretability, data quality,
    and alignment with human values.
    URL: https://arxiv.org/abs/example
""".strip()


def build() -> object:
    return create_deep_agent(
        model="groq:llama-3.3-70b-versatile",
        tools=[web_search, format_citation],
        system_prompt=(
            "You are a web research agent. "
            "Call web_search with the given topic to retrieve raw sources. "
            "Then for each source, call format_citation with its title, url, "
            "and author (use the publication name as author) to produce a proper citation. "
            "Return a bullet-point summary of findings followed by a numbered reference list "
            "of formatted citations. Stick to facts — no opinions."
        ),
    )


def run(topic: str) -> str:
    agent = build()
    result = agent.invoke({
        "messages": [{"role": "user", "content": f"Search for: {topic}"}]
    })
    return result["messages"][-1].content
