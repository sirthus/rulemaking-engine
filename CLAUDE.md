# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Coordination

This project uses `PROJECT_STATUS.md` as the tracked handoff between Claude Code and Codex. Read it before starting work. It records the current implementation state, accepted architecture decisions, active focus, and the next recommended task.

The old blueprint and phase spec files are retired. `PROJECT_STATUS.md` is the current source of truth for the next pass, with `README.md` covering quickstart/operator workflow.

## Current implementation state

As of 2026-04-08, the V2 insight system and UI overhaul are implemented locally. The operating architecture is now:

- local pipeline stages build corpus artifacts
- cluster labeling runs via Codex
- review and insight artifacts are generated under `outputs/`
- published site-safe JSON snapshots are generated under `site_data/`
- a static read-only V2 insight surface under `site_app/` reads only from `site_data/current/`
- Vite serves the published snapshot in local dev and copies it into production builds
- there is no live model API in the product runtime path
- the next planned work is refactor, performance, and a Showpiece README pass without changing the local-first architecture

## LLM runtime

Codex is used for cluster labeling and insight generation. Do not use or reintroduce Ollama as a product workflow dependency.

## Accepted docket set

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
python generate_outputs.py --force
python evaluate_pipeline.py
python generate_insights.py
python publish_site_snapshot.py
python prepare_gold_set_packet.py --docket EPA-HQ-OAR-2020-0430
python validate_gold_set.py --docket EPA-HQ-OAR-2020-0430 --path gold_set/EPA-HQ-OAR-2020-0430.json
```

Frontend workspace:

```bash
cd site_app
npm install
npm test
npm run build
npm run dev
```

Federal Register does not require an API key. Regulations.gov does. Missing or invalid Regulations.gov credentials must never be treated as proof that comment text is absent.

## Important architecture guardrails

- Keep the product artifact-first and local-first.
- Do not reintroduce cloud model configuration or remote model credentials into the product path.
- The site must read `site_data/current/...` JSON only.
- `outputs/` is for operator review artifacts, not for the live site data contract.
- `site_data/` is a publish boundary, not a source-of-truth code asset.
- The React site is static and read-only.
- AI-blind gold sets are accepted as the V2 evaluation baseline.
- Do not add a backend service, SSR requirement, or live inference backend.
- Small compatibility shims for older published V1 snapshot payloads are acceptable, but the normal operator path should always refresh and republish the latest snapshot.

## Coordination with Codex

Claude Code acts as planner/reviewer and Codex acts as implementer. When handing off work:

- keep requests concrete and scope-bounded
- prefer reviewing generated artifacts before asking for new implementation
- record architecture decisions or blockers in `PROJECT_STATUS.md`
