"""
Newsletter Summarizer

Summarises individual newsletter emails and deduplicates stories
across multiple sources within a triage session window.

Session-aware: tracks which newsletter editions have already been
presented so the 4pm run doesn't repeat content from the noon run.
"""

import json
from typing import List

import structlog

from src.ai.claude_client import ClaudeClient
from src.ai.prompts.newsletter import (
    SUMMARISE_SYSTEM,
    build_summarise_prompt,
    build_dedup_prompt,
)
from src.config.settings import Settings
from src.models.email import (
    DeduplicatedDigest,
    Email,
    NewsletterSummary,
    Story,
)

logger = structlog.get_logger()


class NewsletterSummarizer:
    """
    Two-stage newsletter processor:
      1. Summarise each newsletter email individually (parallel-safe)
      2. Deduplicate stories across all summaries in the session window
    """

    def __init__(self, settings: Settings, claude_client: ClaudeClient):
        self.settings = settings
        self.claude = claude_client
        self._model = settings.config.ai.models.newsletter_summary

    async def summarize(self, email: Email) -> NewsletterSummary:
        """
        Summarise a single newsletter email into 3-5 key points.

        The full email body is retained in the summary so that follow-up
        questions during the triage session have access to the original content.

        Args:
            email: An email classified as NEWSLETTER

        Returns:
            NewsletterSummary with key_points and full_content
        """
        source = self._extract_source_name(email)
        body = email.body or email.snippet or ""

        prompt = build_summarise_prompt(
            source=source,
            subject=email.subject or "",
            body=body,
        )

        try:
            raw = await self.claude.complete_json(
                prompt=prompt,
                model=self._model,
                system=SUMMARISE_SYSTEM,
            )
            data = json.loads(raw)
            key_points = data.get("key_points", [])
        except Exception as e:
            logger.warning("newsletter_summarize_failed", email_id=email.id, error=str(e))
            key_points = [f"(Summary failed: {e})"]

        return NewsletterSummary(
            email_id=email.id,
            source=source,
            key_points=key_points,
            full_content=body,  # Kept for follow-up questions in triage session
        )

    async def summarize_batch(self, emails: List[Email]) -> List[NewsletterSummary]:
        """
        Summarise a list of newsletter emails.
        """
        summaries = []
        for email in emails:
            summary = await self.summarize(email)
            summaries.append(summary)
            logger.debug(
                "newsletter_summarized",
                email_id=email.id,
                source=summary.source,
                points=len(summary.key_points),
            )
        return summaries

    async def deduplicate(self, summaries: List[NewsletterSummary]) -> DeduplicatedDigest:
        """
        Merge summaries from multiple newsletters into a single deduplicated digest.

        Stories that appear in more than one newsletter are merged into a single
        entry that lists all sources.

        Args:
            summaries: Summaries from the current triage window (already session-filtered)

        Returns:
            DeduplicatedDigest with unique stories across all sources
        """
        if not summaries:
            return DeduplicatedDigest(stories=[], processed_email_ids=[])

        if len(summaries) == 1:
            # Nothing to deduplicate — convert directly
            s = summaries[0]
            stories = [
                Story(headline=point, summary=point, sources=[s.source])
                for point in s.key_points
            ]
            return DeduplicatedDigest(
                stories=stories,
                processed_email_ids=[s.email_id],
            )

        # Build input for Claude dedup prompt
        summaries_data = [
            {
                "source": s.source,
                "key_points": s.key_points,
            }
            for s in summaries
            if s.key_points  # Skip empty summaries (pure promo)
        ]

        if not summaries_data:
            return DeduplicatedDigest(
                stories=[],
                processed_email_ids=[s.email_id for s in summaries],
            )

        summaries_json = json.dumps(summaries_data, indent=2)
        prompt = build_dedup_prompt(summaries_json)

        try:
            from src.ai.prompts.newsletter import DEDUP_SYSTEM
            raw = await self.claude.complete_json(
                prompt=prompt,
                model=self._model,
                system=DEDUP_SYSTEM,
            )
            data = json.loads(raw)
            stories = [
                Story(
                    headline=s["headline"],
                    summary=s["summary"],
                    sources=s["sources"],
                )
                for s in data.get("stories", [])
            ]
        except Exception as e:
            logger.warning("newsletter_dedup_failed", error=str(e))
            # Fallback: return all points as individual stories
            stories = []
            for s in summaries:
                for point in s.key_points:
                    stories.append(Story(headline=point, summary=point, sources=[s.source]))

        logger.info(
            "newsletter_deduplication_complete",
            input_summaries=len(summaries),
            output_stories=len(stories),
        )

        return DeduplicatedDigest(
            stories=stories,
            processed_email_ids=[s.email_id for s in summaries],
        )

    def _extract_source_name(self, email: Email) -> str:
        """
        Extract a human-readable newsletter name from the email.
        Prefers the sender display name over the raw email address.
        """
        from_address = email.from_address

        # Format: "Display Name <email@domain.com>"
        if "<" in from_address:
            name = from_address.split("<")[0].strip().strip('"')
            if name:
                return name

        # Fall back to domain name
        if "@" in from_address:
            domain = from_address.split("@")[1].rstrip(">").split(".")[0]
            return domain.capitalize()

        return from_address
