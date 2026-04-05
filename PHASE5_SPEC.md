# Phase 5 Spec — Comment Deduplication

## Context

Phase 4 produced change cards with `alignment_signal` level/score/features/evidence_note. The
current scoring counts raw comments: a card with 259 keyword/medium comments scores 518 → "high".
Those 259 comments are almost certainly a bulk form-letter campaign, so 518 is noise. Before any
theme-clustering or LLM work, the corpus needs a deduplication pass that identifies exact
duplicates, near-duplicates, and form-letter families so downstream scoring operates on unique
arguments.

This phase is fully deterministic. No LLM calls. No new dependencies beyond the Python standard
library.

## Deliverables

1. A new standalone script `dedup_comments.py`.
2. An update to `generate_change_cards.py` adding dedup-awareness to `alignment_signal`.
3. `comment_dedup.json` output for all three dockets.
4. Updated `change_cards.json` for all three dockets.

No new directories. No new external dependencies.

---

## Corpus going in

| Docket | Comments |
|---|---|
| EPA-HQ-OAR-2018-0225 | 317 |
| EPA-HQ-OAR-2020-0272 | 85 |
| EPA-HQ-OAR-2020-0430 | 22 |

All comment records have non-empty `text`. Relevant input fields: `comment_id`, `text`,
`posted_date`, `classification`.

---

## Part A: `dedup_comments.py`

### Text normalization

Applied before all comparisons:

1. Lowercase
2. Collapse all whitespace sequences to a single space
3. Strip leading/trailing whitespace

Result: `normalized_text`. Do not strip punctuation — punctuation differences are meaningful for
near-duplicate scoring.

### Pass 1a — Exact deduplication

Compute `sha256(normalized_text.encode("utf-8")).hexdigest()` for each comment. Group by hash.
Any group with size > 1 is an exact-duplicate family.

### Pass 1b — Near-duplicate and form-letter detection

For each comment (including those already in exact-duplicate families), compute a set of
character 5-grams from `normalized_text`. Use Union-Find to merge any two comments whose
Jaccard similarity is ≥ 0.80. Brute-force O(n²) pairwise — acceptable for ≤ 400 comments per
docket.

Jaccard(A, B) = |A ∩ B| / |A ∪ B|  where A, B are multiset-free 5-gram sets.

After Union-Find, merge exact-duplicate groups: members of the same SHA-256 group always belong
to the same Union-Find component.

### Family classification

After all merging is complete:

| Condition | family_type |
|---|---|
| All members share the same SHA-256 hash | `"exact_duplicate"` |
| member_count ≥ 3 (and not all-exact) | `"form_letter"` |
| member_count == 2 (and not all-exact) | `"near_duplicate"` |
| member_count == 1 | `"unique"` |

A family that is all-exact-hash AND size ≥ 3 is still `"exact_duplicate"` (the hash condition
takes precedence).

### Canonical comment selection

Within each family, the canonical comment is:
1. The member with the longest `normalized_text`.
2. Tie-break: earliest `posted_date` (lexicographic comparison of ISO-8601 strings).

The canonical comment is the representative used in downstream dedup-adjusted scoring.

### Output: `comment_dedup.json`

One file per docket at `corpus/{docket_id}/comment_dedup.json`:

```json
{
  "docket_id": "EPA-HQ-OAR-2018-0225",
  "total_comments": 317,
  "unique_families": 142,
  "exact_duplicate_families": 8,
  "near_duplicate_families": 5,
  "form_letter_families": 12,
  "unique_comment_families": 117,
  "families": [
    {
      "family_id": "EPA-HQ-OAR-2018-0225_family_0001",
      "family_type": "form_letter",
      "canonical_comment_id": "EPA-HQ-OAR-2018-0225-0043",
      "member_count": 38,
      "member_ids": ["EPA-HQ-OAR-2018-0225-0043", "EPA-HQ-OAR-2018-0225-0044"]
    }
  ]
}
```

Field notes:
- `unique_families` = total family count. All four `*_families` counts sum to `unique_families`.
- Every comment belongs to exactly one family (no orphans, no double-counting).
- `families` sorted: form_letter first, then near_duplicate, exact_duplicate, unique; within
  each type, descending `member_count`.
- `member_ids` always includes the canonical comment ID.

### Console output

```
[DEDUP]  EPA-HQ-OAR-2018-0225  317 comments → 142 families  (8 exact, 5 near-dup, 12 form-letter, 117 unique)
[DEDUP]  EPA-HQ-OAR-2018-0225  written  corpus/EPA-HQ-OAR-2018-0225/comment_dedup.json
```

Print a summary line after all dockets:

```
=== Phase 5 deduplication complete ===
EPA-HQ-OAR-2018-0225   317 comments → 142 families  (12 form-letter, 5 near-dup, 8 exact, 117 unique)
EPA-HQ-OAR-2020-0272   85 comments  → 71 families   (...)
EPA-HQ-OAR-2020-0430   22 comments  → 20 families   (...)
```

### Error handling

- If `comments.json` is missing for a docket, print a clear error and skip. Do not crash.
- If a comment has null or empty `text`, treat it as a unique family of one. Do not crash.
- Write output via a tmp-file → atomic rename pattern (same as existing scripts).

---

## Part B: `generate_change_cards.py` changes

### Loading dedup data

After loading `comments.json`, attempt to load `corpus/{docket_id}/comment_dedup.json`.
If absent, set `dedup_available = False` and continue. Do not crash. All dedup-dependent
fields fall back to `null` when unavailable.

Build three lookups from `families`:

```python
comment_to_family_id: dict[str, str]       # comment_id → family_id
family_member_count:  dict[str, int]        # family_id → member_count
family_canonical:     dict[str, str]        # family_id → canonical_comment_id
```

### Changes to `alignment_signal.features`

Add two new fields after `comment_count`:

- `unique_comment_count` (int | null): number of distinct comment families represented in
  `related_comments`. If `dedup_available` is False: `null`.
- `largest_family_size` (int | null): `max(family_member_count[fid])` over all families
  present in `related_comments`. 1 if all families are size-1 unique comments. `null` if
  `dedup_available` is False.

### Dedup-adjusted score calculation

When `dedup_available` is True, replace the raw per-comment point sum with a per-family point
sum:

For each comment family represented in `related_comments`:
- Collect all members of that family that appear in `related_comments`.
- Take the maximum `comment_signal_points(c)` across those members.
- Add that maximum to the score once (not once per member).

This prevents a 259-member form-letter family from contributing 259 × 2 = 518 points; it
contributes at most 2 points (keyword/medium) as a single family.

Preamble link scoring is unchanged.

When `dedup_available` is False, score as before (sum all raw comment points).

### Evidence note update

When `dedup_available` is True AND `unique_comment_count != comment_count`, use:

```
"{comment_count} comments ({unique_comment_count} unique arguments) attributed (best: {method}/{confidence}); ..."
```

Example:
```
"259 comments (3 unique arguments) attributed (best: keyword/medium); no preamble discussion linked."
```

When counts match (all unique) or dedup unavailable, use the existing format unchanged.

### Text report update

In the `ALIGNMENT SIGNAL` block, when `dedup_available` is True, add `unique_comment_count=N`
after `comment_count=N`:

```
ALIGNMENT SIGNAL: medium  (score 4)
  comment_count=259  unique_comment_count=3  best_attribution=medium  preamble_link_count=0  best_link_type=none
  259 comments (3 unique arguments) attributed (best: keyword/medium); no preamble discussion linked.
```

### Report footer

Change the footer from `=== Phase 4 change cards complete ===` to
`=== Phase 5 change cards complete ===`.

---

## Pipeline re-run order

```bash
python dedup_comments.py         # produces comment_dedup.json per docket
python generate_change_cards.py  # re-generates change_cards.json with dedup-adjusted signals
```

`fetch_corpus.py` and `align_corpus.py` do not need re-running.

---

## Done criteria

1. `comment_dedup.json` exists for all three dockets and `total_comments` matches
   `len(comments.json)` for each docket.
2. Every comment in each docket belongs to exactly one family (sum of all `member_count`
   values equals `total_comments`).
3. At least one family with `family_type != "unique"` exists in EPA-HQ-OAR-2018-0225
   (317 comments; near-certain to have duplicates at the 0.80 threshold).
4. `generate_change_cards.py` re-runs without error; card count per docket is unchanged.
5. Every `alignment_signal` in the re-generated cards has `unique_comment_count` present
   (either an integer or `null` — not absent from the `features` dict).
6. The largest `comment_count` card in EPA-HQ-OAR-2018-0225 shows `unique_comment_count`
   strictly less than `comment_count` (confirming dedup fired on the inflated card).
7. `PROJECT_STATUS.md` updated to reflect Phase 5 complete.
