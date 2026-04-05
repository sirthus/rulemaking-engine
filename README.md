# Rulemaking Evolution and Comment Impact Engine

Traceable rule-evolution analysis plus cautious comment-theme alignment for public rulemaking dockets.

## Overview

This repository analyzes how EPA rules change from proposed to final form and how public comment themes may relate to those changed sections. The system is designed to stay evidence-backed and conservative: it does not claim that comments "caused" a rule change. The core implemented pipeline through Phase 6 is deterministic, and the optional Phase 7 labeling helper uses an LLM only to name and summarize already-built theme clusters.

## Current Status

The repository has completed deterministic work through Phase 6 for a locked three-docket EPA starter set:

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

The checked-in corpus currently includes:

- fetched proposed/final rule text plus comment data
- section alignment outputs
- change-card artifacts for changed sections
- deduplicated comment-family artifacts
- deterministic comment-theme clustering outputs

`BLUEPRINT.md` remains the long-range roadmap and product vision document. It is not a line-by-line description of the current implementation state.

## Implemented Workflow

The current public repo contains these executable pipeline stages:

- [`fetch_corpus.py`](fetch_corpus.py): fetch Federal Register rule text and Regulations.gov comment data into the local corpus
- [`align_corpus.py`](align_corpus.py): normalize and align proposed/final rule sections, producing per-docket alignment artifacts
- [`cluster_comments.py`](cluster_comments.py): build deterministic theme clusters from the comment corpus and existing per-docket artifacts
- [`label_clusters.py`](label_clusters.py): optionally label existing theme clusters with short names and one-sentence descriptions using an Anthropic-compatible API

The corpus also contains generated outputs from the intermediate deterministic phases, including change-card and comment-dedup artifacts. If Phase 7 labeling is run, `comment_themes.json` is enriched with labels and descriptions, and `label_audit.json` can be generated for token and cost estimation.

## Data Products Under `corpus/`

Each docket directory under `corpus/` contains a deterministic working set such as:

- `proposed_rule.json` and `final_rule.json`
- `comments.json`
- `section_alignment.json` and `alignment_log.json`
- `comment_dedup.json`
- `change_cards.json`
- `change_cards_report.txt`
- `comment_themes.json`
- `label_audit.json` when Phase 7 audit mode is run

For example, the current corpus contains all of the files above for:

- `corpus/EPA-HQ-OAR-2020-0272`
- `corpus/EPA-HQ-OAR-2018-0225`
- `corpus/EPA-HQ-OAR-2020-0430`

## Quick Start

Install the deterministic pipeline dependency:

```bash
pip install requests
```

Install the optional Phase 7 labeling dependency if you want cluster labels:

```bash
pip install anthropic
```

Set a Regulations.gov API key:

```bash
export REGULATIONS_GOV_API_KEY=your_key_here
```

Run the currently checked-in deterministic stages:

```bash
python3 fetch_corpus.py
python3 align_corpus.py
python3 cluster_comments.py
```

Federal Register access does not require an API key. Regulations.gov does.

If you want optional Phase 7 labeling, set an Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Then estimate token and cost usage or apply labels:

```bash
python3 label_clusters.py --audit
python3 label_clusters.py
```

You can also point the labeler at a local Anthropic-compatible endpoint with `--base-url`.

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
- no frontend or chat product
- no causal claim that comments determined a rule change

## Local-Only Workflow Docs

Planner handoff and implementation-tracking files are intentionally kept local and out of GitHub. That includes phase specs, status handoff notes, and similar working documents used during agent collaboration.

## Roadmap

Later phases may add richer theme-to-change integration beyond the current cautious labeling helper. For the broader roadmap, scope discipline, and future-phase intent, see [`BLUEPRINT.md`](BLUEPRINT.md).
