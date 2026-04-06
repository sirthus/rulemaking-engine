# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Coordination

This project uses `PROJECT_STATUS.md` as the live local handoff between Claude Code and Codex. Read it before starting work. It records the current implementation state, accepted architecture decisions, active blockers, and the next recommended task.

## Current implementation state

As of 2026-04-05, the repo is implemented through Phase 9.1. The operating architecture is now:

- deterministic pipeline stages build local corpus artifacts
- Phase 7 labeling runs only against a local Ollama daemon
- review artifacts are generated under `outputs/`
- published site-safe JSON snapshots are generated under `site_data/`
- there is no live model API in the product runtime path

## Supported local LLM runtime

Only Ollama is supported for product LLM work in V1.

Validated local models:

- default operator model: `qwen3:14b`
- faster alternative: `gemma3:12b-it-q8_0`

`qwen3:14b` should generally be run with `--no-think`. The refresh script applies that automatically for Qwen3 models.

## Accepted V1 docket set

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

## Main commands

```bash
pip install requests

export REGULATIONS_GOV_API_KEY=your_key_here

python fetch_corpus.py
python align_corpus.py
python dedup_comments.py
python generate_change_cards.py
python cluster_comments.py
python label_clusters.py --model qwen3:14b --no-think
python generate_outputs.py
python evaluate_pipeline.py
python publish_site_snapshot.py
python refresh_site_snapshot.py --model qwen3:14b
```

Federal Register does not require an API key. Regulations.gov does. Missing or invalid Regulations.gov credentials must never be treated as proof that comment text is absent.

## Important architecture guardrails

- Keep the product artifact-first and local-first.
- Do not reintroduce cloud model configuration or remote model credentials into the product path.
- The future site should read `site_data/current/...` JSON only.
- `outputs/` is for operator review artifacts, not for the live site data contract.
- `site_data/` is a publish boundary, not a source-of-truth code asset.
- No live chat interface, no live inference backend, and no speculative orchestration layer.

## Coordination with Codex

Claude Code acts as planner/reviewer and Codex acts as implementer. When handing off work:

- keep requests concrete and phase-bounded
- prefer reviewing generated artifacts before asking for new implementation
- record architecture decisions or blockers in `PROJECT_STATUS.md`
