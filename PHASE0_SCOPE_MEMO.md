# Phase 0 Scope Memo

This memo closes Phase 0 for the rulemaking-engine project. The Phase 0 outcome is a locked V1 starter set of EPA dockets that fit the current constraints: one agency, a small docket set, one coherent proposed-rule/final-rule comparison per docket, and substantive inline comment text available without attachment parsing.

## Selected V1 Dockets

- `EPA-HQ-OAR-2020-0272` — Revised Cross-State Air Pollution Rule Update for the 2008 Ozone NAAQS
- `EPA-HQ-OAR-2018-0225` — Determination Regarding Good Neighbor Obligations for the 2008 Ozone NAAQS
- `EPA-HQ-OAR-2020-0430` — Primary Copper Smelting National Emission Standards for Hazardous Air Pollutants Reviews (Subparts QQQ and EEEEEE)

## Explicit Non-Goals

- No architecture expansion beyond the standalone feasibility artifact
- No UI or frontend planning
- No pipeline buildout
- No broader data model or reusable framework work
- No cross-agency expansion
- No eCFR integration
- No OCR or attachment parsing
- No analysis that depends on PDF-only or attachment-only comment text

## Rejected Dockets Rationale

The originally shortlisted dockets `EPA-HQ-OAR-2021-0324`, `EPA-HQ-OAR-2021-0427`, and `EPA-HQ-OAR-2009-0734` were dropped because they did not satisfy the V1 inline-comment requirement: sampled Regulations.gov comment payloads were attachment-pointer-only or, after deeper sampling, contained no visible inline text that could support the intended analysis without attachment parsing. The replacement candidate `EPA-HQ-OAR-2003-0062` was also rejected because manual Federal Register review showed it to be an umbrella docket with multiple distinct substantive rulemaking threads rather than one clean proposed-rule/final-rule pair. Together, those issues made the dropped dockets poor fits for the locked V1 scope even when parts of the data were technically retrievable.
