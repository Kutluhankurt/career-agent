# Contributing to Career Agent

Thanks for wanting to help! Every contribution counts, whether it's a bug report, a test
on your OS, a doc fix or a new feature.

**Not sure where to start, or want to discuss a bigger idea first?** Open a
[Discussion](https://github.com/Kutluhankurt/career-agent/discussions) or reach out to
[@Kutluhankurt](https://github.com/Kutluhankurt). Happy to help you get going.

## Ground rules

Career Agent watches people's computers, so trust is the product. Every change must keep these:

1. **Local-first.** No mandatory cloud, account or network call. AI providers are optional.
2. **Privacy.** Never capture keystrokes, screenshots, clipboard, passwords, audio or file contents.
   New data sources are off by default or clearly explained in `career setup`.
3. **Evidence over claims.** Anything that can reach a CV needs evidence and a truth state.
   Never generate impact numbers.
4. **Cross-platform.** No `if windows:` in business logic. OS specifics live behind
   `ActivityCollector` and produce the same normalized events.
5. **Graceful degradation.** If a source fails (no display, no Git, AI offline), collection continues.

## Setup

```bash
git clone https://github.com/Kutluhankurt/career-agent.git
cd career-agent
uv sync --extra claude          # Python 3.12+ via uv
uv run pytest                   # all unit + integration tests
uv run pytest -m platform       # smoke tests against your real desktop
```

Dashboard:

```bash
cd dashboard
npm install
npm run dev:mock                # UI with mock data, no backend needed
npm run typecheck && npm test
npm run build                   # writes ../src/career/server/static
```

Try everything with demo data, without recording yourself:

```bash
CAREER_AGENT_HOME=/tmp/demo uv run python scripts/seed_demo.py
CAREER_AGENT_HOME=/tmp/demo uv run career dashboard
```

## Making a change

1. Open (or comment on) an issue so we don't duplicate work.
2. Branch from `main`: `git checkout -b fix/short-description`.
3. Write tests. Most logic is testable without a desktop: use `MockCollector` and the
   fixtures in `tests/fixtures/` (see `tests/fixtures/day.py` for a full synthetic work day).
4. Run `uv run pytest` (and `npm test` / `npm run typecheck` if you touched the dashboard).
5. Keep the style of the surrounding code: small modules, clear names, short docstrings
   that explain *why*.
6. Open a pull request describing what changed and how you tested it. Screenshots for UI changes.

## Especially welcome

- Running Career Agent on **Windows** or **macOS** and reporting what works.
- **Wayland** window detection.
- Session / achievement rule improvements, backed by a fixture that shows the problem.
- New AI providers behind `career.ai.base.AIProvider`.
- Translations (`general.language`), accessibility and design polish.

## Reporting bugs

Please include your OS, `career version`, what you expected, what happened, and the relevant
lines from `~/.career-agent/logs/agent.log`. **Check the log for private window titles before
sharing it.**

## Code of conduct

Be kind, assume good intent, and keep feedback about the work. Harassment of any kind isn't tolerated.

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).
