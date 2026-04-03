"""
Junk Detection Prompts
"""

JUNK_SYSTEM = """You are an email spam and junk classifier.
Determine whether an email should be deleted, unsubscribed from, or reviewed manually.
Respond with JSON only."""

JUNK_TEMPLATE = """Analyse this email and suggest what to do with it.

From: {from_address}
Subject: {subject}
Snippet: {snippet}
Prior junk emails from this sender: {sender_count}

Respond with this exact JSON:
{{
  "suggestion": "<one of: delete | unsubscribe | review>",
  "confidence": <float 0.0-1.0>,
  "reason": "<one sentence>"
}}

Guidelines:
- delete: Spam, unsolicited cold outreach, fraudulent or phishing emails
- unsubscribe: Legitimate marketing or newsletters the user subscribed to but no longer wants
- review: Ambiguous — could be legitimate, show to the user to decide
- Higher sender_count = higher confidence to delete/unsubscribe"""


def build_junk_prompt(from_address: str, subject: str, snippet: str, sender_count: int) -> str:
    return JUNK_TEMPLATE.format(
        from_address=from_address,
        subject=subject or "(no subject)",
        snippet=snippet or "(no preview)",
        sender_count=sender_count,
    )
