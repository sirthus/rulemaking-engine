#!/usr/bin/env python3

import argparse
import os

import gold_set_workflow
from pipeline_utils import DOCKET_IDS


def parse_args():
    parser = argparse.ArgumentParser(
        description="Prepare a blinded annotation packet and template for one docket."
    )
    parser.add_argument("--docket", required=True, choices=DOCKET_IDS, help="Docket to prepare.")
    parser.add_argument(
        "--site-data-dir",
        default=gold_set_workflow.SITE_DATA_DIR,
        help="Site snapshot directory containing current published data.",
    )
    parser.add_argument(
        "--corpus-dir",
        default=gold_set_workflow.CORPUS_DIR,
        help="Corpus directory with source artifacts.",
    )
    parser.add_argument(
        "--packet-dir",
        default=os.path.join(gold_set_workflow.GOLD_DIR, "packets"),
        help="Destination directory for blinded packets.",
    )
    parser.add_argument(
        "--template-dir",
        default=os.path.join(gold_set_workflow.GOLD_DIR, "templates"),
        help="Destination directory for editable annotation templates.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    packet = gold_set_workflow.build_blinded_annotation_packet(
        args.docket,
        site_data_dir=os.path.abspath(args.site_data_dir),
        corpus_dir=os.path.abspath(args.corpus_dir),
    )
    template = gold_set_workflow.build_gold_set_template(packet)

    packet_path = os.path.join(os.path.abspath(args.packet_dir), f"{args.docket}.packet.json")
    template_path = os.path.join(os.path.abspath(args.template_dir), f"{args.docket}.template.json")

    gold_set_workflow.atomic_write_json(packet_path, packet)
    gold_set_workflow.atomic_write_json(template_path, template)

    print(f"[GOLD]  {args.docket}  written  {os.path.relpath(packet_path, gold_set_workflow.ROOT_DIR)}")
    print(f"[GOLD]  {args.docket}  written  {os.path.relpath(template_path, gold_set_workflow.ROOT_DIR)}")
    print("=== Gold-set packet preparation complete ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
