# Phase 1 Spec — Corpus Fetch and Structure

## Context

Phase 0.5 confirmed working endpoints, request patterns, timing, and data gaps for the accepted V1 docket set. The integration verdict is `go`. Phase 1 builds a local corpus from those confirmed patterns so that later analysis phases have clean, structured input without repeated API calls.

This spec is the authoritative implementation contract for `fetch_corpus.py`. Do not implement anything not described here. Do not scaffold modules, classes, or package structure beyond a single standalone script.

---

## Deliverable

One standalone script: `fetch_corpus.py`.

Running it once produces a complete local corpus. Re-running it is safe and fast because all network I/O is cached. The script requires one environment variable:

```
REGULATIONS_GOV_API_KEY=<key>
pip install requests
python fetch_corpus.py
```

No other dependencies beyond the Python standard library and `requests`.

---

## Output layout

```
corpus/
  EPA-HQ-OAR-2020-0272/
    proposed_rule.xml        # raw FR XML (immutable)
    proposed_rule.json       # parsed sections (see schema)
    final_rule.xml
    final_rule.json
    comments.json            # all comments (see schema)
    fetch_log.json           # timing, cache hits, validation (see schema)
  EPA-HQ-OAR-2018-0225/
    ...
  EPA-HQ-OAR-2020-0430/
    ...
cache/
  immutable/                 # forever TTL — FR docs, comment detail records
  lists/                     # 24h TTL — paginated list pages
```

`corpus/` and `cache/` must be listed in `.gitignore`. If `.gitignore` does not exist, create it with those two entries only.

---

## Docket manifest

These values are fixed and must be hardcoded. Do not re-discover them from the API.

### EPA-HQ-OAR-2020-0272 — Revised Cross-State Air Pollution Rule Update for the 2008 Ozone NAAQS

| Field | Value |
|---|---|
| Proposed FR doc number | `2020-23237` |
| Proposed XML URL | `https://www.federalregister.gov/documents/full_text/xml/2020/10/30/2020-23237.xml` |
| Final FR doc number | `2021-05705` |
| Final XML URL | `https://www.federalregister.gov/documents/full_text/xml/2021/04/30/2021-05705.xml` |
| Comment-on doc ID | `EPA-HQ-OAR-2020-0272-0001` |
| Comment-on object ID | `0900006484941754` |
| Expected total comments | `85` |
| Expected proposed sections (approx) | `290` |
| Expected final sections (approx) | `297` |

### EPA-HQ-OAR-2018-0225 — Determination Regarding Good Neighbor Obligations for the 2008 Ozone NAAQS

| Field | Value |
|---|---|
| Proposed FR doc number | `2018-14737` |
| Proposed XML URL | `https://www.federalregister.gov/documents/full_text/xml/2018/07/10/2018-14737.xml` |
| Final FR doc number | `2018-27160` |
| Final XML URL | `https://www.federalregister.gov/documents/full_text/xml/2018/12/21/2018-27160.xml` |
| Comment-on doc ID | `EPA-HQ-OAR-2018-0225-0001` |
| Comment-on object ID | `09000064834ca2df` |
| Expected total comments | `317` |
| Expected proposed sections (approx) | `47` |
| Expected final sections (approx) | `48` |

### EPA-HQ-OAR-2020-0430 — Primary Copper Smelting NESHAP Reviews

| Field | Value |
|---|---|
| Proposed FR doc number | `2021-28273` |
| Proposed XML URL | `https://www.federalregister.gov/documents/full_text/xml/2022/01/11/2021-28273.xml` |
| Final FR doc number | `2024-09883` |
| Final XML URL | `https://www.federalregister.gov/documents/full_text/xml/2024/05/13/2024-09883.xml` |
| Comment-on doc ID | `EPA-HQ-OAR-2020-0430-0001` |
| Comment-on object ID | `0900006484f17763` |
| Expected total comments | `22` |
| Expected proposed sections (approx) | `100` |
| Expected final sections (approx) | `144` |

---

## Cache layer

All network I/O must go through the cache. Implement two stores:

**Immutable store** (`cache/immutable/`): Federal Register full-text XML documents and Regulations.gov comment detail records. These never change once fetched. TTL is forever — never re-fetch if the file exists.

**List store** (`cache/lists/`): Regulations.gov paginated comment list pages. These can drift. TTL is 24 hours — re-fetch if the cached file is older than 24 hours or does not exist.

Cache key → filename mapping: take the URL or record ID, replace non-alphanumeric characters with underscores, truncate to 200 characters, and append `.json` (or `.xml` for FR documents). Store the raw response body in the file, not a parsed form.

For list-store entries, wrap the response in a thin envelope so the TTL can be checked without parsing the payload:

```json
{
  "_cached_at": "2026-04-04T22:52:18+00:00",
  "body": { ...original response... }
}
```

Write cache files atomically: write to a `.tmp` file in the same directory, then rename to the final path. This prevents corrupt cache files on crash.

---

## Federal Register fetch

Use `requests.get(url, timeout=30)` with no API key required.

For each document, attempt the XML URL first. If the response is not HTTP 200 or the content-type does not contain `xml`, fall back to the HTML URL. Log which source was used.

Write the raw response bytes to:
- `cache/immutable/{cache_key}.xml`
- `corpus/{docket_id}/proposed_rule.xml` (or `final_rule.xml`)

Then parse and write to `corpus/{docket_id}/proposed_rule.json` (see FR parse section below).

---

## Federal Register XML parse

Parse the raw XML with `xml.etree.ElementTree`. The OFR XML schema uses these tags:

- `<HD SOURCE="HED">` — top-level heading
- `<HD SOURCE="HD1">` — first-level subheading
- `<HD SOURCE="HD2">` — second-level subheading
- `<HD SOURCE="HD3">` — third-level subheading
- `<P>` — paragraph
- `<SECTION>` — a discrete regulatory section (in `<REGTEXT>`)
- `<SECTNO>` — section number within `<SECTION>`
- `<SUBJECT>` — subject line within `<SECTION>`

Walk the XML tree in document order. Build a flat list of sections using this algorithm:

1. When an `<HD>` tag is encountered, start a new section. The heading text is the tag's text content (strip whitespace).
2. When a `<P>` tag is encountered inside the current section, append its text content to the current section's `body_text`, separated by a newline.
3. When a `<SECTION>` tag is encountered, treat it as a section. The heading is `{SECTNO text} {SUBJECT text}` (strip and join). Collect all `<P>` children as `body_text`.
4. Track whether the current position is inside a `<PREAMBLE>` ancestor or a `<REGTEXT>` ancestor and set the `source` field accordingly. Anything outside both is `source: "other"` and may be included or omitted at implementer discretion.

Text extraction: walk the node recursively. At each level, collect `node.text` and `child.tail`. Skip any node whose local tag name is in the skip set (`GPH`, `MATH`, `FTNT`, `APPRO`, `FRDOC`) — do not descend into it. Join all collected strings and collapse internal whitespace runs to a single space, stripping leading/trailing whitespace.

Skip `<GPH>`, `<MATH>`, `<FTNT>`, `<APPRO>`, and `<FRDOC>` tags entirely — do not include their content in any section's body.

Section IDs: assign sequentially within each document. Format: `{docket_id}_{doc_type}_{seq:04d}` where `doc_type` is `proposed` or `final` and `seq` starts at 1. Example: `EPA-HQ-OAR-2020-0272_proposed_0001`.

---

## Regulations.gov comment fetch

Base URL: `https://api.regulations.gov/v4`  
Required header: `X-Api-Key: {REGULATIONS_GOV_API_KEY}`  
Required delay between requests: 1.25 seconds (enforced via `time.sleep`).

### Step 1 — page through the comment list

```
GET /v4/comments?filter[commentOnId]={object_id}&page[size]=25&page[number]={n}
```

Start at page 1. Continue until the response contains fewer than 25 records or the `meta.totalElements` count has been reached. Cache each page in the list store with a 24h TTL.

### Step 2 — detail fallback for every comment

For every comment record returned by the list pages, check the `attributes.comment` field. Whether or not it is populated, **always** call the detail endpoint for every comment:

```
GET /v4/comments/{commentId}
```

Cache the detail response in the immutable store by comment ID. On a re-run, skip the detail call if the immutable cache file already exists.

Use the `attributes.comment` field from the detail response as the authoritative text. Do not use the list-page text field.

**Rationale**: The integration spike confirmed that list-page comment fields are empty for ~96% of records across all three dockets. The detail endpoint is the only reliable source of inline text. The full sweep (424 detail calls at 1.25 s/req ≈ 9 minutes total) is a one-time cost; subsequent runs are instant from cache.

### Step 3 — classify each comment

Classify based on the detail-endpoint `attributes.comment` field:

- `substantive_inline` — text is present, length ≥ 10 characters after stripping whitespace, and does not consist solely of attachment-pointer language (see below)
- `attachment_pointer` — text is present but matches attachment-pointer patterns: contains phrases like "see attached", "please see attached", "attached hereto", "attachment", or consists of a submitter name only
- `no_text` — text field is absent, null, or empty after stripping

Store all three classifications in `comments.json`. Do not discard `no_text` or `attachment_pointer` records.

---

## Output schemas

### `proposed_rule.json` and `final_rule.json`

A JSON array of section objects:

```json
[
  {
    "section_id": "EPA-HQ-OAR-2020-0272_proposed_0001",
    "docket_id": "EPA-HQ-OAR-2020-0272",
    "fr_doc_number": "2020-23237",
    "document_type": "proposed",
    "source": "preamble",
    "heading": "I. General Information",
    "body_text": "A. Does this action apply to me?\n\nThis action applies to..."
  }
]
```

`source` is one of `"preamble"`, `"regulatory_text"`, or `"other"`.  
`heading` may be an empty string if no heading tag preceded the paragraphs.  
`body_text` is newline-separated paragraph text. Empty sections (no body text after stripping) should be omitted.

### `comments.json`

A JSON array of comment objects:

```json
[
  {
    "comment_id": "EPA-HQ-OAR-2020-0272-0005",
    "docket_id": "EPA-HQ-OAR-2020-0272",
    "comment_on_doc_id": "EPA-HQ-OAR-2020-0272-0001",
    "comment_on_object_id": "0900006484941754",
    "title": "Comment submitted by...",
    "submitter_name": "John Doe",
    "posted_date": "2020-11-30",
    "text": "The proposed rule should...",
    "classification": "substantive_inline",
    "detail_fallback_used": true
  }
]
```

`text` is the value of `attributes.comment` from the detail endpoint, stripped of leading/trailing whitespace. Use an empty string if absent or null.  
`submitter_name` and `posted_date` come from the list-page `attributes` object. Use `null` if absent.  
`detail_fallback_used` is always `true` for every record in this implementation (since we always call the detail endpoint).

### `fetch_log.json`

```json
{
  "docket_id": "EPA-HQ-OAR-2020-0272",
  "generated_at": "<ISO-8601 UTC timestamp>",
  "fr": {
    "proposed": {
      "fr_doc_number": "2020-23237",
      "source_used": "xml",
      "raw_bytes": 1624729,
      "sections_extracted": 284,
      "sections_expected_approx": 290,
      "sections_within_tolerance": true,
      "cache_hit": false,
      "duration_s": 0.283
    },
    "final": {
      "fr_doc_number": "2021-05705",
      "source_used": "xml",
      "raw_bytes": 1974016,
      "sections_extracted": 291,
      "sections_expected_approx": 297,
      "sections_within_tolerance": true,
      "cache_hit": false,
      "duration_s": 0.372
    }
  },
  "comments": {
    "comment_on_object_id": "0900006484941754",
    "total_reported_by_api": 85,
    "total_fetched": 85,
    "list_pages_fetched": 4,
    "detail_calls_made": 85,
    "detail_calls_cache_hits": 0,
    "substantive_inline": 3,
    "attachment_pointer": 0,
    "no_text": 82,
    "total_requests": 89,
    "wall_clock_s": 112.1
  },
  "validation": {
    "fr_proposed_sections_within_tolerance": true,
    "fr_final_sections_within_tolerance": true,
    "comments_total_matches_api": true,
    "passed": true
  }
}
```

**Section count tolerance**: extracted count must be within ±25% of the expected approximate count from the manifest. Set `sections_within_tolerance` to `false` and print a warning (do not crash) if outside this range.

**Comment count validation**: `total_fetched` must equal `total_reported_by_api`. If they differ, print a warning and record `comments_total_matches_api: false`. Do not crash.

---

## Error handling

- Catch `requests.exceptions.RequestException` on every network call. Log the error, wait 2 seconds, and retry once. If the retry also fails, log it and skip that record. Do not crash the script.
- HTTP 429: wait 60 seconds before retrying. If a second 429 is received, log it and abort the current docket's comment sweep, writing whatever was collected to that point.
- HTTP 404: log as a data gap. Do not retry. Record the gap in `fetch_log.json`.
- HTTP 403: print a clear message indicating an API key problem and exit immediately.
- The script is fully restartable. Because all successful responses are cached before processing, re-running after a crash resumes from the last uncached point. Do not delete cache files on error.

---

## Console output

Print one line per major operation. Use a consistent prefix format:

```
[FR]    EPA-HQ-OAR-2020-0272  proposed  2020-23237  fetching...
[FR]    EPA-HQ-OAR-2020-0272  proposed  2020-23237  ok  (1624729 bytes, 284 sections)
[CMTS]  EPA-HQ-OAR-2020-0272  page 1/4  25 records
[CMTS]  EPA-HQ-OAR-2020-0272  detail  EPA-HQ-OAR-2020-0272-0005  substantive_inline
...
[LOG]   EPA-HQ-OAR-2020-0272  written  corpus/EPA-HQ-OAR-2020-0272/fetch_log.json
```

Print a summary at the end:

```
=== Phase 1 corpus fetch complete ===
EPA-HQ-OAR-2020-0272   proposed 284 sections | final 291 sections | 85 comments (3 substantive)
EPA-HQ-OAR-2018-0225   proposed 44 sections  | final 47 sections  | 317 comments (13 substantive)
EPA-HQ-OAR-2020-0430   proposed 98 sections  | final 141 sections | 22 comments (1 substantive)
Validation: PASS
```

---

## What this script does NOT do

- No section diffing between proposed and final rule
- No comment-to-section alignment or attribution
- No NLP, embeddings, or ML
- No database — file-based output only
- No attachment download or parsing
- No UI, API, or web server
- No cross-agency dockets
- No eCFR integration

---

## Done criteria

1. `fetch_corpus.py` runs end-to-end against live APIs without crashing
2. All 6 FR documents fetched, raw XML written to `corpus/`, parsed JSON written with non-zero section counts
3. All comments for all 3 dockets fetched (425 total, ±1 for any API count drift), with detail sweep completed
4. `comments.json` contains all comment records for each docket with `classification` set on every record
5. `fetch_log.json` present for each docket with `validation.passed: true` (or explicit `false` with a printed warning explaining the discrepancy)
6. Re-running the script immediately after a successful run completes in under 5 seconds (all cache hits, no network calls)
7. `PROJECT_STATUS.md` updated to reflect Phase 1 complete
