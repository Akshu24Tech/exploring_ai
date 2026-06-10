"""
Skill: Citation Formatter
==========================
Reusable tool that any agent can call to turn a raw URL + title + snippet
into a properly formatted citation.

Why a skill and not inline code:
  The same formatting logic is needed by the Web Searcher (to tag its sources)
  and could be needed by the Orchestrator (to cite claims in the final report).
  Defining it once here means both agents get identical, consistent output.

Supported styles: APA (default), MLA, plain
"""

from datetime import date


def format_citation(
    title: str,
    url: str,
    author: str = "Unknown",
    year: str | None = None,
    style: str = "apa",
) -> str:
    """
    Format a web source into a citation string.

    Args:
        title:  Title of the page or article.
        url:    Full URL of the source.
        author: Author name or organisation name.
        year:   Publication year (defaults to current year if omitted).
        style:  Citation style — 'apa', 'mla', or 'plain'.

    Returns a formatted citation string.
    """
    y = year or str(date.today().year)

    if style == "apa":
        return f"{author}. ({y}). *{title}*. Retrieved from {url}"

    if style == "mla":
        return f'{author}. "{title}." Web. {y}. <{url}>'

    # plain — clean one-liner for bullet lists
    return f"{title} ({y}) — {url}"
