# LINA — Build Spec for Claude Code

## 0. How to work with me

- I'm a solo developer with about **one hour a day**. That hour goes to reviewing your work and the daily content queue, so:
  - Build the milestones in §12 one at a time. When a milestone is done, stop and give me: what changed, how to run it, a 5-minute manual test checklist, and anything you need from me.
  - Keep each milestone shippable and small enough to review in one sitting.
- Ask before: adding a paid service, adding a heavy dependency, changing the stack in §4, or deviating from the non-negotiables in §2.
- Maintain a `CLAUDE.md` with conventions, commands, and dated decisions so future sessions stay consistent.
- Write tests for the logic that protects quality: extraction validation, evidence checks, dedupe, scam rules, expiry, digest filtering. Use saved HTML fixtures — tests must never hit the network.
- Secrets live in `.env` only; keep `.env.example` current. Never commit tokens.
- Prefer boring, well-documented tools over clever ones. I have to maintain this alone.

## 1. Product

LINA ([DOMAIN]) is a free, bilingual (Swahili + English) platform that publishes verified opportunities for young people in Tanzania first, then East Africa: jobs, internships, scholarships, fellowships, hackathons, grants, conferences, competitions and trainings — across all fields.

**Positioning:** every kind of opportunity in one place, in Swahili and English, matched to the user, delivered on WhatsApp. It is not "another job board" — the Tanzanian job-board market is already crowded. **Quality beats volume:** the target is 10–20 approved listings per day.

**Daily loop:**
1. A scheduled pipeline fetches official sources, uses the Claude API to extract structured fields and write bilingual summaries, removes duplicates, flags scams, and puts candidates in a review queue.
2. I review in ≤30 minutes (approve / edit / reject).
3. Approved listings publish to the website; an Instagram carousel and a ready-to-paste WhatsApp Channel post are generated; subscribers receive filtered email digests.

**Goals:** side income + social impact. Job seekers never pay for core features (browsing, filters, digests, guides).

## 2. Non-negotiables

### Trust
- Every listing links to the **official source** (the organization's own page or an official portal). If no official page can be found, discard the item.
- Never invent facts. Unknown → `null` / `"unclear"`, shown to users as "Haijabainishwa / Not specified".
- Deadline and eligibility fields require **evidence**: the extractor returns the exact source sentence it used, and code verifies that string appears in the fetched source text. If the check fails, set the field to null and flag the item for review.
- Nothing is published without my approval in Phase 1.
- Scam screening (§6.6) runs on every item. Listings that ask applicants for money are rejected, never published.
- Sponsored items (later phases) must be labelled "Imedhaminiwa / Sponsored".

### Copyright & sources
- Keep source text only as long as needed for extraction and evidence checks. Publish only our own summaries (max ~80 words per language) plus short factual fields. Never republish full descriptions.
- Phase 1 uses **official sources and organization submissions only**. Do not scrape competitor aggregators (job boards, opportunity blogs), LinkedIn, or any site whose robots.txt or terms forbid it.
- Fetch politely: clear User-Agent with a contact URL, respect robots.txt, per-domain rate limits, response caching, backoff on errors.

### Privacy (Tanzania Personal Data Protection Act, 2022)
- Collect minimal data: email, language, preferences. No phone numbers in Phase 1.
- Explicit opt-in (unticked checkbox), double opt-in by email, consent text versioned and stored with a timestamp, one-click unsubscribe in every email, a preference centre via tokenized link, and a documented process for data access/deletion requests.
- Privacy policy and terms pages in Swahili and English — create placeholders with clear TODOs; I will supply the final legal text.
- Note in the README that storing subscriber data with a foreign email provider is a cross-border transfer; I will confirm compliance.

## 3. Language rules

- **Swahili-first on Instagram and WhatsApp; both languages on the website.**
- Website: locale routes `/sw/...` and `/en/...`, `DEFAULT_LOCALE=sw`, `hreflang` tags, a language switcher on every page. Each listing has its own SW and EN page.
- Swahili must be natural Tanzanian Swahili, not word-for-word translation. Keep organization, program and degree names in their original form. Date format: "30 Novemba 2026".
- Create `content/glossary.yaml` as a starting point for me to review and expand, and pass it to the extractor. Examples: deadline → tarehe ya mwisho; scholarship → ufadhili wa masomo; fully funded → ufadhili kamili; internship → mafunzo kwa vitendo; eligibility → vigezo / sifa; job → kazi / ajira. Keep "fellowship" and "hackathon" untranslated.

## 4. Tech stack (my default — confirm or push back in your first reply)

- One language end to end: **TypeScript**.
- **Next.js** (App Router), server-rendered/static pages with incremental revalidation, **Tailwind CSS**, **next-intl** for i18n.
- **PostgreSQL + Prisma.**
- **Worker:** Node scripts in the same repo (run with `tsx`) for the pipeline, expiry, digests and social generation, scheduled by cron inside a worker container.
- **Claude API** via the official Anthropic TypeScript SDK. Models set by env vars: `EXTRACT_MODEL=claude-haiku-5-5` (default for extraction/translation) and `REVIEW_MODEL=claude-sonnet-5-5` (only for low-confidence items). Use structured output via tool use with a JSON schema, validate with zod, use prompt caching for the system prompt and glossary, and consider the Message Batches API since the daily run isn't time-sensitive.
- **Puppeteer** to render Instagram images from HTML templates (I've used it before).
- **Email:** a transactional provider behind an adapter interface — ask me which one before integrating.
- **Admin auth:** Auth.js with GitHub OAuth, restricted to `ADMIN_GITHUB_USERNAME`.
- **Analytics:** optional, self-hosted and privacy-friendly (e.g., Umami) — ask me.
- **Deploy:** Docker Compose on one Linux VPS (web, worker, postgres, reverse proxy with automatic HTTPS). Nightly `pg_dump` backups to off-server storage (ask me where).
- **Timezone everywhere:** `Africa/Dar_es_Salaam` (EAT).

## 5. Data model (starting point — refine it, but keep the intent)

**Opportunity**
- `id`, `slug` (per locale), `type`: job | internship | scholarship | fellowship | hackathon | grant | conference | competition | training
- `title_en`, `title_sw`, `organization`, `organization_url`
- `source_url` (official page), `apply_url`, `source_id`
- `summary_en`, `summary_sw` (our own words, ≤ ~80 words each)
- `fields[]` (sector/discipline tags from a controlled list)
- `education_levels[]`: secondary | certificate | diploma | bachelor | master | phd | any
- `eligible_countries[]` or "any"; `open_to_tanzanians`: yes | no | unclear
- `age_min`, `age_max`, `other_eligibility` (short text)
- `funding`: fully_funded | partially_funded | paid | unpaid | stipend | unclear; `funding_note`
- `location_city`, `location_country`, `work_mode`: onsite | remote | hybrid | unclear
- `deadline` (date, nullable), `deadline_type`: fixed | rolling | unclear
- `evidence`: `{ deadline_quote, eligibility_quote }`
- `confidence` (0–1 per key field), `scam_flags[]`, `report_count`
- `status`: needs_review | approved | rejected | expired | hidden
- `sponsored` (bool, default false), `submitted_by_org` (bool)
- `content_hash`, `dedupe_key`, `first_seen_at`, `published_at`, `updated_at`, `reviewer_note`

**Source**
- `id`, `name`, `url`, `kind`: rss | html_list | sitemap | manual, parsing hints, `default_type`, `country`, `active`, `verified`, `fetch_frequency`, `last_success_at`, `consecutive_failures`, `robots_checked_at`, `notes`

**Subscriber**
- `email`, `locale`, `types[]`, `fields[]`, `education_levels[]`, `frequency`: weekly | daily, `consent_text_version`, `consented_at`, `confirmed_at`, `unsubscribe_token`, `status`

**Also:** `PipelineRun` (counts, errors, tokens used, estimated cost), `Report` (listing reports), `Submission` (organization submissions), `SocialPost` (Instagram/WhatsApp drafts and publish status), `OutboundClick` (apply-button clicks per listing — our main impact metric).

## 6. Daily pipeline (04:00 EAT)

**6.1 Sources.** Seed from `sources.yaml`. Propose 15–25 official candidate sources (names + URLs) across:
- the Tanzanian government public-service recruitment portal;
- announcement pages of major Tanzanian universities (e.g., UDSM, MUHAS, UDOM, SUA, NM-AIST);
- HESLB and COSTECH;
- embassy scholarship pages in Dar es Salaam;
- major international scholarship programs (e.g., Chevening, Commonwealth, Erasmus Mundus, DAAD, MEXT, Mastercard Foundation Scholars, Fulbright);
- UN and international NGO careers pages filtered to Tanzania;
- competition/hackathon platforms relevant to Africa (e.g., Zindi).

For each, check robots.txt and terms, and mark `verified: false` until I confirm.

**6.2 Fetch.** RSS where available; otherwise list page → item links → detail pages. Per-domain rate limits, ETag/Last-Modified caching, retries with backoff, timeouts. Track source health; flag a source after 3 consecutive failures.

**6.3 Pre-filter** cheaply before calling Claude: skip already-seen URLs/content hashes, pages whose deadline has clearly passed, and non-opportunity pages.

**6.4 Extract.** Clean each page to its main text and send it to Claude with the extraction contract (§7). Enforce `MAX_ITEMS_PER_RUN` (default 60) and a daily spend cap `MAX_DAILY_LLM_USD`. Log tokens and estimated cost per run.

**6.5 Validate.** zod schema; evidence strings must exist in the source text (normalize whitespace/case); dates must parse and be in the future; URLs must resolve (follow redirects) and stay on the official domain.

**6.6 Scam screening** — rule-based flags plus a short Claude risk note. Flag: application/processing/"registration" fees; contact only via personal email or WhatsApp; no official domain; guarantees ("100% visa", "guaranteed job"); unrealistic pay for the role; urgency pressure; requests for ID or bank details up front; mismatch between the claimed organization and the domain. **Any fee request → auto-reject with the reason logged.**

**6.7 Dedupe.** Canonical URL + normalized (organization, title, deadline) + fuzzy title similarity. Merge into the existing record instead of creating a new one.

**6.8 Queue + summary.** Everything lands as `needs_review`. After each run, email me a short summary: new candidates, failures, cost.

**6.9 Expiry job (00:15 EAT).** Deadline passed → `expired`. Expired pages stay online with a clear "Imefungwa / Closed" banner, drop out of feeds and digests, and leave the sitemap after 30 days.

## 7. Extraction contract (the Claude prompt you will write)

- **Input:** cleaned source text, source URL, the source's default type, today's date, the glossary.
- **Output:** a single tool call matching the JSON schema — every §5 field the page supports, evidence quotes, per-field confidence, and `is_opportunity` (false → discard).
- **System-prompt rules:**
  - Summarize in your own words; never copy more than a short phrase.
  - Prefer null / "unclear" over guessing.
  - Evidence quotes must be verbatim from the source.
  - `open_to_tanzanians = "yes"` only if the text names Tanzania, East Africa, Africa, developing/low- and middle-income countries, or all nationalities.
  - Write natural Tanzanian Swahili using the glossary; keep proper names untranslated.
- **Golden set:** `eval/golden/` with ~20 hand-checked source pages and expected outputs, plus `npm run eval` reporting field-level accuracy (type, deadline, open_to_tanzanians, funding, education_levels) so prompt or model changes can be measured. I will help label.

## 8. Admin (protected `/admin`)

- **Review queue built for speed** (target ≤30 min/day): one item per screen; extracted fields on the left; source excerpt on the right with evidence quotes highlighted; scam flags and confidences visible; inline editing of every field, including both summaries.
- **Keyboard shortcuts:** A approve, R reject (with quick reasons), E edit, J/K next/previous. Bulk reject.
- **Pages:** queue; all listings (search/filter, unpublish); sources (health, enable/disable, add); reports; submissions; pipeline runs (errors, cost); social posts (preview, copy, publish status); subscribers (counts only, plus export/delete for data requests).
- **"Copy WhatsApp post"** button that copies today's Swahili-first Channel post to the clipboard.

## 9. Public website

- **Mobile-first and light** for cheap phones and small data bundles: minimal client JS, no heavy UI libraries, optimized images, system fonts or one small font. Target listing pages under ~150 KB transferred.
- **Home:** "Inafungwa wiki hii / Closing this week", "Mpya leo / New today", category tiles.
- **One section per type** (e.g., `/sw/ufadhili-wa-masomo` and `/en/scholarships`) with filters: field, education level, open to Tanzanians, funding, work mode, deadline window — plus site search.
- **Listing page:** bilingual summary; key-facts box (deadline, eligibility, funding, location); a prominent "Apply on the official site" button (tracked outbound click); source link; "Report this listing" (3 reports → auto-hide pending review); WhatsApp share button.
- **Guides** (MDX, SW/EN) with placeholders: applying through the government recruitment portal, preparing academic certificates, avoiding scholarship scams, writing a CV.
- **"Submit an opportunity"** form for organizations → goes to my queue.
- **Subscribe page + preference centre.** About, Privacy, Terms, Contact.
- **SEO:** sitemap, robots.txt, canonical + hreflang, Open Graph images, RSS feed per type. Structured data: `Event` for hackathons/conferences. Use `JobPosting` for jobs **only** if our pages meet Google's current job-posting guidelines — check them and tell me if they conflict with our summary-only rule before adding it.

## 10. Distribution

### Instagram (Swahili-first)
- A daily carousel from that day's approved listings: a cover slide plus listing slides (verify the current carousel item limit in Meta's docs), 1080×1350, brand template, rendered with Puppeteer from HTML.
- Caption: Swahili first, one English line, link-in-bio note, hashtags from a configurable list.
- Two modes via env var:
  - `export` (default, build first): save images + caption to an admin page/folder for manual posting.
  - `publish`: Instagram Graph API content publishing — host slides at public URLs, create item containers, create the carousel container, publish; refresh long-lived tokens; check the account's publishing quota via the content-publishing-limit endpoint.

### WhatsApp Channel
- Meta's official Cloud API doesn't support Channels, and I won't use unofficial gateways (number-ban risk). Generate a ready-to-paste, Swahili-first post (a short list with deadlines and one link to today's page) in the admin, with a copy button.

### Newsletter
- Weekly digest Mondays 07:00 EAT; daily digest (07:00 EAT) for subscribers who choose it.
- Each subscriber gets only the types, fields and levels they picked, in their language, sorted by deadline, with a "closing soon" block. Lightweight HTML plus a plain-text version.
- Skip sending when a subscriber has zero matches for that period.

## 11. Operations

- **Schedules (EAT):** pipeline 04:00 → run-summary email; expiry 00:15; Instagram generation at a configurable time after my review; digests at 07:00 (weekly on Mondays, daily for daily subscribers).
- Health endpoint, error alerts to my email, structured logs, a source-health report.
- Running monthly LLM spend estimate on the admin dashboard.
- **README:** local setup; environment variables; how the pipeline works; my daily routine (review → copy WhatsApp post → done); deploy; backup and restore; adding a source; rotating tokens; and a **pre-launch compliance checklist** for me to complete (PDPC registration, confirming with TCRA whether an online-content licence applies, business registration and TIN before taking payments).

## 12. Milestones (Phase 1) — one at a time, stop after each

**M1 — Scaffold.** Repo, Docker Compose (web, worker, db), Prisma schema from §5, i18n skeleton, Tailwind, Auth.js admin login, `CLAUDE.md`, README, `.env.example`, CI running lint + typecheck + tests.
*Done when:* `docker compose up` gives me a bilingual placeholder site and I can log in to `/admin`.

**M2 — Sources & fetching.** `sources.yaml` with proposed (unverified) sources, fetchers (RSS, list → detail), politeness, caching, source health, `PipelineRun` logging, HTML fixtures for tests.
*Done when:* a dry run fetches and stores raw items from verified sources and prints a run report.

**M3 — Extraction & quality gates.** Extraction contract, zod validation, evidence check, URL checks, scam rules, dedupe, cost caps, golden-set eval command.
*Done when:* a run turns raw items into `needs_review` candidates and `npm run eval` prints field-level accuracy.

**M4 — Review queue.** The full admin review flow from §8.
*Done when:* I can review 20 candidates in under 15 minutes.

**M5 — Public site.** Home, sections, filters, search, listing pages, report button, submit form, guide placeholders, SEO, expiry job.
*Done when:* approved items render correctly in SW and EN, closed items show the banner, and Lighthouse mobile performance is ≥ 90 on a listing page.

**M6 — Newsletter & privacy.** Signup with explicit consent, double opt-in, preference centre, unsubscribe, weekly/daily digests, privacy/terms placeholders, data-request process.
*Done when:* I can subscribe, confirm, change preferences, receive a correctly filtered test digest, and unsubscribe in one click.

**M7 — Social.** Instagram export mode, WhatsApp post generator, then Graph API publish mode behind a flag.
*Done when:* each day's approved items produce a carousel + caption and a WhatsApp post I can copy.

**M8 — Deploy & operate.** VPS deploy, HTTPS, cron schedules, backups with a tested restore, alerts, run-summary email, daily-ops section in the README.
*Done when:* the whole daily loop runs unattended except for my review.

## 13. Later phases — design for them, don't build them yet

- **Phase 2:** user accounts and profiles, "You're eligible" feed, deadline reminders, application tracker, more Swahili guides, featured/sponsored listings and paid job posts (mobile money payments).
- **Phase 3:** CV builder tied to specific listings; essay feedback (a coach, not a ghostwriter) on pay-per-use credits; paid WhatsApp alerts via the official Cloud API; employer self-serve posting.
- **Phase 4:** Kenya, Uganda, Rwanda; partner digests for universities.

Keep the schema and code structure friendly to these (e.g., the `sponsored` flag, a payments module boundary, a notification-channel abstraction), but add no UI or logic for them now.

## 14. Open questions — ask me these before starting

1. Brand name, domain and Instagram handle? (Use `[BRAND_NAME]`, `[DOMAIN]`, `[INSTAGRAM_HANDLE]` placeholders until then.)
2. Do you agree with the TypeScript stack in §4, or would a Python (FastAPI) backend + Next.js frontend serve me better? Give a short recommendation with tradeoffs for a solo developer with one hour a day.
3. Which transactional email provider? Recommend 2–3 options; if you can't check current pricing yourself, say so and I'll check.
4. VPS provider/region preference, and where should backups go?
5. Brand colours and fonts for the site and Instagram templates, or should you propose a simple palette?
6. Analytics: self-hosted Umami, or none for now?
