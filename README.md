# LINA

A free, bilingual (Swahili + English) site that publishes verified opportunities for young
people in Tanzania. The full product spec is in [SPEC.md](SPEC.md).

**Status:** Milestone 1 (scaffold). A placeholder site in two languages, an admin login, the
database schema, and CI. No listings yet.

## What is in the repo

| Path | What it is |
| --- | --- |
| `backend/` | Python: FastAPI API, scheduled worker, database models and migrations |
| `web/` | Next.js: public site (`/sw`, `/en`) and the admin (`/admin`) |
| `docker-compose.yml` | Runs the database, API, worker and website together |
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

Sections on the pipeline, the daily routine, deploy, backups, adding a source and rotating
tokens are added in the milestones that build those parts.
