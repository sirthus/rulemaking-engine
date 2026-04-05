# Rulemaking Evolution and Comment Impact Engine

Traceable rule-evolution analysis plus comment-theme alignment for public rulemaking dockets.

## Overview

This project is intended to help analyze how a rule changes from proposed to final form and how public comment themes relate to those changes. The planned workflow is to ingest proposed and final rules, align their structure, identify substantive changes, ingest public comments, cluster those comments into argument themes, and map those themes to changed sections with cautious, evidence-backed relationship signals.

This is not a system that claims to determine which comments "caused" a rule change. The goal is traceable rule evolution plus comment-theme alignment.

## Current status

Phase 0 is closed, Phase 0.5 integration validation is complete, and Phase 1 corpus fetch is complete. The repository now contains standalone spikes for feasibility and API-integration measurement, a locked three-docket EPA V1 starter set, and a completed corpus-fetch script that pulls Federal Register source text plus full Regulations.gov comment details into a local working corpus.

## Planned scope

The intended V1 scope is deliberately narrow:

- one agency
- 3–5 dockets
- one proposed rule and one final rule per docket
- comments only from the main text body

The currently accepted starter set is:

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

For the full roadmap, scope discipline, phase breakdown, and implementation guardrails, see [BLUEPRINT.md](/mnt/c/Users/dalli/github/rulemaking-engine/BLUEPRINT.md).

## What is in this repo today

- [BLUEPRINT.md](/mnt/c/Users/dalli/github/rulemaking-engine/BLUEPRINT.md): detailed project blueprint, roadmap, and scope rules
- [PHASE0_SCOPE_MEMO.md](/mnt/c/Users/dalli/github/rulemaking-engine/PHASE0_SCOPE_MEMO.md): short memo that closes Phase 0 and records the selected V1 dockets plus non-goals
- [PHASE1_SPEC.md](/mnt/c/Users/dalli/github/rulemaking-engine/PHASE1_SPEC.md): Phase 1 implementation spec for corpus fetch and cache behavior
- [feasibility_spike.py](/mnt/c/Users/dalli/github/rulemaking-engine/feasibility_spike.py): standalone Phase 0 feasibility script for docket and source validation
- [api_integration_spike.py](/mnt/c/Users/dalli/github/rulemaking-engine/api_integration_spike.py): standalone Phase 0.5 integration script for endpoint, timing, and retrieval-pattern measurement
- [fetch_corpus.py](/mnt/c/Users/dalli/github/rulemaking-engine/fetch_corpus.py): standalone Phase 1 script that fetches and parses FR source documents and retrieves full comment detail for the accepted dockets
- [INTEGRATION_NOTE.md](/mnt/c/Users/dalli/github/rulemaking-engine/INTEGRATION_NOTE.md): generated integration gate document for Phase 1
- [integration_spike_results.json](/mnt/c/Users/dalli/github/rulemaking-engine/integration_spike_results.json): machine-readable output from the integration spike
- [feasibility_results.json](/mnt/c/Users/dalli/github/rulemaking-engine/feasibility_results.json): earlier feasibility-spike output retained as a historical artifact

## Quick start

Install the current dependency:

```bash
pip install requests
```

Set a Regulations.gov API key:

```bash
export REGULATIONS_GOV_API_KEY=your_key_here
```

Run the feasibility spike:

```bash
python3 feasibility_spike.py
```

Run the integration spike:

```bash
python3 api_integration_spike.py
```

Run the Phase 1 corpus fetch:

```bash
python3 fetch_corpus.py
```

Federal Register access does not require an API key. Regulations.gov checks do.

## Non-goals right now

- no frontend application
- no pipeline implementation yet
- no cross-agency scope
- no OCR or eCFR work
- no attachment parsing

## Learn more

Start with [BLUEPRINT.md](/mnt/c/Users/dalli/github/rulemaking-engine/BLUEPRINT.md) for the full product rationale, phase plan, milestones, and guardrails. For the locked scope and completed pre-Phase-2 artifacts, see [PHASE0_SCOPE_MEMO.md](/mnt/c/Users/dalli/github/rulemaking-engine/PHASE0_SCOPE_MEMO.md), [INTEGRATION_NOTE.md](/mnt/c/Users/dalli/github/rulemaking-engine/INTEGRATION_NOTE.md), and [PHASE1_SPEC.md](/mnt/c/Users/dalli/github/rulemaking-engine/PHASE1_SPEC.md).
