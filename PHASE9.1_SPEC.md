# Phase 9.1 — Hardening & Cleanup Spec

_Drafted: 2026-04-05_
_Status: code tasks implemented and tracked in Git; manual blind-gold-set tasks remain open._

## Purpose

Phase 9 delivered a working end-to-end pipeline with evaluation harness. A systematic
code review identified a set of correctness bugs, evaluation-integrity gaps, test coverage
holes, and code quality issues. This phase addresses all of them in priority order before
any external reporting or expansion of the docket set.

## Non-goals

- No new pipeline stages or phases.
- No shared utility module / repo scaffolding (per CLAUDE.md guardrail; each script
  stays standalone for now; revisit explicitly in a later phase if duplication becomes
  a maintenance problem).
- No refactoring of `render_html_report` in `generate_outputs.py` (no bugs; cosmetic
  only; deferred).
- No fix for the O(n²) pairwise Jaccard loop in `cluster_comments.py` (not a problem
  at V1 docket-set scale; revisit if docket set grows to thousands of comments).

---

## Task inventory

| ID | Priority | File(s) | Type | Description |
|----|----------|---------|------|-------------|
| 9.1-A | P0 | 6 scripts | Bug | `JSONDecodeError` uncaught in `read_json()` |
| 9.1-B | P0 | `label_clusters.py` | Bug | Stale `label_description` on `--force` re-run |
| 9.1-C | P0 | `label_clusters.py` | Bug | `no_think` retry construction is misleading |
| 9.1-D | P0 | `dedup_comments.py` | Bug | Missing NFKC normalization in `normalize_text()` |
| 9.1-E | P1 | `gold_set/` | Manual | Replace seed gold set with blind human annotations |
| 9.1-F | P1 | `gold_set/` | Manual | Add blind gold sets for remaining 2 dockets |
| 9.1-G | P1 | `evaluate_pipeline.py` | Bug | P@1 cluster order is non-deterministic |
| 9.1-H | P2 | `test_cluster_comments.py` | Test | Unit test `tfidf_keywords()` |
| 9.1-I | P2 | `test_change_cards.py` | Test | Unit test `build_preamble_links()` |
| 9.1-J | P2 | `test_phase5.py` | Test | Strengthen family co-membership assertion |
| 9.1-K | P2 | `test_evaluate.py` | Test | Add P@3 eligible test case |
| 9.1-L | P2 | `test_phase8.py` | Test | Add `comment_attribution.json` fixture to test 1 |
| 9.1-M | P3 | `generate_change_cards.py` | Quality | Log WARN on swallowed preamble-link errors |
| 9.1-N | P3 | multiple | Quality | Document STOPWORDS divergence as intentional |
| 9.1-O | housekeeping | git | Ops | Commit untracked Phase 8–9 files |
| 9.1-P | housekeeping | git | Ops | Commit modified tracked files |

---

## Sequencing

1. Do **9.1-O** and **9.1-P** (git hygiene) first so there is a clean baseline.
2. Do **9.1-A through 9.1-D** (P0 bugs) as a single batch commit.
3. Do **9.1-G** (P@1 fix) before running evaluation again.
4. Do **9.1-H through 9.1-L** (test coverage) as a single batch commit.
5. Do **9.1-M** and **9.1-N** (quality) as a single batch commit.
6. **9.1-E** and **9.1-F** (gold set) are manual human tasks; track separately.

---

## Detailed task descriptions

---

### 9.1-O — Commit untracked Phase 8–9 files

**Problem:** The following files are complete and validated but untracked in git:

```
generate_outputs.py
evaluate_pipeline.py
test_phase8.py
test_evaluate.py
gold_set/EPA-HQ-OAR-2020-0272.json
```

**Action:** `git add` each of the above and commit with a message like:
`"add Phase 8–9 output generation, evaluation harness, and seed gold set"`

**Acceptance criteria:**
- All five files appear in `git status` as committed.
- `git log --oneline -1` reflects the commit.

---

### 9.1-P — Commit modified tracked files

**Problem:** The following tracked files have unstaged modifications:

```
.gitignore
README.md
cluster_comments.py
dedup_comments.py
generate_change_cards.py
label_clusters.py
```

**Action:** Review diffs, stage, and commit with an appropriate message. This should be
done after reviewing that the modifications are intentional and complete.

**Acceptance criteria:**
- `git status` shows a clean working tree after the commit (or after also landing 9.1-A
  through 9.1-N).

---

### 9.1-A — `JSONDecodeError` uncaught in `read_json()`

**Problem:** Every script's `read_json()` is wrapped at call sites in
`except (FileNotFoundError, OSError)`. `json.JSONDecodeError` is a subclass of
`ValueError`, not `OSError`. A corrupt, truncated, or partially written JSON file will
raise `JSONDecodeError` and propagate as an unhandled exception, crashing the script
mid-run instead of logging an error and continuing to the next docket.

**Affected files and call sites:**

| Script | Pattern |
|--------|---------|
| `fetch_corpus.py` | `read_json()` + `read_bytes()` call sites |
| `align_corpus.py` | `read_json()` call sites |
| `dedup_comments.py` | `process_docket()` call sites |
| `generate_change_cards.py` | `load_docket_inputs()` call sites |
| `cluster_comments.py` | `main()` / `cluster_payload_for_docket()` call sites |
| `label_clusters.py` | `process_docket()` call sites (lines 344–356) |
| `generate_outputs.py` | `process_docket()` / `load_optional_json()` call sites |
| `evaluate_pipeline.py` | `process_docket()` call sites |

**Fix:** At every call site where `(FileNotFoundError, OSError)` is caught around a
`read_json()` call, add `json.JSONDecodeError` to the except tuple:

```python
# Before
except (FileNotFoundError, OSError) as exc:

# After
except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
```

Where the error message mentions a path, ensure the corrupt-JSON case still logs
something useful (e.g., `str(exc)` which includes the location in the file).

**Note:** `load_optional_json()` in `generate_outputs.py` returns `None` on any error
and prints a warning — the same pattern should apply, adding `json.JSONDecodeError`.

**Acceptance criteria:**
- Writing a zero-byte or truncated JSON file to any corpus path, then running the
  corresponding script, produces a `[ERROR]` or `[WARN]` log line and exits cleanly
  (or continues to the next docket) rather than raising an unhandled `JSONDecodeError`.
- No `except (FileNotFoundError, OSError)` remains in the codebase without
  `json.JSONDecodeError` alongside it, unless the block is not wrapping a JSON read.

---

### 9.1-B — Stale `label_description` on `--force` re-run

**Problem:** In `label_clusters.py`, `process_docket()` lines 374–386:

```python
if label is None or description is None:
    failed += 1
else:
    cluster["label"] = label
    cluster["label_description"] = description
    labeled += 1

cluster["label_meta"] = label_meta

if label is None and "label_description" not in cluster:
    cluster["label_description"] = None
```

When `--force` is used to re-run labeling on a cluster that already has a
`label_description` from a prior run, and the new LLM call fails (returns `label=None`),
the guard `"label_description" not in cluster` is `False`, so the old description is
left in place. The cluster then has `label=None` (unset/stale) but `label_description=
"<old value>"` — an inconsistent state.

**Fix:** Unconditionally write both fields on every label attempt, whether success or
failure. Remove the tail guard entirely.

```python
# Replace lines 374-386 with:
cluster["label"] = label
cluster["label_description"] = description
cluster["label_meta"] = label_meta
if label is None:
    failed += 1
else:
    labeled += 1
```

`label` and `description` are `None` on failure (as returned by `label_cluster()`), so
writing `None` explicitly to both fields is the correct failure signal.

**Acceptance criteria:**
- On `--force` re-run where the LLM call fails for a previously-labeled cluster, both
  `cluster["label"]` and `cluster["label_description"]` are `None` in the output JSON.
- On `--force` re-run where the LLM call succeeds, both fields are updated to the new
  values.
- Unit test: construct a cluster dict with existing `label`/`label_description`, mock
  `label_cluster()` to return `(None, None, {...})`, run `process_docket`, assert both
  fields are `None`.

---

### 9.1-C — `no_think` retry construction is misleading

**Problem:** In `label_clusters.py`, `label_cluster()` lines 266–272:

```python
base_message = build_user_message(docket_id, cluster, comments_by_id)
if no_think:
    base_message += "\n\n/no_think"
retry_message = base_message + "\n\nRespond with valid JSON only, no text before or after."
if no_think and not retry_message.endswith("/no_think"):
    retry_message += "\n\n/no_think"
```

When `no_think=True`:
1. `base_message` ends with `"\n\n/no_think"`.
2. After appending the retry prose, `retry_message` does NOT end with `"/no_think"`.
3. The guard `not retry_message.endswith("/no_think")` is always `True`.
4. `/no_think` is always appended to `retry_message`.

The behavior is correct (the retry message always gets `/no_think`) but the guard
condition is dead logic that implies a case that can never occur. A future editor could
misread it and introduce a real bug.

**Fix:** Remove the guard and construct the retry suffix explicitly:

```python
base_message = build_user_message(docket_id, cluster, comments_by_id)
if no_think:
    base_message += "\n\n/no_think"
retry_suffix = "\n\nRespond with valid JSON only, no text before or after."
if no_think:
    retry_suffix += "\n\n/no_think"
retry_message = base_message + retry_suffix
attempts = [base_message, retry_message]
```

**Acceptance criteria:**
- When `no_think=True`, `retry_message` ends with `"\n\n/no_think"`.
- When `no_think=False`, `retry_message` does not contain `/no_think`.
- Unit test: call `label_cluster()` with `no_think=True` and a mocked client that
  returns malformed JSON on the first call and valid JSON on the second; assert both
  attempts have `/no_think` at end; assert correct label returned on second attempt.

---

### 9.1-D — Missing NFKC normalization in `dedup_comments.py`

**Problem:** `dedup_comments.py`'s `normalize_text()` only lowercases and collapses
whitespace. `align_corpus.py` and `generate_change_cards.py` both apply
`unicodedata.normalize("NFKC", text)` before further normalization. Comments with
non-breaking spaces (`\u00a0`), full-width characters, ligatures (`ﬁ` → `fi`), or
other Unicode presentation variants will not be recognized as duplicates of their
normalized equivalents, even if they are semantically identical form letters.

This is the most impactful gap because form-letter campaigns submitted via different
tools may use different Unicode encodings of the same characters.

**Fix:** Add `import unicodedata` and apply NFKC before lowercase in
`dedup_comments.py`'s `normalize_text()`:

```python
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    return re.sub(r"\s+", " ", text.lower()).strip()
```

**Acceptance criteria:**
- A unit test passes: two strings identical except one uses `\u00a0` (non-breaking
  space) or `ﬁ` (ligature fi) are grouped into the same dedup family.
- `python -m unittest test_phase5.py -v` continues to pass after the change.

---

### 9.1-E — Replace seed gold set with blind human annotations (manual task)

**Problem:** `gold_set/EPA-HQ-OAR-2020-0272.json` was auto-derived from pipeline
output. Its own `notes` field says: _"Seed gold set auto-derived from pipeline output.
Not a blind evaluation. Replace with human-blind annotations before reporting final
metrics."_ All Phase 9 evaluation metrics (100% across the board) are tautological
and cannot be reported externally.

**This is a manual human annotation task, not a code change.**

**What the annotator needs to do:**

1. Open `outputs/EPA-HQ-OAR-2020-0272/change_cards.html` in a browser.
2. For each gold alignment entry, independently verify (using the Federal Register
   documents) whether the proposed/final section pair is a true match, and what the
   correct `change_type` (`unchanged`, `modified`, `added`, `removed`) is.
3. For each gold cluster relevance entry, independently verify whether the listed
   cluster label/description is relevant to the change card it is attributed to.
4. Correct any wrong `expected_change_type`, `expected_match_type`, or `relevance`
   values based on independent inspection.
5. Change the `annotator` field from `"seed"` to your name.
6. Change the `notes` field to reflect that this is a human-blind evaluation.

**Acceptance criteria:**
- `gold_set/EPA-HQ-OAR-2020-0272.json` has `"annotator"` set to a human name.
- The `notes` field no longer contains the auto-derived disclaimer.
- At least some metrics in the resulting eval run are non-trivial (i.e., not 100%
  across every dimension), confirming the annotations are independent of pipeline
  output.
- `python evaluate_pipeline.py --docket EPA-HQ-OAR-2020-0272` exits 0 with the
  updated gold set.

**Dependency:** 9.1-G (P@1 fix) should be done before the blind eval run so that
cluster relevance metrics are computed deterministically.

---

### 9.1-F — Add blind gold sets for remaining 2 dockets (manual task)

**Problem:** Only `EPA-HQ-OAR-2020-0272` has a gold set. The other two dockets
(`EPA-HQ-OAR-2018-0225`, `EPA-HQ-OAR-2020-0430`) have no evaluation coverage.
`EPA-HQ-OAR-2018-0225` is the largest docket (317 comments, 74 clusters) and the one
with the known cluster label parse failure — it most needs evaluation coverage.

**Template for each new gold file:**

```json
{
  "docket_id": "<DOCKET_ID>",
  "annotated_at": "<ISO8601>",
  "annotator": "<name>",
  "notes": "<human-blind annotation>",
  "alignments": [
    {
      "proposed_section_id": "...",
      "final_section_id": "...",
      "expected_change_type": "unchanged|modified|added|removed",
      "expected_match_type": "exact|fuzzy|keyword|sequential|none"
    }
  ],
  "cluster_relevance": [
    {
      "card_id": "...",
      "cluster_id": "...",
      "relevance": "relevant|irrelevant"
    }
  ]
}
```

**Scope per docket:**
- Minimum 10 alignment entries covering at least one of each change type present.
- Minimum 5 cluster relevance judgments.

**Acceptance criteria:**
- `gold_set/EPA-HQ-OAR-2018-0225.json` exists and is valid JSON.
- `gold_set/EPA-HQ-OAR-2020-0430.json` exists and is valid JSON.
- `python evaluate_pipeline.py` (no `--docket` flag) exits 0 and writes eval reports
  for all 3 dockets.

---

### 9.1-G — P@1 cluster order is non-deterministic

**Problem:** In `evaluate_pipeline.py`, `card_cluster_ids()` (lines 90–96) builds an
ordered set of cluster IDs from `related_comments` in insertion order. P@1 checks
`card_clusters[0] == gold_cluster_id`. The "first" cluster is whichever cluster the
first related comment belongs to — this depends on comment ordering in the upstream
`comment_attribution.json`, which is not guaranteed stable across pipeline re-runs.

**Fix:** Sort the returned cluster list by descending frequency of occurrence among
`related_comments` on that card. The most-represented cluster (most comments attributed
to this card that belong to it) should be rank 1.

Replace `card_cluster_ids()`:

```python
def card_cluster_ids(card: dict, comment_to_cluster: dict[str, str]) -> list[str]:
    counts: dict[str, int] = {}
    for related_comment in card.get("related_comments", []) or []:
        cluster_id = comment_to_cluster.get(related_comment.get("comment_id"))
        if cluster_id:
            counts[cluster_id] = counts.get(cluster_id, 0) + 1
    # Descending by count, then stable alphabetical tie-break
    return sorted(counts, key=lambda cid: (-counts[cid], cid))
```

The alphabetical tie-break ensures determinism when two clusters have equal comment
counts on a card.

**Acceptance criteria:**
- `card_cluster_ids()` returns clusters sorted by descending comment-count, with
  alphabetical tie-breaking.
- Unit test: card with 3 related comments in cluster-B and 1 in cluster-A returns
  `["cluster-B", "cluster-A"]`.
- `python -m unittest test_evaluate.py -v` continues to pass.

---

### 9.1-H — Unit test `tfidf_keywords()` in `cluster_comments.py`

**Problem:** `tfidf_keywords()` is the most algorithmically complex function in the
pipeline (smoothed IDF, top-15 extraction, dict-of-dicts output). It has no unit test.
A regression in the IDF formula or top-K selection would be invisible until manual
inspection of cluster outputs.

**File:** Create tests in a new file `test_cluster_comments.py` (or add to an
existing test file if one exists for Phase 6).

**Test cases to cover:**

1. **Basic IDF**: Given 3 documents where "apple" appears in all 3 and "zephyr" appears
   in 1, `tfidf_keywords` should rank "zephyr" higher than "apple" in the document
   that contains it.

2. **Top-15 cap**: A document with 20 unique tokens returns at most 15 keywords in its
   top-keyword list.

3. **Empty corpus**: A corpus of 0 documents returns an empty dict without crashing.

4. **Single document**: A corpus of 1 document returns scores without division-by-zero.

5. **Stopword exclusion**: Tokens in `STOPWORDS` (e.g., `"comment"`, `"rule"`) should
   not appear in keyword lists (since `tokenize()` filters them before calling
   `tfidf_keywords`; test via `tokenize()` + `tfidf_keywords()` together).

**Acceptance criteria:**
- All 5 test cases pass.
- `python -m unittest test_cluster_comments.py -v` exits 0.

---

### 9.1-I — Unit test `build_preamble_links()` in `generate_change_cards.py`

**Problem:** `build_preamble_links()` is the function that links change cards to
preamble sections via CFR citation matching and keyword Jaccard (>=0.15 threshold,
max 5 links per card). It has no unit test. The CFR citation path and the keyword
fallback path are both untested.

**File:** Create tests in a new file `test_change_cards.py`.

**Test cases to cover:**

1. **CFR citation match**: A card whose heading contains `§ 60.5` and a preamble
   section whose heading also contains `§ 60.5` should be linked via `preamble_cfr_index`.

2. **Keyword Jaccard fallback**: A card with heading tokens overlapping a preamble
   section's body tokens at >= 0.15 Jaccard should produce a keyword-type preamble link
   when no CFR match exists.

3. **Max 5 cap**: A card eligible for 8 preamble links receives at most 5.

4. **No double-count**: A preamble section matched by both CFR citation AND keyword
   should appear only once in the card's preamble links.

5. **`added` card skips related comments but still gets preamble links**: Verify
   `build_related_comments` skips `added` cards (returns empty list) while
   `build_preamble_links` still operates on them.

**Acceptance criteria:**
- All 5 test cases pass.
- `python -m unittest test_change_cards.py -v` exits 0.

---

### 9.1-J — Strengthen family co-membership assertion in `test_phase5.py`

**Problem:** In `test_phase5.py`, `test_dedup_detects_exact_and_near_duplicate_families`
asserts:

```python
self.assertIn(3, family_sizes)
self.assertIn("form_letter", family_types)
```

This passes even if c1, c2, and c3 are split across two different families, as long as
any family somewhere has size 3. It does not assert that c1, c2, and c3 are all in the
same family.

**Fix:** Look up the canonical comment IDs and assert that all three input comment IDs
map to the same `family_id`:

```python
family_by_comment = {
    member["comment_id"]: family["family_id"]
    for family in families
    for member in family["members"]
}
self.assertEqual(
    family_by_comment["c1"],
    family_by_comment["c2"],
    "c1 and c2 should be in the same family"
)
self.assertEqual(
    family_by_comment["c1"],
    family_by_comment["c3"],
    "c1 and c3 should be in the same family"
)
```

**Acceptance criteria:**
- The updated test still passes with the current `dedup_comments.py`.
- If the dedup logic is broken to split c3 into a separate family, the test fails.

---

### 9.1-K — Add P@3 eligible test case in `test_evaluate.py`

**Problem:** `test_cluster_relevance_metrics` in `test_evaluate.py` uses only cards
with 0 or 1 related comments, so no card ever has 3+ clusters. The `precision@3`
code path (`eligible_cards >= 1`) is never exercised by the test suite.

**Fix:** Add a fixture card with at least 3 related comments mapped to 3 different
clusters. Include a gold entry referencing one of those clusters as `"relevant"`.
Assert `precision_at_3.eligible_cards >= 1` and `precision_at_3.pct` is the correct
value.

**Acceptance criteria:**
- `test_evaluate.py` exercises the P@3 branch.
- The assertion checks both `eligible_cards` count and `pct` value.
- `python -m unittest test_evaluate.py -v` exits 0.

---

### 9.1-L — Add `comment_attribution.json` fixture to `test_phase8.py` test 1

**Problem:** `test_process_docket_writes_all_output_formats` in `test_phase8.py` does
not supply a `comment_attribution.json` fixture. The `build_summary()` function in
`generate_outputs.py` has a branch that reads this file and computes per-docket
attribution statistics from it; that branch is never exercised.

**Fix:** Add a minimal `comment_attribution.json` fixture to the test's temp directory:

```json
{
  "docket_id": "DOCKET-TEST",
  "attributed_comments": [
    {"comment_id": "c1", "attribution_method": "citation", "confidence": "high"}
  ],
  "unattributed_comments": []
}
```

Assert that the resulting summary JSON contains an `attribution_stats` key with
at least `attributed_count` > 0.

**Acceptance criteria:**
- `test_phase8.py` test 1 exercises the `comment_attribution.json` branch of
  `build_summary()`.
- The resulting summary JSON contains the expected attribution stat.
- `python -m unittest test_phase8.py -v` exits 0.

---

### 9.1-M — Log WARN on swallowed preamble-link errors

**Problem:** In `generate_change_cards.py`, `build_preamble_links()` has a bare
`except Exception` that silently degrades individual cards:

```python
try:
    ...
except Exception:
    pass  # or similar
```

Errors in preamble link building are swallowed with no log output. A tokenization
failure, a missing key, or any other unexpected error would produce a card with
fewer preamble links than expected, with no indication in the output that anything
went wrong.

**Fix:** Replace the silent `pass` with a `print_line("WARN", ...)` call:

```python
except Exception as exc:
    print_line(
        "WARN",
        docket_id,
        f"preamble link build failed for {card.get('card_id', '?')}: {type(exc).__name__}: {exc}",
    )
```

**Acceptance criteria:**
- The WARN log is emitted when `build_preamble_links` raises an exception for any
  individual card.
- The script still completes (the exception is still caught; only a log line is added).
- `python -m unittest test_change_cards.py -v` (from 9.1-I) continues to pass.

---

### 9.1-N — Document STOPWORDS divergence as intentional

**Problem:** Three different `STOPWORDS` sets exist across the codebase. This looks
like a bug but is actually intentional:

| Script | Stopwords scope | Rationale |
|--------|----------------|-----------|
| `align_corpus.py` | Core only | Rulemaking terms help match section headings |
| `dedup_comments.py` | Core only | Rulemaking terms help group form letters by shared language |
| `cluster_comments.py` | Core + rulemaking | Prevents all comments from clustering together because they all say "rule" |
| `generate_change_cards.py` | Core + rulemaking | Rulemaking terms are noise for heading-to-comment similarity |

**Fix:** Add a one-line comment above each `STOPWORDS` definition explaining which
scope is used and why. Example for `dedup_comments.py`:

```python
# Core stopwords only — rulemaking terms intentionally kept so form letters
# sharing phrases like "this rule" or "the proposed rule" match more reliably.
STOPWORDS = {...}
```

And for `cluster_comments.py` / `generate_change_cards.py`:

```python
# Core + rulemaking-domain stopwords — prevents all comments clustering solely
# because they share universal rulemaking vocabulary ("rule", "epa", "section").
STOPWORDS = {...}
```

**Acceptance criteria:**
- Each `STOPWORDS` definition in all 4 scripts has an explanatory comment.
- No behavioral change; tests continue to pass.

---

## Done criteria for Phase 9.1

All of the following must be true before Phase 9.1 is considered complete:

1. `git status` shows a clean working tree (9.1-O, 9.1-P).
2. Writing a truncated JSON to any corpus path and running the corresponding script
   produces an error log, not a crash (9.1-A).
3. `--force` re-run in `label_clusters.py` where LLM call fails leaves both `label`
   and `label_description` as `null` in output JSON (9.1-B).
4. `label_clusters.py` `no_think` retry message construction has no dead guard
   condition (9.1-C).
5. Two Unicode-variant near-duplicate comments are grouped by `dedup_comments.py`
   (9.1-D).
6. `card_cluster_ids()` returns clusters sorted by descending comment-count with
   alphabetical tie-break (9.1-G).
7. `python -m unittest test_cluster_comments.py -v` exits 0 (9.1-H).
8. `python -m unittest test_change_cards.py -v` exits 0 (9.1-I).
9. `python -m unittest test_phase5.py -v` exits 0 and the co-membership assertion
   is present (9.1-J).
10. `python -m unittest test_evaluate.py -v` exits 0 and P@3 is exercised (9.1-K).
11. `python -m unittest test_phase8.py -v` exits 0 and attribution stats are covered
    (9.1-L).
12. `generate_change_cards.py` WARN log fires on preamble-link exception (9.1-M).
13. All four `STOPWORDS` definitions have explanatory comments (9.1-N).
14. `gold_set/EPA-HQ-OAR-2020-0272.json` has a human annotator and non-trivial
    metrics (9.1-E — manual).
15. Gold sets for the other 2 dockets exist and `evaluate_pipeline.py` exits 0 for
    all 3 (9.1-F — manual).

Items 14–15 (manual human annotation tasks) may remain open while code tasks
1–13 are completed and committed.
