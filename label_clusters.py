#!/usr/bin/env python3

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone

import requests

import ollama_runtime


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

DEFAULT_MODEL = "qwen3:14b"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_NUM_PREDICT = 1024
DEFAULT_TIMEOUT_SECONDS = 180
PROMPT_VERSION = "v1"
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


class OllamaClient:
    def __init__(
        self,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        session: requests.Session | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ):
        self.ollama_url = ollama_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def chat(self, model: str, system_prompt: str, user_message: str) -> dict:
        payload = {
            "model": model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "options": {"num_predict": DEFAULT_NUM_PREDICT},
        }
        endpoint = f"{self.ollama_url}/api/chat"

        try:
            response = self.session.post(endpoint, json=payload, timeout=self.timeout_seconds)
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(
                f"Ollama timed out at {self.ollama_url}. Check the model load time or try again."
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            raise RuntimeError(
                f"Could not reach Ollama at {self.ollama_url}. Start `ollama serve` and try again."
            ) from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        if response.status_code != 200:
            detail = response.text.strip()
            try:
                payload = response.json()
            except ValueError:
                payload = None
            if isinstance(payload, dict) and payload.get("error"):
                detail = str(payload["error"])

            if response.status_code == 404 and "not found" in detail.lower():
                raise RuntimeError(
                    f"Model `{model}` is not available in Ollama. Run `ollama pull {model}` first."
                )
            raise RuntimeError(f"Ollama returned HTTP {response.status_code}: {detail}")

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Ollama returned malformed JSON.") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Ollama returned an unexpected response payload.")
        return payload


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
    parser = argparse.ArgumentParser(description="Label clustered docket themes with a local Ollama model.")
    parser.add_argument("--force", action="store_true", help="Re-label clusters that already have labels.")
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Process a single docket.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model identifier to use for labeling.")
    parser.add_argument(
        "--ollama-url",
        default=DEFAULT_OLLAMA_URL,
        help="Base URL for the local Ollama daemon (default: http://localhost:11434).",
    )
    parser.add_argument(
        "--no-think",
        action="store_true",
        help="Append /no_think to prompts (recommended for qwen3:14b).",
    )
    return parser.parse_args()


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


def ns_to_ms(value) -> float:
    raw_value = int(value or 0)
    return round(raw_value / 1_000_000, 1)


def extract_response_text(response_payload: dict) -> str:
    message = response_payload.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("Ollama response did not include a message object.")

    content = message.get("content")
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts).strip()

    raise RuntimeError("Ollama response did not include assistant text content.")


def parse_label_json(raw_text: str) -> tuple[str | None, str | None]:
    cleaned = (raw_text or "").strip()
    if cleaned.startswith("```"):
        fence_match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
        if fence_match:
            cleaned = fence_match.group(1).strip()

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise
        payload = json.loads(cleaned[start : end + 1])

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


def empty_label_meta(model: str, no_think: bool) -> dict:
    return {
        "runtime": "ollama",
        "prompt_version": PROMPT_VERSION,
        "model": model,
        "no_think": no_think,
        "request_count": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "total_duration_ms": 0.0,
        "load_duration_ms": 0.0,
        "prompt_eval_duration_ms": 0.0,
        "eval_duration_ms": 0.0,
    }


def apply_response_usage(label_meta: dict, response_payload: dict) -> None:
    label_meta["request_count"] += 1
    label_meta["input_tokens"] += int(response_payload.get("prompt_eval_count") or 0)
    label_meta["output_tokens"] += int(response_payload.get("eval_count") or 0)
    label_meta["total_duration_ms"] += ns_to_ms(response_payload.get("total_duration"))
    label_meta["load_duration_ms"] += ns_to_ms(response_payload.get("load_duration"))
    label_meta["prompt_eval_duration_ms"] += ns_to_ms(response_payload.get("prompt_eval_duration"))
    label_meta["eval_duration_ms"] += ns_to_ms(response_payload.get("eval_duration"))


def label_cluster(
    client,
    docket_id: str,
    cluster: dict,
    comments_by_id: dict[str, dict],
    model: str,
    no_think: bool = False,
) -> tuple[str | None, str | None, dict]:
    base_message = build_user_message(docket_id, cluster, comments_by_id)
    if no_think:
        base_message += "\n\n/no_think"
    retry_suffix = "\n\nRespond with valid JSON only, no text before or after."
    if no_think:
        retry_suffix += "\n\n/no_think"
    attempts = [base_message, base_message + retry_suffix]
    label_meta = empty_label_meta(model, no_think)

    for user_message in attempts:
        try:
            response_payload = client.chat(model, SYSTEM_PROMPT, user_message)
        except RuntimeError as exc:
            label_meta["error"] = "request_failed"
            label_meta["error_detail"] = str(exc)
            print_line(
                "WARN",
                docket_id,
                f"{cluster.get('cluster_id')} labeling failed: {exc}",
            )
            return None, None, label_meta

        apply_response_usage(label_meta, response_payload)

        try:
            raw_text = extract_response_text(response_payload)
        except RuntimeError as exc:
            label_meta["error"] = "malformed_response"
            label_meta["error_detail"] = str(exc)
            print_line(
                "WARN",
                docket_id,
                f"{cluster.get('cluster_id')} returned malformed content: {exc}",
            )
            return None, None, label_meta

        try:
            label, description = parse_label_json(raw_text)
        except json.JSONDecodeError:
            continue

        return label, description, label_meta

    label_meta["error"] = "parse_failed"
    print_line(
        "WARN",
        docket_id,
        f"{cluster.get('cluster_id')} returned malformed JSON after retry; leaving label empty",
    )
    return None, None, label_meta


def build_cluster_run_record(cluster: dict, status: str) -> dict:
    label_meta = cluster.get("label_meta") if isinstance(cluster.get("label_meta"), dict) else {}
    return {
        "cluster_id": cluster.get("cluster_id"),
        "status": status,
        "label": cluster.get("label"),
        "label_description": cluster.get("label_description"),
        "input_tokens": int(label_meta.get("input_tokens", 0) or 0),
        "output_tokens": int(label_meta.get("output_tokens", 0) or 0),
        "total_duration_ms": round(float(label_meta.get("total_duration_ms", 0.0) or 0.0), 1),
        "load_duration_ms": round(float(label_meta.get("load_duration_ms", 0.0) or 0.0), 1),
        "prompt_eval_duration_ms": round(
            float(label_meta.get("prompt_eval_duration_ms", 0.0) or 0.0), 1
        ),
        "eval_duration_ms": round(float(label_meta.get("eval_duration_ms", 0.0) or 0.0), 1),
        "request_count": int(label_meta.get("request_count", 0) or 0),
        "error": label_meta.get("error"),
        "error_detail": label_meta.get("error_detail"),
    }


def build_processing_run(
    docket_id: str,
    client: OllamaClient,
    model: str,
    model_profile: dict | None,
    no_think: bool,
    started_at: str,
    completed_at: str,
    wall_clock_ms: float,
    cluster_count: int,
    labeled: int,
    skipped: int,
    failed: int,
    total_input_tokens: int,
    total_output_tokens: int,
    total_duration_ms: float,
    total_load_duration_ms: float,
    total_prompt_eval_duration_ms: float,
    total_eval_duration_ms: float,
) -> dict:
    return {
        "phase": "7",
        "script": "label_clusters.py",
        "runtime": "ollama",
        "docket_id": docket_id,
        "model": model,
        "model_profile": ollama_runtime.profile_for_manifest(model_profile),
        "prompt_version": PROMPT_VERSION,
        "ollama_url": client.ollama_url,
        "no_think": no_think,
        "started_at": started_at,
        "completed_at": completed_at,
        "wall_clock_ms": round(wall_clock_ms, 1),
        "cluster_count": cluster_count,
        "labeled": labeled,
        "skipped": skipped,
        "failed": failed,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_duration_ms": round(total_duration_ms, 1),
        "total_load_duration_ms": round(total_load_duration_ms, 1),
        "total_prompt_eval_duration_ms": round(total_prompt_eval_duration_ms, 1),
        "total_eval_duration_ms": round(total_eval_duration_ms, 1),
    }


def process_docket(
    client: OllamaClient,
    docket_id: str,
    model: str,
    force: bool,
    no_think: bool = False,
    model_profile: dict | None = None,
) -> dict | None:
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    themes_path = os.path.join(base_dir, "comment_themes.json")
    comments_path = os.path.join(base_dir, "comments.json")
    label_run_path = os.path.join(base_dir, "label_run.json")

    try:
        themes = read_json(themes_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("ERROR", docket_id, f"missing required theme input {path}")
        return None

    try:
        comments = read_json(comments_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("WARN", docket_id, f"missing comments input {path}; proceeding without excerpts")
        comments = []

    comments_by_id = {comment.get("comment_id"): comment for comment in comments if comment.get("comment_id")}
    clusters = themes.get("clusters", [])

    started_at = utc_now_iso()
    started_clock = time.perf_counter()
    labeled = 0
    skipped = 0
    failed = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0.0
    total_load_duration_ms = 0.0
    total_prompt_eval_duration_ms = 0.0
    total_eval_duration_ms = 0.0
    cluster_runs = []

    for index, cluster in enumerate(clusters, start=1):
        cluster_id = cluster.get("cluster_id", f"{docket_id}_cluster_unknown")
        if cluster.get("label") and not force:
            skipped += 1
            cluster_runs.append(build_cluster_run_record(cluster, "skipped"))
            continue

        print_line("LABEL", docket_id, f"{index}/{len(clusters)}  {cluster_id}")
        label, description, label_meta = label_cluster(
            client,
            docket_id,
            cluster,
            comments_by_id,
            model,
            no_think=no_think,
        )
        cluster["label"] = label
        cluster["label_description"] = description
        cluster["label_meta"] = label_meta

        total_input_tokens += int(label_meta.get("input_tokens", 0) or 0)
        total_output_tokens += int(label_meta.get("output_tokens", 0) or 0)
        total_duration_ms += float(label_meta.get("total_duration_ms", 0.0) or 0.0)
        total_load_duration_ms += float(label_meta.get("load_duration_ms", 0.0) or 0.0)
        total_prompt_eval_duration_ms += float(
            label_meta.get("prompt_eval_duration_ms", 0.0) or 0.0
        )
        total_eval_duration_ms += float(label_meta.get("eval_duration_ms", 0.0) or 0.0)

        if label is None:
            failed += 1
            cluster_runs.append(build_cluster_run_record(cluster, "failed"))
        else:
            labeled += 1
            cluster_runs.append(build_cluster_run_record(cluster, "labeled"))

    wall_clock_ms = (time.perf_counter() - started_clock) * 1000.0
    completed_at = utc_now_iso()
    processing_run = build_processing_run(
        docket_id,
        client,
        model,
        model_profile or ollama_runtime.resolve_model_profile(model),
        no_think,
        started_at,
        completed_at,
        wall_clock_ms,
        len(clusters),
        labeled,
        skipped,
        failed,
        total_input_tokens,
        total_output_tokens,
        total_duration_ms,
        total_load_duration_ms,
        total_prompt_eval_duration_ms,
        total_eval_duration_ms,
    )
    themes["processing_run"] = processing_run

    label_run_payload = {
        "schema_version": "v1",
        **processing_run,
        "clusters": cluster_runs,
    }

    atomic_write_json(themes_path, themes)
    atomic_write_json(label_run_path, label_run_payload)
    print_line(
        "LABEL",
        docket_id,
        (
            f"done  {labeled} labeled  {skipped} skipped  {failed} failed  "
            f"{total_input_tokens} in / {total_output_tokens} out"
        ),
    )
    print_line("LABEL", docket_id, f"written  corpus/{docket_id}/comment_themes.json")
    print_line("LABEL", docket_id, f"written  corpus/{docket_id}/label_run.json")
    return {
        "docket_id": docket_id,
        "cluster_count": len(clusters),
        "labeled": labeled,
        "skipped": skipped,
        "failed": failed,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_duration_ms": round(total_duration_ms, 1),
        "wall_clock_ms": round(wall_clock_ms, 1),
        "model_profile": ollama_runtime.profile_for_manifest(
            model_profile or ollama_runtime.resolve_model_profile(model)
        ),
    }


def main():
    args = parse_args()
    docket_ids = [args.docket] if args.docket else DOCKET_IDS
    client = OllamaClient(args.ollama_url)
    preflight = ollama_runtime.run_preflight(
        args.ollama_url,
        args.model,
        session=getattr(client, "session", None),
        timeout_seconds=getattr(client, "timeout_seconds", ollama_runtime.DEFAULT_TIMEOUT_SECONDS),
    )
    model_profile = preflight["profile"]
    for line in ollama_runtime.preflight_summary_lines(preflight):
        print(f"[PREFLIGHT]  {line}")

    summaries = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_duration_ms = 0.0

    for docket_id in docket_ids:
        summary = process_docket(
            client,
            docket_id,
            args.model,
            args.force,
            no_think=args.no_think,
            model_profile=model_profile,
        )
        if summary is None:
            continue
        summaries.append(summary)
        total_input_tokens += summary["input_tokens"]
        total_output_tokens += summary["output_tokens"]
        total_duration_ms += summary["total_duration_ms"]

    print("=== Phase 7 cluster labeling complete ===")
    for summary in summaries:
        print(
            f"{summary['docket_id']}   {summary['cluster_count']} clusters  {summary['labeled']} labeled"
        )
    print(
        f"Total tokens: {total_input_tokens} in / {total_output_tokens} out  "
        f"({round(total_duration_ms, 1)} ms model time)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
