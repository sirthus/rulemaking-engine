# Phase 4 Spec — Source Fix and Relationship Signals

## Context

Phase 3 produced change cards with empty `preamble_links` because the corpus has no sections
with `source == "preamble"`. The cause is a tag mismatch: `fetch_corpus.py` checks for
`<PREAMBLE>` and `<REGTEXT>`, but Federal Register XML uses `<SUPLINF>` for preamble discussion
and omits `<REGTEXT>` in many documents. This spec fixes that, re-runs the pipeline, and adds
an `alignment_signal` field to every change card.

## Deliverables

1. A 2-line patch to `fetch_corpus.py` fixing source detection.
2. A re-run of the three-script pipeline (all from cache, no new network calls).
3. A new `alignment_signal` field in every change card in `generate_change_cards.py`.

No new scripts. No new dependencies. No new output files beyond updating the existing ones.

---

## Part A: fetch_corpus.py changes

### Change 1 — Source context tag detection

In `process()`, replace:
    if tag == "PREAMBLE":
        current_source = "preamble"
    elif tag == "REGTEXT":
        current_source = "regulatory_text"

With:
    if tag in {"PREAMBLE", "SUPLINF"}:
        current_source = "preamble"
    elif tag == "REGTEXT":
        current_source = "regulatory_text"

`<SUPLINF>` is the Supplementary Information element in OFR XML. It contains preamble
analysis, background, and response-to-comments text. `<PREAMBLE>` is retained for compatibility.

### Change 2 — SECTION source override

In the `<SECTION>` handler, replace:
    add_section(current_source, heading, body_text)

With:
    section_source = "regulatory_text" if sectno else current_source
    add_section(section_source, heading, body_text)

`<SECTION>` elements with a `<SECTNO>` child are CFR amendment sections and must be
`regulatory_text` regardless of their position in the document tree.

---

## Part B: Pipeline re-run

After the corpus fix, re-run in this exact order:

    python fetch_corpus.py        # re-parses cached XML with corrected source labels
    python align_corpus.py        # re-aligns with corrected section metadata
    python generate_change_cards.py  # re-generates cards (preamble linkage now active)

All three scripts read only from disk (network layer fully cached). No API key required.

**Validation after `fetch_corpus.py`:** print a warning and halt if any docket has zero
sections with `source == "preamble"` in its `proposed_rule.json` or `final_rule.json`.
A preamble-free corpus means the XML structure changed and preamble linkage cannot work.

---

## Part C: generate_change_cards.py — alignment_signal field

Add `alignment_signal` to every change card. Compute it after `build_preamble_links()`.

### Scoring

For each card, compute a total point score:

| Evidence item | Points |
|---|---|
| Comment: attribution_method="citation", confidence="high" | 3 |
| Comment: attribution_method="keyword", confidence="medium" | 2 |
| Comment: attribution_method="keyword", confidence="low" | 1 |
| Any other related comment | 1 |
| Preamble link: link_type="cfr_citation" | 3 |
| Preamble link: link_type="keyword" | 1 |

Level thresholds: score=0 → "none"; 1–2 → "low"; 3–5 → "medium"; ≥6 → "high".

### Features

- `comment_count`: len(related_comments)
- `best_attribution_confidence`: highest confidence among related_comments; order:
  high > medium > low > none. "none" if no related comments.
- `preamble_link_count`: len(preamble_links)
- `best_link_type`: "cfr_citation" if any preamble link has that type, else "keyword" if
  any keyword link exists, else "none".

### Evidence note

A plain English sentence. No causal language (no: caused, led to, resulted in, because,
triggered, drove, prompted). Examples:

- No evidence: "No substantive inline comments or preamble discussion linked to this section."
- Comment only: "1 comment attributed by citation (high confidence); no preamble discussion linked."
- Preamble only: "No inline comments; 2 preamble sections linked (CFR citation)."
- Both: "2 comments attributed (best: keyword/medium); 1 preamble section linked by CFR citation."

### Schema

`alignment_signal` goes after `preamble_links`, before `review_status`:

    {
      "alignment_signal": {
        "level": "medium",
        "score": 5,
        "features": {
          "comment_count": 1,
          "best_attribution_confidence": "high",
          "preamble_link_count": 1,
          "best_link_type": "cfr_citation"
        },
        "evidence_note": "..."
      }
    }

### Text report

Append after the PREAMBLE LINKS block:

    ALIGNMENT SIGNAL: medium  (score 5)
      comment_count=1  best_attribution=high  preamble_link_count=1  best_link_type=cfr_citation
      <evidence_note text>

---

## Done criteria

1. After re-running `fetch_corpus.py`, at least one section per docket has `source == "preamble"`
   in `proposed_rule.json` and `final_rule.json`.
2. After re-running `generate_change_cards.py`, at least one change card per docket has a
   non-empty `preamble_links` array.
3. Every change card in every docket has an `alignment_signal` field with `level` in
   {none, low, medium, high} and `score >= 0`.
4. No `evidence_note` string contains causal language.
5. At least one card per docket has `alignment_signal.level != "none"` (confirming signals fire).
6. `PROJECT_STATUS.md` updated to reflect Phase 4 complete.
