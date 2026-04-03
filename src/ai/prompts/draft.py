"""
Email Draft Generation Prompts
"""

DRAFT_SYSTEM = """You are a writing assistant helping a CPO draft email replies.
You know their communication style: {tone}, {style}.
You always write in first person as if you are them.
Generate exactly 3 reply options. Respond with JSON only."""

DRAFT_TEMPLATE = """Generate 3 reply options for this email.

--- THREAD ---
{thread}
--- END THREAD ---

The most recent email requiring a reply:
From: {from_address}
Subject: {subject}

Generate these 3 options:
1. short_ack — A brief acknowledgement (2-4 sentences). Buys time without committing.
2. full_reply — A substantive response that addresses the email's key points directly.
3. decline — A polite way to decline, defer, or redirect without closing the door.

Respond with this exact JSON:
{{
  "options": [
    {{
      "style": "short_ack",
      "subject": "Re: {subject}",
      "body": "<reply body>"
    }},
    {{
      "style": "full_reply",
      "subject": "Re: {subject}",
      "body": "<reply body>"
    }},
    {{
      "style": "decline",
      "subject": "Re: {subject}",
      "body": "<reply body>"
    }}
  ],
  "thread_summary": "<one sentence summary of what this email thread is about>"
}}

Rules:
- Sign off with: {signature}
- Do not invent facts or commitments not supported by the thread
- Match the tone already established in the thread
- short_ack should be under 60 words
- full_reply should be under 200 words"""


ACTION_DETECTION_SYSTEM = """You are an email triage assistant.
Determine whether an email requires a reply, a non-email action (task), or both.
Respond with JSON only."""

ACTION_DETECTION_TEMPLATE = """Analyse this email and determine what action is needed.

From: {from_address}
Subject: {subject}
Body:
{body}

Respond with this exact JSON:
{{
  "action_type": "<one of: reply_only | task_only | both>",
  "needs_reply": <true|false>,
  "needs_task": <true|false>,
  "task_title": "<concise task title if needs_task is true, else null>",
  "task_due_date": "<YYYY-MM-DD if a deadline is detectable, else null>",
  "task_tags": ["<tag1>", "<tag2>"],
  "reasoning": "<one sentence>"
}}

Guidelines:
- reply_only: The email is a question or request directed at you requiring a written response
- task_only: The email notifies you of something requiring offline action (review a doc, attend a meeting, approve in a system)
- both: The email needs a reply AND creates a task
- task_tags should reflect the topic (e.g. "budget", "hiring", "roadmap") — 1-2 tags max, no # prefix"""


def build_draft_prompt(
    thread_text: str,
    from_address: str,
    subject: str,
    tone: str,
    style: str,
    signature: str,
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)"""
    system = DRAFT_SYSTEM.format(tone=tone, style=style)
    prompt = DRAFT_TEMPLATE.format(
        thread=thread_text,
        from_address=from_address,
        subject=subject or "(no subject)",
        signature=signature,
    )
    return system, prompt


def build_action_detection_prompt(
    from_address: str, subject: str, body: str
) -> str:
    max_body = 2000
    if len(body) > max_body:
        body = body[:max_body] + "\n... [truncated]"
    return ACTION_DETECTION_TEMPLATE.format(
        from_address=from_address,
        subject=subject or "(no subject)",
        body=body,
    )
