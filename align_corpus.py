#!/usr/bin/env python3

import hashlib
import json
import os
import re
import time
import unicodedata

from pipeline_utils import (
    STOPWORDS,
    atomic_write_json,
    normalize_heading,
    normalize_text,
    normalize_whitespace,
    print_line,
    read_json,
    utc_now_iso,
)


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")

DOCKET_MANIFEST = [
    {
        "docket_id": "EPA-HQ-OAR-2020-0272",
        "section_coverage_min": 60.0,
        "attribution_rate_min": 30.0,
    },
    {
        "docket_id": "EPA-HQ-OAR-2018-0225",
        "section_coverage_min": 60.0,
        "attribution_rate_min": 40.0,
    },
    {
        "docket_id": "EPA-HQ-OAR-2020-0430",
        "section_coverage_min": 60.0,
        "attribution_rate_min": 30.0,
    },
]

CONTENT_GROUPS = ("preamble_style", "reg_style")

OUTLINE_RANGE_RE = re.compile(
    r"\bSections?\s+([IVXivx]+(?:\.[A-Za-z0-9]+)*)\s*(?:through|to|-|–|and)\s*([IVXivx]+(?:\.[A-Za-z0-9]+)*)",
    re.IGNORECASE,
)
OUTLINE_RE = re.compile(r"\bSections?\s+([IVXivx]+(?:\.[A-Za-z0-9]+)*)", re.IGNORECASE)
CFR_SECTION_SIGN_RE = re.compile(r"(?:§|\xa7|&#167;|&sect;)\s*(\d+\.\d+)", re.IGNORECASE)
PLAIN_CFR_RE = re.compile(r"\bsection\s+(\d{2,}\.\d+)\b", re.IGNORECASE)
def heading_tokens(heading: str) -> set[str]:
    normalized = normalize_heading(heading, strip_outline_prefix=True)
    return {
        token
        for token in normalized.split()
        if len(token) >= 2 and token not in STOPWORDS
    }


def body_tokens(text: str, *, limit: int | None = None) -> set[str]:
    if limit is not None:
        text = (text or "")[:limit]
    text = normalize_text(text)
    return {
        token
        for token in re.findall(r"\b[a-z]{4,}\b", text)
        if token not in STOPWORDS
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def derive_content_group(section: dict) -> str:
    heading = section.get("heading") or ""
    source = section.get("source")
    if "§" in heading or "\xa7" in heading or source == "regulatory_text":
        return "reg_style"
    return "preamble_style"


def short_body_hash(text: str) -> str:
    body = normalize_text((text or "")[:4096])
    return hashlib.sha1(body.encode("utf-8")).hexdigest()


def body_text_changed(proposed_section: dict, final_section: dict) -> bool:
    return short_body_hash(proposed_section.get("body_text") or "") != short_body_hash(final_section.get("body_text") or "")


def enrich_sections(sections: list[dict]) -> list[dict]:
    enriched = []
    for index, section in enumerate(sections):
        enriched_section = dict(section)
        heading = enriched_section.get("heading") or ""
        enriched_section["_index"] = index
        enriched_section["_content_group"] = derive_content_group(enriched_section)
        enriched_section["_normalized_heading"] = normalize_heading(heading)
        enriched_section["_heading_tokens"] = heading_tokens(heading)
        enriched_section["_body_tokens_full"] = body_tokens(enriched_section.get("body_text") or "")
        enriched_section["_outline_citations"] = extract_outline_heading_keys(heading)
        enriched_section["_cfr_citations"] = extract_cfr_heading_keys(heading)
        enriched.append(enriched_section)
    return enriched


def extract_outline_heading_keys(heading: str) -> set[str]:
    heading = unicodedata.normalize("NFKC", heading or "").strip()
    results = set()
    match = re.match(r"^([IVXivx]+(?:\.[A-Za-z0-9]+)*)\b", heading)
    if match:
        results.add(match.group(1).lower())
    return results


def extract_cfr_heading_keys(heading: str) -> set[str]:
    return set(re.findall(r"\b\d{2,}\.\d+\b", unicodedata.normalize("NFKC", heading or "")))


def load_inputs(docket_id: str):
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    proposed = enrich_sections(read_json(os.path.join(base_dir, "proposed_rule.json")))
    final = enrich_sections(read_json(os.path.join(base_dir, "final_rule.json")))
    comments = read_json(os.path.join(base_dir, "comments.json"))
    return proposed, final, comments


def _body_keyword_assist(
    proposed_section: dict,
    candidate_sections: list[dict],
    available_section_ids: set[str],
) -> tuple[dict | None, float]:
    best_section = None
    best_score = 0.0
    proposed_tokens = proposed_section["_body_tokens_full"]
    if not proposed_tokens:
        return None, 0.0
    for candidate in candidate_sections:
        if candidate["section_id"] not in available_section_ids:
            continue
        candidate_tokens = candidate["_body_tokens_full"]
        overlap = len(proposed_tokens & candidate_tokens)
        score = overlap / len(proposed_tokens) if proposed_tokens else 0.0
        if score > best_score:
            best_score = score
            best_section = candidate
    if best_score >= 0.35:
        return best_section, best_score
    return None, 0.0


def align_sections(proposed_sections: list[dict], final_sections: list[dict]):
    final_by_group = {
        group: [section for section in final_sections if section["_content_group"] == group]
        for group in CONTENT_GROUPS
    }
    proposed_by_group = {
        group: [section for section in proposed_sections if section["_content_group"] == group]
        for group in CONTENT_GROUPS
    }
    matched_final_ids = set()
    alignments_by_proposed = {}
    remaining_final_ids_by_group = {
        group: {section["section_id"] for section in sections}
        for group, sections in final_by_group.items()
    }

    for group in CONTENT_GROUPS:
        heading_index = {}
        heading_offsets = {}
        for section in final_by_group[group]:
            normalized_heading = section["_normalized_heading"]
            if not normalized_heading:
                continue
            heading_index.setdefault(normalized_heading, []).append(section)
        for proposed_section in proposed_by_group[group]:
            normalized_heading = proposed_section["_normalized_heading"]
            if not normalized_heading:
                continue
            candidates = heading_index.get(normalized_heading, [])
            candidate_index = heading_offsets.get(normalized_heading, 0)
            while candidate_index < len(candidates) and candidates[candidate_index]["section_id"] in matched_final_ids:
                candidate_index += 1
            heading_offsets[normalized_heading] = candidate_index
            if candidate_index < len(candidates):
                matched_final = candidates[candidate_index]
                heading_offsets[normalized_heading] = candidate_index + 1
                matched_final_ids.add(matched_final["section_id"])
                remaining_final_ids_by_group[group].discard(matched_final["section_id"])
                alignments_by_proposed[proposed_section["section_id"]] = {
                    "final": matched_final,
                    "match_type": "exact_heading",
                    "heading_similarity": 1.0,
                }

    for group in CONTENT_GROUPS:
        for proposed_section in [
            section
            for section in proposed_by_group[group]
            if section["section_id"] not in alignments_by_proposed and section["_heading_tokens"]
        ]:
            best_section = None
            best_score = 0.0
            for final_section in final_by_group[group]:
                if (
                    final_section["section_id"] not in remaining_final_ids_by_group[group]
                    or not final_section["_heading_tokens"]
                ):
                    continue
                score = jaccard(proposed_section["_heading_tokens"], final_section["_heading_tokens"])
                if score > best_score:
                    best_score = score
                    best_section = final_section
            if best_section is not None and best_score >= 0.5:
                matched_final_ids.add(best_section["section_id"])
                remaining_final_ids_by_group[group].discard(best_section["section_id"])
                alignments_by_proposed[proposed_section["section_id"]] = {
                    "final": best_section,
                    "match_type": "fuzzy_heading",
                    "heading_similarity": round(best_score, 4),
                }

    for group in CONTENT_GROUPS:
        for proposed_section in [
            section
            for section in proposed_by_group[group]
            if section["section_id"] not in alignments_by_proposed and bool(section["_body_tokens_full"])
        ]:
            assisted_match, assisted_score = _body_keyword_assist(
                proposed_section,
                final_by_group[group],
                remaining_final_ids_by_group[group],
            )
            if assisted_match is not None:
                matched_final_ids.add(assisted_match["section_id"])
                remaining_final_ids_by_group[group].discard(assisted_match["section_id"])
                alignments_by_proposed[proposed_section["section_id"]] = {
                    "final": assisted_match,
                    "match_type": "fuzzy_heading",
                    "heading_similarity": round(assisted_score, 4),
                }

    for group in CONTENT_GROUPS:
        unmatched_proposed = [
            section
            for section in proposed_by_group[group]
            if section["section_id"] not in alignments_by_proposed and not section["_normalized_heading"]
        ]
        unmatched_final = [
            section
            for section in final_by_group[group]
            if section["section_id"] in remaining_final_ids_by_group[group] and not section["_normalized_heading"]
        ]
        for proposed_section, final_section in zip(unmatched_proposed, unmatched_final):
            matched_final_ids.add(final_section["section_id"])
            remaining_final_ids_by_group[group].discard(final_section["section_id"])
            alignments_by_proposed[proposed_section["section_id"]] = {
                "final": final_section,
                "match_type": "sequential",
                "heading_similarity": 0.0,
            }

    alignment_records = []
    for proposed_section in proposed_sections:
        matched = alignments_by_proposed.get(proposed_section["section_id"])
        if matched is None:
            alignment_records.append(
                {
                    "proposed_section_id": proposed_section["section_id"],
                    "final_section_id": None,
                    "match_type": "unmatched",
                    "heading_similarity": 0.0,
                    "proposed_heading": proposed_section.get("heading"),
                    "final_heading": None,
                    "change_type": "removed",
                    "body_text_changed": False,
                }
            )
            continue
        final_section = matched["final"]
        changed = body_text_changed(proposed_section, final_section)
        alignment_records.append(
            {
                "proposed_section_id": proposed_section["section_id"],
                "final_section_id": final_section["section_id"],
                "match_type": matched["match_type"],
                "heading_similarity": matched["heading_similarity"],
                "proposed_heading": proposed_section.get("heading"),
                "final_heading": final_section.get("heading"),
                "change_type": "modified" if changed else "unchanged",
                "body_text_changed": changed,
            }
        )

    for final_section in final_sections:
        if final_section["section_id"] in matched_final_ids:
            continue
        alignment_records.append(
            {
                "proposed_section_id": None,
                "final_section_id": final_section["section_id"],
                "match_type": "unmatched",
                "heading_similarity": 0.0,
                "proposed_heading": None,
                "final_heading": final_section.get("heading"),
                "change_type": "added",
                "body_text_changed": False,
            }
        )

    alignment_records.sort(
        key=lambda record: (
            record["proposed_section_id"] is None,
            record["proposed_section_id"] or "",
            record["final_section_id"] or "",
        )
    )
    return alignment_records


def _build_heading_index(proposed_sections: list[dict]):
    heading_index = {}
    outline_index = {}
    cfr_index = {}
    for section in proposed_sections:
        heading_index[section["section_id"]] = {
            "tokens": heading_tokens(section.get("heading") or ""),
        }
        for outline_key in section["_outline_citations"]:
            outline_index.setdefault(outline_key, []).append(section["section_id"])
        for cfr_key in section["_cfr_citations"]:
            cfr_index.setdefault(cfr_key, []).append(section["section_id"])
    return heading_index, outline_index, cfr_index


def _extract_citations(text: str, outline_index: dict, cfr_index: dict):
    text = unicodedata.normalize("NFKC", text or "")
    matched_ids = []
    patterns_fired = False

    for range_start, range_end in OUTLINE_RANGE_RE.findall(text):
        patterns_fired = True
        matched_ids.extend(outline_index.get(range_start.lower(), []))
        matched_ids.extend(outline_index.get(range_end.lower(), []))
    for outline_key in OUTLINE_RE.findall(text):
        patterns_fired = True
        matched_ids.extend(outline_index.get(outline_key.lower(), []))
    for cfr_key in CFR_SECTION_SIGN_RE.findall(text):
        patterns_fired = True
        matched_ids.extend(cfr_index.get(cfr_key, []))
    for cfr_key in PLAIN_CFR_RE.findall(text):
        patterns_fired = True
        matched_ids.extend(cfr_index.get(cfr_key, []))

    deduped_ids = []
    seen = set()
    for section_id in matched_ids:
        if section_id in seen:
            continue
        seen.add(section_id)
        deduped_ids.append(section_id)
    return patterns_fired, deduped_ids[:5]


def _keyword_match(text: str, heading_index: dict):
    comment_tokens = body_tokens((text or "")[:2000])
    matches = []
    if not comment_tokens:
        return matches
    for section_id, metadata in heading_index.items():
        tokens = metadata["tokens"]
        if not tokens:
            continue
        overlap = len(tokens & comment_tokens)
        if not overlap:
            continue
        score = overlap / len(tokens)
        if score >= 0.2:
            matches.append((section_id, score))
    matches.sort(key=lambda item: (-item[1], item[0]))
    return matches[:5]


def attribute_comments(comments: list[dict], proposed_sections: list[dict]):
    heading_index, outline_index, cfr_index = _build_heading_index(proposed_sections)
    attribution_records = []

    for comment in comments:
        classification = comment.get("classification")
        if classification != "substantive_inline":
            attribution_records.append(
                {
                    "comment_id": comment.get("comment_id"),
                    "docket_id": comment.get("docket_id"),
                    "classification": classification,
                    "target_sections": [],
                    "attribution_method": "unattributed",
                    "confidence": "none",
                    "citation_patterns_detected": False,
                }
            )
            continue

        text = comment.get("text") or ""
        patterns_fired, cited_section_ids = _extract_citations(text, outline_index, cfr_index)
        if cited_section_ids:
            attribution_records.append(
                {
                    "comment_id": comment.get("comment_id"),
                    "docket_id": comment.get("docket_id"),
                    "classification": classification,
                    "target_sections": cited_section_ids,
                    "attribution_method": "citation",
                    "confidence": "high",
                    "citation_patterns_detected": patterns_fired,
                }
            )
            continue

        keyword_matches = _keyword_match(text, heading_index)
        if keyword_matches:
            top_score = keyword_matches[0][1]
            confidence = "medium" if top_score >= 0.4 else "low"
            attribution_records.append(
                {
                    "comment_id": comment.get("comment_id"),
                    "docket_id": comment.get("docket_id"),
                    "classification": classification,
                    "target_sections": [section_id for section_id, _score in keyword_matches],
                    "attribution_method": "keyword",
                    "confidence": confidence,
                    "citation_patterns_detected": patterns_fired,
                }
            )
            continue

        attribution_records.append(
            {
                "comment_id": comment.get("comment_id"),
                "docket_id": comment.get("docket_id"),
                "classification": classification,
                    "target_sections": [],
                    "attribution_method": "unattributed",
                    "confidence": "none",
                    "citation_patterns_detected": patterns_fired,
                }
        )

    return attribution_records


def compute_alignment_stats(proposed_sections: list[dict], final_sections: list[dict], alignment_records: list[dict]):
    exact_heading_matches = sum(1 for record in alignment_records if record["match_type"] == "exact_heading")
    fuzzy_heading_matches = sum(1 for record in alignment_records if record["match_type"] == "fuzzy_heading")
    sequential_matches = sum(1 for record in alignment_records if record["match_type"] == "sequential")
    matched_count = sum(
        1 for record in alignment_records if record["proposed_section_id"] is not None and record["final_section_id"] is not None
    )
    removed_count = sum(1 for record in alignment_records if record["change_type"] == "removed")
    added_count = sum(1 for record in alignment_records if record["change_type"] == "added")
    coverage_pct = round((matched_count / len(proposed_sections) * 100.0), 1) if proposed_sections else 0.0
    return {
        "proposed_count": len(proposed_sections),
        "final_count": len(final_sections),
        "matched_count": matched_count,
        "removed_count": removed_count,
        "added_count": added_count,
        "exact_heading_matches": exact_heading_matches,
        "fuzzy_heading_matches": fuzzy_heading_matches,
        "sequential_matches": sequential_matches,
        "coverage_pct": coverage_pct,
    }


def compute_attribution_stats(comments: list[dict], attribution_records: list[dict]):
    substantive_inline = sum(1 for comment in comments if comment.get("classification") == "substantive_inline")
    attributed_records = [
        record
        for record in attribution_records
        if record["classification"] == "substantive_inline" and record["attribution_method"] in {"citation", "keyword"}
    ]
    by_method = {
        "citation": sum(1 for record in attributed_records if record["attribution_method"] == "citation"),
        "keyword": sum(1 for record in attributed_records if record["attribution_method"] == "keyword"),
    }
    unattributed = substantive_inline - len(attributed_records)
    attribution_rate_pct = round((len(attributed_records) / substantive_inline * 100.0), 1) if substantive_inline else 0.0
    return {
        "total_comments": len(comments),
        "substantive_inline": substantive_inline,
        "attributed": len(attributed_records),
        "unattributed": unattributed,
        "attribution_rate_pct": attribution_rate_pct,
        "by_method": by_method,
    }


def evaluate_validation(docket_config: dict, alignment_stats: dict, attribution_stats: dict):
    coverage_passed = alignment_stats["coverage_pct"] >= docket_config["section_coverage_min"]
    attribution_passed = attribution_stats["attribution_rate_pct"] >= docket_config["attribution_rate_min"]
    warnings = []
    if not coverage_passed:
        warnings.append(
            f"Section alignment coverage {alignment_stats['coverage_pct']}% is below the {docket_config['section_coverage_min']}% threshold."
        )
    if not attribution_passed:
        warnings.append(
            f"Comment attribution rate {attribution_stats['attribution_rate_pct']}% is below the {docket_config['attribution_rate_min']}% threshold."
        )
    return {
        "section_coverage_meets_threshold": coverage_passed,
        "comment_attribution_rate_meets_threshold": attribution_passed,
        "passed": coverage_passed and attribution_passed,
    }, warnings


def write_outputs(docket_id: str, alignment_records: list[dict], attribution_records: list[dict], log_payload: dict):
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    atomic_write_json(os.path.join(base_dir, "section_alignment.json"), alignment_records)
    atomic_write_json(os.path.join(base_dir, "comment_attribution.json"), attribution_records)
    atomic_write_json(os.path.join(base_dir, "alignment_log.json"), log_payload)


def print_summary(summary_rows: list[dict], overall_passed: bool, elapsed_s: float):
    print("\n=== Phase 2 alignment complete ===")
    for row in summary_rows:
        print(
            f"{row['docket_id']}   proposed {row['proposed_count']} | final {row['final_count']} | "
            f"matched {row['matched_count']} | coverage {row['coverage_pct']:.1f}% | "
            f"attr {row['attr_rate']:.1f}% | {'PASS' if row['passed'] else 'WARN'}"
        )
    print(f"Elapsed: {elapsed_s:.2f}s")
    print(f"Validation: {'PASS' if overall_passed else 'WARN'}")


def main():
    started_at = time.perf_counter()
    summary_rows = []
    overall_passed = True

    for docket_config in DOCKET_MANIFEST:
        docket_id = docket_config["docket_id"]
        print_line("ALIGN", docket_id, "loading corpus...")
        try:
            proposed_sections, final_sections, comments = load_inputs(docket_id)
        except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
            path = getattr(exc, "filename", None) or str(exc)
            print_line("ALIGN", docket_id, f"error: skipping docket due to file I/O problem: {path}")
            overall_passed = False
            continue
        print_line(
            "ALIGN",
            docket_id,
            f"loaded {len(proposed_sections)} proposed, {len(final_sections)} final, {len(comments)} comments",
        )
        print_line("ALIGN", docket_id, "running section alignment...")
        alignment_records = align_sections(proposed_sections, final_sections)
        print_line("ALIGN", docket_id, "running comment attribution...")
        attribution_records = attribute_comments(comments, proposed_sections)

        alignment_stats = compute_alignment_stats(proposed_sections, final_sections, alignment_records)
        attribution_stats = compute_attribution_stats(comments, attribution_records)
        validation, warnings = evaluate_validation(docket_config, alignment_stats, attribution_stats)
        log_payload = {
            "docket_id": docket_id,
            "generated_at": utc_now_iso(),
            "section_alignment": alignment_stats,
            "comment_attribution": attribution_stats,
            "validation": validation,
        }
        if warnings:
            log_payload["warnings"] = warnings

        write_outputs(docket_id, alignment_records, attribution_records, log_payload)
        print_line(
            "ALIGN",
            docket_id,
            f"alignment coverage {alignment_stats['coverage_pct']:.1f}%  "
            f"attribution rate {attribution_stats['attribution_rate_pct']:.1f}%  "
            f"validation {'PASS' if validation['passed'] else 'WARN'}",
        )
        print_line("LOG", docket_id, f"written  corpus/{docket_id}/alignment_log.json")

        summary_rows.append(
            {
                "docket_id": docket_id,
                "proposed_count": alignment_stats["proposed_count"],
                "final_count": alignment_stats["final_count"],
                "matched_count": alignment_stats["matched_count"],
                "coverage_pct": alignment_stats["coverage_pct"],
                "attr_rate": attribution_stats["attribution_rate_pct"],
                "passed": validation["passed"],
            }
        )
        overall_passed = overall_passed and validation["passed"]

    elapsed_s = time.perf_counter() - started_at
    print_summary(summary_rows, overall_passed, elapsed_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
