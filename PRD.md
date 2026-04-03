# Coco – Product Requirements Document

## tl;dr

Coco is a personal email automation assistant for a CPO at Digital Science. It runs a background sync continuously, pre-processes emails twice a day (noon + 4pm), then surfaces the results in an interactive Claude Code triage session. You can go deep on anything — ask follow-up questions on a newsletter story, refine a draft reply, get context from Coda — before committing to any action. Tasks land in your Obsidian backlog. Drafts are saved but never sent without you.

---

## Goals

### Business Goals
- Eliminate the cognitive overhead of manual inbox triage
- Surface the right emails at the right time, not just all emails all the time
- Create a structured, auditable record of actions taken on email

### User Goals
- Go through email in focused 10–15 minute sessions, not ad-hoc all day
- Ask questions about content before deciding what to do with it
- Have tasks and drafts created automatically, ready to act on
- Never have Coco take an irreversible action without confirmation

### Non-Goals
- No auto-sending emails
- No auto-deleting emails (suggest only)
- No Slack integration (yet)
- No mobile experience
- No team collaboration or shared access

---

## Email Categories

Every email synced from Gmail is classified into one of five categories. All downstream processing flows from this classification.

| Category | Examples | What Coco does |
|---|---|---|
| **JUNK** | Marketing, ads, cold outreach, unsolicited | Surfaces suggestion to delete or unsubscribe |
| **NEWSLETTER** | Subscribed digests, industry news | Summarises, deduplicates across sources |
| **SYSTEM_NOTIFICATION** | SAP, Concur, Bob/HiBob, Asana, other DS systems | Parses structurally, aggregates into one paragraph |
| **ACTION_REQUIRED** | Needs a reply or a non-email action from you | Generates draft reply and/or creates Obsidian task |
| **FYI** | CC'd, informational, no action needed | Summarised briefly, no task or draft generated |

---

## Interaction Model

### Background (always running)
- Gmail syncs every 15 minutes
- Each new email is classified immediately after sync
- No pre-processing yet — classification only

### Pre-processing (noon + 4pm)
A scheduled job runs at 12:00 and 16:00 in your timezone:
- Newsletters from the period are summarised and deduplicated across sources
- System notifications are parsed and aggregated
- Action emails have drafts generated and tasks queued
- Junk emails are scored with deletion confidence
- A short notification email is sent: "Triage ready — 14 emails processed, 3 need your input"

The noon run covers midnight → 11:59am.
The 4pm run covers 12:00 → 3:59pm and flags what needs to happen before EOD vs what can wait.

### Triage Session (Claude Code)
When you're ready, you open Claude Code and say "let's triage" (or similar). Coco presents the pre-processed results by category. You can:
- Accept, skip, or modify any suggestion
- Ask follow-up questions about any item ("tell me more about that story", "is this relevant to our roadmap?")
- Request a different draft tone or approach
- Add context that changes how Coco handles something

Full email content is available throughout the session, so follow-up questions work without re-fetching anything. The session ends when the queue is clear or you close it.

### What gets actioned during a session
- **Junk**: You confirm → email gets a "to delete" label in Gmail (actual deletion is your choice)
- **Newsletters**: You confirm → emails archived, summary optionally saved to Obsidian
- **System notifications**: Acknowledged → emails archived
- **Action — reply**: You confirm draft → saved as Gmail draft (not sent)
- **Action — task**: Created automatically → written to Obsidian `tasks/Backlog.md`
- **FYI**: You acknowledge → archived

---

## Task Integration

Tasks are written to your Obsidian vault at:
```
/Users/akenall/Documents/Obsidian Vault/tasks/Backlog.md
```

Format uses the Obsidian Tasks plugin syntax:
```markdown
- [ ] Reply to Sarah Chen re: Budget sign-off 📅 2026-04-04 #email #coco
- [ ] Approve expense report – Concur (ref: EXP-2891) 📅 2026-04-03 #system #coco
- [ ] Review AI Act briefing doc before team meeting 📅 2026-04-07 #research #coco
```

All Coco-created tasks are tagged `#coco` for easy filtering. Tasks include a source reference (email sender + subject, or system + reference number) and a suggested due date where one is detectable.

The vault path is configurable in `config.yaml` so it can be adjusted without code changes.

---

## System Notification Parsing

Digital Science systems produce highly patterned notification emails. Coco parses these structurally before sending anything to Claude, which keeps costs low and parsing reliable.

| System | Patterns detected |
|---|---|
| **Concur** | Expense report submitted / approved / rejected / pending your approval |
| **SAP** | Purchase order / invoice / workflow approval required |
| **Bob / HiBob** | Leave request / new joiner / policy update / anniversary |
| **Asana** | Task assigned to you / task completed / project update / deadline approaching |
| **Other DS systems** | Falls back to Claude classification |

The triage session presents these as a single aggregated paragraph: *"3 items need your attention: 2 expense reports pending approval in Concur (EXP-2891, EXP-2892), and 1 leave request from [name] in Bob."*

---

## Newsletter Handling

Newsletters are summarised per-email, then deduplicated across all sources in a session window. If three newsletters cover the same story, you see it once with sources noted.

Session-awareness: the noon run and 4pm run do not re-surface content you already reviewed. Each run tracks which newsletter editions were processed so there is no repetition.

---

## Draft Generation

For ACTION_REQUIRED emails that need a reply, Coco generates three draft options:
1. **Short ACK** — brief acknowledgement, buys time
2. **Full reply** — substantive response with context from the thread
3. **Decline / defer** — polite way to push back or postpone

You can ask Coco to adjust tone, add or remove context, or start from scratch. Confirmed drafts are saved to Gmail Drafts. Nothing is sent automatically.

---

## Success Metrics

- Triage sessions complete in under 15 minutes
- >80% of suggested junk classifications are confirmed correct
- >50% of generated drafts are used as-is or with minor edits
- At least 3 tasks per day created that would otherwise have been missed
- Subjective: "Feels like it saves me 45+ minutes a day"

---

## Technical Stack

- **Language**: Python 3.11+
- **AI**: Anthropic Claude API (claude-sonnet-4-6 for drafts/synthesis, claude-haiku-4-5 for classification/scoring)
- **Database**: SQLite + FTS5 (local, private)
- **Integrations**: Gmail OAuth, Google Calendar OAuth, Coda API
- **Task output**: Obsidian vault (filesystem write)
- **Draft output**: Gmail Drafts API
- **Scheduler**: APScheduler
- **Triage interface**: Claude Code CLI (conversational)

---

## Security & Privacy

- All data stored locally in SQLite — nothing leaves the machine except API calls
- OAuth tokens stored locally with encryption
- No external logging of email content
- Obsidian vault writes are append-only to `Backlog.md` — no existing notes modified
- Gmail Drafts API used for draft storage — no SMTP credentials required

---

## Milestones

### Phase 3 — Email Intelligence (next)
- Claude API client wrapper
- Email classifier (5 categories)
- Junk detector with confidence scoring
- System notification parser (Concur, SAP, Bob, Asana)
- Newsletter summariser with cross-source deduplication
- Action processor (draft generator + task creator)

### Phase 4 — Triage Infrastructure
- Pre-processing jobs at noon + 4pm
- Obsidian task writer
- Gmail Draft saver
- Notification email ("triage ready")
- Session state tracking (what's been reviewed)

### Phase 5 — Triage Session
- Claude Code triage interface
- Queue presentation by category
- Conversational follow-up support
- Session completion and carry-forward logic

### Phase 6 — Polish & Feedback
- Junk sender memory (auto-classify known junk senders)
- Newsletter subscription quality scoring ("you never read this one")
- Feedback loop on draft quality
- Weekly summary: inbox trends, response rate, task completion
