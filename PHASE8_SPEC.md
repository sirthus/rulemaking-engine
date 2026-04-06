# Phase 8 Spec — Outputs and Usability

Status: implemented and tracked in Git.

## Goal

Create `generate_outputs.py` that consumes all per-docket corpus artifacts and writes three
output formats to `outputs/{docket_id}/`:

- `report.json` — machine-readable consolidated export
- `report.csv` — tabular export for spreadsheet review
- `report.html` — self-contained static HTML for human review

No backend. No framework. No causal claims. This is the final pipeline stage.

---

## CLI

```bash
python generate_outputs.py [--docket DOCKET_ID] [--output-dir PATH] [--force]
```

| Flag | Default | Meaning |
|------|---------|---------|
| `--docket` | all three | Process only the specified docket ID |
| `--output-dir` | `outputs/` (repo root) | Root directory for all output files |
| `--force` | off | Overwrite existing outputs; without this flag, skip dockets whose outputs already exist |

Valid docket IDs:
- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

---

## Input files

All read from `corpus/{docket_id}/`.

| File | Required | Used for |
|------|----------|---------|
| `comment_themes.json` | **Yes** | clusters, commenter counts, labels |
| `comments.json` | No | fallback text lookup (unused in V1 outputs) |
| `change_cards.json` | No | change card records |
| `comment_attribution.json` | No | attribution stats for summary |
| `alignment_log.json` | No | alignment coverage stats for summary |

- If `comment_themes.json` is absent → print error, skip that docket, continue to next.
- If `change_cards.json` is absent → print warning, write outputs with empty `change_cards` array and note the absence in summary.
- Other missing files → silently skip the fields they would populate; do not error.

---

## Comment → Cluster join

Build lookup structures from `comment_themes.json` before processing cards:

```python
clusters_by_id = {c["cluster_id"]: c for c in themes.get("clusters", [])}

comment_to_cluster: dict[str, str] = {}
for cluster in themes.get("clusters", []):
    for cid in cluster.get("member_canonical_ids", []):
        comment_to_cluster[cid] = cluster["cluster_id"]
```

For each change card, derive `related_clusters` as follows:

1. Collect `(cluster_id, relationship_label, comment_id)` tuples from `card["related_comments"]`
   by looking up each `comment_id` in `comment_to_cluster`.
2. Group by `cluster_id`, collecting all `relationship_labels` (deduplicated).
3. For each unique cluster, record `comment_count` (count of related_comments that map to it).
4. Join to `clusters_by_id` to get `label`, `label_description`, `canonical_count`.
5. Sort by `canonical_count` descending.

---

## Output 1 — `report.json`

```json
{
  "docket_id": "EPA-HQ-OAR-2020-0272",
  "generated_at": "<ISO8601 UTC>",
  "generator": "generate_outputs.py",
  "summary": {
    "total_comments": 100,
    "total_canonical_comments": 80,
    "total_clusters": 5,
    "labeled_clusters": 3,
    "total_change_cards": 20,
    "change_type_counts": {"modified": 15, "added": 3, "removed": 2},
    "alignment_signal_counts": {"high": 5, "medium": 8, "low": 4, "none": 3},
    "review_status_counts": {"pending": 20}
  },
  "clusters": [
    {
      "cluster_id": "EPA-HQ-OAR-2020-0272_cluster_001",
      "label": "Compliance Timeline and Cost Burden for Small Refineries",
      "label_description": "Small refineries argue the proposed timeline and costs are disproportionately burdensome.",
      "canonical_count": 7,
      "total_raw_comments": 14,
      "top_keywords": ["refinery", "cost", "compliance", "deadline"],
      "commenter_type_distribution": {"business": 5, "individual": 2}
    }
  ],
  "change_cards": [
    {
      "card_id": "EPA-HQ-OAR-2020-0272_card_0001",
      "change_type": "modified",
      "match_type": "exact_heading",
      "heading_similarity": 0.95,
      "proposed_section_id": "proposed_001",
      "final_section_id": "final_001",
      "proposed_heading": "Section heading text",
      "final_heading": "Section heading text",
      "proposed_text_snippet": "...",
      "final_text_snippet": "...",
      "alignment_signal": {
        "level": "high",
        "score": 8,
        "features": {
          "comment_count": 5,
          "unique_comment_count": 3,
          "largest_family_size": 2,
          "best_attribution_confidence": "high",
          "preamble_link_count": 1,
          "best_link_type": "cfr_citation"
        },
        "evidence_note": "5 comments (3 unique arguments) attributed..."
      },
      "related_clusters": [
        {
          "cluster_id": "EPA-HQ-OAR-2020-0272_cluster_001",
          "label": "Compliance Timeline and Cost Burden for Small Refineries",
          "label_description": "...",
          "comment_count": 3,
          "canonical_count": 7,
          "relationship_labels": ["related concern cited in comment"]
        }
      ],
      "preamble_links": [
        {
          "preamble_section_id": "preamble_005",
          "preamble_heading": "Response to Comments on Compliance Deadlines",
          "link_type": "cfr_citation",
          "link_score": 0.85,
          "relationship_label": "same section cited in preamble discussion"
        }
      ],
      "review_status": "pending"
    }
  ]
}
```

**Field notes:**
- `summary.total_comments` and `total_canonical_comments`: from `comment_themes.json` top-level fields.
- `summary.labeled_clusters`: count of clusters where `label` is non-null and non-empty.
- `summary.change_type_counts`, `alignment_signal_counts`, `review_status_counts`: derived from `change_cards.json`; omit or zero-fill if file absent.
- `clusters`: include only the fields listed above — do not include `member_canonical_ids` or `label_meta` in the export.
- `related_clusters` on each card: derived via the comment→cluster join described above.

---

## Output 2 — `report.csv`

One row per change card. 19 columns in this order:

| # | Column | Source |
|---|--------|--------|
| 1 | `docket_id` | `card["docket_id"]` |
| 2 | `card_id` | `card["card_id"]` |
| 3 | `change_type` | `card["change_type"]` |
| 4 | `match_type` | `card["match_type"]` |
| 5 | `heading_similarity` | `card["heading_similarity"]` |
| 6 | `proposed_section_id` | `card["proposed_section_id"]` |
| 7 | `final_section_id` | `card["final_section_id"]` |
| 8 | `proposed_heading` | `card["proposed_heading"]` |
| 9 | `final_heading` | `card["final_heading"]` |
| 10 | `proposed_text_snippet` | `card["proposed_text_snippet"]` |
| 11 | `final_text_snippet` | `card["final_text_snippet"]` |
| 12 | `alignment_signal_level` | `card["alignment_signal"]["level"]` |
| 13 | `alignment_score` | `card["alignment_signal"]["score"]` |
| 14 | `related_comment_count` | `len(card["related_comments"])` |
| 15 | `related_cluster_count` | count of unique cluster IDs derived from related_comments |
| 16 | `top_cluster_label` | label of first `related_cluster` (by canonical_count desc), or `""` |
| 17 | `preamble_link_count` | `len(card["preamble_links"])` |
| 18 | `evidence_note` | `card["alignment_signal"]["evidence_note"]` |
| 19 | `review_status` | `card["review_status"]` |

- Use `csv.DictWriter`.
- Encoding: `utf-8-sig` (UTF-8 with BOM) for Excel compatibility.
- If `change_cards.json` is absent, write the header row only; no data rows.
- `None` values should be written as empty string `""`.

---

## Output 3 — `report.html`

Single self-contained file. **No CDN. No external assets. Inline CSS and vanilla JS only.**

### Page structure

```
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{docket_id} — Rule Change Analysis</title>
  <style>/* all CSS inline here */</style>
</head>
<body>
  <header>
    <h1>{docket_id}</h1>
    <p class="subtitle">Rule Change Analysis</p>
    <p class="generated">Generated {ISO8601 datetime} · generate_outputs.py</p>
  </header>

  <section id="summary">
    <h2>Summary</h2>
    <table class="stats-table">
      <!-- Two-column key/value rows: -->
      <!-- Total public comments | {N} -->
      <!-- Unique arguments (canonical) | {N} -->
      <!-- Comment themes (clusters) | {N} ({labeled} labeled) -->
      <!-- Change cards | {N} -->
      <!-- Changes: modified / added / removed | {N} / {N} / {N} -->
      <!-- Alignment signal: high / medium / low / none | {N} / {N} / {N} / {N} -->
    </table>
  </section>

  <section id="clusters">
    <h2>Comment Themes ({N} clusters)</h2>
    <table class="clusters-table">
      <thead>
        <tr>
          <th>Label</th>
          <th>Description</th>
          <th>Unique Args</th>
          <th>Total Submissions</th>
          <th>Top Keywords</th>
          <th>Commenter Mix</th>
        </tr>
      </thead>
      <tbody>
        <!-- one <tr> per cluster -->
        <!-- Label: cluster label or cluster_id if unlabeled -->
        <!-- Commenter mix: "business: 5, individual: 2" style string -->
      </tbody>
    </table>
  </section>

  <section id="cards">
    <h2>Change Cards ({N} cards)</h2>
    <div id="filter-bar">
      <label>Change type:
        <select id="filter-change-type">
          <option value="all">all</option>
          <option value="modified">modified</option>
          <option value="added">added</option>
          <option value="removed">removed</option>
        </select>
      </label>
      <label>Alignment signal:
        <select id="filter-signal">
          <option value="all">all</option>
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
          <option value="none">none</option>
        </select>
      </label>
    </div>

    <div id="cards-container">
      <!-- one <details class="card"> per card -->
      <details class="card" data-change-type="{change_type}" data-signal="{level}">
        <summary>
          <span class="card-id">{card_id}</span>
          <span class="badge change-{change_type}">{change_type}</span>
          <span class="badge signal-{level}">{LEVEL}</span>
          <span class="heading-text">{effective heading}</span>
        </summary>
        <div class="card-body">

          <div class="text-compare">
            <div class="text-block proposed">
              <h4>Proposed (<code>{proposed_section_id}</code>)</h4>
              <pre>{proposed_text_snippet}</pre>
            </div>
            <div class="text-block final">
              <h4>Final (<code>{final_section_id}</code>)</h4>
              <pre>{final_text_snippet}</pre>
            </div>
          </div>

          <div class="related-clusters">
            <h4>Related Comment Themes ({N})</h4>
            <!-- if none: <p class="empty">No related comment themes.</p> -->
            <!-- else: one <div class="cluster-item"> per related cluster: -->
            <!--   cluster label (or cluster_id if unlabeled) -->
            <!--   description (if present) -->
            <!--   "{comment_count} related comment(s) · {canonical_count} unique arguments in cluster" -->
            <!--   relationship labels as comma-separated italic text -->
          </div>

          <div class="preamble-links">
            <h4>Preamble Discussion ({N})</h4>
            <!-- if none: <p class="empty">No preamble links found.</p> -->
            <!-- else: one <div class="preamble-item"> per link: -->
            <!--   section ID, heading (if present), link_type badge, relationship_label -->
          </div>

          <div class="signal-detail">
            <h4>Alignment Signal: <span class="badge signal-{level}">{LEVEL}</span> (score {score})</h4>
            <p class="evidence-note">{evidence_note}</p>
            <ul class="features">
              <!-- one <li> per feature key: value pair in alignment_signal.features -->
            </ul>
          </div>

          <div class="review-status">
            <strong>Review status:</strong> {review_status}
          </div>

        </div>
      </details>
    </div>

    <p id="no-cards-msg" hidden>No cards match the current filters.</p>
  </section>

  <script>/* all JS inline here */</script>
</body>
</html>
```

### "Effective heading" in card `<summary>`
- If `proposed_heading` and `final_heading` are equal (or one is null): show whichever is non-null.
- If both are non-null and different: show `"{proposed_heading} → {final_heading}"`.
- If both are null: show the `card_id`.

### JS filtering (inline `<script>`)

```javascript
(function () {
  const selType = document.getElementById('filter-change-type');
  const selSignal = document.getElementById('filter-signal');
  const noMsg = document.getElementById('no-cards-msg');

  function applyFilters() {
    const typeVal = selType.value;
    const signalVal = selSignal.value;
    let visible = 0;
    document.querySelectorAll('.card').forEach(function (card) {
      const show =
        (typeVal === 'all' || card.dataset.changeType === typeVal) &&
        (signalVal === 'all' || card.dataset.signal === signalVal);
      card.hidden = !show;
      if (show) visible++;
    });
    noMsg.hidden = visible > 0;
  }

  selType.addEventListener('change', applyFilters);
  selSignal.addEventListener('change', applyFilters);
})();
```

### CSS guidelines (inline `<style>`)

- Body: `font-family: system-ui, sans-serif; max-width: 1100px; margin: 0 auto; padding: 1rem 2rem`
- `pre`: `white-space: pre-wrap; max-height: 200px; overflow-y: auto; background: #f5f5f5; padding: .5rem; border-radius: 4px`
- `.text-compare`: `display: flex; gap: 1rem` (each `.text-block` takes `flex: 1`)
- Signal badge colors:
  - `.signal-high`: `background: #2e7d32; color: #fff`
  - `.signal-medium`: `background: #e65100; color: #fff`
  - `.signal-low`: `background: #757575; color: #fff`
  - `.signal-none`: `background: #e0e0e0; color: #333`
- Change type badge colors:
  - `.change-modified`: `background: #1565c0; color: #fff`
  - `.change-added`: `background: #00695c; color: #fff`
  - `.change-removed`: `background: #b71c1c; color: #fff`
- `.badge`: `display: inline-block; padding: 2px 7px; border-radius: 3px; font-size: .8em; font-weight: 600; margin-right: 4px`
- `details.card`: `border: 1px solid #ddd; border-radius: 5px; margin-bottom: .75rem; padding: .5rem`
- `details.card > summary`: `cursor: pointer; list-style: none; padding: .25rem`
- `.card-body`: `margin-top: .75rem; padding-top: .75rem; border-top: 1px solid #eee`
- Tables: `border-collapse: collapse; width: 100%`; `th, td`: `text-align: left; padding: .4rem .6rem; border-bottom: 1px solid #ddd`
- `#filter-bar`: `margin-bottom: 1rem; display: flex; gap: 1.5rem; align-items: center`

---

## Code patterns

Match the existing codebase style exactly:

```python
#!/usr/bin/env python3

import argparse
import csv
import html as html_module
import json
import os
from datetime import datetime, timezone

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def read_json(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)

def atomic_write_json(path: str, payload) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2))

def print_line(prefix: str, docket_id: str, message: str) -> None:
    print(f"[{prefix}]  {docket_id}  {message}")
```

Use `html_module.escape()` on all user-derived text interpolated into HTML.

---

## .gitignore update

Add `outputs/` to `.gitignore` alongside `corpus/` and `cache/`.

---

## Done criteria

1. `python generate_outputs.py --docket EPA-HQ-OAR-2020-0272` exits 0.
2. `outputs/EPA-HQ-OAR-2020-0272/report.json` is valid JSON; contains `summary`, `clusters`, `change_cards`.
3. `outputs/EPA-HQ-OAR-2020-0272/report.csv` is valid CSV with 19 columns; opens in Excel without encoding issues.
4. `outputs/EPA-HQ-OAR-2020-0272/report.html` opens in a browser; cards render; change-type and signal filters show/hide cards correctly.
5. Running with `change_cards.json` absent produces a warning but still writes valid (partial) outputs.
6. No causal language in any output: no "caused", "resulted in", "led to", "drove", "prompted".
7. `outputs/` is in `.gitignore`.
