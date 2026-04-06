# Project Status

Last updated: 2026-04-06

## Current implementation state

- The repo is implemented through Phase 10.
- The pipeline remains artifact-first and local-first.
- Deterministic stages write working artifacts under `corpus/`.
- Phase 7 labeling runs only against local Ollama.
- Review/operator artifacts are written under `outputs/`.
- Published site-safe JSON snapshots are written under `site_data/`.
- A static React app now lives under `site_app/` and reads only from `site_data/current/`.
- Vite now serves the published snapshot in dev and copies it into `dist/` for production builds.
- The frontend loader now tolerates earlier published V1 snapshot payloads as a compatibility shim.
- `label_audit.json` remains retired in favor of `label_run.json`.
- `PROJECT_STATUS.md` and the Phase 8-10 spec files are now tracked in Git for cross-machine handoff.

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

Observed Phase 7 comparison on `EPA-HQ-OAR-2020-0430`:

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
- `publish_site_snapshot.py`
- `refresh_site_snapshot.py`
- `prepare_gold_set_packet.py`
- `validate_gold_set.py`

Key artifact boundaries:

- `corpus/{docket_id}/comment_themes.json`
- `corpus/{docket_id}/label_run.json`
- `outputs/{docket_id}/report.json`
- `outputs/{docket_id}/eval_report.json`
- `site_data/current/manifest.json`
- `site_data/current/release_summary.json`
- `site_data/current/dockets/index.json`
- `site_app/`

## Latest local verification

Phase 10 verification completed on 2026-04-05:

- backend/unit suite passed for the Phase 7 to Phase 10 Python surface:
  - `python -m unittest test_phase5.py test_phase8.py test_evaluate.py test_cluster_comments.py test_change_cards.py test_label_clusters.py test_publish_site_snapshot.py test_refresh_site_snapshot.py test_docs_acceptance.py test_ollama_runtime.py test_gold_set_workflow.py -v`
- frontend verification passed:
  - `npm test`
  - `npm run build`
- frontend runtime issues resolved:
  - Vitest hoisting fix in `App.test.tsx`
  - selector fixes in `App.test.tsx`
  - Vite snapshot-serving support in dev/build
  - legacy published snapshot compatibility in the frontend loader
- real local Phase 7 smoke runs completed for:
  - `qwen3:14b --no-think --force`
  - `gemma3:12b-it-q8_0 --force`
- real local refresh/publish path completed for:
  - `refresh_site_snapshot.py --docket EPA-HQ-OAR-2020-0430 --model qwen3:14b --force-labels`

## Active blockers

- External evaluation reporting is still blocked by gold-set quality. Only `EPA-HQ-OAR-2020-0272` has a committed gold set, and that set is seed-derived rather than blind human annotation.
- Full blind gold sets do not yet exist for `EPA-HQ-OAR-2018-0225` or `EPA-HQ-OAR-2020-0430`.
- If the site shows evaluation as `not_available` for `EPA-HQ-OAR-2018-0225` or `EPA-HQ-OAR-2020-0430`, that is expected until those gold sets are completed and committed.

## Notes for the next implementation pass

- Generate blind annotation packets for the remaining two dockets.
- Complete blind human gold sets for `EPA-HQ-OAR-2018-0225` and `EPA-HQ-OAR-2020-0430`.
- Replace the seed-derived `EPA-HQ-OAR-2020-0272` gold set with blind human annotation before any external reporting.
- Rerun `evaluate_pipeline.py` or `refresh_site_snapshot.py --model qwen3:14b` after each gold-set update.
- Verify the React site against the refreshed multi-docket snapshot.
