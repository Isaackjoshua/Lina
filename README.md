# LINA

A free, bilingual (Swahili + English) site that publishes verified opportunities for young
people in Tanzania. The full product spec is in [SPEC.md](SPEC.md).

**Status:** Milestone 3 (extraction and quality gates). The site is still a placeholder. The
pipeline fetches verified sources, reads each page with Claude, checks the result, and leaves
candidates in the database for review. The review screen is Milestone 4.

## What is in the repo

| Path | What it is |
| --- | --- |
| `backend/` | Python: FastAPI API, scheduled worker, database models and migrations |
| `web/` | Next.js: public site (`/sw`, `/en`) and the admin (`/admin`) |
| `docker-compose.yml` | Runs the database, API, worker and website together |
| `backend/sources.yaml` | The list of official sources |
| `backend/content/glossary.yaml` | Swahili terms given to the extractor. Yours to review and expand |
| `backend/eval/golden/` | Hand-checked pages for measuring extraction accuracy |
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
| `MAX_ITEMS_PER_RUN` | backend | Most pages fetched, and most extracted, in one run (default 60) |
| `ANTHROPIC_API_KEY` | backend | Claude API key. Extraction refuses to run without it |
| `EXTRACT_MODEL` | backend | Model that reads pages (default `claude-haiku-5-5`) |
| `REVIEW_MODEL` | backend | Second-opinion model for shaky answers (default `claude-sonnet-5-5`) |
| `MAX_DAILY_LLM_USD` | backend | Daily spend cap for extraction, estimated (default 2) |

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

## How the pipeline works

Commands run from `backend/` (or inside Docker: `docker compose run --rm api python -m lina.pipeline <command>`).

| Command | What it does |
| --- | --- |
| `uv run python -m lina.pipeline sync` | Copies `sources.yaml` into the database |
| `uv run python -m lina.pipeline check --probe` | Checks every source's robots.txt and loads each allowed listing once |
| `uv run python -m lina.pipeline fetch` | The dry run: fetches verified sources, stores new pages as raw items, prints a report |
| `uv run python -m lina.pipeline fetch --source udsm` | Same, for one source |
| `uv run python -m lina.pipeline run` | The daily pipeline: fetch, then extract into the review queue. The worker runs this at 04:00 EAT |
| `uv run python -m lina.pipeline extract` | Only the extraction step, on pages already fetched |
| `uv run python -m lina.eval` | Measures extraction accuracy on the golden set (calls the API, costs a few cents) |

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

### From page to review candidate

Each fetched page goes through these steps. Nothing is published by any of them; everything
ends as `needs_review` or `rejected`.

1. **Clean** the page to its main text. A free check drops pages that are clearly not
   opportunities (news, stubs) before any money is spent.
2. **Extract** with Claude (`EXTRACT_MODEL`): type, titles and summaries in both languages,
   deadline, eligibility, funding and so on, plus the exact sentence it took the deadline and
   eligibility from, and a confidence score per key field.
3. **Check the evidence.** Code looks for each quoted sentence in the page. If it is not there,
   the field is blanked and the item is flagged. "Open to Tanzanians: yes" is only kept if the
   page names Tanzania, the region, or all nationalities.
4. **Second opinion.** If confidence is low or an evidence check failed, the page is read again
   by `REVIEW_MODEL`, and that answer goes through the same checks.
5. **Drop** pages that are not opportunities or whose deadline has passed.
6. **Check the apply link**: it must load. A link that leaves the official site is kept but flagged.
7. **Scam rules**: fees, personal email or WhatsApp-only contact, guarantees, pressure, requests
   for ID or bank details, organization not matching the site. **Any request for money rejects
   the listing automatically**, with the offending sentence saved as the reason.
8. **Dedupe**: the same page, the same organization + title + deadline, or a near-identical title
   is merged into the existing candidate. A listing you have already approved or rejected is
   never changed by a later run.

The raw page is deleted as soon as it is processed. The cleaned text is kept only until the
listing is reviewed.

**Cost control.** A run handles at most `MAX_ITEMS_PER_RUN` pages and stops extracting once the
day's estimated spend reaches `MAX_DAILY_LLM_USD`; the rest wait for the next run. Every run
records tokens and estimated cost in `pipeline_runs`. The prices used for the estimate are in
`backend/lina/pipeline/extract.py` and need updating if Anthropic changes them.

### Measuring accuracy

`backend/eval/golden/` holds saved pages with hand-checked answers. `uv run python -m lina.eval`
prints accuracy per field (type, deadline, open to Tanzanians, funding, education levels) and
lists every miss. Run it before and after changing the prompt or a model. See
`backend/eval/golden/README.md` for how to add a case.

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
UNDER CONSTRUCTION!!!!
