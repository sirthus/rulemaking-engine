#!/usr/bin/env python3
"""
Phase 0.5 API Integration Spike — Rulemaking Engine

This standalone script validates the external integration surface for the
accepted V1 docket set. It produces:
  - integration_spike_results.json
  - INTEGRATION_NOTE.md

It measures:
  - Federal Register document download size and structure
  - Regulations.gov comment volume and sample text mix
  - observed response timings and rate-limit behavior
  - caching requirements and confirmed integration gaps

Requires:
  REGULATIONS_GOV_API_KEY environment variable for Regulations.gov checks
  pip install requests
"""

import json
import math
import os
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from html import unescape

import requests


REGS_GOV_API_KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "")
FR_BASE = "https://www.federalregister.gov/api/v1"
REGS_BASE = "https://api.regulations.gov/v4"
REGS_REQUEST_DELAY = 1.25
MAX_REGS_DOCUMENT_PAGES = 4
TEXT_PREVIEW_CHARS = 160

CANDIDATES = [
    {
        "sequence": 1,
        "docket_id": "EPA-HQ-OAR-2020-0272",
        "title": "Revised Cross-State Air Pollution Rule Update for the 2008 Ozone NAAQS",
    },
    {
        "sequence": 2,
        "docket_id": "EPA-HQ-OAR-2018-0225",
        "title": "Determination Regarding Good Neighbor Obligations for the 2008 Ozone NAAQS",
    },
    {
        "sequence": 3,
        "docket_id": "EPA-HQ-OAR-2020-0430",
        "title": "Primary Copper Smelting National Emission Standards for Hazardous Air Pollutants Reviews (Subparts QQQ and EEEEEE)",
    },
]

STOPWORDS = {
    "a", "an", "and", "for", "from", "in", "of", "the", "to", "with",
}

NON_MAIN_DOC_KEYWORDS = {
    "correction",
    "correcting",
    "corrections",
    "delay",
    "extension",
    "extend",
    "notice of availability",
    "notice of data availability",
    "petition",
    "public hearing",
    "reconsideration",
    "remand",
    "reopening",
    "stay",
    "supplemental notice",
    "technical amendment",
    "technical correction",
    "withdrawal",
}

ATTACHMENT_POINTER_RE = re.compile(
    r"^\s*(?:please\s+)?see\s+attach\w*\.?\s*$"
    r"|^\s*(?:please\s+)?see\s+(?:the\s+)?attached\s+(?:file|document|comment|pdf)s?\.?\s*$"
    r"|^\s*attach\w*\s+only\.?\s*$"
    r"|^\s*comment\s+(?:is\s+)?attach\w*\.?\s*$"
    r"|^\s*refer\s+to\s+attach\w*\.?\s*$",
    re.IGNORECASE,
)

SESSION = requests.Session()
HTTP_EVENTS = []
LAST_REGS_REQUEST_AT = None


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_for_match(text: str) -> str:
    cleaned = (text or "").lower()
    cleaned = cleaned.replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"[^a-z0-9\s-]", " ", cleaned)
    return normalize_whitespace(cleaned)


def significant_tokens(text: str) -> list:
    tokens = []
    for token in normalize_for_match(text).split():
        if len(token) >= 4 and token not in STOPWORDS:
            tokens.append(token)
    return tokens


def title_alignment_metrics(candidate_title: str, document_title: str) -> dict:
    candidate_tokens = set(significant_tokens(candidate_title))
    document_tokens = set(significant_tokens(document_title))
    overlap = sorted(candidate_tokens & document_tokens)
    ratio = 0.0
    if candidate_tokens:
        ratio = len(overlap) / len(candidate_tokens)
    return {
        "candidate_tokens": sorted(candidate_tokens),
        "document_tokens": sorted(document_tokens),
        "overlap_tokens": overlap,
        "overlap_count": len(overlap),
        "overlap_ratio": round(ratio, 3),
    }


def doc_has_non_main_keyword(title: str, action: str) -> bool:
    haystack = normalize_for_match(f"{title} {action}")
    return any(keyword in haystack for keyword in NON_MAIN_DOC_KEYWORDS)


def strip_markup(raw_text: str) -> str:
    text = raw_text or ""
    text = re.sub(r"<\?xml.*?\?>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def preview(text: str, limit: int = TEXT_PREVIEW_CHARS) -> str:
    compact = normalize_whitespace(text)
    if len(compact) <= limit:
        return compact
    return compact[:limit].rstrip() + "..."


def safe_json(resp: requests.Response) -> dict:
    try:
        return resp.json() if resp.content else {}
    except ValueError:
        return {}


def extract_visible_comment_text(attrs: dict) -> str:
    text = (attrs or {}).get("comment") or (attrs or {}).get("commentText") or ""
    return text.strip()


def is_substantive_inline_text(text: str) -> bool:
    if not text or not text.strip():
        return False
    stripped = normalize_whitespace(text)
    if len(stripped) < 30:
        return ATTACHMENT_POINTER_RE.match(stripped) is None and len(stripped) > 5
    return ATTACHMENT_POINTER_RE.match(stripped) is None


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def round_seconds(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 3)


def record_http_event(service: str, method: str, url: str, status_code: int | None, duration_s: float, params: dict | None):
    HTTP_EVENTS.append({
        "service": service,
        "method": method,
        "url": url,
        "status_code": status_code,
        "duration_seconds": round_seconds(duration_s),
        "params": params or {},
    })


def perform_request(service: str, url: str, params: dict | None = None, headers: dict | None = None) -> dict:
    global LAST_REGS_REQUEST_AT

    if service == "regs":
        if not REGS_GOV_API_KEY:
            return {
                "status": "auth_failure",
                "http_status": None,
                "message": "REGULATIONS_GOV_API_KEY is not set. Authentication is unverified.",
                "body": None,
                "response": None,
            }
        if LAST_REGS_REQUEST_AT is not None:
            elapsed = time.perf_counter() - LAST_REGS_REQUEST_AT
            if elapsed < REGS_REQUEST_DELAY:
                time.sleep(REGS_REQUEST_DELAY - elapsed)

    start = time.perf_counter()
    try:
        response = SESSION.get(url, params=params, headers=headers, timeout=30)
        duration_s = time.perf_counter() - start
    except requests.RequestException as exc:
        duration_s = time.perf_counter() - start
        record_http_event(service, "GET", url, None, duration_s, params)
        if service == "regs":
            LAST_REGS_REQUEST_AT = time.perf_counter()
        return {
            "status": "network_error",
            "http_status": None,
            "message": f"Request failed: {exc}",
            "body": None,
            "response": None,
        }

    record_http_event(service, "GET", response.url, response.status_code, duration_s, params)
    if service == "regs":
        LAST_REGS_REQUEST_AT = time.perf_counter()

    status_code = response.status_code
    body = safe_json(response)

    if service == "fr":
        if status_code == 200:
            return {
                "status": "ok",
                "http_status": status_code,
                "message": "OK",
                "body": body,
                "response": response,
            }
        return {
            "status": "http_error",
            "http_status": status_code,
            "message": f"Federal Register returned HTTP {status_code}.",
            "body": body,
            "response": response,
        }

    if status_code == 200:
        return {
            "status": "ok",
            "http_status": status_code,
            "message": "OK",
            "body": body,
            "response": response,
        }
    if status_code in (401, 403):
        detail = "api_key_rejected" if REGS_GOV_API_KEY else "missing_api_key"
        return {
            "status": "auth_failure",
            "http_status": status_code,
            "message": "Regulations.gov authentication failed. Do not interpret this as data absence.",
            "auth_detail": detail,
            "body": body,
            "response": response,
        }
    if status_code == 404:
        return {
            "status": "not_found",
            "http_status": status_code,
            "message": "Regulations.gov returned 404.",
            "body": body,
            "response": response,
        }
    if status_code == 429:
        return {
            "status": "rate_limited",
            "http_status": status_code,
            "message": "Regulations.gov rate limit encountered. Do not interpret this as missing data.",
            "body": body,
            "response": response,
        }
    return {
        "status": "unexpected_http_status",
        "http_status": status_code,
        "message": f"Unexpected Regulations.gov status {status_code}.",
        "body": body,
        "response": response,
    }


def get_fr(path: str, params: dict) -> dict:
    return perform_request("fr", f"{FR_BASE}/{path}", params=params)


def get_regs(path: str, params: dict) -> dict:
    headers = {"X-Api-Key": REGS_GOV_API_KEY} if REGS_GOV_API_KEY else {}
    return perform_request("regs", f"{REGS_BASE}/{path}", params=params, headers=headers)


def summarize_fr_doc(doc: dict, candidate_title: str) -> dict:
    metrics = title_alignment_metrics(candidate_title, doc.get("title") or "")
    title = doc.get("title") or ""
    action = doc.get("action") or ""
    xml_url = doc.get("full_text_xml_url")
    html_url = doc.get("html_url")
    return {
        "document_number": doc.get("document_number"),
        "document_type": doc.get("type"),
        "title": title,
        "publication_date": doc.get("publication_date"),
        "action": action,
        "has_xml": bool(xml_url),
        "has_html": bool(html_url),
        "full_text_xml_url": xml_url,
        "html_url": html_url,
        "non_main_keyword_flag": doc_has_non_main_keyword(title, action),
        "title_alignment": metrics,
    }


def sort_fr_candidates(docs: list) -> list:
    def sort_key(doc: dict):
        metrics = doc.get("title_alignment") or {}
        overlap_count = metrics.get("overlap_count", 0)
        overlap_ratio = metrics.get("overlap_ratio", 0.0)
        non_main = 1 if doc.get("non_main_keyword_flag") else 0
        has_text = 1 if (doc.get("has_xml") or doc.get("has_html")) else 0
        date = doc.get("publication_date") or "9999-99-99"
        return (non_main, -overlap_count, -overlap_ratio, -has_text, date)

    return sorted(docs, key=sort_key)


def choose_main_fr_document(docs: list, doc_label: str) -> dict:
    if not docs:
        return {
            "status": "missing",
            "doc_label": doc_label,
            "selected": None,
            "notes": [f"No {doc_label} documents found in Federal Register results."],
        }

    ranked = sort_fr_candidates(docs)
    plausible = []
    for doc in ranked:
        metrics = doc.get("title_alignment") or {}
        materially_aligned = metrics.get("overlap_count", 0) >= 2
        if materially_aligned and not doc.get("non_main_keyword_flag"):
            plausible.append(doc)

    if plausible:
        selected = plausible[0]
        if len(plausible) > 1:
            return {
                "status": "ambiguous",
                "doc_label": doc_label,
                "selected": selected,
                "notes": [
                    f"Multiple plausible {doc_label} documents matched the candidate title; selected the earliest best-aligned option."
                ],
            }
        return {
            "status": "selected",
            "doc_label": doc_label,
            "selected": selected,
            "notes": [f"Selected the best-aligned {doc_label} document."],
        }

    non_main_filtered = [doc for doc in ranked if not doc.get("non_main_keyword_flag")]
    selected = non_main_filtered[0] if non_main_filtered else ranked[0]
    return {
        "status": "weak_match",
        "doc_label": doc_label,
        "selected": selected,
        "notes": [
            f"No materially aligned {doc_label} document found; selected the earliest non-excluded option for manual review."
        ],
    }


def fetch_fr_documents(candidate: dict) -> dict:
    params = {
        "conditions[docket_id]": candidate["docket_id"],
        "fields[]": [
            "document_number",
            "type",
            "title",
            "publication_date",
            "full_text_xml_url",
            "html_url",
            "action",
        ],
        "per_page": 100,
        "order": "oldest",
    }
    response = get_fr("documents", params)
    if response["status"] != "ok":
        return response

    docs = response["body"].get("results", [])
    proposed_docs = [
        summarize_fr_doc(doc, candidate["title"])
        for doc in docs
        if doc.get("type") == "Proposed Rule"
    ]
    final_docs = [
        summarize_fr_doc(doc, candidate["title"])
        for doc in docs
        if doc.get("type") == "Rule"
    ]
    proposed_choice = choose_main_fr_document(proposed_docs, "proposed rule")
    final_choice = choose_main_fr_document(final_docs, "final rule")
    return {
        "status": "ok",
        "all_proposed_rule_documents": proposed_docs,
        "all_final_rule_documents": final_docs,
        "proposed_choice": proposed_choice,
        "final_choice": final_choice,
    }


def count_section_markers(raw_text: str, source_label: str) -> tuple[int, str]:
    if source_label == "xml":
        count = len(re.findall(r"<(?:HD|SECTION)\b", raw_text or "", flags=re.IGNORECASE))
        return count, "Counted <HD> and <SECTION> tags in XML."
    count = len(re.findall(r"<(?:h[1-6]|section)\b", raw_text or "", flags=re.IGNORECASE))
    return count, "XML unavailable; counted heading/section tags in HTML."


def measure_fr_download(doc: dict, role: str) -> dict:
    if not doc:
        return {
            "role": role,
            "status": "not_selected",
            "attempts": [],
            "message": "No Federal Register document was selected for download.",
        }

    attempts = []
    for source_label, url in (("xml", doc.get("full_text_xml_url")), ("html", doc.get("html_url"))):
        if not url:
            continue
        response = perform_request("fr", url)
        attempt = {
            "source": source_label,
            "url": url,
            "status": response["status"],
            "http_status": response.get("http_status"),
            "message": response["message"],
        }
        attempts.append(attempt)
        if response["status"] != "ok":
            continue

        raw_bytes = response["response"].content
        raw_text = response["response"].text
        cleaned_text = strip_markup(raw_text)
        section_count, section_note = count_section_markers(raw_text, source_label)
        return {
            "role": role,
            "document_number": doc.get("document_number"),
            "title": doc.get("title"),
            "publication_date": doc.get("publication_date"),
            "source_used": source_label,
            "url_used": url,
            "content_type": response["response"].headers.get("Content-Type"),
            "raw_bytes": len(raw_bytes),
            "stripped_character_count": len(cleaned_text),
            "word_count": len(re.findall(r"\b\S+\b", cleaned_text)),
            "approx_section_count": section_count,
            "section_count_note": section_note,
            "download_duration_seconds": next(
                (event["duration_seconds"] for event in reversed(HTTP_EVENTS) if event["url"] == response["response"].url),
                None,
            ),
            "preview": preview(cleaned_text),
            "attempts": attempts,
            "status": "ok",
        }

    return {
        "role": role,
        "document_number": doc.get("document_number"),
        "title": doc.get("title"),
        "publication_date": doc.get("publication_date"),
        "status": "failed",
        "attempts": attempts,
        "message": "XML and HTML download attempts failed.",
    }


def summarize_regs_doc(doc: dict, candidate_title: str) -> dict:
    attrs = doc.get("attributes") or {}
    return {
        "id": doc.get("id"),
        "object_id": attrs.get("objectId"),
        "fr_doc_num": attrs.get("frDocNum"),
        "document_type": attrs.get("documentType"),
        "title": attrs.get("title"),
        "posted_date": attrs.get("postedDate"),
        "open_for_comment": attrs.get("openForComment"),
        "withdrawn": attrs.get("withdrawn"),
        "title_alignment": title_alignment_metrics(candidate_title, attrs.get("title") or ""),
    }


def fetch_regs_documents(docket_id: str, candidate_title: str) -> dict:
    page_number = 1
    all_docs = []
    total_reported = None
    sampled_all_pages = True

    while True:
        response = get_regs("documents", {
            "filter[docketId]": docket_id,
            "page[size]": 250,
            "page[number]": page_number,
        })
        if response["status"] != "ok":
            return {
                "status": response["status"],
                "message": response["message"],
                "documents": all_docs,
                "documents_sampled": len(all_docs),
                "documents_total_reported": total_reported,
                "sampled_all_pages": sampled_all_pages,
                "http_status": response.get("http_status"),
            }

        body = response["body"] or {}
        page_docs = body.get("data") or []
        meta = body.get("meta") or {}
        total_reported = meta.get("totalElements", total_reported)
        all_docs.extend(page_docs)
        total_pages = meta.get("totalPages")

        if not page_docs:
            break
        if not total_pages or page_number >= total_pages:
            break
        if page_number >= MAX_REGS_DOCUMENT_PAGES:
            sampled_all_pages = False
            break
        page_number += 1

    return {
        "status": "ok",
        "message": "OK",
        "documents": [summarize_regs_doc(doc, candidate_title) for doc in all_docs],
        "documents_sampled": len(all_docs),
        "documents_total_reported": total_reported,
        "sampled_all_pages": sampled_all_pages,
        "http_status": 200,
    }


def select_regs_proposed_doc(candidate: dict, selected_fr_proposed_doc: dict) -> dict:
    documents_response = fetch_regs_documents(candidate["docket_id"], candidate["title"])
    if documents_response["status"] != "ok":
        return {
            "status": documents_response["status"],
            "message": documents_response["message"],
            "documents_response": documents_response,
            "selected_document": None,
            "selection_note": "Document listing failed.",
        }

    proposed_docs = [
        doc for doc in documents_response["documents"]
        if doc.get("document_type") == "Proposed Rule" and not doc.get("withdrawn")
    ]
    fr_doc_number = (selected_fr_proposed_doc or {}).get("document_number")
    exact_matches = [doc for doc in proposed_docs if doc.get("fr_doc_num") == fr_doc_number]
    if exact_matches:
        exact_matches.sort(key=lambda doc: doc.get("posted_date") or "9999-99-99")
        return {
            "status": "ok",
            "message": "OK",
            "documents_response": documents_response,
            "selected_document": exact_matches[0],
            "selection_note": f"Matched Regulations.gov proposed-rule document by frDocNum {fr_doc_number}.",
        }

    ranked = sorted(
        proposed_docs,
        key=lambda doc: (
            -(doc.get("title_alignment") or {}).get("overlap_count", 0),
            -((doc.get("title_alignment") or {}).get("overlap_ratio", 0.0)),
            doc.get("posted_date") or "9999-99-99",
        ),
    )
    selected = ranked[0] if ranked else None
    return {
        "status": "ok" if selected else "not_found",
        "message": "OK" if selected else "No non-withdrawn Proposed Rule document found in Regulations.gov listing.",
        "documents_response": documents_response,
        "selected_document": selected,
        "selection_note": "No frDocNum match was available; selected the best title-aligned proposed-rule document."
        if selected else "No relevant proposed-rule document was available.",
    }


def classify_comment_text(text: str) -> str:
    if not text:
        return "no_text"
    if is_substantive_inline_text(text):
        return "substantive_inline"
    return "attachment_pointer"


def build_detail_fallback_result(
    status: str,
    comment_id: str | None = None,
    classification: str | None = None,
    text: str | None = None,
    message: str | None = None,
    http_status: int | None = None,
) -> dict:
    return {
        "status": status,
        "comment_id": comment_id,
        "classification": classification,
        "text_preview": preview(text) if text else None,
        "http_status": http_status,
        "message": message,
    }


def comment_sample_attachment_fields(sample_comments: list) -> list:
    fields = set()
    for comment in sample_comments:
        attrs = comment.get("attributes") or {}
        for key in attrs.keys():
            lowered = key.lower()
            if "attach" in lowered or "file" in lowered:
                fields.add(key)
    return sorted(fields)


def measure_regs_comment_census(candidate: dict, selected_regs_doc: dict, documents_response: dict) -> dict:
    if not selected_regs_doc:
        return {
            "status": "not_found",
            "message": "No Regulations.gov proposed-rule document was available for comment census.",
        }

    object_id = selected_regs_doc.get("object_id")
    if not object_id:
        return {
            "status": "missing_object_id",
            "message": "Selected Regulations.gov proposed-rule document has no objectId.",
            "selected_document": selected_regs_doc,
        }

    volume_response = get_regs("comments", {
        "filter[commentOnId]": object_id,
        "page[size]": 250,
        "page[number]": 1,
    })
    if volume_response["status"] != "ok":
        return {
            "status": volume_response["status"],
            "message": volume_response["message"],
            "selected_document": selected_regs_doc,
            "selected_document_note": "Volume census failed before total comment count could be confirmed.",
        }

    volume_body = volume_response["body"] or {}
    volume_meta = volume_body.get("meta") or {}
    total_comments = volume_meta.get("totalElements", 0)
    pages_needed_at_25 = math.ceil(total_comments / 25) if total_comments else 0
    estimated_request_count = pages_needed_at_25
    estimated_wall_clock_seconds = round_seconds(estimated_request_count * REGS_REQUEST_DELAY)

    sample_response = get_regs("comments", {
        "filter[commentOnId]": object_id,
        "page[size]": 25,
        "page[number]": 1,
    })
    if sample_response["status"] != "ok":
        return {
            "status": sample_response["status"],
            "message": sample_response["message"],
            "selected_document": selected_regs_doc,
            "total_comments": total_comments,
            "pages_needed_at_25": pages_needed_at_25,
            "estimated_request_count": estimated_request_count,
            "estimated_wall_clock_seconds": estimated_wall_clock_seconds,
        }

    sample_body = sample_response["body"] or {}
    sample_comments = sample_body.get("data") or []
    classifications = {"substantive_inline": 0, "attachment_pointer": 0, "no_text": 0}
    previews = {"substantive_inline": [], "attachment_pointer": []}
    detail_fallback_used = False
    detail_fallback = build_detail_fallback_result(
        status="not_needed",
        message="List sample already contained visible text or no sampled comments were available.",
    )

    for comment in sample_comments:
        attrs = comment.get("attributes") or {}
        text = extract_visible_comment_text(attrs)
        bucket = classify_comment_text(text)
        classifications[bucket] += 1
        if text and len(previews.get(bucket, [])) < 2 and bucket in previews:
            previews[bucket].append(preview(text))

    if sample_comments and classifications["substantive_inline"] == 0 and classifications["attachment_pointer"] == 0:
        first_comment_id = sample_comments[0].get("id")
        detail_response = get_regs(f"comments/{first_comment_id}", {})
        detail_fallback_used = True
        if detail_response["status"] != "ok":
            detail_fallback = build_detail_fallback_result(
                status=detail_response["status"],
                comment_id=first_comment_id,
                http_status=detail_response.get("http_status"),
                message=detail_response["message"],
            )
        else:
            detail_body = detail_response["body"] or {}
            detail_data = detail_body.get("data") or {}
            detail_attrs = detail_data.get("attributes") or {}
            detail_text = extract_visible_comment_text(detail_attrs)
            detail_bucket = classify_comment_text(detail_text)
            if classifications["no_text"] > 0:
                classifications["no_text"] -= 1
            classifications[detail_bucket] += 1
            if detail_text and detail_bucket in previews and len(previews[detail_bucket]) < 2:
                previews[detail_bucket].append(preview(detail_text))
            detail_fallback = build_detail_fallback_result(
                status="ok",
                comment_id=first_comment_id,
                classification=detail_bucket,
                text=detail_text,
                http_status=detail_response.get("http_status"),
                message="Confirmed sample comment text via detail endpoint because the list endpoint returned empty text.",
            )

    sample_count = len(sample_comments)
    inline_fraction = (classifications["substantive_inline"] / sample_count) if sample_count else 0.0
    projected_substantive_comments = round(total_comments * inline_fraction) if total_comments else 0

    return {
        "status": "ok",
        "message": "OK",
        "selected_document": selected_regs_doc,
        "selected_document_note": "Comment census used the selected Regulations.gov proposed-rule document.",
        "documents_sampled": documents_response["documents_sampled"],
        "documents_total_reported": documents_response["documents_total_reported"],
        "sampled_all_pages": documents_response["sampled_all_pages"],
        "total_comments": total_comments,
        "pages_needed_at_25": pages_needed_at_25,
        "estimated_request_count": estimated_request_count,
        "estimated_wall_clock_seconds": estimated_wall_clock_seconds,
        "sample_page_size": 25,
        "sample_count": sample_count,
        "sample_classification_counts": classifications,
        "sample_inline_fraction": round(inline_fraction, 3),
        "projected_substantive_comments": projected_substantive_comments,
        "sample_previews": previews,
        "attachment_metadata_fields_seen": comment_sample_attachment_fields(sample_comments),
        "detail_fallback_used": detail_fallback_used,
        "detail_fallback": detail_fallback,
    }


def summarize_timings() -> dict:
    fr_events = [event for event in HTTP_EVENTS if event["service"] == "fr"]
    regs_events = [event for event in HTTP_EVENTS if event["service"] == "regs"]

    def event_summary(events: list) -> dict:
        durations = [event["duration_seconds"] for event in events if event["duration_seconds"] is not None]
        return {
            "request_count": len(events),
            "mean_seconds": round_seconds(statistics.mean(durations)) if durations else None,
            "max_seconds": round_seconds(max(durations)) if durations else None,
        }

    return {
        "federal_register": event_summary(fr_events),
        "regulations_gov": event_summary(regs_events),
        "observed_429": any(event["status_code"] == 429 for event in HTTP_EVENTS),
        "documented_regs_limit_per_minute": 50,
        "documented_floor_seconds_per_request": 1.2,
        "configured_safe_delay_seconds": REGS_REQUEST_DELAY,
    }


def readiness_verdict(docket_results: list, auth_status: dict) -> dict:
    blockers = []
    if not auth_status["api_key_present"]:
        blockers.append("REGULATIONS_GOV_API_KEY was missing.")
    if auth_status["auth_failures_observed"]:
        blockers.append("At least one Regulations.gov auth failure was observed.")

    for entry in docket_results:
        fr = entry["federal_register"]
        regs = entry["regulations_gov"]
        for role in ("proposed_rule", "final_rule"):
            if fr[role]["download"].get("status") != "ok":
                blockers.append(
                    f"{entry['candidate']['docket_id']} {role} full-text download did not complete successfully."
                )
        if regs["comment_census"].get("status") != "ok":
            blockers.append(
                f"{entry['candidate']['docket_id']} Regulations.gov comment census did not complete successfully."
            )

    if blockers:
        return {
            "status": "no_go",
            "message": "Phase 1 should not begin until the integration blockers below are resolved.",
            "blockers": blockers,
        }
    return {
        "status": "go",
        "message": "Phase 1 can proceed: working endpoints, request patterns, timing, and data-gap observations were all confirmed for the accepted V1 docket set.",
        "blockers": [],
    }


def render_integration_note(results: dict) -> str:
    lines = []
    timing = results["timing_summary"]
    verdict = results["readiness_verdict"]

    lines.append("# Integration Note")
    lines.append("")
    lines.append("## 1. Confirmed docket set")
    lines.append("")
    for entry in results["docket_results"]:
        candidate = entry["candidate"]
        lines.append(f"- `{candidate['docket_id']}` — {candidate['title']}")

    lines.append("")
    lines.append("## 2. Federal Register — endpoints, request patterns, document sizes, structural observations")
    lines.append("")
    lines.append("- Working search endpoint: `GET /api/v1/documents?conditions[docket_id]=...&fields[]=document_number&type&title&publication_date&full_text_xml_url&html_url&action`")
    lines.append("- Working full-text pattern: use `full_text_xml_url` first and fall back to `html_url` only when XML is unavailable or fails.")
    lines.append("")
    for entry in results["docket_results"]:
        candidate = entry["candidate"]
        fr = entry["federal_register"]
        lines.append(f"### {candidate['docket_id']}")
        lines.append(f"- Proposed rule: `{(fr['proposed_rule']['selected_document'] or {}).get('document_number', 'n/a')}`")
        lines.append(f"- Final rule: `{(fr['final_rule']['selected_document'] or {}).get('document_number', 'n/a')}`")
        for role_label, role_key in (("Proposed", "proposed_rule"), ("Final", "final_rule")):
            doc = fr[role_key]["download"]
            lines.append(
                f"- {role_label} download: `{doc.get('source_used', 'n/a')}` "
                f"| raw bytes `{doc.get('raw_bytes', 'n/a')}` "
                f"| stripped chars `{doc.get('stripped_character_count', 'n/a')}` "
                f"| words `{doc.get('word_count', 'n/a')}` "
                f"| approx sections `{doc.get('approx_section_count', 'n/a')}` "
                f"| content-type `{doc.get('content_type', 'n/a')}` "
                f"| duration `{doc.get('download_duration_seconds', 'n/a')} s`"
            )
        lines.append("")

    lines.append("## 3. Regulations.gov — endpoints, request patterns, comment volumes per docket, inline-text fraction, auth notes")
    lines.append("")
    lines.append("- Working document listing pattern: `GET /v4/documents?filter[docketId]={docketId}&page[size]=250&page[number]=N`")
    lines.append("- Working comment census pattern: `GET /v4/comments?filter[commentOnId]={objectId}&page[size]=250&page[number]=1`")
    lines.append("- Working sample pattern: `GET /v4/comments?filter[commentOnId]={objectId}&page[size]=25&page[number]=1`")
    lines.append("- Working detail fallback pattern: `GET /v4/comments/{commentId}` when the list endpoint returns empty text fields.")
    lines.append("- Docket endpoint note: `GET /v4/dockets/{docketId}` was not tested in this spike.")
    auth_text = "accepted" if not results["auth_status"]["auth_failures_observed"] and results["auth_status"]["api_key_present"] else "not fully confirmed"
    lines.append(f"- Regulations.gov authentication status: API key present = `{results['auth_status']['api_key_present']}`, observed auth result = `{auth_text}`")
    lines.append("")
    for entry in results["docket_results"]:
        candidate = entry["candidate"]
        regs = entry["regulations_gov"]["comment_census"]
        selected_doc = regs.get("selected_document") or {}
        lines.append(f"### {candidate['docket_id']}")
        lines.append(f"- Proposed-rule doc for comment census: `{selected_doc.get('id', 'n/a')}` / objectId `{selected_doc.get('object_id', 'n/a')}`")
        lines.append(f"- Total comments reported: `{regs.get('total_comments', 'n/a')}`")
        lines.append(f"- Estimated pages at page_size=25: `{regs.get('pages_needed_at_25', 'n/a')}`")
        lines.append(f"- Estimated full retrieval request count: `{regs.get('estimated_request_count', 'n/a')}`")
        lines.append(f"- Estimated full retrieval wall-clock at 1.25 s/request: `{regs.get('estimated_wall_clock_seconds', 'n/a')} s`")
        counts = regs.get("sample_classification_counts") or {}
        lines.append(
            f"- 25-comment sample mix: substantive inline `{counts.get('substantive_inline', 'n/a')}`, "
            f"attachment pointer `{counts.get('attachment_pointer', 'n/a')}`, "
            f"no text `{counts.get('no_text', 'n/a')}`"
        )
        lines.append(f"- Detail fallback used: `{regs.get('detail_fallback_used', False)}`")
        detail = regs.get("detail_fallback") or {}
        if regs.get("detail_fallback_used"):
            lines.append(
                f"- Detail fallback result: status `{detail.get('status', 'n/a')}`, "
                f"classification `{detail.get('classification', 'n/a')}`, "
                f"preview `{detail.get('text_preview', 'n/a')}`"
            )
        lines.append(f"- Projected inline-text fraction: `{regs.get('sample_inline_fraction', 'n/a')}`")
        lines.append(f"- Projected substantive comment count: `{regs.get('projected_substantive_comments', 'n/a')}`")
        lines.append(f"- Attachment/file metadata fields seen in sample: `{', '.join(regs.get('attachment_metadata_fields_seen') or []) or 'none'}`")
        lines.append("")

    lines.append("## 4. Rate limits and timing — observed behavior, documented limits, full-ingestion estimates")
    lines.append("")
    lines.append(
        f"- Federal Register observed mean/max response time: `{timing['federal_register']['mean_seconds']} s` / "
        f"`{timing['federal_register']['max_seconds']} s` across `{timing['federal_register']['request_count']}` requests"
    )
    lines.append(
        f"- Regulations.gov observed mean/max response time: `{timing['regulations_gov']['mean_seconds']} s` / "
        f"`{timing['regulations_gov']['max_seconds']} s` across `{timing['regulations_gov']['request_count']}` requests"
    )
    lines.append(f"- Observed any HTTP 429 responses: `{timing['observed_429']}`")
    lines.append(
        f"- Documented Regulations.gov limit used here: `{timing['documented_regs_limit_per_minute']} req/min`, "
        f"which implies a floor of `{timing['documented_floor_seconds_per_request']} s/req`."
    )
    lines.append(
        f"- Configured safe delay in this spike: `{timing['configured_safe_delay_seconds']} s/req`."
    )
    lines.append("- Full-ingestion estimate per docket is computed as `ceil(total_comments / 25) * 1.25 s`.")
    lines.append("")

    lines.append("## 5. Caching requirements — immutable vs drifting data, recommended strategy")
    lines.append("")
    lines.append("- Treat Federal Register full text by document number as immutable once fetched; cache by full-text URL or FR document number with a forever TTL.")
    lines.append("- Treat Regulations.gov comment detail by comment ID as effectively immutable for V1 purposes; cache by comment ID with a forever TTL.")
    lines.append("- Treat Regulations.gov docket document listings and paginated comment lists as drifting resources; cache those by full request URL with a 24-hour TTL.")
    lines.append("- Recommended cache shape for Phase 1: file-based cache keyed by canonical request URL or immutable record ID, with separate stores for immutable and list resources.")
    lines.append("")

    lines.append("## 6. Data gaps — attachment-only comments quantified, other gaps")
    lines.append("")
    for entry in results["docket_results"]:
        candidate = entry["candidate"]
        regs = entry["regulations_gov"]["comment_census"]
        counts = regs.get("sample_classification_counts") or {}
        lines.append(
            f"- `{candidate['docket_id']}` sample gap profile: substantive inline `{counts.get('substantive_inline', 0)}`, "
            f"attachment pointer `{counts.get('attachment_pointer', 0)}`, no text `{counts.get('no_text', 0)}`."
        )
    lines.append("- Regulations.gov list pages alone do not reliably expose comment text for these dockets; the detail endpoint is a required retrieval pattern when list payloads are empty.")
    lines.append("- Attachment-only or no-text comments remain a real data-shape limitation, but list-endpoint emptiness should not be confused with true text absence.")
    lines.append("- This spike did not implement cache storage, attachment parsing, or any downstream pipeline behavior.")
    lines.append("")

    lines.append("## 7. Readiness verdict — go/no-go for Phase 1")
    lines.append("")
    lines.append(f"- Verdict: `{verdict['status']}`")
    lines.append(f"- Summary: {verdict['message']}")
    if verdict["blockers"]:
        lines.append("- Blockers:")
        for blocker in verdict["blockers"]:
            lines.append(f"  - {blocker}")

    lines.append("")
    lines.append(f"_Generated by `api_integration_spike.py` on {results['generated_at']}._")
    return "\n".join(lines) + "\n"


def process_candidate(candidate: dict) -> dict:
    fr_docs = fetch_fr_documents(candidate)
    if fr_docs["status"] != "ok":
        return {
            "candidate": candidate,
            "federal_register": {"status": fr_docs["status"], "message": fr_docs["message"]},
            "regulations_gov": {"status": "not_attempted"},
        }

    proposed_doc = fr_docs["proposed_choice"]["selected"]
    final_doc = fr_docs["final_choice"]["selected"]
    fr_result = {
        "status": "ok",
        "proposed_rule": {
            "selection_status": fr_docs["proposed_choice"]["status"],
            "selection_notes": fr_docs["proposed_choice"]["notes"],
            "selected_document": proposed_doc,
            "download": measure_fr_download(proposed_doc, "proposed_rule") if proposed_doc else {
                "role": "proposed_rule",
                "status": "not_selected",
                "attempts": [],
                "message": "No proposed-rule document was selected for download.",
            },
        },
        "final_rule": {
            "selection_status": fr_docs["final_choice"]["status"],
            "selection_notes": fr_docs["final_choice"]["notes"],
            "selected_document": final_doc,
            "download": measure_fr_download(final_doc, "final_rule") if final_doc else {
                "role": "final_rule",
                "status": "not_selected",
                "attempts": [],
                "message": "No final-rule document was selected for download.",
            },
        },
    }

    regs_selection = select_regs_proposed_doc(candidate, proposed_doc)
    regs_result = {
        "status": regs_selection["status"],
        "document_selection": {
            "status": regs_selection["status"],
            "message": regs_selection["message"],
            "selection_note": regs_selection["selection_note"],
            "selected_document": regs_selection["selected_document"],
            "documents_sampled": regs_selection["documents_response"]["documents_sampled"] if regs_selection.get("documents_response") else None,
            "documents_total_reported": regs_selection["documents_response"]["documents_total_reported"] if regs_selection.get("documents_response") else None,
            "sampled_all_pages": regs_selection["documents_response"]["sampled_all_pages"] if regs_selection.get("documents_response") else None,
        },
        "comment_census": measure_regs_comment_census(
            candidate,
            regs_selection["selected_document"],
            regs_selection["documents_response"],
        ) if regs_selection["status"] == "ok" else {
            "status": regs_selection["status"],
            "message": regs_selection["message"],
        },
    }
    return {
        "candidate": candidate,
        "federal_register": fr_result,
        "regulations_gov": regs_result,
    }


def write_outputs(results: dict):
    root = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(root, "integration_spike_results.json")
    note_path = os.path.join(root, "INTEGRATION_NOTE.md")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2)
    with open(note_path, "w", encoding="utf-8") as handle:
        handle.write(render_integration_note(results))
    return json_path, note_path


def main() -> int:
    print("=" * 72)
    print("Phase 0.5 API Integration Spike")
    print("=" * 72)

    docket_results = []
    for candidate in CANDIDATES:
        print(f"\n[{candidate['sequence']}/{len(CANDIDATES)}] {candidate['docket_id']}")
        result = process_candidate(candidate)
        docket_results.append(result)
        fr = result["federal_register"]
        regs = result["regulations_gov"]
        if fr.get("status") == "ok":
            print(
                f"  FR proposed/final: {fr['proposed_rule']['selection_status']} / "
                f"{fr['final_rule']['selection_status']}"
            )
            print(
                f"  FR downloads: proposed={fr['proposed_rule']['download'].get('status')} "
                f"final={fr['final_rule']['download'].get('status')}"
            )
        else:
            print(f"  FR status: {fr.get('status')} ({fr.get('message')})")
        print(f"  Regs selection: {regs.get('document_selection', {}).get('status', regs.get('status'))}")
        print(f"  Regs comment census: {regs.get('comment_census', {}).get('status')}")

    auth_status = {
        "api_key_present": bool(REGS_GOV_API_KEY),
        "auth_failures_observed": any(
            event["service"] == "regs" and event["status_code"] in (401, 403)
            for event in HTTP_EVENTS
        ) or (not REGS_GOV_API_KEY),
    }
    timing_summary = summarize_timings()
    verdict = readiness_verdict(docket_results, auth_status)

    results = {
        "generated_at": iso_now(),
        "candidate_set": CANDIDATES,
        "auth_status": auth_status,
        "timing_summary": timing_summary,
        "docket_results": docket_results,
        "readiness_verdict": verdict,
        "http_events": HTTP_EVENTS,
    }
    json_path, note_path = write_outputs(results)

    print("\nOutputs written:")
    print(f"  - {json_path}")
    print(f"  - {note_path}")
    print(f"Readiness verdict: {verdict['status']}")
    return 0 if verdict["status"] == "go" else 1


if __name__ == "__main__":
    sys.exit(main())
