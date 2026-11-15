# LINA

A free, bilingual (Swahili + English) site that publishes verified opportunities for young
people in Tanzania. The full product spec is in [SPEC.md](SPEC.md).

**Status:** Milestone 2 (sources and fetching). The site is still a placeholder. The pipeline can
fetch pages from verified sources and store them; it does not yet read them (that is Milestone 3).

## What is in the repo

| Path | What it is |
| --- | --- |
| `backend/` | Python: FastAPI API, scheduled worker, database models and migrations |
| `web/` | Next.js: public site (`/sw`, `/en`) and the admin (`/admin`) |
| `docker-compose.yml` | Runs the database, API, worker and website together |
| `backend/sources.yaml` | The list of official sources |
| `.env.example` | Every environment variable, with instructions |

## Run it

You need Docker. For development outside Docker you also need Node 22 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
# Fill in INTERNAL_API_TOKEN and AUTH_SECRET (the file says how to generate them).
docker compose up --build
```

- Site: <http://localhost:3000> (redirects to `/sw`)
- Admin: <http://localhost:3000/admin>
- API health: <http://localhost:8000/health>

### Admin login

1. On GitHub: Settings → Developer settings → OAuth Apps → New OAuth App.
   Homepage `http://localhost:3000`, callback `http://localhost:3000/api/auth/callback/github`.
2. Put the client ID and secret in `.env` as `AUTH_GITHUB_ID` and `AUTH_GITHUB_SECRET`.
3. Set `ADMIN_GITHUB_USERNAME` to your GitHub username. Only that account gets in.
4. `docker compose up -d web` to restart the site with the new values.

### Develop without rebuilding images

```bash
docker compose up -d db                       # Postgres on localhost:5433
cd backend && uv sync && uv run alembic upgrade head
uv run uvicorn lina.api.main:app --reload     # API on :8000
cd ../web && npm install
set -a && . ../.env && set +a && npm run dev  # site on :3000
```

## Environment variables

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SITE_URL` | web | Public address of the site. Used in canonical and hreflang links |
| `DEFAULT_LOCALE` | backend | Default language for generated content (`sw`) |
| `POSTGRES_PASSWORD` | db, backend | Database password |
| `DATABASE_URL` | backend | Only for running the backend outside Docker |
| `INTERNAL_API_TOKEN` | web, backend | Shared secret for the website's calls to the API's admin routes |
| `API_INTERNAL_URL` | web | Only for running the site outside Docker |
| `AUTH_SECRET` | web | Signs the admin session cookie |
| `AUTH_GITHUB_ID`, `AUTH_GITHUB_SECRET` | web | GitHub OAuth app |
| `ADMIN_GITHUB_USERNAME` | web | The one GitHub account allowed into `/admin` |
| `BOT_CONTACT_URL` | backend | Public page saying who runs the bot. Sent with every request; fetching refuses to run without it |
| `FETCH_DELAY_SECONDS` | backend | Minimum gap between two requests to the same site (default 5) |
| `MAX_ITEMS_PER_RUN` | backend | Most detail pages fetched in one run (default 60) |

Secrets live in `.env` only. It is git-ignored; never commit it.

## Checks

```bash
cd backend && uv run ruff check . && uv run mypy && uv run pytest -q
cd web && npm run lint && npm run typecheck && npm test
```

GitHub Actions runs the same checks on every push, plus a migration check against a real Postgres.

## Changing the database

Edit the models in `backend/lina/models/`, then:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
# read the generated file in alembic/versions/ before applying it
uv run alembic upgrade head
```

The API container applies pending migrations each time it starts.

## How the pipeline works (so far)

Commands run from `backend/` (or inside Docker: `docker compose run --rm api python -m lina.pipeline <command>`).

| Command | What it does |
| --- | --- |
| `uv run python -m lina.pipeline sync` | Copies `sources.yaml` into the database |
| `uv run python -m lina.pipeline check --probe` | Checks every source's robots.txt and loads each allowed listing once |
| `uv run python -m lina.pipeline fetch` | The dry run: fetches verified sources, stores new pages as raw items, prints a report |
| `uv run python -m lina.pipeline fetch --source udsm` | Same, for one source |

What a fetch does, per source: load the listing (RSS feed, HTML list page or sitemap), collect
the item links that stay on the official site, skip pages already stored, fetch the new ones,
and save them in `raw_items`. Every run is logged in `pipeline_runs`.

Politeness rules, enforced in one place (`backend/lina/pipeline/http.py`):

- identifies itself with `BOT_CONTACT_URL`, and will not run without it
- obeys robots.txt; if robots.txt cannot be read, the site is treated as off limits
- waits `FETCH_DELAY_SECONDS` between requests to one site, or longer if the site asks
- asks "has this changed?" before re-downloading a listing
- retries failed requests up to three times with growing waits
- a source that fails three runs in a row is flagged in the report

A source is only fetched when it is `active`, has `verified: true`, and its robots.txt allows it.

## Adding or verifying a source

1. Add or edit the entry in `backend/sources.yaml` (the file explains each field).
2. Only official pages: the organization's own site or an official portal. No job boards.
3. Read the site's terms of use. Point `url` at the page that lists the opportunities.
4. Run `check --probe --source <key>`. It reports robots.txt, whether the page loads, how many
   links it found, and any RSS feed the site advertises (prefer `kind: rss` when there is one).
5. If it finds too many or the wrong links, add `parsing_hints` (`item_selector`, `url_pattern`).
6. Set `verified: true`, then run `fetch --source <key>` and read the report.

## Privacy note

Subscriber emails will be stored on a VPS outside Tanzania and sent through an email provider
outside Tanzania. Under the Personal Data Protection Act, 2022 that is a cross-border transfer.
**Owner to confirm compliance before launch.**

## Pre-launch compliance checklist (owner)

- [ ] Register with the Personal Data Protection Commission (PDPC)
- [ ] Confirm with TCRA whether an online-content licence applies
- [ ] Business registration and TIN before taking any payment
- [ ] Final privacy policy and terms text in Swahili and English
- [ ] Confirm the cross-border transfer basis for subscriber data

Sections on the daily routine, deploy, backups and rotating tokens are added in the milestones
that build those parts.
