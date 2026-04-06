#!/usr/bin/env python3

import argparse
import os

import evaluate_pipeline
import generate_outputs
import label_clusters
import ollama_runtime
import publish_site_snapshot


DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Refresh local labels, reports, evaluation outputs, and the published site snapshot."
    )
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Refresh a single docket.")
    parser.add_argument("--model", default=label_clusters.DEFAULT_MODEL, help="Ollama model identifier to use.")
    parser.add_argument(
        "--ollama-url",
        default=label_clusters.DEFAULT_OLLAMA_URL,
        help="Base URL for the local Ollama daemon (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--force-labels",
        action="store_true",
        help="Re-label clusters even when they already have labels.",
    )
    parser.add_argument(
        "--skip-evaluate",
        action="store_true",
        help="Skip evaluation refresh and reuse any existing eval_report.json files.",
    )
    parser.add_argument(
        "--skip-publish",
        action="store_true",
        help="Skip publishing a site snapshot after refreshing local artifacts.",
    )
    parser.add_argument(
        "--output-dir",
        default=generate_outputs.DEFAULT_OUTPUT_DIR,
        help="Root directory for generated output artifacts.",
    )
    parser.add_argument(
        "--gold-dir",
        default=evaluate_pipeline.DEFAULT_GOLD_DIR,
        help="Directory containing gold-set files for evaluation.",
    )
    parser.add_argument(
        "--site-data-dir",
        default=publish_site_snapshot.DEFAULT_SITE_DATA_DIR,
        help="Destination directory for published site snapshots.",
    )
    return parser.parse_args()

def run_refresh(
    docket_ids: list[str],
    model: str,
    ollama_url: str,
    force_labels: bool,
    skip_evaluate: bool,
    skip_publish: bool,
    output_dir: str,
    gold_dir: str,
    site_data_dir: str,
) -> dict:
    client = label_clusters.OllamaClient(ollama_url)
    preflight = ollama_runtime.run_preflight(
        ollama_url,
        model,
        session=getattr(client, "session", None),
        timeout_seconds=getattr(client, "timeout_seconds", ollama_runtime.DEFAULT_TIMEOUT_SECONDS),
    )
    model_profile = preflight["profile"]
    no_think = bool(model_profile.get("recommended_no_think"))
    label_summaries = []
    output_summaries = []
    eval_reports = []

    for docket_id in docket_ids:
        label_summary = label_clusters.process_docket(
            client,
            docket_id,
            model,
            force=force_labels,
            no_think=no_think,
            model_profile=model_profile,
        )
        if label_summary is None:
            raise RuntimeError(f"Label refresh failed for {docket_id}.")
        label_summaries.append(label_summary)

        output_summary = generate_outputs.process_docket(docket_id, output_dir, force=True)
        if output_summary is None:
            raise RuntimeError(f"Output refresh failed for {docket_id}.")
        output_summaries.append(output_summary)

        if not skip_evaluate:
            eval_report = evaluate_pipeline.process_docket(docket_id, gold_dir, output_dir)
            if eval_report is None:
                raise RuntimeError(f"Evaluation refresh failed for {docket_id}.")
            eval_reports.append(eval_report)

    published_manifest = None
    if not skip_publish:
        published_manifest = publish_site_snapshot.publish_snapshot(
            docket_ids,
            output_dir,
            site_data_dir,
            release_metadata={
                "workflow": "refresh_site_snapshot.py",
                "refreshed_docket_ids": docket_ids,
                "model": model,
                "model_profile": ollama_runtime.profile_for_manifest(model_profile),
                "no_think": no_think,
                "label_totals": {
                    "input_tokens": sum(int(item.get("input_tokens", 0) or 0) for item in label_summaries),
                    "output_tokens": sum(int(item.get("output_tokens", 0) or 0) for item in label_summaries),
                    "wall_clock_ms": round(
                        sum(float(item.get("wall_clock_ms", 0.0) or 0.0) for item in label_summaries),
                        1,
                    ),
                },
                "evaluation": {
                    "available": sum(1 for item in eval_reports if item.get("status") == "available"),
                    "not_available": sum(1 for item in eval_reports if item.get("status") != "available"),
                    "skipped": bool(skip_evaluate),
                },
            },
        )

    return {
        "docket_ids": docket_ids,
        "model": model,
        "model_profile": ollama_runtime.profile_for_manifest(model_profile),
        "ollama_url": ollama_url,
        "no_think": no_think,
        "preflight": preflight,
        "label_summaries": label_summaries,
        "output_summaries": output_summaries,
        "eval_reports": eval_reports,
        "published_manifest": published_manifest,
    }


def main():
    args = parse_args()
    docket_ids = [args.docket] if args.docket else DOCKET_IDS
    result = run_refresh(
        docket_ids=docket_ids,
        model=args.model,
        ollama_url=args.ollama_url,
        force_labels=args.force_labels,
        skip_evaluate=args.skip_evaluate,
        skip_publish=args.skip_publish,
        output_dir=os.path.abspath(args.output_dir),
        gold_dir=os.path.abspath(args.gold_dir),
        site_data_dir=os.path.abspath(args.site_data_dir),
    )

    for line in ollama_runtime.preflight_summary_lines(result["preflight"]):
        print(f"[PREFLIGHT]  {line}")
    print("=== Site refresh complete ===")
    print(
        f"Model: {result['model']}  no_think={result['no_think']}  "
        f"dockets={len(result['docket_ids'])}"
    )
    total_input_tokens = sum(int(item.get("input_tokens", 0) or 0) for item in result["label_summaries"])
    total_output_tokens = sum(int(item.get("output_tokens", 0) or 0) for item in result["label_summaries"])
    eval_available = sum(1 for item in result["eval_reports"] if item.get("status") == "available")
    eval_not_available = sum(1 for item in result["eval_reports"] if item.get("status") != "available")
    print(f"Label tokens: {total_input_tokens} in / {total_output_tokens} out")
    if args.skip_evaluate:
        print("Evaluation: skipped")
    else:
        print(f"Evaluation: {eval_available} available / {eval_not_available} not available")
    if result["published_manifest"] is not None:
        print(f"Published release: {result['published_manifest']['release_id']}")
    else:
        print("Published release: skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
