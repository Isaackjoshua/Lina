# LINA — working notes for Claude Code

Read `SPEC.md` first. It is the source of truth; §2 (non-negotiables) wins over convenience.
Build one §12 milestone at a time and stop for review after each.

## Layout

- `backend/` — Python 3.13. FastAPI API (`lina/api`), scheduled jobs (`lina/worker`),
  SQLAlchemy models (`lina/models`), Alembic migrations (`alembic/`). One Docker image, two commands.
- `web/` — Next.js 16 (App Router), Tailwind 4, next-intl, Auth.js. Public site under
  `src/app/[locale]`, admin under `src/app/admin` (English only, not localized).
- `docker-compose.yml` — db, api, worker, web. `.env` at the repo root feeds everything.

## Commands

Backend (run from `backend/`):
- `uv run pytest -q` · `uv run ruff check .` · `uv run ruff format .` · `uv run mypy`
- `uv run uvicorn lina.api.main:app --reload` (needs `docker compose up -d db`)
- New migration: `uv run alembic revision --autogenerate -m "what changed"`, read the file, then
  `uv run alembic upgrade head` and `uv run alembic check`.

Web (run from `web/`):
- `npm run dev` · `npm run lint` · `npm run typecheck` · `npm test` · `npm run build`

Everything: `docker compose up --build` (db is on host port 5433, not 5432).

## Conventions

- The backend owns the database. Next.js never connects to Postgres; it calls the API.
- Admin flow: GitHub login is checked in Next.js (`getAdmin()` in `web/src/auth.ts`), then the
  Next.js server calls `/internal/*` on the API with `INTERNAL_API_TOKEN`. Every admin page and
  server action calls `getAdmin()` first. Public API routes never require the token.
- Enum-like columns are strings; allowed values live in `backend/lina/models/enums.py`.
- Unknown facts are `NULL` / `"unclear"`, shown as "Haijabainishwa / Not specified". Never guess.
- All user-facing text goes in `web/messages/sw.json` and `en.json` with identical keys (tested).
  Swahili is natural Tanzanian Swahili; "fellowship" and "hackathon" stay untranslated.
- Public pages are server-rendered with as little client JavaScript as possible. A new
  `"use client"` component needs a reason.
- Timezone is `Africa/Dar_es_Salaam` everywhere.
- Tests never touch the network. Scraping tests use saved HTML fixtures.
- Brand placeholders (`[DOMAIN]`, `[INSTAGRAM_HANDLE]`) live only in `web/src/lib/site.ts`.
- Next.js 16 differs from older versions (see `web/AGENTS.md`): `proxy.ts` replaces
  `middleware.ts`, Cache Components are on, and anything reading the session or request must sit
  inside `<Suspense>`. Check `web/node_modules/next/dist/docs/` before using an unfamiliar API.
- Git: push to `origin` (github.com/Isaackjoshua/Lina) at the end of each milestone. Commits are
  authored by the owner only; do not add Claude co-author or "generated with" lines.
- Ask before adding a paid service, a heavy dependency, or changing the stack.

## Decisions

- 2026-11-15 — Stack: Python (FastAPI) backend + Next.js frontend, chosen by the owner over the
  all-TypeScript default in SPEC §4. Consequences: SQLAlchemy + Alembic replace Prisma; the worker
  and pipeline are Python; the Claude API is called through the Anthropic Python SDK.
- 2026-11-15 — Enum-like columns are plain strings validated in Python, not Postgres enums,
  because Alembic autogenerate does not detect new values on native enums.
- 2026-11-15 — Scheduling uses APScheduler cron triggers inside the worker process instead of
  system cron in the container: timezone-aware, logs to stdout, inherits the container's env.
- 2026-11-15 — `/` always redirects to `/sw`; no browser-language detection. The default locale
  is a constant in `web/src/i18n/routing.ts`, not an env var, because pages are built statically.
- 2026-11-15 — Auth.js v5 (`next-auth@5.0.0-beta.32`) with JWT sessions and no session table.
  v5 is still tagged beta on npm; v4 is the fallback if it causes trouble.
- 2026-11-15 — Brand name "LINA"; domain and Instagram handle still placeholders.
- 2026-11-15 — Palette proposed in `web/src/app/globals.css` (deep green, amber accent, system
  fonts, light theme only). Not yet confirmed by the owner.
- 2026-11-15 — Email: Resend, behind an adapter (M6). Pricing not yet verified.
- 2026-11-15 — Hosting: Hetzner VPS, nightly backups to Backblaze B2 (M8).
- 2026-11-15 — Analytics: none for now. `OutboundClick` is the impact metric.

## Milestones

- M1 Scaffold — built 2026-11-15, awaiting owner review.
