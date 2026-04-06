# Rulemaking Evolution and Comment Impact Engine

Traceable rule-evolution analysis plus cautious comment-theme alignment for public rulemaking dockets.

## Overview

This repository is an artifact-first local product:

- deterministic stages build corpus artifacts under `corpus/`
- local Ollama batches add Phase 7 labels
- review artifacts are written under `outputs/`
- published site-safe JSON snapshots are written under `site_data/`
- a static React app under `site_app/` reads only from `site_data/current/`

There is no live model API in the product path, and the site never invokes a model directly.

## Current Status

The repo is implemented through Phase 10 for the locked three-docket EPA starter set:

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

Phase 10 adds:

- a static React snapshot viewer
- shared Ollama model profiles and preflight checks
- a richer published snapshot contract with `release_summary.json`
- blind gold-set packet generation and validation tooling
- Vite dev/build support for serving and packaging the published snapshot

## Prerequisites

Python/runtime:

- `python` or `python3`
- `pip`
- `requests`

Frontend/runtime:

- `node`
- `npm`

Local LLM/runtime:

- `ollama`
- at least one pulled local model

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

## Deterministic Pipeline

Run the deterministic stages:

```bash
python fetch_corpus.py
python align_corpus.py
python dedup_comments.py
python generate_change_cards.py
python cluster_comments.py
```

## Local Ollama Workflow

Phase 7 is local-only. Start Ollama and pull one of the supported profiles:

```bash
ollama serve
ollama pull qwen3:14b
ollama pull gemma3:12b-it-q8_0
```

Validated local profiles:

- accuracy-first default: `qwen3:14b`
- speed-first alternative: `gemma3:12b-it-q8_0`

Run labeling directly:

```bash
python label_clusters.py --model qwen3:14b --no-think
```

Or refresh the whole post-clustering path:

```bash
python refresh_site_snapshot.py --model qwen3:14b
```

That refresh command is the normal Phase 10 operator entrypoint. It now:

1. runs Ollama preflight and validates the requested model
2. resolves the supported model profile and `no_think` behavior
3. labels clusters locally
4. regenerates `report.json`, `report.csv`, and `report.html`
5. regenerates `eval_report.json`
6. publishes a new immutable snapshot release plus `site_data/current/`

For `qwen3:14b`, `refresh_site_snapshot.py` applies the recommended `no_think` behavior automatically through the shared model profile. You do not need to pass an extra flag there.

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

`report.csv`, `report.html`, raw corpus files, and operator-only manifests are intentionally excluded from the site contract.

## Static React Site

The first site lives under `site_app/`. It is a client-only React app with:

- no backend
- no SSR requirement
- no model calls
- no browser editing workflow

The site expects a published snapshot to exist first:

```bash
python refresh_site_snapshot.py --model qwen3:14b
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

- the newer Phase 10 snapshot shape
- the earlier published snapshot shape from before the richer docket index fields existed

That compatibility is only a safety net. The recommended path is still to regenerate the snapshot with `refresh_site_snapshot.py` so the site gets the latest Phase 10 metadata.

## Blind Evaluation Workflow

Phase 10 makes blind gold-set mechanics a first-class repo workflow.

Generate a blinded packet and editable template from the current published snapshot:

```bash
python prepare_gold_set_packet.py --docket EPA-HQ-OAR-2020-0430
```

That writes:

- `gold_set/packets/{docket_id}.packet.json`
- `gold_set/templates/{docket_id}.template.json`

After a reviewer completes a gold set, validate it before evaluation:

```bash
python validate_gold_set.py --docket EPA-HQ-OAR-2020-0430 --path gold_set/EPA-HQ-OAR-2020-0430.json
```

Then regenerate evaluation:

```bash
python evaluate_pipeline.py --docket EPA-HQ-OAR-2020-0430
```

If a docket has no committed gold set yet, Phase 9 still writes an `eval_report.json` stub with `status: "not_available"`.

## Verified Commands

Backend verification:

```bash
python -m unittest test_phase5.py test_phase8.py test_evaluate.py test_cluster_comments.py test_change_cards.py test_label_clusters.py test_publish_site_snapshot.py test_refresh_site_snapshot.py test_docs_acceptance.py test_ollama_runtime.py test_gold_set_workflow.py -v
```

Frontend verification:

```bash
cd site_app
npm test
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

## Local-Only Working Docs

Planner handoff notes, phase specs, and local implementation trackers are intentionally kept out of GitHub. That includes `PROJECT_STATUS.md` and `PHASE*_SPEC.md`.

## Roadmap

See `BLUEPRINT.md` for the broader roadmap, future-phase constraints, and the Phase 10 architecture decision that keeps the product local, static, and artifact-driven.
