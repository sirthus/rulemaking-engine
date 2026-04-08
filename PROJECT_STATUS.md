# Project Status

Last updated: 2026-04-07

## Current Implementation State

- The V1 substrate and V2 insight layer are implemented for the locked three-docket EPA starter set.
- The pipeline remains artifact-first and local-first.
- Local corpus stages write working artifacts under `corpus/`.
- Cluster labeling and insight synthesis now run through Codex as the labeling agent.
- Review/operator artifacts are written under `outputs/`, including `insight_report.json`.
- Published site-safe JSON snapshots are written under `site_data/`.
- A static read-only React insight surface lives under `site_app/` and reads only from `site_data/current/`.
- The site has a docket story launcher, insight summaries, top findings, evidence drilldown, proposed/final diffs, analyst-first card sorting, and lower-signal card folding.
- Vite serves the published snapshot in dev and copies it into `dist/` for production builds.
- The frontend loader tolerates earlier published V1 snapshot payloads as a compatibility shim.
- `label_audit.json` remains retired in favor of `label_run.json`.
- `PROJECT_STATUS.md`, `BLUEPRINT.md` for V1, `V2_BLUEPRINT.md` for the V2 implementation plan, `README.md`, and `CLAUDE.md` are the active tracked handoff docs.

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
- `site_app/`

## Latest Local Verification

V2 final verification refreshed on 2026-04-07:

- V2 insight/publish/refresh pytest coverage passed:
  - `TMPDIR=/tmp TMP=/tmp TEMP=/tmp python -m pytest test_generate_insights.py test_publish_site_snapshot.py test_refresh_site_snapshot.py -v`
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
  - Vitest hoisting fix in `App.test.tsx`
  - selector fixes in `App.test.tsx`
  - Vite snapshot-serving support in dev/build
  - legacy published snapshot compatibility in the frontend loader
  - V2 insight loading fallbacks
  - home story launcher and evidence drilldown UI
  - card priority/size sorting and lower-signal folding

## Active Focus

- V2 implementation is complete for the current three-docket EPA scope.
- Human-blind annotation is no longer a blocker. AI-blind gold sets remain the accepted V2 evaluation baseline.
- The next product pass is V2.5: rework the React site so it comes across as a clean, modern analyst UI with stronger visual hierarchy and more polished docket/card presentation.
- If the site shows stale or unavailable evaluation for any docket, rerun `evaluate_pipeline.py`, `generate_insights.py`, and `publish_site_snapshot.py` after committing the gold-set baseline.

## Notes For The Next Pass

- Keep V2.5 frontend-only unless a specific product need requires new snapshot fields.
- Preserve the local-first/static architecture: no backend service, no live inference, no direct site reads from `corpus/` or `outputs/`.
- Keep Codex as the labeling and synthesis agent; do not route new product work through legacy local model entrypoints.
- Treat V2.5 as UI modernization and polish, not a new model or data-pipeline phase.
- Before handoff, run the focused frontend suite, build, docs acceptance test, and `git diff --check`.
