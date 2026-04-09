# Rulemaking Evolution and Comment Impact Engine

Traceable rule-evolution analysis plus cautious comment-theme alignment for public rulemaking dockets.

## Overview

This repository is an artifact-first local product:

- local corpus stages build artifacts under `corpus/`
- Codex runs cluster labeling and insight generation
- review artifacts are written under `outputs/`
- published site-safe JSON snapshots are written under `site_data/`
- a static React app under `site_app/` reads only from `site_data/current/`

There is no live model API in the product path, and the site never invokes a model directly.

## Current Status

The V2 insight-first analyst surface is implemented for the locked three-docket EPA starter set:

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

The current product includes:

- a static read-only React insight and review surface
- the completed UI overhaul across the home, overview, priority changes, comment themes, and card detail surfaces
- a completed refactor/performance pass across both the Python pipeline and the React app
- shared Python pipeline helpers in `pipeline_utils.py`
- per-docket parallelism in the dedup, change-card, and clustering stages, plus parallel Federal Register fetches
- `generate_insights.py` and per-docket `insight_report.json`
- published insight reports under `site_data/current/`
- a home docket story launcher with preview titles embedded in the published docket index
- docket-level summaries, top findings, and card detail evidence drilldown
- analyst-first card sorting, proposed/final diffs, and lower-signal card folding
- a richer published snapshot contract with `release_summary.json`
- a route-split React app with lazy-loaded pages, memoized review/theme selectors, and cached snapshot fetches
- blind gold-set packet generation and validation tooling
- Vite dev/build support for serving and packaging the published snapshot
- removal of the old local runtime helper and earlier spike artifacts that no longer belong in the product path

## Prerequisites

Python/runtime:

- `python` or `python3`
- `pip`
- `requests`

Frontend/runtime:

- `node`
- `npm`

API access:

- `REGULATIONS_GOV_API_KEY` for `fetch_corpus.py`

Install the Python dependency:

```bash
pip install requests
```

Set your Regulations.gov API key before fetching comments:

```bash
export REGULATIONS_GOV_API_KEY=your_key_here
```

Federal Register does not require an API key. Regulations.gov does.

## Local Corpus Pipeline

Run the corpus-building stages:

```bash
python fetch_corpus.py
python align_corpus.py
python dedup_comments.py
python generate_change_cards.py
python cluster_comments.py
```

## Codex Labeling and Publish Refresh

Codex is the labeling and insight-generation agent. Do not use Ollama as a product workflow dependency.

After Codex updates labels or insight text, regenerate and publish the downstream artifacts:

```bash
python generate_outputs.py --force
python evaluate_pipeline.py
python generate_insights.py
python publish_site_snapshot.py
```

That post-label refresh flow:

1. regenerates `report.json`, `report.csv`, and `report.html`
2. regenerates `eval_report.json`
3. regenerates `insight_report.json`
4. publishes a new immutable snapshot release plus `site_data/current/`

## Outputs vs Published Site Data

The repo now has three distinct artifact layers:

- `corpus/`: source-of-truth working artifacts from the local pipeline
- `outputs/`: operator review artifacts
- `site_data/`: published JSON snapshots for the site

Published snapshot contract:

- `site_data/current/manifest.json`
- `site_data/current/release_summary.json`
- `site_data/current/dockets/index.json`
- `site_data/current/dockets/{docket_id}/report.json`
- `site_data/current/dockets/{docket_id}/eval_report.json`
- `site_data/current/dockets/{docket_id}/insight_report.json`

`report.csv`, `report.html`, raw corpus files, and operator-only manifests are intentionally excluded from the site contract.

The published `dockets/index.json` now carries enough metadata for the homepage to render docket previews without eagerly fetching all three `insight_report.json` files.

## Static React Site

The site lives under `site_app/`. It is a client-only V2 insight surface with:

- no backend
- no SSR requirement
- no model calls
- no browser editing workflow
- route-based code splitting for the home, docket, and card-detail pages
- immutable snapshot JSON caching inside the frontend loader

The site expects a published snapshot to exist first:

```bash
python publish_site_snapshot.py
```

Then use the frontend workspace:

```bash
cd site_app
npm install
npm test
npm run build
npm run dev
```

Useful routes:

- `/`
- `/dockets/:docketId`
- `/dockets/:docketId/cards/:cardId`

Local serving behavior:

- in `npm run dev`, Vite serves `site_data/current/` directly at `/site_data/current/...`
- in `npm run build`, the snapshot is copied into `dist/site_data/current/`
- `npm run preview` serves the built snapshot-aware site

The frontend loader now tolerates both:

- the current V2 snapshot shape
- the earlier published snapshot shape from before the richer docket index fields existed

That compatibility is only a safety net. The recommended path is still to regenerate the downstream artifacts after Codex labeling, then publish the snapshot so the site gets the latest V2 metadata and insight reports.

## Blind Evaluation Workflow

The workflow makes blind gold-set mechanics a first-class repo workflow.

Generate a blinded packet and editable template from the current published snapshot:

```bash
python prepare_gold_set_packet.py --docket EPA-HQ-OAR-2020-0430
```

That writes:

- `gold_set/packets/{docket_id}.packet.json`
- `gold_set/templates/{docket_id}.template.json`

AI-blind gold sets are accepted as the V2 evaluation baseline. Validate any new or updated gold set before evaluation:

```bash
python validate_gold_set.py --docket EPA-HQ-OAR-2020-0430 --path gold_set/EPA-HQ-OAR-2020-0430.json
```

Then regenerate evaluation:

```bash
python evaluate_pipeline.py --docket EPA-HQ-OAR-2020-0430
```

If a docket lacks a committed gold set, evaluation writes an `eval_report.json` stub with `status: "not_available"`.

## Verified Commands

Backend verification:

```bash
python -m unittest test_pipeline_utils.py test_label_clusters.py test_refresh_site_snapshot.py test_comment_dedup_and_signals.py test_change_cards.py test_cluster_comments.py test_publish_site_snapshot.py -v
python -m unittest test_comment_dedup_and_signals.py test_generate_outputs.py test_evaluate.py test_cluster_comments.py test_change_cards.py test_publish_site_snapshot.py test_docs_acceptance.py test_gold_set_workflow.py test_gold_set_consistency.py -v
TMPDIR=/tmp TMP=/tmp TEMP=/tmp python -m pytest test_generate_insights.py test_publish_site_snapshot.py test_refresh_site_snapshot.py -v
TMPDIR=/tmp TMP=/tmp TEMP=/tmp python -m pytest test_pipeline_utils.py -v
```

Frontend verification:

```bash
cd site_app
npm test -- --run src/App.test.tsx src/snapshot.test.ts
npm run build
```

## Scope And Guardrails

The operating scope is intentionally narrow:

- one agency: EPA
- three locked dockets
- one proposed rule and one final rule per docket
- comments from the main text body only
- read-only browser review surface

Current non-goals:

- no attachment parsing
- no OCR pipeline
- no eCFR integration
- no live inference backend
- no browser editing workflow
- no causal claim that comments determined a rule change

## Portable Handoff Docs

The active handoff docs are tracked in Git so another machine can pull the repo and know what to do next:

- `PROJECT_STATUS.md`: current state, accepted architecture decisions, verification notes, and next tasks
- `README.md`: quickstart and operator workflow
- `CLAUDE.md`: Claude Code coordination and guardrails

If a fresh checkout is unclear, read `PROJECT_STATUS.md` first. It is the canonical brief handoff for the next work block.

## Roadmap

The V2 insight surface, UI overhaul, and refactor/performance pass are complete for the current three-docket EPA scope.

The next planned work is:

1. turn the top-level `README.md` into a stronger Showpiece README for the project
2. audit the large stylesheet and remove dead CSS left over from the UI overhaul
3. continue low-risk cleanup without changing the local-first/static architecture
