# Project Status

Last updated: 2026-04-07

## Current implementation state

- The V1 substrate is implemented.
- The pipeline remains artifact-first and local-first.
- Deterministic stages write working artifacts under `corpus/`.
- Cluster labeling runs only against local Ollama.
- Review/operator artifacts are written under `outputs/`.
- Published site-safe JSON snapshots are written under `site_data/`.
- A static React app now lives under `site_app/` and reads only from `site_data/current/`.
- V2 is implemented through Phase 5: insight generation, publish/refresh integration, the React insight surface, card evidence drilldown, and final QA handoff.
- `generate_insights.py` produces deterministic `insight_report.json` artifacts from existing docket reports and evaluation reports.
- The React site surfaces docket-level insight summaries, ranked findings, priority cards, and card-level evidence drilldown while preserving V1 snapshot fallbacks.
- Vite now serves the published snapshot in dev and copies it into `dist/` for production builds.
- The frontend loader now tolerates earlier published V1 snapshot payloads as a compatibility shim.
- `label_audit.json` remains retired in favor of `label_run.json`.
- `PROJECT_STATUS.md`, `BLUEPRINT.md` for V1, `V2_BLUEPRINT.md` for the insight-system roadmap, `README.md`, and `CLAUDE.md` are the active tracked handoff docs.

## Architecture decisions

### 2026-04-05 — local-only product path

The product path should not use a live model API.

Chosen operating model:

1. Run deterministic ingestion and analysis locally.
2. Run LLM labeling locally in batches with Ollama.
3. Regenerate review outputs.
4. Publish a clean JSON snapshot for the site.
5. Serve a static React site from the published snapshot only.

Implications:

- no product dependency on remote model credentials
- no live inference from the website
- no direct site reads from `corpus/` or `outputs/`
- `site_data/current/` is the site contract boundary

### 2026-04-05 — validated local model profiles

- Default operator model: `qwen3:14b`
- Faster alternative: `gemma3:12b-it-q8_0`

Observed local labeler comparison on `EPA-HQ-OAR-2020-0430`:

- `gemma3:12b-it-q8_0`
  - wall clock: about `25.2s`
  - model time: about `23.1s`
  - `4757` input tokens / `490` output tokens
  - faster and cheaper
  - slightly more likely to over-specify a label
- `qwen3:14b --no-think`
  - wall clock: about `126.4s`
  - model time: about `124.3s`
  - `5323` input tokens / `9867` output tokens
  - slower and much chattier internally
  - safer labeling baseline for this repo

Decision:

- keep `qwen3:14b` as the default local operator model
- document `gemma3:12b-it-q8_0` as the faster alternative
- centralize `/no_think` behavior through shared model profiles

## Current repository shape

Core scripts:

- `fetch_corpus.py`
- `align_corpus.py`
- `dedup_comments.py`
- `generate_change_cards.py`
- `cluster_comments.py`
- `label_clusters.py`
- `generate_outputs.py`
- `evaluate_pipeline.py`
- `generate_insights.py`
- `publish_site_snapshot.py`
- `refresh_site_snapshot.py`
- `prepare_gold_set_packet.py`
- `validate_gold_set.py`

Key artifact boundaries:

- `corpus/{docket_id}/comment_themes.json`
- `corpus/{docket_id}/label_run.json`
- `outputs/{docket_id}/report.json`
- `outputs/{docket_id}/eval_report.json`
- `outputs/{docket_id}/insight_report.json`
- `site_data/current/manifest.json`
- `site_data/current/release_summary.json`
- `site_data/current/dockets/index.json`
- `site_data/current/dockets/{docket_id}/insight_report.json`
- `site_app/`

## Latest local verification

V2 final verification refreshed on 2026-04-07:

- V2 insight/publish/refresh pytest coverage passed:
  - `TMPDIR=/tmp TMP=/tmp TEMP=/tmp python -m pytest test_generate_insights.py test_publish_site_snapshot.py test_refresh_site_snapshot.py -v`
- backend/unit suite passed for the local pipeline and site publishing Python surface:
  - `python -m unittest test_comment_dedup_and_signals.py test_generate_outputs.py test_evaluate.py test_cluster_comments.py test_change_cards.py test_label_clusters.py test_docs_acceptance.py test_ollama_runtime.py test_gold_set_workflow.py test_gold_set_consistency.py -v`
- frontend verification passed:
  - `npm test`
  - `npm run build`
- artifact verification passed:
  - parsed all published `report.json`, `eval_report.json`, `insight_report.json`, `dockets/index.json`, and `release_summary.json`
  - confirmed all three dockets have `insight_available: true`
  - confirmed `release_summary.json` reports `"insights": {"available": 3, "not_available": 0}`
  - confirmed generated insight reports have zero banned causal-language violations
- docs cleanup verification passed:
  - `git diff --check -- PROJECT_STATUS.md`
- full local refresh caveat:
  - `python refresh_site_snapshot.py --model qwen3:14b` was attempted but could not reach Ollama at `http://localhost:11434`
  - deterministic fallback completed with existing local `outputs/` artifacts: `python generate_insights.py` then `python publish_site_snapshot.py`
- real local labeler smoke runs completed for:
  - `qwen3:14b --no-think --force`
  - `gemma3:12b-it-q8_0 --force`
- real local refresh/publish path completed for:
  - `refresh_site_snapshot.py --docket EPA-HQ-OAR-2020-0430 --model qwen3:14b --force-labels`

## Active focus

- V2 implementation is complete for the current three-docket EPA scope.
- Human-blind annotation is no longer a blocker. AI-blind gold sets remain the accepted V2 evaluation baseline.
- The next useful pass is reviewer/product polish: inspect the insight wording, card drilldown ergonomics, and any Claude review feedback on the final handoff PR.
- If the site shows stale or unavailable evaluation for any docket, start Ollama and rerun `refresh_site_snapshot.py --model qwen3:14b`; otherwise use `generate_insights.py` plus `publish_site_snapshot.py` for deterministic insight refreshes from existing reports.

## Notes for the next pass

- Review and merge the final Phase 5 handoff PR.
- Keep any future product changes small and evidence-first: no live browser inference, no remote model API dependency, and no causal claims in generated or user-facing insight text.
- Consider a later polish pass for finding/card navigation, copy review, and visual hierarchy after using the site on the three published dockets.
