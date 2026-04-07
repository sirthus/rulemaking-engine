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
- Vite now serves the published snapshot in dev and copies it into `dist/` for production builds.
- The frontend loader now tolerates earlier published V1 snapshot payloads as a compatibility shim.
- `label_audit.json` remains retired in favor of `label_run.json`.
- `PROJECT_STATUS.md`, `BLUEPRINT.md` for V1, `V2_BLUEPRINT.md` for the next product phase, `README.md`, and `CLAUDE.md` are the active tracked handoff docs.

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

Python/docs verification refreshed on 2026-04-07:

- backend/unit suite passed for the local pipeline and site publishing Python surface:
  - `python -m unittest test_comment_dedup_and_signals.py test_generate_outputs.py test_evaluate.py test_cluster_comments.py test_change_cards.py test_label_clusters.py test_publish_site_snapshot.py test_refresh_site_snapshot.py test_docs_acceptance.py test_ollama_runtime.py test_gold_set_workflow.py test_gold_set_consistency.py -v`
- docs cleanup verification passed:
  - `git diff --check`

Frontend verification last passed on 2026-04-05:

- frontend verification passed:
  - `npm test`
  - `npm run build`
- frontend runtime issues resolved:
  - Vitest hoisting fix in `App.test.tsx`
  - selector fixes in `App.test.tsx`
  - Vite snapshot-serving support in dev/build
  - legacy published snapshot compatibility in the frontend loader
- real local labeler smoke runs completed for:
  - `qwen3:14b --no-think --force`
  - `gemma3:12b-it-q8_0 --force`
- real local refresh/publish path completed for:
  - `refresh_site_snapshot.py --docket EPA-HQ-OAR-2020-0430 --model qwen3:14b --force-labels`

## Active focus

- Human-blind annotation is no longer a blocker for V2. AI-blind gold sets are accepted as the V2 evaluation baseline.
- The next product gap is insight quality: the current site is mostly an artifact viewer, while V2 should surface rulemaking narratives, ranked findings, and evidence-backed explanations.
- If the site shows stale or unavailable evaluation for any docket, rerun `evaluate_pipeline.py` or `refresh_site_snapshot.py --model qwen3:14b` after committing the gold-set baseline.

## Notes for the next implementation pass

- Commit the AI-blind gold-set baseline and the consistency test.
- Rerun `evaluate_pipeline.py` or `refresh_site_snapshot.py --model qwen3:14b` after gold-set updates.
- Verify the React site against the refreshed multi-docket snapshot.
- Start V2 from `V2_BLUEPRINT.md`: add an insight artifact layer, publish it into `site_data/current/`, and upgrade the React site from artifact viewer to insight surface.
