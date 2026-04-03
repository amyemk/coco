"""
Newsletter Summarisation and Deduplication Prompts
"""

SUMMARISE_SYSTEM = """You are a research assistant helping a CPO stay informed without reading every newsletter.
Summarise concisely. Focus on what's actionable, novel, or strategically relevant.
Ignore sponsor content, ads, and filler. Respond with JSON only."""

SUMMARISE_TEMPLATE = """Summarise this newsletter email in 3-5 bullet points.

From: {source}
Subject: {subject}

Body:
{body}

Respond with this exact JSON:
{{
  "source": "{source}",
  "key_points": [
    "<bullet 1>",
    "<bullet 2>",
    "<bullet 3>"
  ]
}}

Rules:
- Each bullet point should be one concise sentence
- Focus on news, trends, product releases, or strategic insights
- Skip promotions, events, and administrative content
- If the email is purely promotional with no informational value, return an empty key_points array"""


DEDUP_SYSTEM = """You are a research editor. You have summaries from multiple newsletters.
Your job is to merge them into a single deduplicated digest — one entry per unique story.
If the same story appears in multiple sources, merge them and list all sources.
Respond with JSON only."""

DEDUP_TEMPLATE = """Deduplicate these newsletter summaries into unique stories.

{summaries_json}

Respond with this exact JSON:
{{
  "stories": [
    {{
      "headline": "<short headline>",
      "summary": "<2-3 sentence summary>",
      "sources": ["<newsletter name 1>", "<newsletter name 2>"]
    }}
  ]
}}

Rules:
- Merge stories covering the same news event or topic
- Keep stories that are genuinely different, even if tangentially related
- Order by relevance to a CPO at a tech/data company (product, AI, strategy first)
- Maximum 8 stories in the output"""


def build_summarise_prompt(source: str, subject: str, body: str) -> str:
    # Truncate very long bodies to stay within context limits
    max_body = 3000
    if len(body) > max_body:
        body = body[:max_body] + "\n... [truncated]"
    return SUMMARISE_TEMPLATE.format(source=source, subject=subject or "(no subject)", body=body)


def build_dedup_prompt(summaries_json: str) -> str:
    return DEDUP_TEMPLATE.format(summaries_json=summaries_json)
