#!/usr/bin/env python3

import argparse
import json
import os
import shutil
from datetime import datetime, timezone


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")
DEFAULT_SITE_DATA_DIR = os.path.join(ROOT_DIR, "site_data")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def release_id_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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


def print_line(prefix: str, message: str) -> None:
    print(f"[{prefix}]  {message}")


def parse_args():
    parser = argparse.ArgumentParser(description="Publish site-safe JSON snapshots from output artifacts.")
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Publish a single docket.")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Root directory containing generated report and evaluation artifacts.",
    )
    parser.add_argument(
        "--site-data-dir",
        default=DEFAULT_SITE_DATA_DIR,
        help="Destination directory for published site snapshots.",
    )
    return parser.parse_args()


def validate_source_report(payload: dict, docket_id: str, artifact_name: str) -> None:
    if payload.get("schema_version") != "v1":
        raise RuntimeError(f"{artifact_name} for {docket_id} is missing schema_version v1.")
    if payload.get("docket_id") != docket_id:
        raise RuntimeError(f"{artifact_name} for {docket_id} has the wrong docket_id.")


def build_index_entry(report: dict, eval_report: dict, docket_id: str, published_at: str) -> dict:
    summary = report.get("summary") or {}
    labeling = summary.get("labeling") if isinstance(summary.get("labeling"), dict) else {}
    evaluation_status = eval_report.get("status") or "available"
    return {
        "docket_id": docket_id,
        "display_title": report.get("docket_title") or report.get("title") or docket_id,
        "report_path": f"dockets/{docket_id}/report.json",
        "eval_report_path": f"dockets/{docket_id}/eval_report.json",
        "latest_publish_at": published_at,
        "generated_at": report.get("generated_at"),
        "evaluated_at": eval_report.get("evaluated_at"),
        "evaluation_status": evaluation_status,
        "evaluation_available": evaluation_status == "available",
        "total_clusters": summary.get("total_clusters", 0),
        "total_change_cards": summary.get("total_change_cards", 0),
        "labeled_clusters": summary.get("labeled_clusters", 0),
        "change_type_counts": summary.get("change_type_counts", {}),
        "alignment_signal_counts": summary.get("alignment_signal_counts", {}),
        "review_status_counts": summary.get("review_status_counts", {}),
        "labeling": {
            "model": labeling.get("model"),
            "prompt_version": labeling.get("prompt_version"),
            "labeled_at": labeling.get("labeled_at"),
            "no_think": bool(labeling.get("no_think")),
            "total_input_tokens": int(labeling.get("total_input_tokens", 0) or 0),
            "total_output_tokens": int(labeling.get("total_output_tokens", 0) or 0),
        },
    }


def build_release_summary(
    release_id: str,
    published_at: str,
    index_entries: list[dict],
    output_dir: str,
    release_metadata: dict | None,
) -> dict:
    available_evaluations = sum(1 for entry in index_entries if entry.get("evaluation_status") == "available")
    not_available_evaluations = len(index_entries) - available_evaluations
    total_input_tokens = sum(
        int(((entry.get("labeling") or {}).get("total_input_tokens")) or 0)
        for entry in index_entries
    )
    total_output_tokens = sum(
        int(((entry.get("labeling") or {}).get("total_output_tokens")) or 0)
        for entry in index_entries
    )
    models = sorted(
        {
            (entry.get("labeling") or {}).get("model")
            for entry in index_entries
            if (entry.get("labeling") or {}).get("model")
        }
    )

    summary = {
        "schema_version": "v1",
        "release_id": release_id,
        "published_at": published_at,
        "generator": "publish_site_snapshot.py",
        "source_output_dir": os.path.abspath(output_dir),
        "docket_count": len(index_entries),
        "docket_ids": [entry["docket_id"] for entry in index_entries],
        "evaluation": {
            "available": available_evaluations,
            "not_available": not_available_evaluations,
        },
        "labeling": {
            "models": models,
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
        },
    }

    if isinstance(release_metadata, dict):
        summary["refresh"] = release_metadata

    return summary


def mirror_release_to_current(release_dir: str, current_dir: str) -> None:
    tmp_current_dir = f"{current_dir}.tmp"
    if os.path.exists(tmp_current_dir):
        shutil.rmtree(tmp_current_dir)
    shutil.copytree(release_dir, tmp_current_dir)
    if os.path.exists(current_dir):
        shutil.rmtree(current_dir)
    os.replace(tmp_current_dir, current_dir)


def publish_snapshot(
    docket_ids: list[str],
    output_dir: str,
    site_data_dir: str,
    release_id: str | None = None,
    release_metadata: dict | None = None,
) -> dict:
    resolved_release_id = release_id or release_id_now()
    published_at = utc_now_iso()
    release_dir = os.path.join(site_data_dir, "releases", resolved_release_id)
    current_dir = os.path.join(site_data_dir, "current")

    if os.path.exists(release_dir):
        raise RuntimeError(f"Release directory already exists: {release_dir}")

    index_entries = []
    for docket_id in docket_ids:
        report_path = os.path.join(output_dir, docket_id, "report.json")
        eval_report_path = os.path.join(output_dir, docket_id, "eval_report.json")
        if not os.path.exists(report_path):
            raise RuntimeError(f"Missing required report artifact: {report_path}")
        if not os.path.exists(eval_report_path):
            raise RuntimeError(f"Missing required evaluation artifact: {eval_report_path}")

        report = read_json(report_path)
        eval_report = read_json(eval_report_path)
        validate_source_report(report, docket_id, "report.json")
        validate_source_report(eval_report, docket_id, "eval_report.json")

        release_docket_dir = os.path.join(release_dir, "dockets", docket_id)
        atomic_write_json(os.path.join(release_docket_dir, "report.json"), report)
        atomic_write_json(os.path.join(release_docket_dir, "eval_report.json"), eval_report)
        index_entries.append(build_index_entry(report, eval_report, docket_id, published_at))

    release_summary = build_release_summary(
        resolved_release_id,
        published_at,
        index_entries,
        output_dir,
        release_metadata,
    )

    docket_index = {
        "schema_version": "v1",
        "snapshot": {
            "release_id": resolved_release_id,
            "published_at": published_at,
            "docket_count": len(index_entries),
        },
        "published_at": published_at,
        "release_id": resolved_release_id,
        "dockets": index_entries,
    }
    manifest = {
        "schema_version": "v1",
        "snapshot": {
            "release_id": resolved_release_id,
            "published_at": published_at,
            "docket_count": len(index_entries),
        },
        "release_id": resolved_release_id,
        "published_at": published_at,
        "generator": "publish_site_snapshot.py",
        "source_output_dir": os.path.abspath(output_dir),
        "docket_count": len(index_entries),
        "release_summary_path": "release_summary.json",
        "dockets": index_entries,
    }

    atomic_write_json(os.path.join(release_dir, "manifest.json"), manifest)
    atomic_write_json(os.path.join(release_dir, "release_summary.json"), release_summary)
    atomic_write_json(os.path.join(release_dir, "dockets", "index.json"), docket_index)
    mirror_release_to_current(release_dir, current_dir)

    print_line("PUBLISH", f"written  {os.path.relpath(os.path.join(release_dir, 'manifest.json'), ROOT_DIR)}")
    print_line(
        "PUBLISH",
        f"written  {os.path.relpath(os.path.join(release_dir, 'release_summary.json'), ROOT_DIR)}",
    )
    print_line("PUBLISH", f"written  {os.path.relpath(os.path.join(release_dir, 'dockets', 'index.json'), ROOT_DIR)}")
    print_line("PUBLISH", f"updated  {os.path.relpath(current_dir, ROOT_DIR)}")
    return manifest


def main():
    args = parse_args()
    docket_ids = [args.docket] if args.docket else DOCKET_IDS
    publish_snapshot(
        docket_ids,
        os.path.abspath(args.output_dir),
        os.path.abspath(args.site_data_dir),
    )
    print("=== Site snapshot publish complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
