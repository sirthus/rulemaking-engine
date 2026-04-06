# Phase 9 Spec — Evaluation Framework + Pipeline Polish

Status: implemented and tracked in Git.

## Goal

Two deliverables:
1. **Pipeline polish**: replace the remaining `→` (U+2192) characters in print output with `->` in `dedup_comments.py` (lines 264, 283) and `cluster_comments.py` (line 466). Same fix already applied to `generate_change_cards.py`.
2. **Evaluation framework**: a `evaluate_pipeline.py` script, a seed gold set at `gold_set/EPA-HQ-OAR-2020-0272.json`, and unit tests in `test_evaluate.py`.

---

## Part 1 — Encoding fixes (already done by Claude Code)

`dedup_comments.py` and `cluster_comments.py` have had their `→` characters replaced with `->`. No further work needed here.

---

## Part 2 — Gold Set

### Directory
Create `gold_set/` at the repo root. This directory is **committed** (do not add to `.gitignore`). It contains human-annotatable JSON files that serve as the evaluation ground truth.

### File: `gold_set/EPA-HQ-OAR-2020-0272.json`

Populate by reading `corpus/EPA-HQ-OAR-2020-0272/section_alignment.json` and `corpus/EPA-HQ-OAR-2020-0272/change_cards.json` and `corpus/EPA-HQ-OAR-2020-0272/comment_themes.json`.

**Schema:**
```json
{
  "docket_id": "EPA-HQ-OAR-2020-0272",
  "annotated_at": "<ISO8601 UTC>",
  "annotator": "seed",
  "notes": "Seed gold set auto-derived from pipeline output. Not a blind evaluation. Replace with human-blind annotations before reporting final metrics.",
  "alignments": [ ... ],
  "cluster_relevance": [ ... ]
}
```

**`alignments` — 10 entries:**

Draw from `section_alignment.json`. Pick entries in this mix:
- 5 records where `match_type` is `exact_heading` and `change_type` is `modified`
- 3 records where `match_type` is `exact_heading` and `change_type` is `unchanged`
- 2 records where `change_type` is `added` or `removed` (one side null)

Each entry:
```json
{
  "proposed_section_id": "<value or null>",
  "final_section_id": "<value or null>",
  "expected_match_type": "exact_heading",
  "expected_change_type": "modified",
  "notes": "<heading text or brief description>"
}
```

Use the pipeline's own values as the expected values (these are seed annotations, not independent labels).

**`cluster_relevance` — 5 entries:**

Draw from `change_cards.json` — pick 5 cards that have at least one entry in `related_comments`. For each, look up the comment's cluster in `comment_themes.json` using the `member_canonical_ids` lists. Use the first related comment's cluster as the gold cluster.

Each entry:
```json
{
  "card_id": "<card_id>",
  "cluster_id": "<cluster_id>",
  "relevance": "relevant",
  "notes": "<brief description of why this cluster is relevant to this card>"
}
```

Mark all 5 as `"relevant"` since they are auto-derived from actual pipeline links (the pipeline itself attributed comments from that cluster to the card).

---

## Part 3 — `evaluate_pipeline.py`

### CLI
```bash
python evaluate_pipeline.py [--docket DOCKET_ID] [--gold-dir PATH] [--output-dir PATH]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--docket` | all three | Process only the specified docket ID |
| `--gold-dir` | `gold_set/` | Directory containing `{docket_id}.json` gold files |
| `--output-dir` | `outputs/` | Root directory for evaluation report files |

Valid docket IDs: `EPA-HQ-OAR-2020-0272`, `EPA-HQ-OAR-2018-0225`, `EPA-HQ-OAR-2020-0430`

If no gold set file exists for a docket, print `[INFO]  {docket_id}  no gold set found; skipping` and continue.

### Outputs per docket
- `outputs/{docket_id}/eval_report.json`
- `outputs/{docket_id}/eval_report.txt`

Both written atomically.

### Inputs per docket
| File | Required | Used for |
|------|----------|---------|
| `gold_set/{docket_id}.json` | Yes (skip if absent) | ground truth |
| `corpus/{docket_id}/section_alignment.json` | Yes | alignment metrics |
| `corpus/{docket_id}/change_cards.json` | Yes | cluster relevance metrics |
| `corpus/{docket_id}/comment_themes.json` | Yes | comment → cluster join |

If any corpus file is missing, print error for that docket and skip it.

### Comment → cluster join

Same logic as `generate_outputs.py`:
```python
comment_to_cluster: dict[str, str] = {}
for cluster in themes.get("clusters", []):
    for cid in cluster.get("member_canonical_ids", []):
        comment_to_cluster[cid] = cluster["cluster_id"]
```

### Alignment metrics

Index `section_alignment.json` into lookup dicts:
```python
by_both  = {(r["proposed_section_id"], r["final_section_id"]): r for r in records if r.get("proposed_section_id") and r.get("final_section_id")}
by_final = {r["final_section_id"]: r for r in records if r.get("final_section_id") and not r.get("proposed_section_id")}
by_proposed = {r["proposed_section_id"]: r for r in records if r.get("proposed_section_id") and not r.get("final_section_id")}
```

For each gold `alignments` entry:
- If both IDs non-null: look up `by_both[(proposed_section_id, final_section_id)]`
- If only `final_section_id`: look up `by_final[final_section_id]`
- If only `proposed_section_id`: look up `by_proposed[proposed_section_id]`
- If not found: record as unmatched

Compute:
- `total_gold_alignments`: `len(gold["alignments"])`
- `pipeline_matched`: count of gold entries with a found pipeline record
- `change_type_agreement`: among matched, count where `pipeline_record["change_type"] == gold_entry["expected_change_type"]`
- `match_type_agreement`: among matched, count where `pipeline_record["match_type"] == gold_entry["expected_match_type"]`

Report each as `{"matched": N, "total": M, "pct": float}` where `pct = round(matched/total*100, 1) if total else 0.0`.

### Cluster relevance metrics

Index `change_cards.json` by `card_id`. For each card, derive its related cluster IDs:
```python
def card_cluster_ids(card: dict, comment_to_cluster: dict) -> list[str]:
    seen = {}
    for rc in card.get("related_comments", []) or []:
        cid = comment_to_cluster.get(rc.get("comment_id"))
        if cid and cid not in seen:
            seen[cid] = True
    return list(seen.keys())
```

For each gold `cluster_relevance` entry:
- Look up the card. If card not found: skip (note as unresolved).
- Compute `card_clusters = card_cluster_ids(card, comment_to_cluster)` — ordered list (insertion order = order of related_comments)
- `pipeline_cluster_found`: 1 if gold cluster_id appears anywhere in `card_clusters`, else 0
- `relevant_found`: 1 if `pipeline_cluster_found` AND gold `relevance` in `{"relevant", "partially_relevant"}`, else 0

For `precision_at_1`:
- For each gold entry where card was found: check if `card_clusters[0] == gold_cluster_id` AND gold relevance is `relevant`
- `{"matched": N, "total": found_count, "pct": ...}`

For `precision_at_3`:
- Only consider gold entries where `len(card_clusters) >= 3`
- Check if `gold_cluster_id` appears in `card_clusters[:3]` AND gold relevance is `relevant` or `partially_relevant`
- `{"matched": N, "eligible_cards": M, "pct": ...}` where `eligible_cards` is count of entries with ≥3 clusters

### `eval_report.json` schema
```json
{
  "docket_id": "EPA-HQ-OAR-2020-0272",
  "evaluated_at": "<ISO8601 UTC>",
  "gold_set_annotator": "<annotator field from gold set>",
  "alignment_metrics": {
    "total_gold_alignments": 10,
    "pipeline_matched": 10,
    "change_type_agreement": {"matched": 9, "total": 10, "pct": 90.0},
    "match_type_agreement": {"matched": 10, "total": 10, "pct": 100.0}
  },
  "cluster_relevance_metrics": {
    "total_gold_judgments": 5,
    "pipeline_cluster_found": 5,
    "relevant_found": 5,
    "precision_at_1": {"matched": 3, "total": 5, "pct": 60.0},
    "precision_at_3": {"matched": 2, "eligible_cards": 3, "pct": 66.7}
  }
}
```

### `eval_report.txt` format
```
=== Evaluation Report: EPA-HQ-OAR-2020-0272 ===
Gold set: seed  (10 alignments, 5 cluster judgments)

Alignment metrics (10 gold entries):
  pipeline_matched:      10 / 10  (100.0%)
  change_type_agreement: 9  / 10  (90.0%)
  match_type_agreement:  10 / 10  (100.0%)

Cluster relevance metrics (5 gold judgments):
  pipeline_cluster_found: 5 / 5  (100.0%)
  relevant_found:         5 / 5  (100.0%)
  precision@1:            3 / 5  (60.0%)
  precision@3:            2 / 3 eligible cards  (66.7%)
```

### Code patterns
Copy the standard helpers from `generate_outputs.py`:
- `utc_now_iso()`, `read_json()`, `atomic_write_text()`, `atomic_write_json()`, `print_line()`
- Handle missing files with `try/except (FileNotFoundError, OSError)`
- Docket list: `DOCKET_IDS = ["EPA-HQ-OAR-2020-0272", "EPA-HQ-OAR-2018-0225", "EPA-HQ-OAR-2020-0430"]`

---

## Part 4 — `test_evaluate.py`

Use `unittest.TestCase` with temp dir fixtures. Monkey-patch `evaluate_pipeline.CORPUS_DIR` and `evaluate_pipeline.DEFAULT_GOLD_DIR` to temp paths (same pattern as `test_phase8.py`).

### Test 1: `test_alignment_metrics`

Fixture:
- `section_alignment.json`: 5 records, all `exact_heading`; 4 `modified`, 1 `unchanged`
- Gold set: 5 alignments; 4 expect `modified`, 1 expects `added` (deliberate mismatch on last)

Assert:
- `alignment_metrics.pipeline_matched == 5`
- `alignment_metrics.change_type_agreement.matched == 4`  (1 mismatch)
- `alignment_metrics.change_type_agreement.pct == 80.0`
- `alignment_metrics.match_type_agreement.matched == 5`  (all match_type correct)

### Test 2: `test_cluster_relevance_metrics`

Fixture:
- `comment_themes.json`: 1 cluster with `member_canonical_ids: ["c1", "c2"]`
- `change_cards.json`: 2 cards; card_A has `related_comments: [{comment_id: "c1", ...}]`; card_B has no related_comments
- Gold set: 2 cluster_relevance entries; entry for card_A + cluster → `relevant`; entry for card_B + cluster → `relevant`

Assert:
- `cluster_relevance_metrics.total_gold_judgments == 2`
- `cluster_relevance_metrics.pipeline_cluster_found == 1`  (card_B has no comments, cluster not found)
- `cluster_relevance_metrics.relevant_found == 1`

### Both tests
- Assert output files `eval_report.json` and `eval_report.txt` exist
- Assert `eval_report.json` is valid JSON with `alignment_metrics` and `cluster_relevance_metrics` keys

---

## Done criteria

1. `python dedup_comments.py` prints without `PYTHONIOENCODING=utf-8`
2. `python cluster_comments.py` prints without `PYTHONIOENCODING=utf-8`
3. `python -m unittest test_evaluate.py -v` — 2 tests pass
4. `python evaluate_pipeline.py --docket EPA-HQ-OAR-2020-0272` exits 0
5. `outputs/EPA-HQ-OAR-2020-0272/eval_report.json` is valid JSON with both metric sections
6. `outputs/EPA-HQ-OAR-2020-0272/eval_report.txt` is readable plain text
7. `gold_set/EPA-HQ-OAR-2020-0272.json` is valid JSON with 10 alignments and 5 cluster_relevance entries
