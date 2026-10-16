# Career Agent — Dashboard UI/UX Plan

Companion to `ROADMAP.md`. It replaces the short dashboard notes in sections 32–35 and plans
the user-facing interface in full: information architecture, screens, interaction flows,
motion, design tokens, tech stack and delivery order.

Interactive prototype of the key screens: see the published "Career Agent Dashboard" artifact.

---

## 1. UX Thesis

The dashboard is where raw activity becomes *trusted career memory*. Every screen serves
one loop:

```
OBSERVED  →  INFERRED  →  REVIEWED  →  REMEMBERED  →  PROVEN (CV)
```

Three feelings the UI must create:

| Feeling | Meaning | How the UI delivers it |
|---|---|---|
| **Calm** | "It works quietly beside me." | Low-saturation surfaces, no noisy counters, live state shown by one breathing dot, not flashing widgets. |
| **Trust** | "I know what it saw and why it thinks this." | Every claim shows its truth state, confidence and evidence. Raw observations are one click away. Pause is always visible. |
| **Progress** | "My work is turning into something." | Count-ups, skill bars that grow with a visible delta, confirmed items flying into Memory, a CV that visibly gets richer. |

It must never feel like:

- a time tracker (no app-hours pie charts on the home screen)
- employee monitoring (no "productivity score", no red "idle" shaming)
- a gamified toy (no streaks, XP, confetti storms)

---

## 2. Information Architecture

> Updated: the shipped layout uses a translucent top bar with a segmented control
> (Today · Timeline · Review · Memory · CV) instead of the sidebar below; Projects, Skills,
> Achievements, Insights and Settings live inside Memory/CV or behind the status/⌘K menus.
> See §7 for the visual direction. The grouping below still defines priority.

```
┌──────────────┬─────────────────────────────────────────────────────┐
│  SIDEBAR     │  TOP BAR: ● Recording · Supervisor · VS Code  [⏸]  ⌘K│
│              ├─────────────────────────────────────────────────────┤
│  Today       │                                                     │
│  Timeline    │                  MAIN CANVAS                        │
│  Review  (5) │                                                     │
│  ─────────   │                                       ┌───────────┐ │
│  Projects    │                                       │  DETAIL   │ │
│  Skills      │                                       │  DRAWER   │ │
│  Achievements│                                       │ (on click)│ │
│  Memory      │                                       └───────────┘ │
│  ─────────   │                                                     │
│  Insights    │                                                     │
│  CV          │                                                     │
│  ─────────   │                                                     │
│  Settings    │                                                     │
│ Learning 3/7 │                                                     │
└──────────────┴─────────────────────────────────────────────────────┘
```

Groups, in order of daily use:

1. **Daily loop** — Today, Timeline, Review (badge = unreviewed count)
2. **Career Memory** — Projects, Skills, Achievements, Memory (everything, editable)
3. **Output** — Insights (week/month), CV
4. **System** — Settings

Global elements:

- **Agent status pill** (top bar): `● Recording`, `◐ Paused`, `○ Stopped`, `⚠ AI offline`.
  Click opens a popover: uptime, events today, current app/project, Pause 15m / 1h / until tomorrow.
- **Pause button** is always visible. Privacy control is never more than one click away.
- **Command palette** (`Ctrl/⌘+K`): jump to any project/skill/session, run "Analyze now",
  "Generate CV", "Pause tracking", "Export data".
- **Learning Mode badge** (first 7 days): progress ring `Day 3/7` at the sidebar bottom.
- **Detail drawer**: any session, skill, project, achievement or CV bullet opens in the same
  right-side drawer. One pattern to learn, everywhere.

Mapping to roadmap `career` commands — the dashboard is a visual twin of the CLI:

| CLI | Screen |
|---|---|
| `career today` | Today |
| `career events --today` | Timeline → "Show raw observations" |
| `career review` | Review |
| `career projects / skills / achievements / memory` | Same-named screens |
| `career analyze --week / --month` | Insights |
| `career cv` | CV |
| `career config`, `career export/backup` | Settings |
| `career status` | Status pill popover |

---

## 3. Shared Visual Language

### 3.1 Truth states (roadmap §22) — the most important visual system

Every fact in the UI carries one of four states. Users must recognise them without reading.

| State | Visual | Meaning to user |
|---|---|---|
| `OBSERVED` | Solid neutral chip, eye icon | "The agent saw this directly." |
| `INFERRED` | Dashed amber outline, sparkle icon | "The AI thinks this. Please check." |
| `USER_CONFIRMED` | Solid green fill, check icon | "You confirmed this. It can go on the CV." |
| `USER_REJECTED` | Muted, strikethrough, hidden by default | "You said no. Never used again." |

Rule: only `OBSERVED` + `USER_CONFIRMED` facts may appear on the CV without a warning.

### 3.2 Confidence (roadmap §20)

Shown as a 5-segment meter, never as a bare percentage alone.

```
Unknown   ▮▯▯▯▯  0–39
Weak      ▮▮▯▯▯  40–59
Possible  ▮▮▮▯▯  60–79
Strong    ▮▮▮▮▯  80–94
Very strong ▮▮▮▮▮ 95–100
```

Hover shows the exact number and "Confidence is not truth — see evidence".

### 3.3 Evidence chips (roadmap §21)

Monospace chips with a type icon: `▣ temperature_test.py` · `⎇ abc123` · `# AI-1842` ·
`▶ pytest` · `◫ Temperature_Result.xlsx` · `◎ jira.company.com`.
Hover = when and where it was observed. Click = jump to that moment in the Timeline.

### 3.4 Project colours

Each project gets a stable hue (hash of project id → one of 8 tuned hues that work in both
themes). The same hue is used in the timeline, project cards, skill evidence and CV
highlights so the eye links them across screens.

---

## 4. Screens

### 4.1 First Run (web onboarding, mirrors roadmap §15)

Conversational, one question per screen, full-screen, no sidebar.

1. **Welcome** — "Career Agent quietly turns your daily work into a career record. Everything stays on this computer."
2. **Privacy promise** — what is collected / what is never collected (keystrokes, passwords, screenshots, mic, camera). Toggles for browser + file tracking.
3. **Role** — job title, free text with suggestions.
4. **Focus** — "What do you mainly work on?"
5. **Projects** — chips input; the agent also suggests repos it found in `~/` (Git detection).
6. **Tools** — tappable chips (Jira, VS Code, Git, Python, Excel…).
7. **AI provider** — Claude / Gemini / OpenAI / Local / "Skip for now (collect offline)". API key goes to OS keychain; UI says so.
8. **Autostart** — yes/no.
9. **Start** — big button; on press the button morphs into the status pill and flies to the top bar, then the empty Today screen fades in.

Motion: steps slide horizontally (x: 40px → 0, opacity), progress dots along the bottom,
`Enter` advances, `Esc` goes back.

### 4.2 Today (Overview, roadmap §33)

Purpose: answer "What has my day turned into so far?" in 5 seconds.

```
Good morning, Kutluhan                                 Thursday, 16 Oct
────────────────────────────────────────────────────────────────────
 6h 42m meaningful work      ┌ NOW ─────────────────────────────┐
 11 sessions · 3 projects    │ ● Supervisor temperature testing │
                             │   VS Code · temperature_test.py  │
 [day ribbon ▇▇▇░▇▇▇▇░▇▇▇]   │   00:32:14  ▮▮▮▮▯ Strong         │
                             └──────────────────────────────────┘
┌ 5 items need your review ───────────────────────── Review → ┐
└─────────────────────────────────────────────────────────────┘
 Top skills today           This week               Potential achievements
 Python      ████████ +3%   ▁▃▅▇▅▃▁ 31h 18m         • Validated temperature…
 Testing     ██████   +2%                           • …
 Git         ████
```

- **Hero number** counts up on load (600ms, ease-out).
- **Day ribbon**: a thin horizontal bar of today's sessions in project colours; hovering a
  segment shows a tooltip, click jumps to Timeline.
- **Now card**: live timer ticks every second; the dot breathes (scale 1 → 1.4, 2.4s loop).
  When the session changes, the card content crossfades and the old session drops into the
  ribbon.
- **Review banner**: only shown when count > 0. Gentle, not red.
- Empty state (day 1): "I'm observing. Your first sessions will appear here in about 30 minutes." with a slow pulsing outline of where the timeline will be.

### 4.3 Timeline (roadmap §34)

Vertical time axis; sessions are blocks whose height is proportional to duration.

- Colour = project; border style = truth state (dashed = inferred, solid = confirmed).
- Idle / breaks shown as a narrow hatched gap labelled "Break 45m" — neutral, never red.
- Zoom: Day · Week (week = 7 columns, same blocks scaled).
- **Click a session** → the block expands into the detail drawer (shared-element
  transition): Activity, Project, Skills, Evidence chips, Confidence, truth state, actions
  `Confirm` / `Edit` / `Reject` / `Split` / `Merge with previous`.
- **"Show raw observations"** toggle inside the drawer: lists the normalized events that
  produced this session (window titles, files, git). This is the transparency feature.
- Live: the current session block grows downward in real time.

### 4.4 Review (roadmap §28, §23) — the core loop

Inbox of inferred items: sessions, project guesses, skills, achievements, Learning Mode
questions.

```
Review today                                     2 of 5 reviewed  ▮▮▯▯▯
┌──────────────────────────────────────────────────────────┐
│  INFERRED · Session · 09:12–10:04                         │
│  Supervisor temperature testing                           │
│  Skills: Test automation · Python · Test analysis         │
│  Evidence: # AI-1842  ▣ temperature_test.py  ▶ pytest  ◫ …│
│  Confidence ▮▮▮▮▯ 94%                                     │
│                                                           │
│  [ Y  Confirm ]   [ E  Edit ]   [ N  Reject ]             │
└──────────────────────────────────────────────────────────┘
   (next card peeks underneath, scaled 0.96, offset 10px)
```

- Keyboard first: `Y` / `E` / `N`, `←/→` to skip. Same keys as the CLI.
- **Confirm** → card shrinks and flies along a curve into the "Memory" item in the sidebar;
  the Memory icon bumps (scale 1.15) and its counter increments. This is the product's
  signature moment: you *see* work becoming memory.
- **Reject** → card slides left and fades, short "Undo" toast (5s).
- **Edit** → card flips into an inline form (activity name, project dropdown, skills chips).
- Learning Mode questions use the same card with answer buttons
  ("Is `supervisor/` your Supervisor project?  [Yes] [No] [Tell me more]").
- Finished: calm end state — "All caught up. 5 items added to your Career Memory." with a
  small summary of what changed (e.g. "Python +2%"). No confetti.

### 4.5 Projects (roadmap §26)

- Grid of cards: name, hue, total hours, sessions, tickets, repos, top 3 skills, mini
  sparkline (last 30 days).
- Project page: header stats, activity chart, sessions list, skills used, achievements,
  evidence, repos/tickets.
- Actions: rename, merge (drag one card onto another → merge confirmation sheet), archive,
  mark as "not a project".
- Suggested projects (inferred) show with dashed borders in their own row: "Found 2 possible projects".

### 4.6 Skills (roadmap §25)

- List with score bars, trend arrow and delta since last week. Bars animate from previous
  value to new value (not from 0) so growth is visible.
- Skill detail drawer: **score breakdown** as a stacked bar of the six factors (frequency,
  duration, complexity, project diversity, evidence, confirmation) so the score is
  explainable; growth line chart; projects that used this skill; evidence list.
- Copy beside the score: "Based on evidence, not time spent."

### 4.7 Achievements (roadmap §27)

- Each achievement shows its **story stepper**:
  `Problem → Investigation → Implementation → Testing → Verification`, each step lit only
  if evidence exists for it.
- "Add impact" field: impact numbers are only ever entered by the user, never generated.
  The UI states this next to the field.
- States: Potential (inferred) → Confirmed → On CV.

### 4.8 Memory (roadmap §24, §35)

The power-user view of everything.

- Tabs: Projects · Skills · Technologies · Achievements · Evidence.
- Filter by truth state, project, date range. Bulk confirm / reject / delete / merge.
- Table view by default; optional graph view later (roadmap §63 Career Graph).

### 4.9 Insights (roadmap §29–31)

Week / Month switch. Written as answer cards to the roadmap's monthly questions:

- "What did I actually work on?" — project share bar + top activities
- "Which skills increased?" — skill deltas, small multiples
- "What did I accomplish?" — confirmed achievements
- "What am I repeatedly doing?" / "What did I stop doing?" — patterns
- "What can go into my CV?" — link to CV with N new candidate bullets

Each card has a "Why?" link that opens the evidence behind the statement.

### 4.10 CV (roadmap §36–37)

Split view.

```
┌───────────── CV PREVIEW (paper) ──────────┬──── EVIDENCE ─────────────┐
│ Test Engineer                             │ Hover a bullet to see     │
│ Supervisor Platform                       │ what proves it.           │
│ • Designed and executed temperature   ────┼─▶ # AI-1842               │
│   testing workflows.          ▮▮▮▮▯       │   ▣ temperature_test.py   │
│ • Developed Python-based test             │   ⎇ abc123 "Fix temp…"    │
│   automation.                             │                           │
└───────────────────────────────────────────┴───────────────────────────┘
 [Regenerate]  [Export ▾ Markdown · PDF · DOCX · JSON]
```

- Hovering a bullet highlights it and draws connector lines to its evidence items.
- Bullets with weak evidence get a quiet amber marker: "Needs more evidence".
- **Regenerate** shows a diff: new bullets slide in with a green tint, removed ones collapse.
- Inline editing of any bullet; edited bullets become `USER_CONFIRMED`.

### 4.11 Settings

Sections: General (language TR/EN, timezone), Tracking & Privacy (browser, files, screen
understanding OFF, excluded apps/domains/folders), AI (provider, key status via keychain,
analysis interval, "Analyze now"), Data (export, import, backup, delete everything — typed
confirmation inside the page), Startup (autostart), About (version, DB path, logs path).

Every privacy toggle has a one-line plain explanation of what changes.

---

## 5. System States (must be designed, not left to defaults)

| State | UI |
|---|---|
| Agent running | Green breathing dot in status pill |
| Paused | Amber half-dot; top bar shows "Paused until 14:30 · Resume" |
| Stopped | Grey dot; Today shows "Agent is stopped. Start" |
| AI offline / no key (roadmap §54–55) | Info banner: "AI is offline. Collection continues — 42 sessions are waiting for analysis. [Analyze when online]" |
| Learning Mode (days 1–7) | Ring badge, more review questions, copy says "I'm still learning your work." |
| First day / empty | Designed empty states per screen with what will appear and when |
| Loading | Skeleton blocks in the final layout shape (no spinners on main content) |
| Server not reachable | Full-page message: "Career Agent isn't running. Run `career start` in a terminal." with copy button |
| Error on an action | Inline message near the control with a retry; never a generic toast only |

---

## 6. Motion System

### 6.1 Principles

1. **Motion explains causality.** Things move *from* where they came *to* where they go
   (confirm → Memory, session → drawer, status → top bar).
2. **Fast by default.** Users open this daily; nothing may make them wait.
3. **Only `transform` and `opacity`.** 60 fps on low-end laptops; no layout-thrashing animations.
4. **Data never dances.** Live updates change numbers in place; lists don't re-animate on
   every SSE tick.
5. **`prefers-reduced-motion`** → all transitions become 0–80ms opacity fades; breathing
   dot becomes static; count-ups show final value immediately.

### 6.2 Motion tokens

| Token | Value | Use |
|---|---|---|
| `--dur-instant` | 90ms | hover, press, focus ring |
| `--dur-fast` | 160ms | chips, toggles, tooltips |
| `--dur-base` | 240ms | drawer, cards, page fade |
| `--dur-slow` | 420ms | shared-element, fly-to-memory |
| `--dur-count` | 600ms | number count-up |
| `--ease-out` | `cubic-bezier(.22,1,.36,1)` | entering |
| `--ease-in` | `cubic-bezier(.4,0,1,1)` | leaving |
| spring (Motion) | `stiffness 380, damping 32` | drawers, card stack, layout |

### 6.3 Signature moments (build these well; keep everything else quiet)

1. **Live dot** — breathing status in top bar and Now card.
2. **Confirm → Memory flight** — the Review card flies into the sidebar Memory item.
3. **Session → drawer** — shared-layout expansion from a timeline block.
4. **Skill growth** — bars animate from old to new value with a `+3%` tag that fades in.
5. **CV ↔ evidence lines** — connectors draw on hover (stroke-dashoffset).
6. **Onboarding start** — Start button morphs into the status pill.

### 6.4 Page transitions

Route change: outgoing page fades (120ms), incoming page rises 8px + fades in (240ms).
Lists on first mount stagger children 30ms apart, max 8 items, then the rest appear together.

---

## 7. Visual Direction & Design Tokens

**Direction: Apple-like — simple, quiet, premium.** The interface should feel like an
apple.com product page or a macOS/iOS app, not an "AI dashboard".

- One centered content column (max ~1000px), generous whitespace, few elements per screen.
- Translucent top bar (backdrop blur) with a **segmented control** for navigation
  (Today · Timeline · Review · Memory · CV); iOS-style tab bar on phones. No sidebar.
- Big, confident headlines (48px, tight tracking) with a short grey lede under them.
- Borderless white cards on a light grey ground (`#f5f5f7`); true black ground in dark mode.
- One accent colour (system blue) for actions and links only. Pill-shaped buttons.
- No badges-everywhere, no dashed outlines, no monospace chips in the main UI. Truth state is
  a small dot + word ("Needs review" / "Confirmed"); confidence is a word + % ("Likely · 86%").
- Detail opens as a floating rounded **sheet** from the right (iOS sheet), not a full-height panel.
- Motion is soft and slow-settling (ease-out 0.5–0.75s, light spring on the segmented thumb),
  never bouncy or flashy.
- Copy is short and human: "Is this right?", "You're up to date.", "Written from real work."

Dark and light themes from day 1 (follows OS, overridable in Settings).

```
Color (semantic)               light        dark
  --bg                         #f5f5f7      #000000
  --card                       #ffffff      #1c1c1e
  --fill (controls, tracks)    #e8e8ed      #2c2c2e
  --text                       #1d1d1f      #f5f5f7
  --muted                      #6e6e73      #a1a1a6
  --blue (only accent)         #0071e3      #0a84ff
  --green  (confirmed)         #248a3d      #30d158
  --orange (needs review)      #c76a00      #ff9f0a
  --project-1..8               system-like hues, used as tints (13%) in the timeline

Type
  System stack: -apple-system / SF Pro → Inter → Segoe UI (one family, weights do the work)
  Scale:   12 / 13 / 15 / 17 (body) / 21 (lede) / 24 / 32 / 48 / 96 (hero number)
  Tracking: slightly negative on all text, more on display sizes
  Numbers: tabular-nums everywhere digits align

Space   8 / 12 / 16 / 24 / 28 / 32 / 48 / 56
Radius  980 (pills) / 12 (timeline blocks) / 20 (cards) / 22–24 (sheet, review card)
Shadow  barely visible on cards; a deep soft shadow only on floating layers (sheet, CV paper)
```

---

## 8. Accessibility & Internationalisation

- Full keyboard operation; visible focus ring; `Y/E/N` shortcuts also exposed as buttons.
- Truth states never rely on colour alone (icon + border style + label).
- WCAG AA contrast in both themes; charts have text alternatives.
- i18n from day 1: `en` and `tr` (config `general.language`). Dates/durations via `Intl`.
  All copy in translation files, no hard-coded strings.

---

## 9. Frontend Architecture

Stays within roadmap §6 (React + Vite + TypeScript) and adds:

| Concern | Choice | Why |
|---|---|---|
| Styling | Tailwind CSS + CSS variables for tokens | fast, theme via variables |
| Primitives | Radix UI | accessible dialogs, popovers, tabs, tooltips |
| Animation | Motion (Framer Motion) | `layoutId` shared transitions, springs, `AnimatePresence` |
| Server state | TanStack Query | caching, refetch, optimistic confirm/reject |
| UI state | Zustand | drawer, palette, filters |
| Routing | TanStack Router or React Router | typed routes |
| Charts | visx (or Recharts) | sparklines, bars, timeline |
| Command palette | cmdk | `⌘K` |
| i18n | i18next | TR/EN |
| Tests | Vitest + Testing Library + Playwright | unit + E2E against mock API |

Delivery model (local-first, no Node at runtime):

```
dashboard/  → vite build → dist/  → copied into  src/career/server/static/
career dashboard → FastAPI serves static files + /api on 127.0.0.1:7342
```

Folder layout:

```
dashboard/src/
├── app/            routes, layout, providers
├── components/     ui primitives (Chip, ConfidenceMeter, TruthBadge, EvidenceChip, Drawer…)
├── features/
│   ├── today/  timeline/  review/  projects/  skills/
│   ├── achievements/  memory/  insights/  cv/  settings/  onboarding/
├── motion/         tokens, shared variants, useReducedMotion wrappers
├── api/            typed client (generated from FastAPI OpenAPI), query hooks
├── live/           SSE connection, live store
├── i18n/           en.json, tr.json
└── styles/         tokens.css, themes
```

---

## 10. API Contract Needed by the UI

Add to `server/routes.py` (types generated into the dashboard from OpenAPI):

```
GET  /api/status                      agent state, uptime, current app/project, learning day
POST /api/agent/pause   {minutes}     POST /api/agent/resume
GET  /api/today                       hero stats, ribbon, top skills, review count
GET  /api/sessions?from&to            timeline blocks
GET  /api/sessions/{id}               detail + evidence + raw events
PATCH /api/sessions/{id}              edit / split / merge
GET  /api/review                      inbox items
POST /api/review/{id}  {action: confirm|reject|edit, payload}
GET  /api/projects  /api/projects/{id}
GET  /api/skills    /api/skills/{id}  (includes factor breakdown + history)
GET  /api/achievements
GET  /api/memory?type&state&project
GET  /api/insights?period=week|month
GET  /api/cv        POST /api/cv/regenerate   GET /api/cv/export?format=
GET/PUT /api/settings
POST /api/onboarding
GET  /api/stream   (SSE) → status, current_session_tick, review_count, analysis_done
```

SSE over WebSocket: one-way, auto-reconnect, simple in FastAPI.

---

## 11. Delivery Plan (replaces roadmap Sprint 9, extends Sprint 10)

Dashboard work can start in parallel with Sprint 6–8 by developing against a **mock API**
backed by the `fixtures/` dataset (roadmap §52).

**Sprint 9a — Dashboard foundation**
- [ ] Vite + React + TS + Tailwind + Radix + Motion
- [ ] Tokens, both themes, fonts, motion tokens, reduced-motion handling
- [ ] Core components: TruthBadge, ConfidenceMeter, EvidenceChip, Drawer, StatusPill, Skeleton
- [ ] App shell: sidebar, top bar, command palette, routing, i18n
- [ ] Mock API (MSW) from fixtures; FastAPI static serving + `/api/status`
- [ ] SSE live store

**Sprint 9b — Daily loop**
- [ ] Today (hero, Now card, ribbon, review banner, empty states)
- [ ] Timeline (day view, drawer with shared transition, raw observations)
- [ ] Review (card stack, keyboard, fly-to-memory, undo, Learning Mode cards)
- [ ] System states: paused, stopped, AI offline, server unreachable

**Sprint 9c — Career Memory**
- [ ] Projects (grid, detail, merge)
- [ ] Skills (list, factor breakdown, history)
- [ ] Achievements (story stepper, user-entered impact)
- [ ] Memory (table, filters, bulk actions)

**Sprint 10 (extended) — Output**
- [ ] Insights week/month
- [ ] CV split view, evidence connectors, regenerate diff, export
- [ ] Web onboarding flow
- [ ] Settings

**Sprint 11 additions**
- [ ] Playwright E2E for the daily loop
- [ ] Performance budget: first load < 1s on localhost, JS < 300 KB gzipped, 60 fps animations
- [ ] Accessibility audit (keyboard, contrast, screen reader labels)

**Later (post-v1)**
- Week timeline view, Career Graph view, system tray mini-status, end-of-day OS
  notification "Your review is ready (5 items)", job-match screen (roadmap §62).

---

## 12. Dashboard Definition of Done

A screen is done when it has:

- loading, empty, error and live states designed
- both themes and reduced-motion verified
- keyboard operation and TR/EN copy
- truth state + confidence + evidence visible for every career claim
- E2E test for its primary action
