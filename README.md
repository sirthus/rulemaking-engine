# Rulemaking Evolution and Comment Impact Engine

Traceable rule-evolution analysis plus cautious comment-theme alignment for public rulemaking dockets.

## Overview

This repository analyzes how EPA rules change from proposed to final form and how public comment themes may relate to those changed sections. The system is artifact-first and local-first:

- deterministic stages build corpus artifacts under `corpus/`
- local Ollama batch runs add Phase 7 cluster labels
- review artifacts are written under `outputs/`
- published site-safe JSON snapshots are written under `site_data/`

The product does not do live inference at request time, and it does not claim that comments "caused" a rule change.

## Current Status

The repository has completed the current V1 pipeline through Phase 9.1 for the locked three-docket EPA starter set:

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

`BLUEPRINT.md` remains the long-range roadmap and product vision document. It is not a line-by-line description of the current implementation state.

## Implemented Workflow

The current public repo contains these executable pipeline stages:

- [`fetch_corpus.py`](fetch_corpus.py): fetch Federal Register rule text and Regulations.gov comment data into the local corpus
- [`align_corpus.py`](align_corpus.py): normalize and align proposed/final rule sections, producing per-docket alignment artifacts
- [`dedup_comments.py`](dedup_comments.py): collapse exact and near-duplicate public comments into canonical families
- [`generate_change_cards.py`](generate_change_cards.py): generate change-card records with cautious relationship signals
- [`cluster_comments.py`](cluster_comments.py): build deterministic theme clusters from the comment corpus and existing per-docket artifacts
- [`label_clusters.py`](label_clusters.py): label existing theme clusters with a local Ollama model
- [`generate_outputs.py`](generate_outputs.py): consolidate per-docket artifacts into JSON, CSV, and static HTML review outputs under `outputs/`
- [`evaluate_pipeline.py`](evaluate_pipeline.py): evaluate pipeline outputs against committed per-docket gold sets and write evaluation reports
- [`publish_site_snapshot.py`](publish_site_snapshot.py): publish site-safe JSON snapshots under `site_data/releases/` and `site_data/current/`
- [`refresh_site_snapshot.py`](refresh_site_snapshot.py): run the post-clustering local refresh path in one command

Phase 7 now writes `label_run.json` with real local run provenance, including model, prompt version, token counts, durations, and per-cluster outcomes.

Phase 8 writes review-friendly exports under `outputs/{docket_id}/`:

- `report.json`
- `report.csv`
- `report.html`

Phase 9 writes evaluation artifacts under `outputs/{docket_id}/`:

- `eval_report.json`
- `eval_report.txt`

Published site snapshots live under `site_data/`:

- `site_data/current/manifest.json`
- `site_data/current/dockets/index.json`
- `site_data/current/dockets/{docket_id}/report.json`
- `site_data/current/dockets/{docket_id}/eval_report.json`

## Quick Start

Install the pipeline dependency:

```bash
pip install requests
```

Set a Regulations.gov API key:

```bash
export REGULATIONS_GOV_API_KEY=your_key_here
```

Run the deterministic pipeline stages:

```bash
python3 fetch_corpus.py
python3 align_corpus.py
python3 dedup_comments.py
python3 generate_change_cards.py
python3 cluster_comments.py
```

Federal Register access does not require an API key. Regulations.gov does.

## Local Ollama Labeling

Phase 7 is local-only. Start Ollama and pull one of the validated models:

```bash
ollama serve
ollama pull qwen3:14b
ollama pull gemma3:12b-it-q8_0
```

Recommended model defaults:

- Accuracy-first default: `qwen3:14b`
- Faster alternative: `gemma3:12b-it-q8_0`

Run local labeling:

```bash
python3 label_clusters.py --model qwen3:14b --no-think
```

Or label one docket:

```bash
python3 label_clusters.py --docket EPA-HQ-OAR-2020-0430 --model gemma3:12b-it-q8_0
```

`qwen3:14b` is the default operator model for this repo. `--no-think` is recommended for Qwen and is automatically applied by `refresh_site_snapshot.py` when the selected model name contains `qwen3`.

## Outputs vs Published Site Data

The repo now distinguishes between working outputs and published site inputs:

- `outputs/` is for operator review and local QA
- `site_data/` is for clean published JSON snapshots only

Use the review/export path when you want operator artifacts:

```bash
python3 generate_outputs.py
python3 evaluate_pipeline.py
```

Publish a site-safe snapshot from existing artifacts:

```bash
python3 publish_site_snapshot.py
```

Or run the full local refresh flow after clustering:

```bash
python3 refresh_site_snapshot.py --model qwen3:14b
```

That refresh flow:

1. labels clusters locally with Ollama
2. regenerates `report.json` / `report.csv` / `report.html`
3. regenerates `eval_report.json` when evaluation is enabled
4. publishes a clean JSON snapshot under `site_data/`

If a docket has no committed gold set yet, Phase 9 writes an `eval_report.json` stub with `status: "not_available"` so the published snapshot stays schema-complete without overstating evaluation coverage.

## Scope And Guardrails

The current V1 operating scope is intentionally narrow:

- one agency: EPA
- three dockets
- one proposed rule and one final rule per docket
- comments from the main text body only

Current non-goals:

- no attachment parsing
- no OCR pipeline
- no eCFR integration
- no live chat product
- no live model API in the product path
- no causal claim that comments determined a rule change

## Local-Only Workflow Docs

Planner handoff and implementation-tracking files are intentionally kept local and out of GitHub. That includes phase specs, status handoff notes, and similar working documents used during agent collaboration.

## Roadmap

Later phases may add richer theme-to-change integration beyond the current cautious labeling helper. For the broader roadmap, scope discipline, and future-phase intent, see [`BLUEPRINT.md`](BLUEPRINT.md).
