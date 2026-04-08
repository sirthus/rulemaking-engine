# Rulemaking Engine V2 Blueprint

## Summary

V2 turns the current artifact substrate into an insight-first analyst system. The goal is no longer "prove the pipeline exists," but "help a user understand the rulemaking story": what changed, what commenters emphasized, where final text appears aligned with comment themes, and what evidence supports that interpretation.

AI-blind gold sets are accepted as the V2 evaluation baseline. Human-blind annotation is no longer a blocker.

Status note, 2026-04-07: V2 phases are implemented locally. The next planned product pass is V2.5, a frontend UI modernization pass to make the static React site come across as a clean, modern analyst UI while preserving the local-first, read-only architecture.

## Product Goal

Build a static, local-first rulemaking intelligence surface that lets a user quickly answer:

- What changed between the proposed and final rule?
- Which changes matter most?
- What public comment themes were raised?
- Which themes appear related or aligned with final-rule changes?
- What evidence supports each relationship?
- Where should an analyst inspect the underlying artifacts?

V2 must continue to avoid causal claims. It should say "related," "aligned," "appears responsive," or "no clear relationship," not "caused."

## Architecture

- Keep the current artifact-first pipeline.
- Keep all LLM work as local batch generation through Codex.
- Add an insight artifact layer between `outputs/` and `site_data/`.
- Keep the React site static and read-only.
- The site continues to read only from `site_data/current/`.
- No backend service, SSR, browser inference, cloud model API, or chat interface.

## Core V2 Additions

- Add `generate_insights.py`.
  - Inputs: per-docket `report.json`, `eval_report.json`, and existing card/cluster evidence.
  - Output: `outputs/{docket_id}/insight_report.json`.
  - Uses grounded evidence selection plus Codex synthesis when possible.
  - Records model profile, prompt version, token totals, generation time, and source artifact paths.

- Add `insight_report.json` v1.
  - `executive_summary`: short grounded docket summary.
  - `top_findings`: ranked findings with title, summary, why it matters, evidence notes, card IDs, and cluster IDs.
  - `rule_story`: structured sections for what changed, what commenters emphasized, where final text aligned, and caveats.
  - `priority_cards`: ranked change cards with score and feature breakdown.
  - Hard language rule: no causal phrasing.

- Extend publishing.
  - Copy `insight_report.json` into `site_data/current/dockets/{docket_id}/`.
  - Add `insight_report_path` and insight availability to the docket index.
  - Update the publish flow to run Codex labeling handoff, outputs, evaluation, insights, then publish.

- Upgrade the React site.
  - Home page becomes a docket story launcher, not just a snapshot index.
  - Docket page opens with insight summary, top findings, and ranked priority cards.
  - Raw clusters/cards remain available as inspection layers.
  - Card detail explains why the card matters and links back to findings, clusters, preamble links, and source snippets.

## Execution Phases

These phases are intentionally light scaffolding. Claude Code should do a deeper planning pass inside each phase before implementation.

1. Insight Artifact MVP
   - Add `generate_insights.py` and `insight_report.json` v1.
   - Start with grounded evidence selection and Codex-written summaries from existing `report.json` and `eval_report.json`.
   - Use Codex synthesis where it improves analyst-facing language while preserving evidence traceability.
   - Add Python tests for schema shape, ranking behavior, missing evidence, provenance, and banned causal language.

2. Publishing and Refresh Integration
   - Publish `insight_report.json` into `site_data/current/dockets/{docket_id}/`.
   - Add `insight_report_path` and insight availability to docket index entries.
   - Update refresh flow order: labels, outputs, evaluation, insights, publish.
   - Extend publish and refresh tests for present and missing insight artifacts.

3. React Insight Surface
   - Add frontend types and loader support for insight reports.
   - Make the docket page open with executive summary, top findings, and ranked priority cards.
   - Keep raw clusters and change cards available as inspection layers.
   - Add missing-insight fallback UI so V1-style snapshots still render.

4. Evidence Drilldown
   - Upgrade card detail pages to explain why a card matters.
   - Link findings back to card IDs, cluster IDs, preamble links, and source snippets.
   - Preserve the "related/aligned/appears responsive" language discipline and avoid causal claims.

5. End-to-End Quality Pass
   - Run the full local pipeline on all three dockets.
   - Confirm all three publish insight reports and evaluation remains available.
   - Run backend tests, frontend tests, build, and `git diff --check`.
   - Update `PROJECT_STATUS.md` with the completed phase and next recommended phase.

## Agent Workflow

- Codex implements and runs tests.
- Claude Code reviews each slice.
- `PROJECT_STATUS.md` remains the handoff log.
- Claude review prompts should check:
  - no causal language
  - no backend/live inference
  - site reads only from `site_data/current/`
  - summaries are grounded in existing evidence
  - new artifacts are reproducible and versioned

## Test Plan

- Python:
  - Add `test_generate_insights.py`.
  - Cover ranking behavior, schema shape, missing-evidence fallbacks, no-causal-language checks, and token/provenance metadata.
  - Update publish/refresh tests for insight artifact handling.
  - Run `python -m unittest -v`.

- Frontend:
  - Add loader/model tests for insight reports.
  - Update app tests for home, docket, missing-insight fallback, and card detail evidence paths.
  - Run `npm test`.
  - Run `npm run build`.

- End-to-end:
  - Run `python generate_outputs.py --force`.
  - Run `python evaluate_pipeline.py`.
  - Run `python generate_insights.py`.
  - Run `python publish_site_snapshot.py`.
  - Confirm all three dockets publish `insight_report.json`.
  - Confirm each docket page starts with useful narrative insight and links to evidence.
  - Run `git diff --check`.

## Assumptions

- AI-blind gold sets are sufficient for V2 evaluation.
- V2 is an insight product, not a benchmark paper or public marketing site.
- The current three-docket EPA scope remains the V2 scope.
- Codex is the LLM runtime.
- Ollama should not be used or reintroduced for product workflow labeling.
- V2 succeeds when the site feels like a useful analyst system, not merely a viewer for pipeline artifacts.
