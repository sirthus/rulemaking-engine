#!/usr/bin/env python3

import argparse
import os

import gold_set_workflow


DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Validate a completed gold set before evaluation.")
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Expected docket id.")
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the gold-set JSON file to validate.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    path = os.path.abspath(args.path)
    payload = gold_set_workflow.read_json(path)
    errors = gold_set_workflow.validate_gold_set_payload(payload, expected_docket_id=args.docket)

    if errors:
        print("=== Gold-set validation failed ===")
        for error in errors:
            print(f"- {error}")
        return 1

    provenance = gold_set_workflow.provenance_for_gold(payload)
    print("=== Gold-set validation passed ===")
    print(f"Docket: {payload.get('docket_id')}")
    print(f"Annotator: {provenance.get('annotator')}")
    print(f"Annotation method: {provenance.get('annotation_method')}")
    print(f"Blinded: {provenance.get('blinded')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
