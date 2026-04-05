#!/usr/bin/env python3

import argparse
import json
import os
import time
from datetime import datetime, timezone

import anthropic


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
PROMPT_VERSION = "v1"
ESTIMATED_OUTPUT_TOKENS = 80
INPUT_COST_PER_MILLION = 0.80
OUTPUT_COST_PER_MILLION = 4.00
MAX_EXCERPTS = 3
MAX_EXCERPT_CHARS = 400

SYSTEM_PROMPT = """You are analyzing public comments submitted to an EPA rulemaking docket.
Given a cluster of related comments described by keywords, commenter types, and
representative excerpts, generate a concise label and one-sentence description.

Respond with valid JSON only, no markdown fences:
{"label": "3-7 word label", "description": "One sentence (under 25 words)."}

Guidelines:
- Label should be specific and informative, not generic (e.g., "Cost Impact on Small
  Refineries" not "Cost Concerns").
- Description summarizes the core argument or concern without causal language.
- Do not use the word "comments" in the label."""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_text(path: str, text: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


def atomic_write_json(path: str, payload):
    atomic_write_text(path, json.dumps(payload, indent=2))


def print_line(prefix: str, docket_id: str, message: str):
    print(f"[{prefix}]  {docket_id}  {message}")


def parse_args():
    parser = argparse.ArgumentParser(description="Label clustered docket themes with an LLM.")
    parser.add_argument("--audit", action="store_true", help="Write token and cost audit files without labeling.")
    parser.add_argument("--force", action="store_true", help="Re-label clusters that already have labels.")
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Process a single docket.")
    parser.add_argument("--base-url", help="Override the Anthropic-compatible base URL.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Model identifier to use for labeling.")
    return parser.parse_args()


def build_client(base_url: str | None) -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY") or ("ollama" if base_url else None)
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is required unless --base-url is set for a local Anthropic-compatible endpoint."
        )
    return anthropic.Anthropic(api_key=api_key, base_url=base_url)


def normalize_excerpt_text(text: str) -> str:
    return " ".join((text or "").split()).strip()


def build_excerpts(cluster: dict, comments_by_id: dict[str, dict]) -> list[dict[str, str]]:
    excerpts = []
    for canonical_id in cluster.get("member_canonical_ids", []):
        comment = comments_by_id.get(canonical_id)
        if not comment:
            continue
        raw_text = comment.get("text") or normalize_excerpt_text(comment.get("normalized_text") or "")
        excerpt_text = normalize_excerpt_text(raw_text)
        if not excerpt_text:
            continue
        excerpts.append(
            {
                "comment_id": canonical_id,
                "excerpt": excerpt_text[:MAX_EXCERPT_CHARS],
            }
        )
        if len(excerpts) >= MAX_EXCERPTS:
            break
    return excerpts


def build_user_message(docket_id: str, cluster: dict, comments_by_id: dict[str, dict]) -> str:
    keywords = cluster.get("top_keywords", [])[:20]
    commenter_mix = cluster.get("commenter_type_distribution", {})
    excerpts = build_excerpts(cluster, comments_by_id)

    lines = [
        f"Docket: {docket_id}",
        f"Cluster ID: {cluster.get('cluster_id')}",
        f"Keywords: {', '.join(keywords) if keywords else '(none)'}",
        "Commenter mix:",
        json.dumps(commenter_mix, indent=2, sort_keys=True),
        (
            "Scale: "
            f"{cluster.get('canonical_count', 0)} unique arguments, "
            f"{cluster.get('total_raw_comments', 0)} total submissions"
        ),
    ]

    if excerpts:
        lines.append("Representative excerpts:")
        for excerpt in excerpts:
            lines.append(f"- {excerpt['comment_id']}: {excerpt['excerpt']}")

    return "\n".join(lines)


def extract_response_text(response) -> str:
    blocks = []
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            blocks.append(text)
    return "\n".join(blocks).strip()


def parse_label_json(raw_text: str) -> tuple[str | None, str | None]:
    payload = json.loads(raw_text)
    label = payload.get("label")
    description = payload.get("description")
    if isinstance(label, str):
        label = label.strip() or None
    else:
        label = None
    if isinstance(description, str):
        description = description.strip() or None
    else:
        description = None
    return label, description


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return round(
        ((input_tokens / 1_000_000) * INPUT_COST_PER_MILLION)
        + ((output_tokens / 1_000_000) * OUTPUT_COST_PER_MILLION),
        4,
    )


def count_prompt_tokens(client: anthropic.Anthropic, model: str, user_message: str) -> int:
    count = client.messages.count_tokens(
        model=model,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return count.input_tokens


def run_audit_for_docket(client: anthropic.Anthropic, docket_id: str, model: str) -> dict | None:
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    themes_path = os.path.join(base_dir, "comment_themes.json")
    comments_path = os.path.join(base_dir, "comments.json")
    audit_path = os.path.join(base_dir, "label_audit.json")

    try:
        themes = read_json(themes_path)
    except (FileNotFoundError, OSError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("ERROR", docket_id, f"missing required theme input {path}")
        return None

    try:
        comments = read_json(comments_path)
    except (FileNotFoundError, OSError):
        comments = []

    comments_by_id = {comment.get("comment_id"): comment for comment in comments if comment.get("comment_id")}

    clusters = []
    total_input_tokens = 0
    for cluster in themes.get("clusters", []):
        user_message = build_user_message(docket_id, cluster, comments_by_id)
        try:
            input_tokens = count_prompt_tokens(client, model, user_message)
        except Exception as exc:
            print_line("ERROR", docket_id, f"audit token counting failed for {cluster.get('cluster_id')}: {exc}")
            return None
        total_input_tokens += input_tokens
        clusters.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": ESTIMATED_OUTPUT_TOKENS,
            }
        )

    estimated_output_tokens = len(clusters) * ESTIMATED_OUTPUT_TOKENS
    payload = {
        "docket_id": docket_id,
        "model": model,
        "cluster_count": len(clusters),
        "estimated_input_tokens": total_input_tokens,
        "estimated_output_tokens": estimated_output_tokens,
        "estimated_cost_usd": estimate_cost_usd(total_input_tokens, estimated_output_tokens),
        "clusters": clusters,
    }
    atomic_write_json(audit_path, payload)
    print_line(
        "AUDIT",
        docket_id,
        f"{len(clusters)} clusters  ~{total_input_tokens} input tokens  ~${payload['estimated_cost_usd']:.2f}",
    )
    return payload


def label_cluster(
    client: anthropic.Anthropic,
    docket_id: str,
    cluster: dict,
    comments_by_id: dict[str, dict],
    model: str,
) -> tuple[str | None, str | None, dict]:
    base_message = build_user_message(docket_id, cluster, comments_by_id)
    attempts = [base_message, base_message + "\n\nRespond with valid JSON only, no text before or after."]

    for user_message in attempts:
        for rate_attempt in range(1, 5):
            try:
                response = client.messages.create(
                    model=model,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_message}],
                    max_tokens=150,
                )
                raw_text = extract_response_text(response)
                label, description = parse_label_json(raw_text)
                usage = getattr(response, "usage", None)
                label_meta = {
                    "prompt_version": PROMPT_VERSION,
                    "model": model,
                    "input_tokens": getattr(usage, "input_tokens", 0),
                    "output_tokens": getattr(usage, "output_tokens", 0),
                }
                return label, description, label_meta
            except anthropic.RateLimitError:
                if rate_attempt >= 4:
                    print_line(
                        "WARN",
                        docket_id,
                        f"{cluster.get('cluster_id')} rate-limited after 3 retries; leaving label empty",
                    )
                    return None, None, {
                        "error": "rate_limit_exceeded",
                        "prompt_version": PROMPT_VERSION,
                        "model": model,
                    }
                time.sleep(2 ** rate_attempt)
            except json.JSONDecodeError:
                break
            except Exception as exc:
                print_line(
                    "WARN",
                    docket_id,
                    f"{cluster.get('cluster_id')} labeling failed with {type(exc).__name__}: {exc}",
                )
                return None, None, {
                    "error": "request_failed",
                    "prompt_version": PROMPT_VERSION,
                    "model": model,
                }

    print_line(
        "WARN",
        docket_id,
        f"{cluster.get('cluster_id')} returned malformed JSON after retry; leaving label empty",
    )
    return None, None, {
        "error": "parse_failed",
        "prompt_version": PROMPT_VERSION,
        "model": model,
    }


def process_docket(
    client: anthropic.Anthropic,
    docket_id: str,
    model: str,
    force: bool,
) -> dict | None:
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    themes_path = os.path.join(base_dir, "comment_themes.json")
    comments_path = os.path.join(base_dir, "comments.json")

    try:
        themes = read_json(themes_path)
    except (FileNotFoundError, OSError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("ERROR", docket_id, f"missing required theme input {path}")
        return None

    try:
        comments = read_json(comments_path)
    except (FileNotFoundError, OSError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("WARN", docket_id, f"missing comments input {path}; proceeding without excerpts")
        comments = []

    comments_by_id = {comment.get("comment_id"): comment for comment in comments if comment.get("comment_id")}
    clusters = themes.get("clusters", [])
    labeled = 0
    skipped = 0
    failed = 0
    total_input_tokens = 0
    total_output_tokens = 0

    for index, cluster in enumerate(clusters, start=1):
        cluster_id = cluster.get("cluster_id", f"{docket_id}_cluster_unknown")
        if cluster.get("label") and not force:
            skipped += 1
            continue

        print_line("LABEL", docket_id, f"{index}/{len(clusters)}  {cluster_id}")
        label, description, label_meta = label_cluster(client, docket_id, cluster, comments_by_id, model)
        if label is None or description is None:
            failed += 1
        else:
            cluster["label"] = label
            cluster["label_description"] = description
            labeled += 1

        cluster["label_meta"] = label_meta
        total_input_tokens += int(label_meta.get("input_tokens", 0) or 0)
        total_output_tokens += int(label_meta.get("output_tokens", 0) or 0)

        if label is None and "label_description" not in cluster:
            cluster["label_description"] = None

    themes["processing_run"] = {
        "phase": "7",
        "script": "label_clusters.py",
        "model": model,
        "prompt_version": PROMPT_VERSION,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "labeled_at": utc_now_iso(),
    }

    atomic_write_json(themes_path, themes)
    print_line(
        "LABEL",
        docket_id,
        (
            f"done  {labeled} labeled  {skipped} skipped  {failed} failed  "
            f"{total_input_tokens} in / {total_output_tokens} out"
        ),
    )
    print_line("LABEL", docket_id, f"written  corpus/{docket_id}/comment_themes.json")
    return {
        "docket_id": docket_id,
        "cluster_count": len(clusters),
        "labeled": labeled,
        "skipped": skipped,
        "failed": failed,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
    }


def main():
    args = parse_args()
    docket_ids = [args.docket] if args.docket else DOCKET_IDS

    try:
        client = build_client(args.base_url)
    except RuntimeError as exc:
        print(f"[ERROR]  {exc}")
        raise SystemExit(1)

    if args.audit:
        audit_summaries = []
        total_clusters = 0
        total_input_tokens = 0
        total_cost = 0.0
        for docket_id in docket_ids:
            payload = run_audit_for_docket(client, docket_id, args.model)
            if payload is None:
                continue
            audit_summaries.append(payload)
            total_clusters += payload["cluster_count"]
            total_input_tokens += payload["estimated_input_tokens"]
            total_cost += payload["estimated_cost_usd"]

        print(
            f"[AUDIT]  total: {total_clusters} clusters  ~{total_input_tokens} input tokens  ~${total_cost:.2f}"
        )
        return

    summaries = []
    total_input_tokens = 0
    total_output_tokens = 0
    for docket_id in docket_ids:
        summary = process_docket(client, docket_id, args.model, args.force)
        if summary is None:
            continue
        summaries.append(summary)
        total_input_tokens += summary["input_tokens"]
        total_output_tokens += summary["output_tokens"]

    print("=== Phase 7 cluster labeling complete ===")
    for summary in summaries:
        print(
            f"{summary['docket_id']}   {summary['cluster_count']} clusters  {summary['labeled']} labeled"
        )
    print(f"Total tokens: {total_input_tokens} in / {total_output_tokens} out")


if __name__ == "__main__":
    main()
