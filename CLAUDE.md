# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Coordination

This project uses `PROJECT_STATUS.md` as the tracked handoff between Claude Code and Codex. Read it before starting work. It records the current implementation state, accepted architecture decisions, active focus, and the next recommended task.

Use `BLUEPRINT.md` for the V1 substrate history and `V2_BLUEPRINT.md` for the next product plan. The old phase spec files have been retired.

## Current implementation state

As of 2026-04-07, the V1 substrate is implemented. The operating architecture is now:

- deterministic pipeline stages build local corpus artifacts
- cluster labeling runs only against a local Ollama daemon
- review artifacts are generated under `outputs/`
- published site-safe JSON snapshots are generated under `site_data/`
- a static React app under `site_app/` reads only from `site_data/current/`
- Vite serves the published snapshot in local dev and copies it into production builds
- there is no live model API in the product runtime path

## Supported local LLM runtime

Only Ollama is supported for product LLM work in V1 and planned V2 work.

Validated local model profiles:

- default operator model: `qwen3:14b`
- faster alternative: `gemma3:12b-it-q8_0`

`qwen3:14b` should generally be run with `--no-think` when calling `label_clusters.py` directly. `refresh_site_snapshot.py` resolves that behavior automatically through the shared model profile.

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
python refresh_site_snapshot.py --model qwen3:14b
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
- The React site is static and read-only in V1.
- AI-blind gold sets are accepted as the V2 evaluation baseline.
- Do not add a backend service, SSR requirement, or live inference backend.
- Small compatibility shims for older published V1 snapshot payloads are acceptable, but the normal operator path should always refresh and republish the latest snapshot.

## Coordination with Codex

Claude Code acts as planner/reviewer and Codex acts as implementer. When handing off work:

- keep requests concrete and scope-bounded
- prefer reviewing generated artifacts before asking for new implementation
- record architecture decisions or blockers in `PROJECT_STATUS.md`
