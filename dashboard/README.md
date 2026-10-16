# Career Agent dashboard

React 18 + Vite + TypeScript single-page app. Talks to the local API described in `../docs/API.md`.

## Run

```bash
npm install
npm run dev:mock   # no backend needed; in-memory mock of every endpoint (src/api/mock.ts)
npm run dev        # proxies /api to http://127.0.0.1:7342 (a running `career dashboard`)
npm test           # vitest: formatting helpers, confidence words, mock API
npm run typecheck
npm run build      # tsc -b && vite build
```

Mock-only URL flags: `?onboarding=1` (incomplete profile), `?empty=1` (first day), `?offline=1` (server not running).

## How it ships

`npm run build` writes to `../src/career/server/static/` (emptied first). `career dashboard` serves those files
and `/api` from FastAPI on `127.0.0.1:7342`; no Node is needed at runtime. The mock is not part of production bundles.
Fonts (Inter, latin + latin-ext) are bundled, so the app makes no external requests.

## Layout

`src/api` types (copied from API.md), fetch client, react-query hooks, mock · `src/pages` one file per route ·
`src/components` shell, sheet, toast, charts (hand-rolled SVG) · `src/lib` formatting and helpers · `src/styles` tokens + CSS.
