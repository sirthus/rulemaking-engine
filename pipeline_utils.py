#!/usr/bin/env python3

import html
import json
import os
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any


DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

# Canonical core stopwords shared across the pipeline. Scripts that need
# additional domain-specific words can layer them on top locally.
STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "of",
    "in",
    "to",
    "for",
    "on",
    "at",
    "by",
    "with",
    "from",
    "as",
    "is",
    "are",
    "be",
    "we",
    "our",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "do",
    "does",
    "how",
    "what",
    "which",
    "under",
    "per",
}

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_OUTLINE_PREFIX_RE = re.compile(r"^(?:[IVXivx]+|[A-Za-z]|\d)\.\s+")
_CFR_HEADING_RE = re.compile(r"^\d{2,}\.\d+\b")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_bytes(path: str, data: bytes) -> None:
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "wb") as handle:
        handle.write(data)
    os.replace(tmp_path, path)


def atomic_write_text(path: str, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: str, payload: Any, *, trailing_newline: bool = False) -> None:
    suffix = "\n" if trailing_newline else ""
    atomic_write_text(path, json.dumps(payload, indent=2) + suffix)


def normalize_whitespace(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_text(text: str | None, *, strip_html: bool = False) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    if strip_html:
        normalized = html.unescape(normalized)
        normalized = _HTML_TAG_RE.sub(" ", normalized)
    return normalize_whitespace(normalized.lower())


def normalize_heading(heading: str | None, *, strip_outline_prefix: bool = False) -> str:
    original_heading = unicodedata.normalize("NFKC", heading or "").strip()
    if (
        strip_outline_prefix
        and not original_heading.startswith("§")
        and not _CFR_HEADING_RE.match(original_heading)
    ):
        original_heading = _OUTLINE_PREFIX_RE.sub("", original_heading)

    heading_text = normalize_text(original_heading)
    heading_text = heading_text.replace("§", " ")
    heading_text = re.sub(r"[^a-z0-9\s]+", " ", heading_text)
    return normalize_whitespace(heading_text)


def print_line(prefix: str, docket_id: str | None = None, message: str | None = None) -> None:
    if message is None:
        if docket_id is None:
            raise ValueError("print_line requires a message.")
        print(f"[{prefix}]  {docket_id}")
        return

    if docket_id:
        print(f"[{prefix}]  {docket_id}  {message}")
        return

    print(f"[{prefix}]  {message}")
