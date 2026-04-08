Rulemaking Engine V1 Blueprint
------------------------------

Status note

This is the V1 blueprint. V1 built the local, artifact-first substrate: corpus artifacts, change cards, comment clusters, evaluation plumbing, published snapshots, and a read-only React snapshot site.

V2 planning now lives in `V2_BLUEPRINT.md`. V2 accepts AI-blind gold sets as the evaluation baseline and focuses on turning this substrate into an insight-first analyst system.

Product goal



Build an open-source system that:



ingests a proposed rule and final rule

aligns their text structure and identifies substantive changes

ingests the public comments

groups comments into deduplicated argument clusters

maps those clusters to changed sections with evidence-backed, cautious relationship signals



The product is not “AI determines which comments caused the rule change.”

The product is traceable rule evolution plus comment-theme alignment.

Current implemented state as of 2026-04-06



The repo is implemented through Phase 10.



The current product shape is:



deterministic local pipeline stages build `corpus/` artifacts

Phase 7 cluster labeling runs via Codex

operator review artifacts are written under `outputs/`

site-safe JSON snapshots are published under `site_data/current/`

a static React app under `site_app/` reads only from `site_data/current/`

there is no live model API, backend web application, SSR requirement, or browser-side inference in the V1 product path



The active cross-machine handoff docs are:



`PROJECT_STATUS.md`

`BLUEPRINT.md`

`V2_BLUEPRINT.md`

`README.md`

`CLAUDE.md`



Immediate next blueprint work



The V1 blueprint is complete through Phase 10. The next blueprint work is V2 insight-product work in `V2_BLUEPRINT.md`, not further V1 architecture.



AI-blind gold sets are accepted as sufficient for the V2 evaluation baseline.

Human-blind annotation remains a possible future quality upgrade, but it is not a blocker for V2.

Rerun evaluation and `refresh_site_snapshot.py --model qwen3:14b` after gold-set updates.

Verify the React site against the refreshed multi-docket snapshot.

The next substantive product work is richer relationship ranking, evidence-grounded explanation, and a site experience that surfaces the rulemaking story.



Expected current evaluation state



AI-blind gold sets are accepted as the V2 evaluation baseline for the V1 docket set.



After all three top-level `gold_set/{docket_id}.json` files are committed and evaluation is rerun, all three dockets should publish `eval_report.json` with `status: "available"`.



Core scope discipline

V1 operating scope



Lock V1 to:



one agency

3–5 dockets

one proposed rule + one final rule per docket

comments only from the main text body

no OCR pipeline

no eCFR integration

no chat interface

no backend web application or live model-backed frontend

Schema vs operational scope



The schema may support future complexity. The implementation must not.



That means:



schema may support multiple document versions

V1 pipeline only supports proposed → final

Phase 0 — Scope lock and feasibility spike

Goal



Choose a starter scope that is narrow, viable, and analytically interesting.



Docket selection criteria



Pick candidate dockets where:



both proposed and final rule text are available in machine-usable form

comment text is retrievable through the API

comment volume is manageable

the final rule preamble meaningfully discusses comments

there are real textual changes between proposed and final versions

document structure is usable enough for segmentation

Feasibility spike



Before committing to the docket set, build a throwaway script that:



pulls proposed and final text for candidate dockets

confirms comments are retrievable

checks rough comment count

verifies text segmentation is possible

confirms preamble/comment discussion exists in usable form

API key note

Regulations.gov requires a free API key from api.data.gov

Federal Register does not require an API key

authentication or authorization failures from Regulations.gov must be recorded separately from true data absence

missing or invalid Regulations.gov credentials must not be interpreted as meaning a docket has no comment text

Deliverables

shortlist of candidate dockets

one-page scope memo

selected 3–5 dockets

explicit non-goals list

Non-goals at this stage

no architecture expansion

no UI planning

no cross-agency ambition

no eCFR work

Phase 0.5 — API integration spike

Goal



Validate the external data sources before building the actual pipeline.



Verify

Federal Register access for full rule text

Regulations.gov access for comment text and metadata

rate-limit behavior

required caching behavior

file/attachment metadata shape

whether a valid Regulations.gov API key is available before treating comment-retrieval checks as conclusive

Deliverable



A short integration note with:



working endpoints

request patterns

error handling notes

rate limit assumptions

confirmed data gaps

authentication status notes for Regulations.gov

Phase 1 — Rule evolution backbone

Goal



Make a useful standalone rule-diff system before touching influence analysis.



Core capabilities



Given a proposed and final rule, the system should produce:



normalized document structure

section/chunk alignment

change classification

evidence traces to source text

Data model



Core entities:



Docket

RuleDocument

RuleVersion

DocumentChunk

ChunkAlignment

ChangeRecord

EvidenceSpan

ProcessingRun

Attachment

Comment

CommentCluster



Notes:



RuleVersion supports future extensions, but V1 uses only proposed and final

DocumentChunk is more robust than assuming perfect section trees

preserve original structural markers from source text

ProcessingRun records model/prompt/version/run metadata for every pipeline stage

Representation strategy



Do not assume all rules can be represented as:



document → section → subsection → paragraph



Instead:



parse headings and structural markers where present

normalize into chunks

preserve source numbering and headings

fall back to paragraph-level chunking when structure is weak

Alignment strategy



Use a hybrid approach:



structural/heading/number matching where possible

text/embedding similarity for unmatched chunks

confidence scoring on every alignment

uncertain cases remain flagged for manual inspection

Change classification



For aligned chunks, classify changes such as:



no meaningful change

wording clarification

definition changed

scope expanded

scope narrowed

exception added

requirement added

requirement removed

timing/compliance changed

procedure/enforcement changed

Deliverable



A rule-diff engine that is useful without comment analysis.



Definition of done



A user can review a docket and see:



what changed

where it changed

what kind of change it was

the source text supporting that conclusion

Phase 1.5 — Token and cost audit

Goal



Get a real cost baseline before further LLM-heavy work.



Requirement



Before starting the first milestone that depends materially on LLM output, run the pipeline on one docket with logging that records:



total input tokens per stage

total output tokens per stage

number of calls per stage

prompt type used

model used

cached vs uncached calls

Deliverable



A simple cost audit note showing:



tokens in/out by stage

which stages are cheap vs expensive

projected cost per docket

where batching/caching is required



This is mandatory. No hand-wavy estimates.



Phase 2 — Comment corpus engine

Goal



Turn raw comments into structured arguments without overreaching.



Comment ingestion



Store:



comment ID

submitter metadata

organization if present

date

main text

attachment metadata

source identifiers



Do not parse attachment content yet.



Deduplication strategy



Use two passes:



Pass 1 — fast dedup



Use normalization plus hash/simhash/MinHash-style methods for:



exact duplicates

near-exact duplicates

obvious form letters

Pass 2 — semantic grouping



On remaining distinct comments, use semantic methods to detect:



lightly modified campaigns

strongly similar argument variants

Commenter labeling



Keep labels simple:



individual

business

trade association

NGO / advocacy

academic

government / official

unknown

Theme extraction



Do not start with a fixed taxonomy.



Instead:



cluster comments unsupervised or semi-supervised

generate human-readable labels after clustering

allow optional later mapping to a taxonomy



Example themes may emerge such as cost, feasibility, timing, scope, scientific concerns, implementation, exemptions, legal authority, but these are examples only, not required categories.



Deliverable



A compact, traceable summary of the docket’s comment landscape.



Definition of done



A user can see:



unique argument clusters

major campaign families

representative comments

commenter mix

counts and evidence

Phase 3 — Change-to-comment mapping

Goal



Connect rule changes to relevant comment themes.



Core capability



For each changed chunk, identify likely related comment clusters.



Mapping method



For each changed chunk:



retrieve candidate comment clusters

score them by lexical, semantic, and citation/context overlap

keep top candidates

record evidence spans from both sides

Preamble linkage



Where possible, also link:



preamble discussion

response-to-comments language

rationale text

changed chunk



This is often the strongest bridge.



Output labels



Use cautious relationship labels such as:



related concern present in comments

same issue discussed in preamble

final text appears responsive to theme

no clear relationship found

ambiguous relationship



Do not use causal language.



Deliverable



A “change card” that shows:



changed text

related clusters

related preamble discussion

evidence spans

confidence

Phase 4 — Relationship signal layer

Goal



Add cautious synthesis, not causal claims.



Output style



Examples:



“This concern was frequently raised and related text changed in the final rule.”

“The agency discussed this issue in the preamble and revised nearby language.”

“This theme appears aligned with the final revision.”

“No visible textual response detected.”

Scoring features



Use interpretable features such as:



cluster size after deduplication

diversity of commenter types

semantic closeness to changed chunk

overlap with preamble discussion

direct issue-term overlap

whether the change appears to address the concern

Output

low / medium / high alignment

feature breakdown

linked evidence



No single opaque magic score.



Human review scope cap

Purpose



Support lightweight validation without building a workflow application.



V1 implementation only



Human review in V1 is limited to:



a review\_status field on key records such as:

alignments

change classifications

section-cluster links

allowed values:

pending

confirmed

rejected

a simple way to filter records by review\_status



That is all.



Explicit non-goals

no review dashboard

no assignment system

no queues with ownership

no notifications

no approvals workflow

no workflow engine



This is a data flag plus filtering, not a product subsystem.



Evaluation plan

Gold set



Create a small hand-labeled set using 3–5 dockets.



For at least 2 dockets, label:

all meaningful chunk alignments

major change types

major comment clusters

obvious changed-chunk ↔ cluster relationships

Label format



Keep it simple. Use spreadsheet or JSON with fields like:



proposed\_chunk\_id

final\_chunk\_id

alignment\_label

change\_type

comment\_cluster\_label

linked\_cluster\_ids

reviewer\_notes



Create labels before reviewing system output where possible.



Metrics by phase

Phase 1

alignment precision/recall

confidence calibration on alignments

change-classification agreement

Phase 2

exact/near-duplicate detection quality

cluster coherence

commenter-label precision on a small sample

Phase 3



For each changed chunk, take system top-3 suggested clusters and have a reviewer mark:



relevant

partially relevant

not relevant



Report:



precision@3

top-1 relevance rate

Phase 4



Evaluate whether the stated alignment signal is supported by visible evidence.



Pipeline stage computation map



You asked for this to be explicit. It should be.



Stage	Primary method

API ingestion	deterministic code

text normalization	deterministic code

chunk extraction	deterministic code + heuristics

structural alignment	deterministic rules

fallback semantic alignment	local embeddings and/or local batch LLM assistance

change classification	local batch LLM-assisted or hybrid

exact/near dedup	deterministic hashing/similarity

semantic dedup of remainder	local embeddings

cluster labeling/summarization	local batch LLM

change-to-cluster ranking	hybrid retrieval + local semantic scoring

relationship signal explanation	local batch LLM with structured evidence inputs

Local batch LLM policy



For V1, all LLM-dependent stages should run offline in local batches and write durable artifacts back into the corpus/output pipeline. There should be no live model API in the product path. The intended operating model is:



run deterministic ingestion and analysis locally

run Codex batch jobs for the LLM-dependent stages

persist the results as versioned artifacts

publish a clean JSON snapshot for the future site to read



The future site should consume published snapshot data, not invoke a model directly.



Phase 10 — Static React snapshot site and blind evaluation workflow

Goal



Turn the local pipeline into a usable local product surface without changing the core architecture.



Status



Implemented as of 2026-04-06.



The remaining Phase 10 follow-through is to keep evaluation artifacts refreshed from the accepted AI-blind gold sets. Human-blind annotation is no longer a blocker for V2.



Phase 10 scope



Allow a static React site after the snapshot contract is stable.



The site must:



read only from `site_data/current/`

remain read-only in the browser

have no backend service

have no server-side rendering requirement

have no live model calls

In local development and static builds, the published snapshot may be served or copied alongside the React assets, but it must remain the same snapshot contract and not become a backend API layer.



Initial routes:



`/`

`/dockets/:docketId`

`/dockets/:docketId/cards/:cardId`



Site responsibilities:



show docket summaries

show cluster labels and descriptions

show change cards with simple client-side filters

show evaluation available vs not available state

deep-link to individual change cards



Not in scope for Phase 10 site:



no in-browser editing of `review_status`

no reviewer login

no persistence layer

no live inference tools



LLM operator hardening



Implemented in Phase 10:



shared model profiles for validated local models

release summaries that record model profile, token totals, and publish metadata



Blind evaluation workflow



Implemented in Phase 10:



blinded annotation packet generation from published snapshot data plus source artifacts

editable gold-set templates

gold-set validation before evaluation

evaluation provenance describing whether a gold set is seed-derived, AI-blind, or blind human annotation



This remains an annotation workflow rather than a live model feature. The repo supports the mechanics and provenance tracking; V2 accepts AI-blind annotations as sufficient.



Remaining evaluation work after Phase 10:



commit the AI-blind gold sets for `EPA-HQ-OAR-2018-0225` and `EPA-HQ-OAR-2020-0430`

keep the `EPA-HQ-OAR-2020-0272` AI-blind gold set as the V2 baseline

rerun evaluation and refresh the published snapshot after each gold-set update



Implementation note



The static React site should be tolerant of published snapshot evolution within the declared `schema_version` boundary. Narrow compatibility shims are acceptable for legacy V1 snapshot payloads, but the main operator path should still refresh and republish the latest snapshot rather than relying on compatibility indefinitely.



Required rule



Every LLM-dependent stage must:



log prompt version

log model version

log token usage

support caching

attach outputs to ProcessingRun where a formal ProcessingRun record exists; until that model exists, write explicit stage run artifacts such as `label_run.json` and `release_summary.json`

Milestone sequence

Milestone 0



Scope memo + feasibility spike



Done when:



candidate dockets evaluated

selected docket set locked

non-goals written

Milestone 0.5



API integration spike



Done when:



source APIs confirmed usable

rate-limit and caching notes captured

Regulations.gov authentication status clearly verified

Milestone 1



Ingest and normalize 3 dockets



Done when:



proposed/final texts stored

comments stored

chunk extraction works

Milestone 2



Alignment + change cards



Done when:



hybrid alignment works

changed chunks identified

evidence spans visible

review\_status exists and can be filtered

Milestone 3



Deduplication pipeline



Done when:



duplicate/form-letter families identified

semantic dedup pass works on remainder

representative comments selected

Milestone 4



Theme clustering



Done when:



major themes extracted

cluster labels generated

cluster evidence and counts visible

Milestone 5



Token/cost audit



Done when:



one docket processed end-to-end with token logs

stage-by-stage token and cost numbers recorded

Milestone 6



Changed-chunk ↔ cluster mapping



Done when:



top related clusters shown per changed chunk

preamble linkage included where available

precision@3 can be measured

Milestone 7



Relationship signals



Done when:



low/medium/high alignment labels work

evidence trace is visible

no causal language appears

Milestone 8



Outputs and usability



Include only:



JSON export

CSV export

static HTML report or very simple local review page

published JSON snapshot for the site



Not a full frontend.



Milestone 10



Static React snapshot site + blind evaluation workflow



Status:



Implemented as of 2026-04-06.



Done when:



the React site reads only from `site_data/current/`

the site supports docket list, docket detail, and card detail routes

the site exposes read-only filters for change cards and clusters

model-profile behavior is shared across the local operator flow

release summaries are written into published snapshots

gold-set packets and validation tooling exist for blind annotation work



Remaining after Milestone 10:



commit AI-blind gold sets for `EPA-HQ-OAR-2018-0225` and `EPA-HQ-OAR-2020-0430`

keep the `EPA-HQ-OAR-2020-0272` AI-blind gold set as the V2 baseline

evaluation refresh and published snapshot refresh after the gold-set baseline is committed



Claude Code implementation guardrails

Required instructions



Tell Claude Code:



build a monolith

favor direct API calls

favor concrete implementations over abstractions

keep the first useful interface to CLI + reports

optimize for traceability and reproducibility

Explicit prohibitions



Tell Claude Code not to generate:

React frontend in early milestones before the snapshot contract is stable

LangChain, LlamaIndex, or orchestration frameworks

abstract plugin systems

Docker/Kubernetes before local end-to-end success

chat interface

“chat with regulations” feature

speculative multi-agent architecture

premature microservices

Deferred features



These are explicitly out of scope for V1:



eCFR integration

attachment OCR/parsing

multi-agency analytics

cross-docket benchmarking

predictive influence models

full document-version graphs beyond proposed/final execution path

rich review workflow

polished web application



Clarification



A static React snapshot viewer is allowed after Milestone 8 artifacts are stable. A polished or backend-driven web application remains deferred.

Recommended V1 slice



If you want the strongest credible first version, make V1 exactly this:



one agency

3 dockets

proposed/final ingestion

chunk extraction

hybrid alignment

change classification

comment ingestion

two-pass deduplication

unsupervised theme clustering

changed-chunk to cluster top-match display

review\_status flag + filter only

token/cost audit on one docket

JSON/CSV/static HTML output

published JSON snapshots under `site_data/current/`

static React snapshot site under `site_app/`

