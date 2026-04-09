# Project Status

Last updated: 2026-04-09

## Current Implementation State

- The V1 substrate and V2 insight layer are implemented for the locked three-docket EPA starter set.
- The pipeline remains artifact-first and local-first.
- Local corpus stages write working artifacts under `corpus/`.
- Cluster labeling and insight synthesis now run through Codex as the labeling agent.
- Review/operator artifacts are written under `outputs/`, including `insight_report.json`.
- Published site-safe JSON snapshots are written under `site_data/`.
- A static read-only React insight surface lives under `site_app/` and reads only from `site_data/current/`.
- The site has a docket story launcher, insight summaries, top findings, evidence drilldown, proposed/final diffs, analyst-first card sorting, and lower-signal card folding.
- The UI overhaul pass is complete across the home, overview, priority changes, comment themes, and card detail surfaces.
- The refactor/performance pass is now complete across the shared Python pipeline surface and the React app shell.
- Shared Python helpers now live in `pipeline_utils.py`, removing duplicated file-write, normalization, and docket-list logic from the pipeline scripts.
- `fetch_corpus.py`, `dedup_comments.py`, `generate_change_cards.py`, and `cluster_comments.py` now parallelize independent docket/source work where safe.
- The frontend is split into page modules plus shared hooks/constants, with route lazy-loading, memoized docket selectors, and cached snapshot fetches.
- The published docket index now includes `top_finding_title`, so the homepage no longer eager-loads every insight report for preview text.
- Legacy spike artifacts and the old `ollama_runtime.py` helper have been removed from the active repository shape.
- Vite serves the published snapshot in dev and copies it into `dist/` for production builds.
- The frontend loader tolerates earlier published V1 snapshot payloads as a compatibility shim.
- `label_audit.json` remains retired in favor of `label_run.json`.
- `PROJECT_STATUS.md`, `README.md`, and `CLAUDE.md` are the active tracked handoff docs.

## Architecture Decisions

### 2026-04-05 — Local-Only Product Path

The product path should not use a live model API.

Chosen operating model:

1. Run local ingestion and analysis stages.
2. Use Codex for labeling and insight generation whenever judgment or synthesis helps.
3. Regenerate review outputs.
4. Publish a clean JSON snapshot for the site.
5. Serve a static React site from the published snapshot only.

Implications:

- no product dependency on remote model credentials
- no live inference from the website
- no direct site reads from `corpus/` or `outputs/`
- `site_data/current/` is the site contract boundary

### 2026-04-07 — Codex Labeling Direction

Codex is now the labeling and insight-generation agent.

Decision:

- do not use or reintroduce Ollama for the product workflow
- prefer Codex-generated labels, summaries, and evidence explanations when the task benefits from synthesis
- keep rule alignment and publishing artifact-first and reproducible
- avoid over-fitting the product to purely deterministic text rankings when a grounded Codex pass can produce better analyst-facing language

## Current Repository Shape

Core scripts:

- `pipeline_utils.py`
- `fetch_corpus.py`
- `align_corpus.py`
- `dedup_comments.py`
- `generate_change_cards.py`
- `cluster_comments.py`
- `generate_outputs.py`
- `generate_insights.py`
- `evaluate_pipeline.py`
- `publish_site_snapshot.py`
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
- `site_app/src/pages/`
- `site_app/src/hooks/`
- `site_app/src/constants.ts`
- `site_app/`

## Latest Local Verification

Refactor/performance verification refreshed on 2026-04-09:

- V2 insight/publish/refresh pytest coverage passed:
  - `TMPDIR=/tmp TMP=/tmp TEMP=/tmp python -m pytest test_generate_insights.py test_publish_site_snapshot.py test_refresh_site_snapshot.py -v`
- shared pipeline utility coverage passed:
  - `TMPDIR=/tmp TMP=/tmp TEMP=/tmp python -m pytest test_pipeline_utils.py -v`
- focused pipeline utility/runtime/unit coverage passed:
  - `python -m unittest test_pipeline_utils.py test_label_clusters.py test_refresh_site_snapshot.py test_comment_dedup_and_signals.py test_change_cards.py test_cluster_comments.py test_publish_site_snapshot.py -v`
- backend/unit suite passed for the local pipeline and site publishing Python surface:
  - `python -m unittest test_comment_dedup_and_signals.py test_generate_outputs.py test_evaluate.py test_cluster_comments.py test_change_cards.py test_publish_site_snapshot.py test_docs_acceptance.py test_gold_set_workflow.py test_gold_set_consistency.py -v`
- V2 frontend verification passed:
  - `npm test -- --run src/App.test.tsx src/snapshot.test.ts`
  - `npm run build`
- artifact verification passed:
  - parsed all published `report.json`, `eval_report.json`, `insight_report.json`, `dockets/index.json`, and `release_summary.json`
  - confirmed all three dockets have `insight_available: true`
  - confirmed `release_summary.json` reports `"insights": {"available": 3, "not_available": 0}`
  - confirmed generated insight reports have zero banned causal-language violations
- docs cleanup verification passed:
  - `git diff --check`
- frontend runtime/product issues resolved:
  - `App.tsx` split into route-level page modules
  - route lazy-loading and code splitting
  - snapshot JSON cache layer in the frontend loader
  - published `top_finding_title` previews in `dockets/index.json`
  - memoized docket review/theme derivations and memoized diff computation
  - per-docket pipeline parallelism and shared Python utility extraction

## Active Focus

- V2 implementation is complete for the current three-docket EPA scope.
- The UI overhaul pass is complete for the current static React analyst surface.
- The refactor and performance work blocks are complete.
- Human-blind annotation is no longer a blocker. AI-blind gold sets remain the accepted V2 evaluation baseline.
- The next work block is:
  1. Showpiece README
  2. CSS audit / dead-style cleanup
  3. incremental cleanup where it improves maintainability without reopening product direction
- If the site shows stale or unavailable evaluation for any docket, rerun `evaluate_pipeline.py`, `generate_insights.py`, and `publish_site_snapshot.py` after committing the gold-set baseline.

## Notes For The Next Pass

- Treat the UI overhaul and refactor/performance pass as complete. The next pass should focus on presentation/documentation polish and targeted cleanup rather than reopen product-direction specs.
- Preserve the local-first/static architecture: no backend service, no live inference, no direct site reads from `corpus/` or `outputs/`.
- Keep Codex as the labeling and synthesis agent; do not route new product work through legacy local model entrypoints.
- Prioritize:
  1. rewriting the top-level README into a stronger Showpiece README
  2. auditing/removing dead CSS and other low-risk leftover cleanup
  3. preserving the refactored structure instead of collapsing code back into monolith files
- Before handoff, run the focused frontend suite, build, docs acceptance test, and `git diff --check`.
