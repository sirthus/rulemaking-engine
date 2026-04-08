#!/usr/bin/env python3

import argparse
import json
import os
import re
from datetime import datetime, timezone


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")

DOCKETS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

BANNED_CAUSAL_REPLACEMENTS = {
    "caused": "associated with",
    "led to": "aligned with",
    "resulted in": "aligned with",
    "because of": "with",
    "triggered": "coincided with",
    "drove": "coincided with",
    "prompted": "coincided with",
    "due to": "with",
    "in response to": "alongside",
}
BANNED_CAUSAL_PATTERN = re.compile(
    r"\b("
    + "|".join(
        re.escape(term).replace(r"\ ", r"\s+")
        for term in sorted(BANNED_CAUSAL_REPLACEMENTS, key=len, reverse=True)
    )
    + r")\b",
    flags=re.IGNORECASE,
)


class InsightGenerationError(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


def atomic_write_json(path: str, payload) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2) + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate deterministic insight reports from output artifacts.")
    parser.add_argument("--docket", choices=DOCKETS, help="Process a single docket.")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Root directory containing report.json inputs and receiving insight_report.json outputs.",
    )
    return parser.parse_args()


def relative_display_path(path: str) -> str:
    try:
        return os.path.relpath(path, ROOT_DIR)
    except ValueError:
        return path


def load_optional_json(path: str):
    try:
        return read_json(path)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def numeric_value(value, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def integer_value(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def alignment_signal(card: dict) -> dict:
    signal = card.get("alignment_signal")
    return signal if isinstance(signal, dict) else {}


def alignment_level(card: dict) -> str:
    return alignment_signal(card).get("level") or "none"


def alignment_score(card: dict) -> float:
    return numeric_value(alignment_signal(card).get("score"))


def card_identifier(card: dict) -> str:
    return card.get("card_id") or ""


def section_title(card: dict) -> str:
    return (
        card.get("section_title")
        or card.get("proposed_heading")
        or card.get("final_heading")
        or card_identifier(card)
    )


def related_cluster_ids(card: dict) -> list[str]:
    cluster_ids = []
    for related_cluster in card.get("related_clusters", []) or []:
        if isinstance(related_cluster, dict):
            cluster_id = related_cluster.get("cluster_id")
        else:
            cluster_id = related_cluster
        if cluster_id:
            cluster_ids.append(cluster_id)
    return cluster_ids


def sorted_labeled_clusters(clusters: list[dict]) -> list[dict]:
    labeled = [
        cluster
        for cluster in clusters
        if cluster.get("label") is not None and cluster.get("cluster_id")
    ]
    return sorted(
        labeled,
        key=lambda cluster: (
            -integer_value(cluster.get("canonical_count")),
            cluster.get("cluster_id") or "",
        ),
    )


def cards_for_cluster(cards: list[dict], cluster_id: str) -> list[dict]:
    return [
        card
        for card in cards
        if cluster_id in related_cluster_ids(card)
    ]


def why_it_matters(cards: list[dict]) -> str:
    high_count = sum(1 for card in cards if alignment_level(card) == "high")
    medium_count = sum(1 for card in cards if alignment_level(card) == "medium")

    if high_count and medium_count:
        return (
            f"{high_count} of the associated change cards showed high comment alignment, "
            f"{medium_count} medium."
        )
    if high_count:
        return f"{high_count} of the associated change cards showed high comment alignment."
    if medium_count:
        return f"{medium_count} of the associated change cards showed medium comment alignment."
    return "No associated change cards showed elevated comment alignment."


def highest_scoring_card(cards: list[dict]) -> dict | None:
    if not cards:
        return None
    return sorted(
        cards,
        key=lambda card: (
            -alignment_score(card),
            card_identifier(card),
        ),
    )[0]


def related_cluster_for_card(card: dict, cluster_id: str) -> dict | None:
    for related_cluster in card.get("related_clusters", []) or []:
        if isinstance(related_cluster, dict) and related_cluster.get("cluster_id") == cluster_id:
            return related_cluster
    return None


def build_finding_evidence(evidence_card: dict | None, cluster_id: str) -> dict:
    if evidence_card is None:
        return {
            "evidence_note": "",
            "evidence_card_id": None,
            "evidence_section_title": None,
            "evidence_card_score": None,
            "evidence_cluster_comment_count": None,
        }

    card_id = card_identifier(evidence_card)
    title = section_title(evidence_card)
    score = alignment_score(evidence_card)
    level = alignment_level(evidence_card)
    related_cluster = related_cluster_for_card(evidence_card, cluster_id)
    comment_count = None
    if related_cluster is not None and isinstance(related_cluster.get("comment_count"), (int, float)):
        comment_count = int(related_cluster["comment_count"])

    note_parts = [f"Top linked change card: {title} ({card_id})"]
    if comment_count is not None:
        note_parts.append(f"{comment_count} comment(s) from this theme linked to the card")
    note_parts.append(f"card-level signal {level} (score {score:g})")

    return {
        "evidence_note": "; ".join(note_parts) + ".",
        "evidence_card_id": card_id,
        "evidence_section_title": title,
        "evidence_card_score": score,
        "evidence_cluster_comment_count": comment_count,
    }


def build_top_findings(clusters: list[dict], cards: list[dict]) -> list[dict]:
    findings = []

    for cluster in sorted_labeled_clusters(clusters):
        cluster_id = cluster.get("cluster_id")
        finding_cards = cards_for_cluster(cards, cluster_id)
        card_ids = [card_identifier(card) for card in finding_cards if card_identifier(card)]
        evidence_card = highest_scoring_card(finding_cards)
        evidence_payload = build_finding_evidence(evidence_card, cluster_id)

        label_description = cluster.get("label_description") or ""
        summary = f"{label_description} This theme appears across {len(card_ids)} regulatory change(s).".strip()
        findings.append(
            {
                "finding_id": f"finding-{len(findings) + 1:03d}",
                "title": cluster.get("label") or "",
                "summary": summary,
                "why_it_matters": why_it_matters(finding_cards),
                **evidence_payload,
                "card_ids": card_ids,
                "cluster_ids": [cluster_id],
            }
        )

    residual_cards = [
        card
        for card in cards
        if alignment_level(card) in {"high", "medium"}
        and not related_cluster_ids(card)
    ]
    if residual_cards:
        card_ids = [card_identifier(card) for card in residual_cards if card_identifier(card)]
        findings.append(
            {
                "finding_id": f"finding-{len(findings) + 1:03d}",
                "title": "Unclustered Regulatory Changes",
                "summary": (
                    f"{len(card_ids)} high- or medium-signal change card(s) were not "
                    "associated with any comment cluster."
                ),
                "why_it_matters": (
                    "These changes had measurable comment engagement but no cluster grouping."
                ),
                "evidence_note": "",
                "evidence_card_id": None,
                "evidence_section_title": None,
                "evidence_card_score": None,
                "evidence_cluster_comment_count": None,
                "card_ids": card_ids,
                "cluster_ids": [],
            }
        )

    return findings


def finding_ids_by_card(top_findings: list[dict]) -> dict[str, list[str]]:
    lookup: dict[str, list[str]] = {}
    for finding in top_findings:
        finding_id = finding.get("finding_id")
        for card_id in finding.get("card_ids", []) or []:
            if not card_id or not finding_id:
                continue
            lookup.setdefault(card_id, []).append(finding_id)
    return lookup


def build_priority_cards(cards: list[dict], top_findings: list[dict]) -> list[dict]:
    card_findings = finding_ids_by_card(top_findings)
    sorted_cards = sorted(
        cards,
        key=lambda card: (
            -alignment_score(card),
            card_identifier(card),
        ),
    )

    return [
        {
            "card_id": card_identifier(card),
            "section_title": section_title(card),
            "change_type": card.get("change_type") or "",
            "score": alignment_score(card),
            "alignment_level": alignment_level(card),
            "finding_ids": card_findings.get(card_identifier(card), []),
        }
        for card in sorted_cards
    ]


def count_change_types(cards: list[dict]) -> dict[str, int]:
    counts = {"modified": 0, "added": 0, "removed": 0}
    for card in cards:
        change_type = card.get("change_type")
        if change_type in counts:
            counts[change_type] += 1
    return counts


def count_alignment_levels(cards: list[dict]) -> dict[str, int]:
    counts = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for card in cards:
        level = alignment_level(card)
        if level in counts:
            counts[level] += 1
        else:
            counts["none"] += 1
    return counts


def build_commenter_emphasis(clusters: list[dict]) -> str:
    top_clusters = sorted_labeled_clusters(clusters)[:3]
    if not top_clusters:
        return "Commenters most frequently raised: none."

    rendered_clusters = ", ".join(
        f"{cluster.get('label') or ''} ({integer_value(cluster.get('canonical_count'))} comments)"
        for cluster in top_clusters
    )
    return f"Commenters most frequently raised: {rendered_clusters}."


def build_rule_story(cards: list[dict], clusters: list[dict]) -> dict:
    change_counts = count_change_types(cards)
    alignment_counts = count_alignment_levels(cards)
    total = len(cards)
    return {
        "what_changed": (
            f"{change_counts['modified']} section(s) modified, "
            f"{change_counts['added']} added, {change_counts['removed']} removed "
            f"across {total} change cards."
        ),
        "what_commenters_emphasized": build_commenter_emphasis(clusters),
        "where_final_text_aligned": (
            f"{alignment_counts['high']} change card(s) showed high comment alignment, "
            f"{alignment_counts['medium']} medium, {alignment_counts['low']} low, "
            f"{alignment_counts['none']} with no attributable comment engagement."
        ),
        "caveats": (
            "Alignment signals are based on keyword and structural matching between comment text "
            "and rule sections. They indicate co-occurrence, not causation. Evaluation metrics "
            "reflect pipeline accuracy against a blinded AI-generated gold set."
        ),
    }


def section_count(cards: list[dict]) -> int:
    section_ids = {
        card.get("proposed_section_id") or card.get("section_id")
        for card in cards
        if card.get("proposed_section_id") or card.get("section_id")
    }
    return len(section_ids)


def build_executive_summary(
    docket_id: str,
    cards: list[dict],
    clusters: list[dict],
    top_findings: list[dict],
) -> str:
    top_clusters = sorted_labeled_clusters(clusters)
    if top_clusters:
        top_cluster_label = top_clusters[0].get("label") or "none"
        top_cluster_count = integer_value(top_clusters[0].get("canonical_count"))
    else:
        top_cluster_label = "none"
        top_cluster_count = 0

    high_signal_count = sum(
        1
        for card in cards
        if alignment_level(card) in {"high", "medium"}
    )

    return (
        f"{docket_id}: {len(cards)} regulatory change(s) identified across "
        f"{section_count(cards)} rule section(s). {high_signal_count} change(s) showed "
        f"measurable comment engagement. Top commenter theme: {top_cluster_label} "
        f"({top_cluster_count} comments). {len(top_findings)} finding(s) derived from "
        f"{len(clusters)} comment cluster(s)."
    )


def sanitize_causal_language(value: str) -> str:
    def replace(match: re.Match) -> str:
        normalized = re.sub(r"\s+", " ", match.group(0).lower())
        return BANNED_CAUSAL_REPLACEMENTS.get(normalized, match.group(0))

    return BANNED_CAUSAL_PATTERN.sub(replace, value)


def sanitize_json_strings(value):
    if isinstance(value, str):
        return sanitize_causal_language(value)
    if isinstance(value, list):
        return [sanitize_json_strings(item) for item in value]
    if isinstance(value, dict):
        return {
            key: sanitize_json_strings(item)
            for key, item in value.items()
        }
    return value


def build_insight_report(
    report: dict,
    eval_report: dict | None = None,
    *,
    docket_id: str | None = None,
    source_report: str | None = None,
    source_eval_report: str | None = None,
    generated_at: str | None = None,
) -> dict:
    resolved_docket_id = docket_id or report.get("docket_id") or ""
    source_report = source_report or f"outputs/{resolved_docket_id}/report.json"
    source_eval_report = source_eval_report or f"outputs/{resolved_docket_id}/eval_report.json"
    cards = report.get("change_cards", []) or []
    clusters = report.get("clusters", []) or []

    top_findings = build_top_findings(clusters, cards)
    priority_cards = build_priority_cards(cards, top_findings)

    payload = {
        "schema_version": "v1",
        "docket_id": resolved_docket_id,
        "generated_at": generated_at or utc_now_iso(),
        "generator": "generate_insights.py",
        "executive_summary": build_executive_summary(
            resolved_docket_id,
            cards,
            clusters,
            top_findings,
        ),
        "top_findings": top_findings,
        "rule_story": build_rule_story(cards, clusters),
        "priority_cards": priority_cards,
        "provenance": {
            "source_report": source_report,
            "source_eval_report": source_eval_report,
            "eval_available": eval_report is not None,
            "report_schema_version": report.get("schema_version") or "",
            "card_count": len(cards),
            "cluster_count": len(clusters),
            "finding_count": len(top_findings),
        },
    }
    return sanitize_json_strings(payload)


def process_docket(docket_id: str, output_dir: str) -> dict:
    docket_output_dir = os.path.join(output_dir, docket_id)
    report_path = os.path.join(docket_output_dir, "report.json")
    eval_report_path = os.path.join(docket_output_dir, "eval_report.json")
    insight_report_path = os.path.join(docket_output_dir, "insight_report.json")

    if not os.path.exists(report_path):
        raise InsightGenerationError(f"missing required input {relative_display_path(report_path)}")

    try:
        report = read_json(report_path)
    except (OSError, json.JSONDecodeError) as exc:
        raise InsightGenerationError(f"could not read {relative_display_path(report_path)}: {exc}") from exc

    eval_report = load_optional_json(eval_report_path)
    insight_report = build_insight_report(
        report,
        eval_report,
        docket_id=docket_id,
        source_report=relative_display_path(report_path),
        source_eval_report=relative_display_path(eval_report_path),
    )

    atomic_write_json(insight_report_path, insight_report)
    print(
        f"[{docket_id}] insight_report.json written "
        f"({len(insight_report['top_findings'])} findings, "
        f"{len(insight_report['priority_cards'])} priority cards)"
    )
    return insight_report


def main() -> int:
    args = parse_args()
    output_dir = os.path.abspath(args.output_dir)
    docket_ids = [args.docket] if args.docket else DOCKETS

    failures = 0
    for docket_id in docket_ids:
        try:
            process_docket(docket_id, output_dir)
        except InsightGenerationError as exc:
            failures += 1
            prefix = "ERROR" if args.docket else "WARN"
            print(f"[{docket_id}] {prefix}: {exc}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
