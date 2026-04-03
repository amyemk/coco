#!/usr/bin/env python3
"""
Coco Triage CLI

The entry point for interactive triage sessions in Claude Code.

Usage:
  python scripts/triage.py                    # Print session summary (human-readable)
  python scripts/triage.py --json             # Output full session data as JSON
  python scripts/triage.py action write-task  <session_id> '<task_json>'
  python scripts/triage.py action save-draft  <session_id> <email_id> <style>
  python scripts/triage.py action confirm-junk <session_id> <email_id>
  python scripts/triage.py action mark-reviewed <session_id> <email_id>
  python scripts/triage.py action defer       <session_id> <email_id>
  python scripts/triage.py action complete    <session_id>
  python scripts/triage.py email body         <email_id>
  python scripts/triage.py run now            <noon|afternoon>   # Manual trigger

All action commands print a JSON result: {"ok": true} or {"ok": false, "error": "..."}
This lets Claude Code parse results programmatically.
"""

import json
import sys
from pathlib import Path

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))


def _init():
    from dotenv import load_dotenv
    load_dotenv()
    from src.config.settings import init_settings
    from src.db.connection import init_db, get_db
    settings = init_settings()
    db_path = settings.get_database_path()
    db = init_db(db_path)
    info = db.get_db_info()
    if info.get("table_count", 0) == 0:
        db.initialize_schema()
    return settings


def cmd_status(as_json: bool = False):
    """Load the latest pending session and display a summary."""
    settings = _init()
    from src.triage.session import TriageSession
    from src.triage.presenter import TriagePresenter

    session = TriageSession.load_latest(settings)
    if session is None:
        if as_json:
            print(json.dumps({"session": None, "message": "No pending triage session."}))
        else:
            print("No pending triage session. Pre-processing runs at noon and 4pm.")
        return

    summary = session.get_summary()

    if as_json:
        # Full data dump for Claude Code to parse
        output = {
            "session": summary,
            "junk": [
                {
                    "email_id": a.email_id,
                    "suggestion": a.suggestion.value,
                    "confidence": a.confidence,
                    "reason": a.reason,
                    "sender_history_count": a.sender_history_count,
                }
                for a in session.junk
            ],
            "newsletter_digest": (
                {
                    "stories": [
                        {
                            "index": i + 1,
                            "headline": s.headline,
                            "summary": s.summary,
                            "sources": s.sources,
                        }
                        for i, s in enumerate(session.newsletter_digest.stories)
                    ],
                    "processed_email_ids": session.newsletter_digest.processed_email_ids,
                }
                if session.newsletter_digest
                else None
            ),
            "system_notifications": [
                {
                    "email_id": n.email_id,
                    "system": n.system,
                    "action_type": n.action_type,
                    "entity_name": n.entity_name,
                    "status": n.status,
                    "requires_action": n.requires_action,
                    "raw_summary": n.raw_summary,
                    "deadline": n.deadline.isoformat() if n.deadline else None,
                    "deep_link": n.deep_link,
                }
                for n in session.system_notifications
            ],
            "system_notification_aggregate": session.system_notification_aggregate,
            "actions": [
                {
                    "email_id": a.email_id,
                    "action_type": a.action_type,
                    "is_eod_urgent": session.is_eod_urgent(a.email_id),
                    "draft_options": (
                        [
                            {
                                "style": o.style,
                                "subject": o.subject,
                                "body_preview": o.body[:200],
                                "body": o.body,
                            }
                            for o in a.draft_set.options
                        ]
                        if a.draft_set
                        else []
                    ),
                    "thread_summary": a.draft_set.thread_summary if a.draft_set else None,
                    "task": (
                        {
                            "title": a.task.title,
                            "due_date": a.task.due_date.isoformat() if a.task.due_date else None,
                            "tags": a.task.tags,
                            "source_ref": a.task.source_ref,
                        }
                        if a.task
                        else None
                    ),
                }
                for a in session.actions
            ],
            "deferred": [
                {
                    "email_id": d.email_id,
                    "subject": d.subject,
                    "from_address": d.from_address,
                    "original_category": d.original_category,
                }
                for d in session.deferred
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        presenter = TriagePresenter()
        print(presenter.format_session_intro(summary))
        if session.deferred:
            print()
            print(presenter.format_deferred(session.deferred))


def cmd_action(args: list):
    """Execute a triage action and print JSON result."""
    if len(args) < 2:
        _fail("Usage: triage.py action <command> <session_id> [args...]")

    command = args[0]
    session_id = args[1]

    settings = _init()
    from src.triage.session import TriageSession
    from src.triage.session_store import TriageSessionStore

    # Load session by ID
    store = TriageSessionStore()
    db = store.db
    row = db.fetchone("SELECT * FROM triage_sessions WHERE id = ?", (session_id,))
    if not row:
        _fail(f"Session not found: {session_id}")

    session = TriageSession(session_id=session_id, session_row=dict(row), settings=settings)

    if command == "write-task":
        if len(args) < 3:
            _fail("Usage: action write-task <session_id> '<task_json>'")
        task_data = json.loads(args[2])
        from src.models.email import ObsidianTask
        from datetime import date
        task = ObsidianTask(
            title=task_data["title"],
            due_date=date.fromisoformat(task_data["due_date"]) if task_data.get("due_date") else None,
            tags=task_data.get("tags", []),
            source_ref=task_data.get("source_ref", ""),
            email_id=task_data.get("email_id"),
        )
        ok = session.write_task(task)
        _result(ok, error="Failed to write task — check Obsidian vault path in config.yaml")

    elif command == "save-draft":
        if len(args) < 4:
            _fail("Usage: action save-draft <session_id> <email_id> <style>")
        email_id, style = args[2], args[3]
        draft_id = session.save_draft(email_id, style)
        if draft_id:
            print(json.dumps({"ok": True, "draft_id": draft_id}))
        else:
            print(json.dumps({"ok": False, "error": "Draft save failed or feature disabled"}))

    elif command == "confirm-junk":
        if len(args) < 3:
            _fail("Usage: action confirm-junk <session_id> <email_id>")
        session.confirm_junk(args[2])
        _result(True)

    elif command == "mark-reviewed":
        if len(args) < 3:
            _fail("Usage: action mark-reviewed <session_id> <email_id>")
        session.mark_reviewed(args[2])
        _result(True)

    elif command == "defer":
        if len(args) < 3:
            _fail("Usage: action defer <session_id> <email_id>")
        session.defer(args[2])
        _result(True)

    elif command == "complete":
        session.complete()
        # Count what was done
        row = db.fetchone("SELECT tasks_created, drafts_saved FROM triage_sessions WHERE id = ?", (session_id,))
        tasks = len(json.loads(row["tasks_created"] or "[]")) if row else 0
        drafts = len(json.loads(row["drafts_saved"] or "[]")) if row else 0
        from src.triage.presenter import TriagePresenter
        print(TriagePresenter().format_session_complete(tasks, drafts))

    else:
        _fail(f"Unknown action: {command}")


def cmd_email_body(args: list):
    """Print the full body of an email by ID."""
    if not args:
        _fail("Usage: triage.py email body <email_id>")
    _init()
    from src.repositories.email_repository import EmailRepository
    email = EmailRepository().get_by_id(args[0])
    if not email:
        print(json.dumps({"ok": False, "error": "Email not found"}))
    else:
        print(json.dumps({"ok": True, "body": email.body or "", "subject": email.subject, "from": email.from_address}))


def cmd_run_now(args: list):
    """Manually trigger a triage pre-processing run."""
    import asyncio
    run_type = args[0] if args else "noon"
    if run_type not in ("noon", "afternoon"):
        _fail("run_type must be 'noon' or 'afternoon'")

    settings = _init()
    from src.triage.pre_processor import TriagePreProcessor
    from src.delivery.triage_notification import TriageNotificationSender
    from src.triage.session_store import TriageSessionStore

    async def _run():
        processor = TriagePreProcessor(settings)
        result = await processor.run(run_type=run_type)
        notifier = TriageNotificationSender(settings)
        sent = notifier.send(result)
        if sent:
            TriageSessionStore().mark_notification_sent(result.session_id)
        print(f"✅ Triage run complete: session {result.session_id}")
        print(f"   Processed {result.total_processed} emails ({result.action_items_count} need action)")
        print(f"   Notification {'sent' if sent else 'not sent (check config)'}")

    asyncio.run(_run())


def _result(ok: bool, error: str = ""):
    if ok:
        print(json.dumps({"ok": True}))
    else:
        print(json.dumps({"ok": False, "error": error}))


def _fail(msg: str):
    print(json.dumps({"ok": False, "error": msg}))
    sys.exit(1)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("status", "--help", "-h"):
        cmd_status(as_json=False)
    elif args[0] == "--json":
        cmd_status(as_json=True)
    elif args[0] == "action":
        cmd_action(args[1:])
    elif args[0] == "email" and len(args) > 1 and args[1] == "body":
        cmd_email_body(args[2:])
    elif args[0] == "run" and len(args) > 1 and args[1] == "now":
        cmd_run_now(args[2:])
    else:
        print(f"Unknown command: {args[0]}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
