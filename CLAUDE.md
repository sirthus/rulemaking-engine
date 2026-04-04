# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Coordination

This project uses `PROJECT_STATUS.md` as the live handoff between Claude Code and Codex. Read it before starting work. It records the current phase, accepted docket set, active blockers, next task, and done criteria.

## Current phase

This repository is currently at **Phase 0.5 — API integration spike**.

Phase 0 is closed:
- the V1 starter set is locked
- the Phase 0 scope memo exists

Phase 0.5 is complete:
- the integration spike exists
- the generated integration note exists
- the current readiness verdict is `go`

Do not jump ahead into Phase 1 pipeline implementation unless explicitly instructed.

## Accepted V1 docket set

- `EPA-HQ-OAR-2020-0272`
- `EPA-HQ-OAR-2018-0225`
- `EPA-HQ-OAR-2020-0430`

## Repo artifacts

- `feasibility_spike.py`
  Phase 0 feasibility spike for docket selection and source validation.
- `feasibility_results.json`
  Feasibility-spike output artifact.
- `PHASE0_SCOPE_MEMO.md`
  Phase 0 scope lock memo.
- `api_integration_spike.py`
  Phase 0.5 integration spike for endpoint, timing, and request-pattern measurement.
- `integration_spike_results.json`
  Machine-readable integration artifact.
- `INTEGRATION_NOTE.md`
  Generated gate document for Phase 1.

## Commands

```bash
pip install requests

export REGULATIONS_GOV_API_KEY=your_key_here

# Full feasibility check across the accepted V1 docket set
python feasibility_spike.py

# Full Phase 0.5 integration spike
python api_integration_spike.py
```

Federal Register does not require an API key. Regulations.gov does. Missing or invalid credentials must never be treated as proof that comment text is absent.

## Important integration behavior

### Federal Register

- Use `https://www.federalregister.gov/api/v1`
- Proposed/final rule discovery is done from the docket-level document listing
- Full text should use XML first and HTML only as fallback

### Regulations.gov

- Use `https://api.regulations.gov/v4`
- Document discovery uses `/documents?filter[docketId]=...`
- Comment retrieval uses `/comments?filter[commentOnId]=...`
- For these dockets, list payloads often return empty text fields
- The detail endpoint `/comments/{id}` is a required fallback when list payloads are empty

Do not collapse “list endpoint returned empty text” into “this docket has no inline comment text.”

## Guardrails

- No data model
- No repo scaffolding
- No pipeline components unless explicitly approved
- No UI work
- No cross-agency expansion
- No OCR or attachment parsing
- No later-phase architecture hidden inside the spikes

## Coordination with Codex

Claude Code acts as planner/reviewer and Codex acts as implementer. When handing off work:

- update `PROJECT_STATUS.md` with the current task and constraints
- keep requests concrete and phase-bounded
- prefer reviewing generated artifacts before asking for new implementation
