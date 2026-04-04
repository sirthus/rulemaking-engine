# Rulemaking Evolution and Comment Impact Engine

Traceable rule-evolution analysis plus comment-theme alignment for public rulemaking dockets.

## Overview

This project is intended to help analyze how a rule changes from proposed to final form and how public comment themes relate to those changes. The planned workflow is to ingest proposed and final rules, align their structure, identify substantive changes, ingest public comments, cluster those comments into argument themes, and map those themes to changed sections with cautious, evidence-backed relationship signals.

This is not a system that claims to determine which comments "caused" a rule change. The goal is traceable rule evolution plus comment-theme alignment.

## Current status

The repository is currently focused on Phase 0 feasibility validation. The implemented code is a standalone spike used to evaluate candidate EPA dockets, verify source accessibility, and confirm whether the basic inputs for the project appear workable before broader pipeline development begins.

## Planned scope

The intended V1 scope is deliberately narrow:

- one agency
- 3–5 dockets
- one proposed rule and one final rule per docket
- comments only from the main text body

For the full roadmap, scope discipline, phase breakdown, and implementation guardrails, see [BLUEPRINT.md](/mnt/c/Users/dalli/github/rulemaking-engine/BLUEPRINT.md).

## What is in this repo today

- [BLUEPRINT.md](/mnt/c/Users/dalli/github/rulemaking-engine/BLUEPRINT.md): detailed project blueprint, roadmap, and scope rules
- [feasibility_spike.py](/mnt/c/Users/dalli/github/rulemaking-engine/feasibility_spike.py): standalone Phase 0 feasibility script for docket and source validation
- [feasibility_results.json](/mnt/c/Users/dalli/github/rulemaking-engine/feasibility_results.json): latest generated output example from the feasibility spike

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

Federal Register access does not require an API key. Regulations.gov checks do.

## Non-goals right now

- no frontend application
- no pipeline buildout beyond the feasibility spike
- no cross-agency scope
- no OCR or eCFR work

## Learn more

Start with [BLUEPRINT.md](/mnt/c/Users/dalli/github/rulemaking-engine/BLUEPRINT.md) for the full product rationale, phase plan, milestones, and guardrails.
