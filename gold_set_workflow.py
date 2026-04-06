#!/usr/bin/env python3

import json
import os
from datetime import datetime, timezone


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")
GOLD_DIR = os.path.join(ROOT_DIR, "gold_set")
SITE_DATA_DIR = os.path.join(ROOT_DIR, "site_data")
ALIGNMENT_SAMPLE_LIMIT = 25
CLUSTER_SAMPLE_LIMIT = 25
SNIPPET_CHARS = 600
VALID_RELEVANCE = {"relevant", "partially_relevant", "not_relevant"}


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


def normalize_snippet(text: str | None) -> str:
    return " ".join((text or "").split())[:SNIPPET_CHARS]


def annotation_method_for_gold(gold: dict) -> str:
    explicit = gold.get("annotation_method")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    annotator = (gold.get("annotator") or "").strip().lower()
    notes = (gold.get("notes") or "").strip().lower()
    if annotator == "seed" or "seed gold set" in notes or "not a blind evaluation" in notes:
        return "seed_derived"
    return "manual_unspecified"


def provenance_for_gold(gold: dict) -> dict:
    return {
        "annotator": gold.get("annotator"),
        "annotated_at": gold.get("annotated_at"),
        "annotation_method": annotation_method_for_gold(gold),
        "blinded": bool(gold.get("blinded", False)),
        "notes": gold.get("notes"),
    }


def validate_gold_set_payload(gold: dict, expected_docket_id: str | None = None) -> list[str]:
    errors = []
    docket_id = gold.get("docket_id")
    if not isinstance(docket_id, str) or not docket_id.strip():
        errors.append("gold set missing docket_id")
    if expected_docket_id and docket_id != expected_docket_id:
        errors.append(f"gold set docket_id `{docket_id}` does not match expected `{expected_docket_id}`")

    alignments = gold.get("alignments")
    if not isinstance(alignments, list):
        errors.append("gold set alignments must be a list")
    else:
        for index, entry in enumerate(alignments, start=1):
            if not isinstance(entry, dict):
                errors.append(f"alignment {index} must be an object")
                continue
            if not entry.get("proposed_section_id") and not entry.get("final_section_id"):
                errors.append(f"alignment {index} must include proposed_section_id or final_section_id")
            if not isinstance(entry.get("expected_match_type"), str) or not entry["expected_match_type"].strip():
                errors.append(f"alignment {index} missing expected_match_type")
            if not isinstance(entry.get("expected_change_type"), str) or not entry["expected_change_type"].strip():
                errors.append(f"alignment {index} missing expected_change_type")

    cluster_relevance = gold.get("cluster_relevance")
    if not isinstance(cluster_relevance, list):
        errors.append("gold set cluster_relevance must be a list")
    else:
        for index, entry in enumerate(cluster_relevance, start=1):
            if not isinstance(entry, dict):
                errors.append(f"cluster_relevance {index} must be an object")
                continue
            if not isinstance(entry.get("card_id"), str) or not entry["card_id"].strip():
                errors.append(f"cluster_relevance {index} missing card_id")
            if not isinstance(entry.get("cluster_id"), str) or not entry["cluster_id"].strip():
                errors.append(f"cluster_relevance {index} missing cluster_id")
            relevance = entry.get("relevance")
            if relevance not in VALID_RELEVANCE:
                errors.append(
                    f"cluster_relevance {index} has invalid relevance `{relevance}`; "
                    f"expected one of {sorted(VALID_RELEVANCE)}"
                )

    return errors


def _sections_by_id(path: str) -> dict[str, dict]:
    sections = read_json(path)
    return {
        section.get("section_id"): section
        for section in sections
        if isinstance(section, dict) and section.get("section_id")
    }


def _clusters_for_packet(report: dict) -> list[dict]:
    clusters = []
    for cluster in report.get("clusters", [])[:CLUSTER_SAMPLE_LIMIT]:
        clusters.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "label": cluster.get("label"),
                "label_description": cluster.get("label_description"),
                "canonical_count": cluster.get("canonical_count", 0),
                "total_raw_comments": cluster.get("total_raw_comments", 0),
                "top_keywords": cluster.get("top_keywords", [])[:12],
                "commenter_type_distribution": cluster.get("commenter_type_distribution", {}),
            }
        )
    return clusters


def build_blinded_annotation_packet(
    docket_id: str,
    site_data_dir: str = SITE_DATA_DIR,
    corpus_dir: str = CORPUS_DIR,
) -> dict:
    current_dir = os.path.join(site_data_dir, "current")
    manifest_path = os.path.join(current_dir, "manifest.json")
    report_path = os.path.join(current_dir, "dockets", docket_id, "report.json")
    alignment_path = os.path.join(corpus_dir, docket_id, "section_alignment.json")
    proposed_path = os.path.join(corpus_dir, docket_id, "proposed_rule.json")
    final_path = os.path.join(corpus_dir, docket_id, "final_rule.json")

    report = read_json(report_path)
    manifest = read_json(manifest_path)
    alignments = read_json(alignment_path)
    proposed_sections = _sections_by_id(proposed_path)
    final_sections = _sections_by_id(final_path)

    alignment_tasks = []
    for record in alignments[:ALIGNMENT_SAMPLE_LIMIT]:
        proposed_id = record.get("proposed_section_id")
        final_id = record.get("final_section_id")
        proposed_section = proposed_sections.get(proposed_id, {})
        final_section = final_sections.get(final_id, {})
        alignment_tasks.append(
            {
                "task_id": f"{docket_id}_alignment_{len(alignment_tasks) + 1:04d}",
                "proposed_section_id": proposed_id,
                "final_section_id": final_id,
                "proposed_heading": proposed_section.get("heading") or record.get("proposed_heading"),
                "final_heading": final_section.get("heading") or record.get("final_heading"),
                "proposed_text": normalize_snippet(proposed_section.get("body_text")),
                "final_text": normalize_snippet(final_section.get("body_text")),
                "annotation_template": {
                    "expected_match_type": "",
                    "expected_change_type": "",
                    "notes": "",
                },
            }
        )

    cluster_catalog = _clusters_for_packet(report)
    cluster_lookup = {cluster["cluster_id"]: cluster for cluster in cluster_catalog if cluster.get("cluster_id")}
    cluster_tasks = []
    for card in report.get("change_cards", [])[:ALIGNMENT_SAMPLE_LIMIT]:
        candidate_clusters = []
        for related in card.get("related_clusters", [])[:3]:
            cluster_id = related.get("cluster_id")
            if cluster_id and cluster_id in cluster_lookup:
                candidate_clusters.append(cluster_lookup[cluster_id])
        cluster_tasks.append(
            {
                "task_id": f"{docket_id}_cluster_{len(cluster_tasks) + 1:04d}",
                "card_id": card.get("card_id"),
                "change_type": card.get("change_type"),
                "proposed_section_id": card.get("proposed_section_id"),
                "final_section_id": card.get("final_section_id"),
                "proposed_heading": card.get("proposed_heading"),
                "final_heading": card.get("final_heading"),
                "proposed_text_snippet": normalize_snippet(card.get("proposed_text_snippet")),
                "final_text_snippet": normalize_snippet(card.get("final_text_snippet")),
                "candidate_clusters": candidate_clusters,
                "annotation_template": {
                    "cluster_id": "",
                    "relevance": "",
                    "notes": "",
                },
            }
        )

    return {
        "schema_version": "v1",
        "docket_id": docket_id,
        "generated_at": utc_now_iso(),
        "generator": "prepare_gold_set_packet.py",
        "source_snapshot_release_id": manifest.get("release_id"),
        "source_snapshot_published_at": manifest.get("published_at"),
        "packet_type": "blind_annotation_packet",
        "notes": [
            "This packet hides pipeline judgment fields such as change_type predictions and relationship ratings.",
            "Annotators should complete the templates without consulting pipeline evaluation output.",
        ],
        "alignment_tasks": alignment_tasks,
        "cluster_catalog": cluster_catalog,
        "cluster_relevance_tasks": cluster_tasks,
    }


def build_gold_set_template(packet: dict) -> dict:
    return {
        "schema_version": "v1",
        "docket_id": packet.get("docket_id"),
        "annotated_at": "",
        "annotator": "",
        "annotation_method": "blind_human",
        "blinded": True,
        "notes": "",
        "alignments": [
            {
                "proposed_section_id": task.get("proposed_section_id"),
                "final_section_id": task.get("final_section_id"),
                "expected_match_type": "",
                "expected_change_type": "",
                "notes": "",
            }
            for task in packet.get("alignment_tasks", [])
        ],
        "cluster_relevance": [
            {
                "card_id": task.get("card_id"),
                "cluster_id": "",
                "relevance": "",
                "notes": "",
            }
            for task in packet.get("cluster_relevance_tasks", [])
        ],
    }
