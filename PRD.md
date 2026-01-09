# 🧠 AI Chief of Staff – V1 PRD

## tl;dr
Build a personal AI assistant for a Chief Product Officer that delivers a **Daily Briefing** each morning. The briefing synthesizes tasks, suggests email replies, surfaces key decisions, and reduces cognitive load. Initial integrations: **Gmail, Google Calendar, and Coda**. Primary interaction is via a daily message (email or Slack) and a lightweight UI to view/respond/delegate.

---

## Goals

### 🎯 Business Goals
- Reduce time spent switching contexts between tools and threads
- Improve speed and quality of email/decision-making
- Create a reusable foundation for future productization

### 🧑‍💼 User Goals
- Get a daily digest that helps stay on top of priorities
- Receive help drafting high-leverage emails
- Be reminded of context, decisions, and open loops without searching

### 🚫 Non-Goals
- No Slack/Dovetail/Gong integration yet
- No standalone app or mobile experience
- No team collaboration or permissions (solo use only)

---

## User Stories

- As a CPO, I want to receive a smart Daily Briefing each morning so I can start my day focused.
- As a CPO, I want feedback on my sent emails so I can improve clarity and tone.
- As a CPO, I want help drafting replies to high-priority emails to save time.
- As a CPO, I want my calendar reviewed so I can see follow-up tasks and prep notes.
- As a CPO, I want key updates from Coda (roadmaps, OKRs) surfaced if there are any changes.

---

## User Experience

### 1. **Daily Briefing Email/Message** (core UI)
Delivered at 7AM daily via email or Slack, containing:

- 🗂️ **Today's Priorities**: Synthesized from calendar, flagged emails, and open to-dos in Coda
- 📬 **Smart Email Drafts**: Suggested replies for flagged or high-priority threads (from Gmail)
- 🎙️ **Meeting Follow-ups**: Tasks or insights extracted from previous day's meetings
- 📊 **Product Org Changes**: Key Coda doc updates (roadmap shifts, OKR changes, new comments)

### 2. **In-Context Actions**
- "Draft reply" button opens the AI-suggested email
- Inline suggestions for rewording, delegation, or prioritization
- Links to source context (email, calendar, doc)

### 3. **Feedback UI (lightweight)**
Optional: quick thumbs up/down on AI suggestions to improve future quality

---

## Narrative

Imagine starting your day with a single message that says:
> "Good morning — here's what matters today."

It pulls from your inbox, your meetings, and your product docs to give you a clear, prioritized path forward.
No more bouncing between Gmail, Calendar, and Coda. No more re-reading threads to remember context.
Your AI Chief of Staff already did the work: it's flagged the decisions you need to make, pre-drafted the email replies, and reminded you why a roadmap item shifted.

It doesn't just remember what happened — it **understands why it matters**. Over time, it becomes a second brain for your org.

---

## Success Metrics

- >80% open rate on Daily Briefing within first hour
- >50% of AI-generated replies are used or edited (vs ignored)
- At least 3 tasks surfaced per day that weren't previously tracked manually
- Subjective feedback: "Feels like it saves me >1 hour/day"

---

## Technical Considerations

- **AI Core**: Built with Claude Code Interpreter
- **Data Storage**: Local or lightweight cloud storage (private, no team access)
- **Integrations**:
  - Gmail (OAuth, access to inbox/sent items)
  - Google Calendar (event read + metadata)
  - Coda (docs read access via API tokens)
- **Email Drafting**: Generate drafts, allow copy/edit/send via native Gmail interface
- **Security**: Local token storage, no external logging

---

## Milestones & Sequencing

### Week 1–2: Foundations
- Set up Claude Code runtime
- Build Gmail and Calendar OAuth auth flow
- Parse and index Gmail + Calendar data

### Week 3–4: Daily Briefing MVP
- Generate a Daily Briefing with mock data
- Add task synthesis and email reply suggestions

### Week 5–6: Coda Integration + UX Polish
- Pull changes from key Coda docs
- Improve UX of email replies (buttons, inline editing)

### Week 7+: Feedback & Iteration
- Add simple feedback mechanism
- Collect usage data + improve quality heuristics
