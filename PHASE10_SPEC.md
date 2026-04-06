# Phase 10 Spec

Local-only Phase 10 implementation contract.

## Goals

- static React site under `site_app/`
- shared Ollama model profiles and preflight
- richer published snapshot contract for the site
- blind gold-set packet generation and validation

## Constraints

- no backend service
- no SSR requirement
- no live model calls from the browser
- site reads only from `site_data/current/`
- browser remains read-only in V1

## Supported local models

- `qwen3:14b`
  - accuracy-first default
  - recommended `no_think = true`
- `gemma3:12b-it-q8_0`
  - speed-first alternative
  - recommended `no_think = false`

`refresh_site_snapshot.py` should derive the `no_think` behavior from the resolved model profile rather than requiring operators to remember it manually.

## Snapshot contract

- `site_data/current/manifest.json`
- `site_data/current/release_summary.json`
- `site_data/current/dockets/index.json`
- `site_data/current/dockets/{docket_id}/report.json`
- `site_data/current/dockets/{docket_id}/eval_report.json`

All published JSON must declare `schema_version: "v1"`.

## Frontend expectations

- `site_app/` is a static React workspace
- Vite must serve `/site_data/current/...` in dev
- Vite builds must copy the published snapshot into `dist/site_data/current/`
- the frontend may normalize older V1 published snapshot payloads for compatibility, but the main operator path should still refresh and republish the current Phase 10 snapshot

## Blind evaluation workflow

- `prepare_gold_set_packet.py` writes blinded packets under `gold_set/packets/`
- `prepare_gold_set_packet.py` writes editable templates under `gold_set/templates/`
- completed reviewer gold sets continue to live under `gold_set/{docket_id}.json`
- `validate_gold_set.py` must pass before evaluation refresh

## Frontend routes

- `/`
- `/dockets/:docketId`
- `/dockets/:docketId/cards/:cardId`

## Verification

- backend: Phase 7 to Phase 10 Python unit suite
- frontend: `npm test`
- frontend: `npm run build`
