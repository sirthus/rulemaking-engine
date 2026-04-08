# Snapshot Site

This is the static read-only V2 insight surface for the rulemaking-engine published snapshot.

## What it reads

The app reads only from:

- `/site_data/current/manifest.json`
- `/site_data/current/dockets/index.json`
- `/site_data/current/dockets/{docket_id}/report.json`
- `/site_data/current/dockets/{docket_id}/eval_report.json`
- `/site_data/current/dockets/{docket_id}/insight_report.json`

It does not read directly from `corpus/` or `outputs/`, and it does not call any model runtime.

## Local usage

From the repo root:

```bash
python publish_site_snapshot.py
```

Then from this directory:

```bash
npm install
npm test
npm run build
npm run dev
```

Optional production preview:

```bash
npm run preview
```

## Dev/build behavior

- In dev, Vite serves the published snapshot from the repo’s `site_data/current/`.
- In production builds, the snapshot is copied into `dist/site_data/current/`.
- The loader includes a compatibility shim for earlier published V1 snapshot payloads, but the preferred path is always to regenerate the current V2 snapshot.

## Routes

- `/`
- `/dockets/:docketId`
- `/dockets/:docketId/cards/:cardId`
