#!/usr/bin/env python3

import argparse
import json
import os
from datetime import datetime, timezone


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")
DEFAULT_GOLD_DIR = os.path.join(ROOT_DIR, "gold_set")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]


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
    atomic_write_text(path, json.dumps(payload, indent=2))


def print_line(prefix: str, docket_id: str, message: str) -> None:
    print(f"[{prefix}]  {docket_id}  {message}")


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate pipeline output against seed gold sets.")
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Process a single docket.")
    parser.add_argument(
        "--gold-dir",
        default=DEFAULT_GOLD_DIR,
        help="Directory containing per-docket gold set files.",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Root directory for generated evaluation report files.",
    )
    return parser.parse_args()


def ratio_payload(matched: int, total: int) -> dict:
    return {
        "matched": matched,
        "total": total,
        "pct": round((matched / total) * 100.0, 1) if total else 0.0,
    }


def precision_at_3_payload(matched: int, eligible_cards: int) -> dict:
    return {
        "matched": matched,
        "eligible_cards": eligible_cards,
        "pct": round((matched / eligible_cards) * 100.0, 1) if eligible_cards else 0.0,
    }


def build_comment_to_cluster(themes: dict) -> dict[str, str]:
    comment_to_cluster = {}
    for cluster in themes.get("clusters", []):
        cluster_id = cluster.get("cluster_id")
        if not cluster_id:
            continue
        for comment_id in cluster.get("member_canonical_ids", []):
            if comment_id:
                comment_to_cluster[comment_id] = cluster_id
    return comment_to_cluster


def card_cluster_ids(card: dict, comment_to_cluster: dict[str, str]) -> list[str]:
    counts = {}
    for related_comment in card.get("related_comments", []) or []:
        cluster_id = comment_to_cluster.get(related_comment.get("comment_id"))
        if cluster_id:
            counts[cluster_id] = counts.get(cluster_id, 0) + 1
    return sorted(counts, key=lambda cluster_id: (-counts[cluster_id], cluster_id))


def compute_alignment_metrics(gold: dict, alignment_records: list[dict]) -> dict:
    by_both = {
        (record["proposed_section_id"], record["final_section_id"]): record
        for record in alignment_records
        if record.get("proposed_section_id") and record.get("final_section_id")
    }
    by_final = {
        record["final_section_id"]: record
        for record in alignment_records
        if record.get("final_section_id") and not record.get("proposed_section_id")
    }
    by_proposed = {
        record["proposed_section_id"]: record
        for record in alignment_records
        if record.get("proposed_section_id") and not record.get("final_section_id")
    }

    total_gold_alignments = len(gold.get("alignments", []))
    pipeline_matched = 0
    change_type_agreement = 0
    match_type_agreement = 0

    for gold_entry in gold.get("alignments", []):
        proposed_section_id = gold_entry.get("proposed_section_id")
        final_section_id = gold_entry.get("final_section_id")

        if proposed_section_id and final_section_id:
            pipeline_record = by_both.get((proposed_section_id, final_section_id))
        elif final_section_id:
            pipeline_record = by_final.get(final_section_id)
        elif proposed_section_id:
            pipeline_record = by_proposed.get(proposed_section_id)
        else:
            pipeline_record = None

        if pipeline_record is None:
            continue

        pipeline_matched += 1
        if pipeline_record.get("change_type") == gold_entry.get("expected_change_type"):
            change_type_agreement += 1
        if pipeline_record.get("match_type") == gold_entry.get("expected_match_type"):
            match_type_agreement += 1

    return {
        "total_gold_alignments": total_gold_alignments,
        "pipeline_matched": pipeline_matched,
        "change_type_agreement": ratio_payload(change_type_agreement, pipeline_matched),
        "match_type_agreement": ratio_payload(match_type_agreement, pipeline_matched),
    }


def compute_cluster_relevance_metrics(gold: dict, change_cards: list[dict], comment_to_cluster: dict[str, str]) -> dict:
    cards_by_id = {
        card.get("card_id"): card
        for card in change_cards
        if card.get("card_id")
    }

    total_gold_judgments = len(gold.get("cluster_relevance", []))
    pipeline_cluster_found = 0
    relevant_found = 0
    precision_at_1_matched = 0
    precision_at_1_total = 0
    precision_at_3_matched = 0
    precision_at_3_eligible = 0

    for gold_entry in gold.get("cluster_relevance", []):
        card = cards_by_id.get(gold_entry.get("card_id"))
        if card is None:
            continue

        gold_cluster_id = gold_entry.get("cluster_id")
        relevance = gold_entry.get("relevance")
        card_clusters = card_cluster_ids(card, comment_to_cluster)

        if gold_cluster_id in card_clusters:
            pipeline_cluster_found += 1
            if relevance in {"relevant", "partially_relevant"}:
                relevant_found += 1

        precision_at_1_total += 1
        if card_clusters and card_clusters[0] == gold_cluster_id and relevance == "relevant":
            precision_at_1_matched += 1

        if len(card_clusters) >= 3:
            precision_at_3_eligible += 1
            if gold_cluster_id in card_clusters[:3] and relevance in {"relevant", "partially_relevant"}:
                precision_at_3_matched += 1

    return {
        "total_gold_judgments": total_gold_judgments,
        "pipeline_cluster_found": pipeline_cluster_found,
        "relevant_found": relevant_found,
        "precision_at_1": ratio_payload(precision_at_1_matched, precision_at_1_total),
        "precision_at_3": precision_at_3_payload(precision_at_3_matched, precision_at_3_eligible),
    }


def render_eval_report_text(report: dict) -> str:
    alignment_metrics = report["alignment_metrics"]
    cluster_metrics = report["cluster_relevance_metrics"]
    p1 = cluster_metrics["precision_at_1"]
    p3 = cluster_metrics["precision_at_3"]

    return "\n".join(
        [
            f"=== Evaluation Report: {report['docket_id']} ===",
            (
                f"Gold set: {report['gold_set_annotator']}  "
                f"({alignment_metrics['total_gold_alignments']} alignments, "
                f"{cluster_metrics['total_gold_judgments']} cluster judgments)"
            ),
            "",
            f"Alignment metrics ({alignment_metrics['total_gold_alignments']} gold entries):",
            (
                f"  pipeline_matched:      {alignment_metrics['pipeline_matched']} / "
                f"{alignment_metrics['total_gold_alignments']}  "
                f"({round((alignment_metrics['pipeline_matched'] / alignment_metrics['total_gold_alignments']) * 100.0, 1) if alignment_metrics['total_gold_alignments'] else 0.0}%)"
            ),
            (
                f"  change_type_agreement: {alignment_metrics['change_type_agreement']['matched']} / "
                f"{alignment_metrics['change_type_agreement']['total']}  "
                f"({alignment_metrics['change_type_agreement']['pct']}%)"
            ),
            (
                f"  match_type_agreement:  {alignment_metrics['match_type_agreement']['matched']} / "
                f"{alignment_metrics['match_type_agreement']['total']}  "
                f"({alignment_metrics['match_type_agreement']['pct']}%)"
            ),
            "",
            f"Cluster relevance metrics ({cluster_metrics['total_gold_judgments']} gold judgments):",
            (
                f"  pipeline_cluster_found: {cluster_metrics['pipeline_cluster_found']} / "
                f"{cluster_metrics['total_gold_judgments']}  "
                f"({round((cluster_metrics['pipeline_cluster_found'] / cluster_metrics['total_gold_judgments']) * 100.0, 1) if cluster_metrics['total_gold_judgments'] else 0.0}%)"
            ),
            (
                f"  relevant_found:         {cluster_metrics['relevant_found']} / "
                f"{cluster_metrics['total_gold_judgments']}  "
                f"({round((cluster_metrics['relevant_found'] / cluster_metrics['total_gold_judgments']) * 100.0, 1) if cluster_metrics['total_gold_judgments'] else 0.0}%)"
            ),
            f"  precision@1:            {p1['matched']} / {p1['total']}  ({p1['pct']}%)",
            f"  precision@3:            {p3['matched']} / {p3['eligible_cards']} eligible cards  ({p3['pct']}%)",
            "",
        ]
    )


def process_docket(docket_id: str, gold_dir: str, output_dir: str) -> dict | None:
    gold_path = os.path.join(gold_dir, f"{docket_id}.json")
    if not os.path.exists(gold_path):
        print_line("INFO", docket_id, "no gold set found; skipping")
        return None

    base_dir = os.path.join(CORPUS_DIR, docket_id)
    try:
        gold = read_json(gold_path)
        alignment_records = read_json(os.path.join(base_dir, "section_alignment.json"))
        change_cards = read_json(os.path.join(base_dir, "change_cards.json"))
        themes = read_json(os.path.join(base_dir, "comment_themes.json"))
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("ERROR", docket_id, f"missing required input {path}")
        return None

    comment_to_cluster = build_comment_to_cluster(themes)
    alignment_metrics = compute_alignment_metrics(gold, alignment_records)
    cluster_relevance_metrics = compute_cluster_relevance_metrics(gold, change_cards, comment_to_cluster)

    report = {
        "docket_id": docket_id,
        "evaluated_at": utc_now_iso(),
        "gold_set_annotator": gold.get("annotator"),
        "alignment_metrics": alignment_metrics,
        "cluster_relevance_metrics": cluster_relevance_metrics,
    }

    output_base_dir = os.path.join(output_dir, docket_id)
    json_output_path = os.path.join(output_base_dir, "eval_report.json")
    text_output_path = os.path.join(output_base_dir, "eval_report.txt")
    atomic_write_json(json_output_path, report)
    atomic_write_text(text_output_path, render_eval_report_text(report))

    print_line("EVAL", docket_id, f"written  {os.path.relpath(json_output_path, ROOT_DIR)}")
    print_line("EVAL", docket_id, f"written  {os.path.relpath(text_output_path, ROOT_DIR)}")
    return report


def main():
    args = parse_args()
    docket_ids = [args.docket] if args.docket else DOCKET_IDS
    gold_dir = os.path.abspath(args.gold_dir)
    output_dir = os.path.abspath(args.output_dir)

    reports = []
    for docket_id in docket_ids:
        report = process_docket(docket_id, gold_dir, output_dir)
        if report is not None:
            reports.append(report)

    print("=== Phase 9 evaluation complete ===")
    for report in reports:
        print(
            f"{report['docket_id']}   "
            f"{report['alignment_metrics']['total_gold_alignments']} alignments  "
            f"{report['cluster_relevance_metrics']['total_gold_judgments']} cluster judgments"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
