# Career Agent — Roadmap Status

The full master plan is in [`docs/ROADMAP.txt`](docs/ROADMAP.txt); the dashboard plan is in
[`docs/DASHBOARD_UX.md`](docs/DASHBOARD_UX.md). This file tracks what is built and verified.

Legend: ✅ built and tested · 🟡 built, not verified on that platform/service · ⬜ not started

## Sprints

| Sprint | Scope | Status |
|---|---|---|
| 1 Foundation | repo, Python project, CLI, config, logging, SQLite, event schema, platform abstraction | ✅ |
| 2 Cross-platform collector | active window + idle on Linux / Windows / macOS, normalized events | ✅ Linux · 🟡 Windows, macOS |
| 3 Session Engine | grouping, idle/sleep/crash handling, boundaries, scoring, session table, mock collector | ✅ |
| 4 Context Intelligence | file tracking (metadata), Git repos/commits/branches, browser sites, terminal commands, tickets, context builder | ✅ |
| 5 User Intelligence | onboarding (`career setup`, web), profile, project definitions, Learning Mode, project inference | ✅ |
| 6 AI | provider interface, strict schema, Claude / OpenAI / Gemini / Local, rules fallback, evidence validation, retry/discard | ✅ rules + adapters · 🟡 live API calls |
| 7 Career Memory | skills, projects, achievements, evidence, truth states, confirm/edit/reject | ✅ |
| 8 Daily Intelligence | `today`, `review`, `analyze` (`--week`, `--month`, `--deep`), summaries | ✅ |
| 9 Dashboard | FastAPI, local server, SSE, React (Today, Timeline, Review, Memory, Insights, CV, Settings, Onboarding) | ✅ (see dashboard notes) |
| 10 CV | schema, evidence mapping, Markdown / DOCX / PDF / JSON export, CV in dashboard | ✅ |
| 11 Production | error handling, logging, performance, security, backup, import/export, installer, autostart, packaging | ✅ Linux · 🟡 Windows, macOS |

## MVP definition (roadmap §66)

| Item | Status |
|---|---|
| Windows | 🟡 all unit + integration tests pass in CI (incl. real background start/stop); not yet used on a real desktop |
| macOS | 🟡 all unit + integration tests pass in CI (incl. real background start/stop); not yet used on a real desktop |
| Linux | ✅ X11, platform smoke tests pass |
| career start / stop / status | ✅ also from the standalone binary |
| Activity collection · idle detection | ✅ |
| SQLite | ✅ WAL, 4 migrations, upgrade from v1 tested |
| Session detection | ✅ 461 synthetic events → the 12 planned sessions |
| File · Git · browser context | ✅ |
| User onboarding | ✅ CLI and dashboard |
| AI classification | ✅ rules offline; provider adapters tested with recorded SDK calls |
| Evidence · Career Memory · daily review | ✅ |
| Dashboard | ✅ |
| Basic CV generation | ✅ |

## Measured (Linux, this machine)

- Agent at steady state: **0.17 % of one CPU core**, ~75 MB RSS, 101 repositories found, 25 watched.
- 150 Python tests (unit + integration) and 26 dashboard tests pass; 4 platform smoke tests pass on Linux X11.
- Dashboard checked against the real API with seeded data: 7 screens × light/dark × desktop/phone with no console errors, failed API calls or horizontal overflow; review confirm, timeline sheet, CV evidence lines and web onboarding driven in Chrome.
- Standalone binary (`scripts/build_binary.py`): 54.7 MB, start / status / stop verified.

## Before calling v1 production-ready

1. Run `uv run pytest -m platform` and a day of real use on **Windows** and **macOS**
   (Accessibility permission flow on macOS; `pythonw` autostart on Windows).
2. Run one real analysis per AI provider with a key (`career config ai`, then `career analyze --deep --days 1`).
3. Build the binary on each target OS/arch (PyInstaller doesn't cross-compile) and host the
   install scripts somewhere (`career-agent.dev` from the plan doesn't exist yet).
4. A week of real usage to tune session thresholds and review volume on real data.

## Deliberately not built (roadmap §64)

SaaS backend, accounts, payments, team dashboards, employee monitoring, keylogging,
screenshots, OAuth integrations (Jira/GitHub/Slack), mobile app, browser extension.
Optional screen understanding (§42) is a setting that stays **off**; no screen capture code exists.
