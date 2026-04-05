#!/usr/bin/env python3
"""
Phase 1 — Corpus Fetch and Structure

Builds a local corpus for the accepted V1 docket set using Federal Register and
Regulations.gov data, with a file-based cache layer for all network I/O.

Requires:
  REGULATIONS_GOV_API_KEY environment variable
  pip install requests
"""

import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests


REGS_GOV_API_KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "")
REGS_BASE = "https://api.regulations.gov/v4"
REGS_REQUEST_DELAY = 1.25
LIST_TTL = timedelta(hours=24)
SKIP_XML_TAGS = {"GPH", "MATH", "FTNT", "APPRO", "FRDOC"}
ATTACHMENT_POINTER_RE = re.compile(
    r"\b(see attached|please see attached|attached hereto|see attachment|attachment|attached file|attached document)\b",
    re.IGNORECASE,
)
SUBMITTER_ONLY_RE = re.compile(
    r"^(comment submitted by|submitted by)\b",
    re.IGNORECASE,
)

MANIFEST = [
    {
        "docket_id": "EPA-HQ-OAR-2020-0272",
        "title": "Revised Cross-State Air Pollution Rule Update for the 2008 Ozone NAAQS",
        "proposed_fr_doc_number": "2020-23237",
        "proposed_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2020/10/30/2020-23237.xml",
        "proposed_html_url": "https://www.federalregister.gov/documents/2020/10/30/2020-23237/revised-cross-state-air-pollution-rule-update-for-the-2008-ozone-naaqs",
        "final_fr_doc_number": "2021-05705",
        "final_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2021/04/30/2021-05705.xml",
        "final_html_url": "https://www.federalregister.gov/documents/2021/04/30/2021-05705/revised-cross-state-air-pollution-rule-update-for-the-2008-ozone-naaqs",
        "comment_on_doc_id": "EPA-HQ-OAR-2020-0272-0001",
        "comment_on_object_id": "0900006484941754",
        "expected_total_comments": 85,
        "expected_proposed_sections_approx": 290,
        "expected_final_sections_approx": 297,
    },
    {
        "docket_id": "EPA-HQ-OAR-2018-0225",
        "title": "Determination Regarding Good Neighbor Obligations for the 2008 Ozone NAAQS",
        "proposed_fr_doc_number": "2018-14737",
        "proposed_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2018/07/10/2018-14737.xml",
        "proposed_html_url": "https://www.federalregister.gov/documents/2018/07/10/2018-14737/determination-regarding-good-neighbor-obligations-for-the-2008-ozone-national-ambient-air-quality",
        "final_fr_doc_number": "2018-27160",
        "final_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2018/12/21/2018-27160.xml",
        "final_html_url": "https://www.federalregister.gov/documents/2018/12/21/2018-27160/determination-regarding-good-neighbor-obligations-for-the-2008-ozone-national-ambient-air-quality",
        "comment_on_doc_id": "EPA-HQ-OAR-2018-0225-0001",
        "comment_on_object_id": "09000064834ca2df",
        "expected_total_comments": 317,
        "expected_proposed_sections_approx": 47,
        "expected_final_sections_approx": 48,
    },
    {
        "docket_id": "EPA-HQ-OAR-2020-0430",
        "title": "Primary Copper Smelting NESHAP Reviews",
        "proposed_fr_doc_number": "2021-28273",
        "proposed_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2022/01/11/2021-28273.xml",
        "proposed_html_url": "https://www.federalregister.gov/documents/2022/01/11/2021-28273/national-emission-standards-for-hazardous-air-pollutants-primary-copper-smelting-residual-risk-and",
        "final_fr_doc_number": "2024-09883",
        "final_xml_url": "https://www.federalregister.gov/documents/full_text/xml/2024/05/13/2024-09883.xml",
        "final_html_url": "https://www.federalregister.gov/documents/2024/05/13/2024-09883/national-emission-standards-for-hazardous-air-pollutants-primary-copper-smelting-residual-risk-and",
        "comment_on_doc_id": "EPA-HQ-OAR-2020-0430-0001",
        "comment_on_object_id": "0900006484f17763",
        "expected_total_comments": 22,
        "expected_proposed_sections_approx": 100,
        "expected_final_sections_approx": 144,
    },
]

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")
CACHE_DIR = os.path.join(ROOT_DIR, "cache")
IMMUTABLE_CACHE_DIR = os.path.join(CACHE_DIR, "immutable")
LIST_CACHE_DIR = os.path.join(CACHE_DIR, "lists")

SESSION = requests.Session()
LAST_REGS_REQUEST_AT = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def local_name(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def cache_key_filename(key: str, extension: str) -> str:
    filename = re.sub(r"[^A-Za-z0-9]+", "_", key).strip("_")
    filename = filename[:200] or "cache_entry"
    return f"{filename}{extension}"


def ensure_dirs():
    for path in (CORPUS_DIR, CACHE_DIR, IMMUTABLE_CACHE_DIR, LIST_CACHE_DIR):
        os.makedirs(path, exist_ok=True)
    for docket in MANIFEST:
        os.makedirs(os.path.join(CORPUS_DIR, docket["docket_id"]), exist_ok=True)


def atomic_write_bytes(path: str, data: bytes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "wb") as handle:
        handle.write(data)
    os.replace(tmp_path, path)


def atomic_write_text(path: str, text: str):
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: str, payload):
    atomic_write_text(path, json.dumps(payload, indent=2))


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def print_line(prefix: str, docket_id: str, message: str):
    print(f"[{prefix}]  {docket_id}  {message}")


def prepared_url(url: str, params: dict | None = None) -> str:
    if not params:
        return url
    return f"{url}?{urlencode(params, doseq=True)}"


def sleep_for_regs_if_needed():
    global LAST_REGS_REQUEST_AT
    if LAST_REGS_REQUEST_AT is None:
        return
    elapsed = time.perf_counter() - LAST_REGS_REQUEST_AT
    if elapsed < REGS_REQUEST_DELAY:
        time.sleep(REGS_REQUEST_DELAY - elapsed)


def request_with_retry(url: str, *, params: dict | None = None, headers: dict | None = None, is_regs: bool = False):
    global LAST_REGS_REQUEST_AT

    last_result = None
    for attempt in (1, 2):
        if is_regs:
            sleep_for_regs_if_needed()
        start = time.perf_counter()
        try:
            response = SESSION.get(url, params=params, headers=headers, timeout=30)
            duration_s = time.perf_counter() - start
        except requests.exceptions.RequestException as exc:
            duration_s = time.perf_counter() - start
            if is_regs:
                LAST_REGS_REQUEST_AT = time.perf_counter()
            last_result = {
                "status": "network_error",
                "message": str(exc),
                "duration_s": round(duration_s, 3),
                "response": None,
            }
            if attempt == 1:
                time.sleep(2)
                continue
            return last_result

        if is_regs:
            LAST_REGS_REQUEST_AT = time.perf_counter()

        if response.status_code == 403:
            print("Regulations.gov returned HTTP 403. Check REGULATIONS_GOV_API_KEY and try again.")
            sys.exit(1)
        if response.status_code == 404:
            return {
                "status": "not_found",
                "message": "HTTP 404",
                "duration_s": round(duration_s, 3),
                "response": response,
            }
        if response.status_code == 429:
            if attempt == 1:
                time.sleep(60)
                continue
            return {
                "status": "rate_limited",
                "message": "HTTP 429",
                "duration_s": round(duration_s, 3),
                "response": response,
            }
        if response.status_code != 200:
            last_result = {
                "status": "http_error",
                "message": f"HTTP {response.status_code}",
                "duration_s": round(duration_s, 3),
                "response": response,
            }
            if attempt == 1:
                time.sleep(2)
                continue
            return last_result

        return {
            "status": "ok",
            "message": "OK",
            "duration_s": round(duration_s, 3),
            "response": response,
        }

    return last_result or {
        "status": "unknown_error",
        "message": "Unexpected request failure.",
        "duration_s": None,
        "response": None,
    }


def fetch_immutable_bytes(
    url: str,
    extension: str,
    *,
    headers: dict | None = None,
    is_regs: bool = False,
    expected_content_substring: str | None = None,
):
    path = os.path.join(IMMUTABLE_CACHE_DIR, cache_key_filename(url, extension))
    start = time.perf_counter()
    if os.path.exists(path):
        return {
            "status": "ok",
            "path": path,
            "cache_hit": True,
            "raw_bytes": read_bytes(path),
            "duration_s": round(time.perf_counter() - start, 3),
            "response_headers": {},
        }

    result = request_with_retry(url, headers=headers, is_regs=is_regs)
    if result["status"] != "ok":
        return {
            "status": result["status"],
            "path": path,
            "cache_hit": False,
            "raw_bytes": None,
            "duration_s": result["duration_s"],
            "response_headers": result["response"].headers if result["response"] is not None else {},
            "message": result["message"],
        }

    response_headers = dict(result["response"].headers)
    content_type = response_headers.get("Content-Type", "")
    if expected_content_substring and expected_content_substring.lower() not in content_type.lower():
        return {
            "status": "invalid_content_type",
            "path": path,
            "cache_hit": False,
            "raw_bytes": None,
            "duration_s": result["duration_s"],
            "response_headers": response_headers,
            "message": f"Expected content-type containing {expected_content_substring!r}, got {content_type!r}.",
        }

    raw_bytes = result["response"].content
    atomic_write_bytes(path, raw_bytes)
    return {
        "status": "ok",
        "path": path,
        "cache_hit": False,
        "raw_bytes": raw_bytes,
        "duration_s": result["duration_s"],
        "response_headers": response_headers,
    }


def fetch_list_json(url: str, params: dict):
    full_url = prepared_url(url, params)
    path = os.path.join(LIST_CACHE_DIR, cache_key_filename(full_url, ".json"))
    if os.path.exists(path):
        try:
            envelope = read_json(path)
            cached_at = datetime.fromisoformat(envelope["_cached_at"])
            if utc_now() - cached_at <= LIST_TTL:
                return {
                    "status": "ok",
                    "cache_hit": True,
                    "body": envelope["body"],
                    "path": path,
                    "duration_s": 0.0,
                }
        except Exception:
            pass

    headers = {"X-Api-Key": REGS_GOV_API_KEY}
    result = request_with_retry(url, params=params, headers=headers, is_regs=True)
    if result["status"] != "ok":
        return {
            "status": result["status"],
            "cache_hit": False,
            "body": None,
            "path": path,
            "duration_s": result["duration_s"],
            "message": result["message"],
        }

    body = result["response"].json()
    atomic_write_json(path, {"_cached_at": utc_now_iso(), "body": body})
    return {
        "status": "ok",
        "cache_hit": False,
        "body": body,
        "path": path,
        "duration_s": result["duration_s"],
    }


def fetch_detail_json(comment_id: str):
    url = f"{REGS_BASE}/comments/{comment_id}"
    path = os.path.join(IMMUTABLE_CACHE_DIR, cache_key_filename(comment_id, ".json"))
    if os.path.exists(path):
        try:
            return {
                "status": "ok",
                "cache_hit": True,
                "body": read_json(path),
                "path": path,
                "duration_s": 0.0,
            }
        except Exception:
            pass

    headers = {"X-Api-Key": REGS_GOV_API_KEY}
    result = request_with_retry(url, headers=headers, is_regs=True)
    if result["status"] != "ok":
        return {
            "status": result["status"],
            "cache_hit": False,
            "body": None,
            "path": path,
            "duration_s": result["duration_s"],
            "message": result["message"],
        }

    body = result["response"].json()
    atomic_write_text(path, result["response"].text)
    return {
        "status": "ok",
        "cache_hit": False,
        "body": body,
        "path": path,
        "duration_s": result["duration_s"],
    }


def extract_text(elem) -> str:
    parts = []

    def walk(node):
        if local_name(node.tag) in SKIP_XML_TAGS:
            return
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(elem)
    return normalize_whitespace("".join(parts))


def parse_sections(raw_bytes: bytes, docket_id: str, fr_doc_number: str, document_type: str):
    root = ET.fromstring(raw_bytes)
    sections = []
    current = None
    seq = 1

    def make_section_id(index: int) -> str:
        return f"{docket_id}_{document_type}_{index:04d}"

    def finalize_current():
        nonlocal current, seq
        if not current:
            return
        body_parts = [normalize_whitespace(part) for part in current["paragraphs"] if normalize_whitespace(part)]
        body_text = "\n\n".join(body_parts).strip()
        if body_text:
            sections.append({
                "section_id": make_section_id(seq),
                "docket_id": docket_id,
                "fr_doc_number": fr_doc_number,
                "document_type": document_type,
                "source": current["source"],
                "heading": current["heading"],
                "body_text": body_text,
            })
            seq += 1
        current = None

    def add_section(source: str, heading: str, body_text: str):
        nonlocal seq
        body_text = body_text.strip()
        if not body_text:
            return
        sections.append({
            "section_id": make_section_id(seq),
            "docket_id": docket_id,
            "fr_doc_number": fr_doc_number,
            "document_type": document_type,
            "source": source,
            "heading": heading,
            "body_text": body_text,
        })
        seq += 1

    def start_section(heading: str, source: str):
        nonlocal current
        finalize_current()
        current = {"heading": heading, "source": source, "paragraphs": []}

    def add_paragraph(text: str, source: str):
        nonlocal current
        text = normalize_whitespace(text)
        if not text:
            return
        if current is None:
            current = {"heading": "", "source": source, "paragraphs": []}
        elif current["source"] != source:
            finalize_current()
            current = {"heading": "", "source": source, "paragraphs": []}
        current["paragraphs"].append(text)

    def process(node, source_ctx: str = "other"):
        tag = local_name(node.tag)
        if tag in SKIP_XML_TAGS:
            return

        current_source = source_ctx
        if tag in {"PREAMBLE", "SUPLINF"}:
            current_source = "preamble"
        elif tag == "REGTEXT":
            current_source = "regulatory_text"

        if tag == "HD":
            heading = extract_text(node)
            if heading:
                start_section(heading, current_source)
            return

        if tag == "SECTION":
            finalize_current()
            sectno = ""
            subject = ""
            paragraphs = []
            for descendant in node.iter():
                desc_tag = local_name(descendant.tag)
                if desc_tag == "SECTNO" and not sectno:
                    sectno = extract_text(descendant)
                elif desc_tag == "SUBJECT" and not subject:
                    subject = extract_text(descendant)
                elif desc_tag == "P":
                    text = extract_text(descendant)
                    if text:
                        paragraphs.append(text)
            body_text = "\n\n".join(normalize_whitespace(p) for p in paragraphs if normalize_whitespace(p)).strip()
            heading = normalize_whitespace(f"{sectno} {subject}")
            section_source = "regulatory_text" if sectno else current_source
            add_section(section_source, heading, body_text)
            return

        if tag == "P":
            add_paragraph(extract_text(node), current_source)
            return

        for child in list(node):
            process(child, current_source)

    process(root)
    finalize_current()
    return sections


def section_count_within_tolerance(extracted: int, expected_approx: int) -> bool:
    lower = expected_approx * 0.75
    upper = expected_approx * 1.25
    return lower <= extracted <= upper


def classify_comment_text(text: str) -> str:
    stripped = normalize_whitespace(text)
    if not stripped:
        return "no_text"
    if ATTACHMENT_POINTER_RE.search(stripped) or SUBMITTER_ONLY_RE.match(stripped):
        return "attachment_pointer"
    if len(stripped) >= 10:
        return "substantive_inline"
    return "attachment_pointer"


def derive_submitter_name(title: str | None):
    if not title:
        return None
    title = title.strip()
    patterns = [
        r"^Comment submitted by (.+)$",
        r"^Submitted by (.+)$",
        r"^Comment from (.+)$",
    ]
    for pattern in patterns:
        match = re.match(pattern, title, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def fetch_fr_role(docket: dict, role: str):
    xml_url = docket[f"{role}_xml_url"]
    html_url = docket[f"{role}_html_url"]
    fr_doc_number = docket[f"{role}_fr_doc_number"]
    docket_id = docket["docket_id"]
    corpus_path = os.path.join(CORPUS_DIR, docket_id, f"{role}_rule.xml")
    json_path = os.path.join(CORPUS_DIR, docket_id, f"{role}_rule.json")

    print_line("FR", docket_id, f"{role:<8} {fr_doc_number}  fetching...")
    start = time.perf_counter()
    attempts = []
    chosen = None

    for source_label, url in (("xml", xml_url), ("html", html_url)):
        result = fetch_immutable_bytes(
            url,
            ".xml",
            is_regs=False,
            expected_content_substring="xml" if source_label == "xml" else None,
        )
        attempts.append({
            "source": source_label,
            "url": url,
            "status": result["status"],
            "cache_hit": result.get("cache_hit", False),
        })
        if result["status"] != "ok":
            continue

        chosen = {
            "source_used": source_label,
            "raw_bytes": result["raw_bytes"],
            "cache_hit": result["cache_hit"],
            "duration_s": round(time.perf_counter() - start, 3),
            "content_type": (result.get("response_headers", {}) or {}).get("Content-Type", ""),
        }
        break

    if not chosen:
        print_line("FR", docket_id, f"{role:<8} {fr_doc_number}  failed")
        return {
            "fr_doc_number": fr_doc_number,
            "source_used": None,
            "raw_bytes": 0,
            "sections_extracted": 0,
            "sections_expected_approx": docket[f"expected_{role}_sections_approx"],
            "sections_within_tolerance": False,
            "cache_hit": False,
            "duration_s": round(time.perf_counter() - start, 3),
            "attempts": attempts,
            "warnings": [f"Failed to fetch {role} Federal Register document."],
        }, []

    raw_bytes = chosen["raw_bytes"]
    atomic_write_bytes(corpus_path, raw_bytes)
    warnings = []
    sections = []
    try:
        sections = parse_sections(raw_bytes, docket_id, fr_doc_number, "proposed" if role == "proposed" else "final")
    except Exception as exc:
        warnings.append(f"XML parse failed for {role} document {fr_doc_number}: {exc}")

    atomic_write_json(json_path, sections)
    section_count = len(sections)
    expected = docket[f"expected_{role}_sections_approx"]
    within_tolerance = section_count_within_tolerance(section_count, expected)
    if not within_tolerance:
        warning = (
            f"{role} section count {section_count} is outside ±25% of expected approx {expected}."
        )
        warnings.append(warning)
        print_line("WARN", docket_id, warning)

    print_line(
        "FR",
        docket_id,
        f"{role:<8} {fr_doc_number}  ok  ({len(raw_bytes)} bytes, {section_count} sections)",
    )
    return {
        "fr_doc_number": fr_doc_number,
        "source_used": chosen["source_used"],
        "raw_bytes": len(raw_bytes),
        "sections_extracted": section_count,
        "sections_expected_approx": expected,
        "sections_within_tolerance": within_tolerance,
        "cache_hit": chosen["cache_hit"],
        "duration_s": chosen["duration_s"],
        "attempts": attempts,
        "warnings": warnings,
    }, sections


def fetch_comments_for_docket(docket: dict):
    docket_id = docket["docket_id"]
    object_id = docket["comment_on_object_id"]
    start = time.perf_counter()
    page_number = 1
    total_reported = None
    pages_fetched = 0
    comments = []
    detail_calls_made = 0
    detail_calls_cache_hits = 0
    warnings = []
    aborted = False

    while True:
        page = fetch_list_json(
            f"{REGS_BASE}/comments",
            {
                "filter[commentOnId]": object_id,
                "page[size]": 25,
                "page[number]": page_number,
            },
        )
        if page["status"] != "ok":
            warning = f"Comment list page {page_number} failed with status {page['status']}."
            warnings.append(warning)
            print_line("WARN", docket_id, warning)
            if page["status"] == "rate_limited":
                aborted = True
            break

        body = page["body"] or {}
        page_comments = body.get("data") or []
        meta = body.get("meta") or {}
        total_reported = meta.get("totalElements", total_reported)
        pages_total = math.ceil(total_reported / 25) if total_reported else "?"
        pages_fetched += 1
        print_line("CMTS", docket_id, f"page {page_number}/{pages_total}  {len(page_comments)} records")

        for item in page_comments:
            comment_id = item.get("id")
            attrs = item.get("attributes") or {}
            detail_calls_made += 1
            detail = fetch_detail_json(comment_id)
            if detail["cache_hit"]:
                detail_calls_cache_hits += 1

            text = ""
            if detail["status"] == "ok":
                detail_attrs = ((detail["body"] or {}).get("data") or {}).get("attributes") or {}
                text = normalize_whitespace(detail_attrs.get("comment") or "")
            elif detail["status"] == "not_found":
                warning = f"Comment detail {comment_id} returned 404."
                warnings.append(warning)
                print_line("WARN", docket_id, warning)
            elif detail["status"] == "rate_limited":
                warning = f"Comment detail {comment_id} hit repeated 429; aborting comment sweep."
                warnings.append(warning)
                print_line("WARN", docket_id, warning)
                aborted = True
                break
            else:
                warning = f"Comment detail {comment_id} failed with status {detail['status']}; skipping record."
                warnings.append(warning)
                print_line("WARN", docket_id, warning)
                continue

            classification = classify_comment_text(text)
            print_line("CMTS", docket_id, f"detail  {comment_id}  {classification}")
            comments.append({
                "comment_id": comment_id,
                "docket_id": docket_id,
                "comment_on_doc_id": docket["comment_on_doc_id"],
                "comment_on_object_id": object_id,
                "title": attrs.get("title"),
                "submitter_name": derive_submitter_name(attrs.get("title")),
                "posted_date": (attrs.get("postedDate") or "")[:10] or None,
                "text": text,
                "classification": classification,
                "detail_fallback_used": True,
            })

        if aborted:
            break
        if len(page_comments) < 25:
            break
        if total_reported is not None and len(comments) >= total_reported:
            break
        page_number += 1

    counts = {"substantive_inline": 0, "attachment_pointer": 0, "no_text": 0}
    for comment in comments:
        counts[comment["classification"]] += 1

    total_requests = pages_fetched + detail_calls_made
    wall_clock_s = round(time.perf_counter() - start, 3)
    comments_total_matches_api = (total_reported == len(comments))
    if total_reported is not None and not comments_total_matches_api:
        warning = (
            f"Fetched {len(comments)} comments but API reported {total_reported}."
        )
        warnings.append(warning)
        print_line("WARN", docket_id, warning)

    return {
        "comment_on_object_id": object_id,
        "total_reported_by_api": total_reported,
        "total_fetched": len(comments),
        "list_pages_fetched": pages_fetched,
        "detail_calls_made": detail_calls_made,
        "detail_calls_cache_hits": detail_calls_cache_hits,
        "substantive_inline": counts["substantive_inline"],
        "attachment_pointer": counts["attachment_pointer"],
        "no_text": counts["no_text"],
        "total_requests": total_requests,
        "wall_clock_s": wall_clock_s,
        "comments_total_matches_api": comments_total_matches_api,
        "warnings": warnings,
        "aborted": aborted,
    }, comments


def write_docket_outputs(docket: dict, proposed_log: dict, final_log: dict, comments_log: dict, comments: list):
    docket_dir = os.path.join(CORPUS_DIR, docket["docket_id"])
    comments_path = os.path.join(docket_dir, "comments.json")
    log_path = os.path.join(docket_dir, "fetch_log.json")
    atomic_write_json(comments_path, comments)

    validation = {
        "fr_proposed_sections_within_tolerance": proposed_log["sections_within_tolerance"],
        "fr_final_sections_within_tolerance": final_log["sections_within_tolerance"],
        "comments_total_matches_api": comments_log["comments_total_matches_api"],
    }
    validation["passed"] = all(validation.values())

    fetch_log = {
        "docket_id": docket["docket_id"],
        "generated_at": utc_now_iso(),
        "fr": {
            "proposed": {k: proposed_log[k] for k in (
                "fr_doc_number",
                "source_used",
                "raw_bytes",
                "sections_extracted",
                "sections_expected_approx",
                "sections_within_tolerance",
                "cache_hit",
                "duration_s",
            )},
            "final": {k: final_log[k] for k in (
                "fr_doc_number",
                "source_used",
                "raw_bytes",
                "sections_extracted",
                "sections_expected_approx",
                "sections_within_tolerance",
                "cache_hit",
                "duration_s",
            )},
        },
        "comments": {
            "comment_on_object_id": comments_log["comment_on_object_id"],
            "total_reported_by_api": comments_log["total_reported_by_api"],
            "total_fetched": comments_log["total_fetched"],
            "list_pages_fetched": comments_log["list_pages_fetched"],
            "detail_calls_made": comments_log["detail_calls_made"],
            "detail_calls_cache_hits": comments_log["detail_calls_cache_hits"],
            "substantive_inline": comments_log["substantive_inline"],
            "attachment_pointer": comments_log["attachment_pointer"],
            "no_text": comments_log["no_text"],
            "total_requests": comments_log["total_requests"],
            "wall_clock_s": comments_log["wall_clock_s"],
            "aborted": comments_log["aborted"],
        },
        "validation": validation,
    }
    warnings = proposed_log["warnings"] + final_log["warnings"] + comments_log["warnings"]
    if warnings:
        fetch_log["warnings"] = warnings
    atomic_write_json(log_path, fetch_log)
    print_line("LOG", docket["docket_id"], f"written  corpus/{docket['docket_id']}/fetch_log.json")
    return fetch_log


def print_summary(summary_rows: list, overall_passed: bool):
    print("\n=== Phase 1 corpus fetch complete ===")
    for row in summary_rows:
        print(
            f"{row['docket_id']}   proposed {row['proposed_sections']} sections | "
            f"final {row['final_sections']} sections | {row['comments']} comments "
            f"({row['substantive']} substantive)"
        )
    print(f"Validation: {'PASS' if overall_passed else 'WARN'}")


def main() -> int:
    if not REGS_GOV_API_KEY:
        print("REGULATIONS_GOV_API_KEY is required.")
        return 1

    ensure_dirs()
    summary_rows = []
    overall_passed = True

    for docket in MANIFEST:
        proposed_log, _ = fetch_fr_role(docket, "proposed")
        final_log, _ = fetch_fr_role(docket, "final")
        comments_log, comments = fetch_comments_for_docket(docket)
        fetch_log = write_docket_outputs(docket, proposed_log, final_log, comments_log, comments)

        if not fetch_log["validation"]["passed"]:
            overall_passed = False

        summary_rows.append({
            "docket_id": docket["docket_id"],
            "proposed_sections": proposed_log["sections_extracted"],
            "final_sections": final_log["sections_extracted"],
            "comments": comments_log["total_fetched"],
            "substantive": comments_log["substantive_inline"],
        })

    print_summary(summary_rows, overall_passed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
