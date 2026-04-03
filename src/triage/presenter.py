"""
Triage Presenter

Formats triage session data into clean, readable text for display
during an interactive Claude Code triage session.

Each format_* method returns a string ready to be printed or included
in a Claude response during the triage session.
"""

from typing import List, Optional

from src.models.email import (
    ActionPlan,
    DeduplicatedDigest,
    JunkAnalysis,
    JunkSuggestion,
    SystemNotification,
)


class TriagePresenter:
    """
    Formats triage session data into readable text blocks.
    """

    def format_session_intro(self, summary: dict) -> str:
        """
        Opening summary shown at the start of a triage session.
        """
        run_label = "noon" if summary["run_type"] == "noon" else "4pm"
        totals = summary["totals"]
        total = sum(totals.values()) - totals.get("deferred_from_prior", 0)

        lines = [
            f"📬  Triage ready — {run_label} run",
            f"    Window: {summary['window']}",
            "",
        ]

        if totals.get("deferred_from_prior"):
            lines.append(
                f"  ↩️  {totals['deferred_from_prior']} deferred from last session (shown first)"
            )

        if totals.get("eod_urgent"):
            lines.append(
                f"  ⚠️  {totals['eod_urgent']} EOD-urgent item{'s' if totals['eod_urgent'] != 1 else ''}"
            )

        lines += [
            "",
            "Queue:",
        ]

        if totals["system_notifications"]:
            lines.append(f"  1. 🔔  System notifications   — {totals['system_notifications']} item{'s' if totals['system_notifications'] != 1 else ''}")
        if totals["actions"]:
            lines.append(f"  2. ⚡  Action required        — {totals['actions']} email{'s' if totals['actions'] != 1 else ''}")
        if totals["newsletters"]:
            lines.append(f"  3. 📰  Newsletters            — {totals['newsletters']} unique {'story' if totals['newsletters'] == 1 else 'stories'}")
        if totals["junk"]:
            lines.append(f"  4. 🗑️  Junk                   — {totals['junk']} email{'s' if totals['junk'] != 1 else ''}")

        if total == 0:
            lines = ["✅  Nothing to triage — your inbox is clear."]

        lines += ["", "Let's start. I'll go category by category."]
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # System notifications
    # -------------------------------------------------------------------------

    def format_system_notifications(
        self,
        notifications: List[SystemNotification],
        aggregate: str,
    ) -> str:
        action_items = [n for n in notifications if n.requires_action]
        info_items = [n for n in notifications if not n.requires_action]

        lines = ["🔔  SYSTEM NOTIFICATIONS", ""]

        if aggregate:
            lines += [aggregate, ""]

        if action_items:
            lines.append("Items needing your action:")
            for i, n in enumerate(action_items, 1):
                link = f"  → {n.deep_link}" if n.deep_link else ""
                deadline = f" (due {n.deadline})" if n.deadline else ""
                lines.append(f"  {i}. [{n.system}] {n.raw_summary}{deadline}{link}")
            lines.append("")

        if info_items:
            lines.append("FYI (no action needed):")
            for n in info_items:
                lines.append(f"  · [{n.system}] {n.raw_summary}")
            lines.append("")

        lines.append("→ Acknowledge all and archive? [y / pick numbers to skip / ask]")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Action emails
    # -------------------------------------------------------------------------

    def format_action_email(
        self,
        plan: ActionPlan,
        from_address: str,
        subject: str,
        snippet: str,
        is_eod_urgent: bool = False,
    ) -> str:
        urgent_flag = "  ⚠️  EOD-URGENT" if is_eod_urgent else ""
        lines = [
            f"⚡  ACTION REQUIRED{urgent_flag}",
            f"    From:    {from_address}",
            f"    Subject: {subject or '(no subject)'}",
            f"    Preview: {snippet or '(no preview)'}",
            "",
        ]

        if plan.draft_set:
            lines.append(f"    Context: {plan.draft_set.thread_summary}")
            lines.append("")
            lines.append("    Draft options:")
            for i, opt in enumerate(plan.draft_set.options, 1):
                style_label = {
                    "short_ack": "Short ACK",
                    "full_reply": "Full reply",
                    "decline": "Decline / defer",
                }.get(opt.style, opt.style)
                # Show first 120 chars of body as preview
                preview = opt.body[:120].replace("\n", " ")
                if len(opt.body) > 120:
                    preview += "…"
                lines.append(f"    [{i}] {style_label}: \"{preview}\"")
            lines.append("")

        if plan.task:
            due = f" 📅 {plan.task.due_date}" if plan.task.due_date else ""
            lines.append(f"    📝  Suggested task: {plan.task.title}{due}")
            lines.append("")

        options = []
        if plan.draft_set:
            options.append("[1/2/3] use draft")
        if plan.task:
            options.append("[t] create task")
        options += ["[s] skip", "[d] defer", "[?] ask me more"]
        lines.append("    → " + " · ".join(options))

        return "\n".join(lines)

    def format_draft_full(self, plan: ActionPlan, style: str) -> str:
        """Show the complete text of a specific draft option."""
        if not plan.draft_set:
            return "(No draft available)"
        option = next((o for o in plan.draft_set.options if o.style == style), None)
        if not option:
            return f"(Draft style '{style}' not found)"
        lines = [
            f"Subject: {option.subject}",
            "",
            option.body,
        ]
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Newsletters
    # -------------------------------------------------------------------------

    def format_newsletter_digest(self, digest: DeduplicatedDigest) -> str:
        if not digest.stories:
            return "📰  NEWSLETTERS\n\n    No significant stories this session."

        lines = [
            f"📰  NEWSLETTERS — {len(digest.stories)} unique {'story' if len(digest.stories) == 1 else 'stories'}",
            "",
        ]
        for i, story in enumerate(digest.stories, 1):
            sources = " + ".join(story.sources)
            lines.append(f"  {i}. {story.headline}  [{sources}]")
            lines.append(f"     {story.summary}")
            lines.append("")

        lines.append("→ Archive all newsletters? [y / ask about a story (e.g. \"tell me more about #2\") / n]")
        return "\n".join(lines)

    def format_story_detail(self, story_index: int, digest: DeduplicatedDigest, full_content: Optional[str] = None) -> str:
        """Detailed view of a single newsletter story for follow-up questions."""
        if story_index < 1 or story_index > len(digest.stories):
            return f"(Story {story_index} not found)"
        story = digest.stories[story_index - 1]
        lines = [
            f"Story {story_index}: {story.headline}",
            f"Sources: {', '.join(story.sources)}",
            "",
            story.summary,
        ]
        if full_content:
            lines += ["", "--- Full newsletter content ---", full_content[:2000]]
            if len(full_content) > 2000:
                lines.append("... [truncated]")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Junk
    # -------------------------------------------------------------------------

    def format_junk_batch(self, analyses: List[JunkAnalysis]) -> str:
        if not analyses:
            return "🗑️  JUNK\n\n    No junk emails this session."

        delete_list = [a for a in analyses if a.suggestion == JunkSuggestion.DELETE]
        unsub_list = [a for a in analyses if a.suggestion == JunkSuggestion.UNSUBSCRIBE]
        review_list = [a for a in analyses if a.suggestion == JunkSuggestion.REVIEW]

        lines = [f"🗑️  JUNK — {len(analyses)} email{'s' if len(analyses) != 1 else ''}", ""]

        if delete_list:
            lines.append(f"  Suggest DELETE ({len(delete_list)}):")
            for a in delete_list:
                conf = f"{int(a.confidence * 100)}%"
                repeat = f" ({a.sender_history_count}x seen)" if a.sender_history_count > 1 else ""
                lines.append(f"    · {a.email_id[:12]}… — {a.reason} [{conf}]{repeat}")
            lines.append("")

        if unsub_list:
            lines.append(f"  Suggest UNSUBSCRIBE ({len(unsub_list)}):")
            for a in unsub_list:
                lines.append(f"    · {a.email_id[:12]}… — {a.reason}")
            lines.append("")

        if review_list:
            lines.append(f"  Review yourself ({len(review_list)}) — low confidence:")
            for a in review_list:
                lines.append(f"    · {a.email_id[:12]}… — {a.reason}")
            lines.append("")

        lines.append("→ Confirm all suggestions? [y / n / pick to change]")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Deferred items
    # -------------------------------------------------------------------------

    def format_deferred(self, deferred: list) -> str:
        if not deferred:
            return ""
        lines = [f"↩️  DEFERRED FROM LAST SESSION — {len(deferred)} item{'s' if len(deferred) != 1 else ''}", ""]
        for i, item in enumerate(deferred, 1):
            lines.append(f"  {i}. [{item.original_category}] {item.subject}  (from {item.from_address})")
        lines += ["", "→ Process now? [y] or skip again [s]"]
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Session complete
    # -------------------------------------------------------------------------

    def format_session_complete(self, tasks_created: int, drafts_saved: int) -> str:
        lines = ["✅  Triage session complete.", ""]
        if tasks_created:
            lines.append(f"  📝  {tasks_created} task{'s' if tasks_created != 1 else ''} written to Obsidian Backlog")
        if drafts_saved:
            lines.append(f"  ✉️   {drafts_saved} draft{'s' if drafts_saved != 1 else ''} saved to Gmail Drafts")
        if not tasks_created and not drafts_saved:
            lines.append("  No tasks or drafts created this session.")
        lines += ["", "See you at the next run."]
        return "\n".join(lines)
