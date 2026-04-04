# Integration Note

## 1. Confirmed docket set

- `EPA-HQ-OAR-2020-0272` — Revised Cross-State Air Pollution Rule Update for the 2008 Ozone NAAQS
- `EPA-HQ-OAR-2018-0225` — Determination Regarding Good Neighbor Obligations for the 2008 Ozone NAAQS
- `EPA-HQ-OAR-2020-0430` — Primary Copper Smelting National Emission Standards for Hazardous Air Pollutants Reviews (Subparts QQQ and EEEEEE)

## 2. Federal Register — endpoints, request patterns, document sizes, structural observations

- Working search endpoint: `GET /api/v1/documents?conditions[docket_id]=...&fields[]=document_number&type&title&publication_date&full_text_xml_url&html_url&action`
- Working full-text pattern: use `full_text_xml_url` first and fall back to `html_url` only when XML is unavailable or fails.

### EPA-HQ-OAR-2020-0272
- Proposed rule: `2020-23237`
- Final rule: `2021-05705`
- Proposed download: `xml` | raw bytes `1624729` | stripped chars `1023454` | words `160603` | approx sections `290` | content-type `text/xml` | duration `0.283 s`
- Final download: `xml` | raw bytes `1974016` | stripped chars `1258630` | words `195481` | approx sections `297` | content-type `text/xml` | duration `0.372 s`

### EPA-HQ-OAR-2018-0225
- Proposed rule: `2018-14737`
- Final rule: `2018-27160`
- Proposed download: `xml` | raw bytes `256791` | stripped chars `175248` | words `26404` | approx sections `47` | content-type `text/xml` | duration `0.197 s`
- Final download: `xml` | raw bytes `485487` | stripped chars `350478` | words `53502` | approx sections `48` | content-type `text/xml` | duration `0.17 s`

### EPA-HQ-OAR-2020-0430
- Proposed rule: `2021-28273`
- Final rule: `2024-09883`
- Proposed download: `xml` | raw bytes `359522` | stripped chars `287975` | words `43456` | approx sections `100` | content-type `text/xml` | duration `0.234 s`
- Final download: `xml` | raw bytes `630935` | stripped chars `488513` | words `74516` | approx sections `144` | content-type `text/xml` | duration `0.147 s`

## 3. Regulations.gov — endpoints, request patterns, comment volumes per docket, inline-text fraction, auth notes

- Working document listing pattern: `GET /v4/documents?filter[docketId]={docketId}&page[size]=250&page[number]=N`
- Working comment census pattern: `GET /v4/comments?filter[commentOnId]={objectId}&page[size]=250&page[number]=1`
- Working sample pattern: `GET /v4/comments?filter[commentOnId]={objectId}&page[size]=25&page[number]=1`
- Working detail fallback pattern: `GET /v4/comments/{commentId}` when the list endpoint returns empty text fields.
- Docket endpoint note: `GET /v4/dockets/{docketId}` was not tested in this spike.
- Regulations.gov authentication status: API key present = `True`, observed auth result = `accepted`

### EPA-HQ-OAR-2020-0272
- Proposed-rule doc for comment census: `EPA-HQ-OAR-2020-0272-0001` / objectId `0900006484941754`
- Total comments reported: `85`
- Estimated pages at page_size=25: `4`
- Estimated full retrieval request count: `4`
- Estimated full retrieval wall-clock at 1.25 s/request: `5.0 s`
- 25-comment sample mix: substantive inline `1`, attachment pointer `0`, no text `24`
- Detail fallback used: `True`
- Detail fallback result: status `ok`, classification `substantive_inline`, preview `Please see attached comments of the Attorneys General of New York, New Jersey, Connecticut, Delaware, and Massachusetts, and the Corporation Counsel of the City...`
- Projected inline-text fraction: `0.04`
- Projected substantive comment count: `3`
- Attachment/file metadata fields seen in sample: `none`

### EPA-HQ-OAR-2018-0225
- Proposed-rule doc for comment census: `EPA-HQ-OAR-2018-0225-0001` / objectId `09000064834ca2df`
- Total comments reported: `317`
- Estimated pages at page_size=25: `13`
- Estimated full retrieval request count: `13`
- Estimated full retrieval wall-clock at 1.25 s/request: `16.25 s`
- 25-comment sample mix: substantive inline `1`, attachment pointer `0`, no text `24`
- Detail fallback used: `True`
- Detail fallback result: status `ok`, classification `substantive_inline`, preview `EPA should establish regulations on Big City Air pollution in Air and Water due to human waste on street, which cause greatest emission and water pollution in t...`
- Projected inline-text fraction: `0.04`
- Projected substantive comment count: `13`
- Attachment/file metadata fields seen in sample: `none`

### EPA-HQ-OAR-2020-0430
- Proposed-rule doc for comment census: `EPA-HQ-OAR-2020-0430-0001` / objectId `0900006484f17763`
- Total comments reported: `22`
- Estimated pages at page_size=25: `1`
- Estimated full retrieval request count: `1`
- Estimated full retrieval wall-clock at 1.25 s/request: `1.25 s`
- 25-comment sample mix: substantive inline `1`, attachment pointer `0`, no text `21`
- Detail fallback used: `True`
- Detail fallback result: status `ok`, classification `substantive_inline`, preview `Comment Submitted by Rio Tinto Kennecott Utah Copper`
- Projected inline-text fraction: `0.045`
- Projected substantive comment count: `1`
- Attachment/file metadata fields seen in sample: `none`

## 4. Rate limits and timing — observed behavior, documented limits, full-ingestion estimates

- Federal Register observed mean/max response time: `0.211 s` / `0.372 s` across `9` requests
- Regulations.gov observed mean/max response time: `0.677 s` / `2.499 s` across `12` requests
- Observed any HTTP 429 responses: `False`
- Documented Regulations.gov limit used here: `50 req/min`, which implies a floor of `1.2 s/req`.
- Configured safe delay in this spike: `1.25 s/req`.
- Full-ingestion estimate per docket is computed as `ceil(total_comments / 25) * 1.25 s`.

## 5. Caching requirements — immutable vs drifting data, recommended strategy

- Treat Federal Register full text by document number as immutable once fetched; cache by full-text URL or FR document number with a forever TTL.
- Treat Regulations.gov comment detail by comment ID as effectively immutable for V1 purposes; cache by comment ID with a forever TTL.
- Treat Regulations.gov docket document listings and paginated comment lists as drifting resources; cache those by full request URL with a 24-hour TTL.
- Recommended cache shape for Phase 1: file-based cache keyed by canonical request URL or immutable record ID, with separate stores for immutable and list resources.

## 6. Data gaps — attachment-only comments quantified, other gaps

- `EPA-HQ-OAR-2020-0272` sample gap profile: substantive inline `1`, attachment pointer `0`, no text `24`.
- `EPA-HQ-OAR-2018-0225` sample gap profile: substantive inline `1`, attachment pointer `0`, no text `24`.
- `EPA-HQ-OAR-2020-0430` sample gap profile: substantive inline `1`, attachment pointer `0`, no text `21`.
- Regulations.gov list pages alone do not reliably expose comment text for these dockets; the detail endpoint is a required retrieval pattern when list payloads are empty.
- Attachment-only or no-text comments remain a real data-shape limitation, but list-endpoint emptiness should not be confused with true text absence.
- This spike did not implement cache storage, attachment parsing, or any downstream pipeline behavior.

## 7. Readiness verdict — go/no-go for Phase 1

- Verdict: `go`
- Summary: Phase 1 can proceed: working endpoints, request patterns, timing, and data-gap observations were all confirmed for the accepted V1 docket set.

_Generated by `api_integration_spike.py` on 2026-04-04T22:52:18+00:00._
