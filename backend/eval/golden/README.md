# Golden set

Pages with hand-checked answers, used by `uv run python -m lina.eval` to measure the
extractor before and after a prompt or model change.

Each case is two files:

- `NAME.html` — the page exactly as fetched.
- `NAME.json` — `page`, `source_url`, `default_type`, `today` (the date the answers assume),
  and `expected`: `is_opportunity`, and for real opportunities `type`, `deadline`
  (YYYY-MM-DD or null), `open_to_tanzanians`, `funding`, `education_levels`.

Label what the page actually supports, not what you know from elsewhere. If the page does not
say who may apply, the right answer is `"unclear"`.

The five `synthetic_*` cases were written by hand to exercise the plumbing. They are easy and
say little about real accuracy. The target is about 20 real pages from verified sources, across
all types, including two or three awkward ones (deadline only in an image, rolling deadline,
page that lists several programmes). Replace the synthetic cases as real ones are added.
