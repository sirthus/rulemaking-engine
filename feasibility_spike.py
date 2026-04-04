#!/usr/bin/env python3
"""
Phase 0 Step 2 Feasibility Spike — Rulemaking Engine

This standalone script checks four already-selected EPA dockets for Phase 0
feasibility by verifying:
  - Federal Register proposed/final rule document pairing and text access
  - Regulations.gov comment retrievability
  - Rough text segmentation feasibility
  - Presence of final-rule preamble comment discussion markers

Requires:
  REGULATIONS_GOV_API_KEY environment variable for Regulations.gov checks
  pip install requests
"""

import json
import os
import re
import time
from html import unescape

import requests

# ── Configuration ──────────────────────────────────────────────────────────────

REGS_GOV_API_KEY = os.environ.get("REGULATIONS_GOV_API_KEY", "")
FR_BASE = "https://www.federalregister.gov/api/v1"
REGS_BASE = "https://api.regulations.gov/v4"

CANDIDATES = [
    {
        "sequence": 1,
        "docket_id": "EPA-HQ-OAR-2021-0324",
        "title": "Renewable Fuel Standard Program: RFS Annual Rules (2020–2022 volumes)",
    },
    {
        "sequence": 2,
        "docket_id": "EPA-HQ-OAR-2020-0272",
        "title": "Revised Cross-State Air Pollution Rule Update for the 2008 Ozone NAAQS",
    },
    {
        "sequence": 3,
        "docket_id": "EPA-HQ-OAR-2021-0427",
        "title": "Renewable Fuel Standard Program: Standards for 2023–2025 and Other Changes",
    },
    {
        "sequence": 4,
        "docket_id": "EPA-HQ-OAR-2009-0734",
        "title": "Standards of Performance for New Residential Wood Heaters, Hydronic Heaters and Forced-Air Furnaces",
    },
]

# The public docs describe a secondary limit of 500 requests/hour and 50/minute
# for commenting API access. This delay is a conservative throttle, not a
# guarantee against rate limiting.
REGS_REQUEST_DELAY = 1.25
MAX_REGS_DOCUMENT_PAGES = 4
TEXT_PREVIEW_CHARS = 160

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
    "petition",
    "reconsideration",
    "remand",
    "reopening",
    "stay",
    "supplemental notice",
    "technical amendment",
    "technical correction",
    "withdrawal",
}

PREAMBLE_MARKERS = [
    "response to comments",
    "we received",
    "commenters",
    "after considering",
    "in response",
    "comments",
    "comment",
]


# ── Generic helpers ────────────────────────────────────────────────────────────

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


def normalize_title_for_compare(text: str) -> str:
    normalized = (text or "").lower()
    normalized = normalized.replace("–", "-").replace("—", "-")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


# ── HTTP helpers ───────────────────────────────────────────────────────────────

def get_fr(path: str, params: dict) -> dict:
    url = f"{FR_BASE}/{path}"
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return {"status": "ok", "body": resp.json()}
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return {
            "status": "http_error",
            "http_status": status_code,
            "message": f"Federal Register HTTP error: {exc}",
        }
    except requests.RequestException as exc:
        return {
            "status": "network_error",
            "http_status": None,
            "message": f"Federal Register request failed: {exc}",
        }


def fetch_text(url: str, source_label: str) -> dict:
    if not url:
        return {
            "status": "no_url",
            "source": source_label,
            "message": "No text URL available.",
            "text": None,
        }

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else None
        return {
            "status": "http_error",
            "source": source_label,
            "http_status": status_code,
            "message": f"Text fetch HTTP error: {exc}",
            "text": None,
            "url": url,
        }
    except requests.RequestException as exc:
        return {
            "status": "network_error",
            "source": source_label,
            "http_status": None,
            "message": f"Text fetch request failed: {exc}",
            "text": None,
            "url": url,
        }

    raw_text = resp.text
    cleaned = strip_markup(raw_text)
    return {
        "status": "ok",
        "source": source_label,
        "http_status": resp.status_code,
        "url": url,
        "text": cleaned,
        "raw_length": len(raw_text),
        "cleaned_length": len(cleaned),
        "preview": preview(cleaned),
    }


def get_regs(path: str, params: dict) -> dict:
    if not REGS_GOV_API_KEY:
        return {
            "status": "auth_failure",
            "http_status": None,
            "body": None,
            "message": "REGULATIONS_GOV_API_KEY is not set. Authentication is unverified.",
            "auth_detail": "missing_api_key",
        }

    url = f"{REGS_BASE}/{path}"
    headers = {"X-Api-Key": REGS_GOV_API_KEY}
    time.sleep(REGS_REQUEST_DELAY)

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=30)
    except requests.RequestException as exc:
        return {
            "status": "network_error",
            "http_status": None,
            "body": None,
            "message": f"Regulations.gov request failed: {exc}",
        }

    body = safe_json(resp)
    status_code = resp.status_code

    if status_code == 200:
        return {
            "status": "ok",
            "http_status": status_code,
            "body": body,
            "message": "OK",
        }
    if status_code in (401, 403):
        detail = "api_key_rejected" if REGS_GOV_API_KEY else "missing_api_key"
        return {
            "status": "auth_failure",
            "http_status": status_code,
            "body": body,
            "message": "Regulations.gov authentication failed. Do not interpret this as data absence.",
            "auth_detail": detail,
        }
    if status_code == 404:
        return {
            "status": "not_found",
            "http_status": status_code,
            "body": body,
            "message": "Regulations.gov returned 404.",
        }
    if status_code == 429:
        return {
            "status": "rate_limited",
            "http_status": status_code,
            "body": body,
            "message": "Regulations.gov rate limit encountered. Do not interpret this as missing data.",
        }
    return {
        "status": "unexpected_http_status",
        "http_status": status_code,
        "body": body,
        "message": f"Unexpected Regulations.gov status {status_code}.",
    }


# ── Federal Register verification ──────────────────────────────────────────────

def summarize_fr_doc(doc: dict, candidate_title: str) -> dict:
    metrics = title_alignment_metrics(candidate_title, doc.get("title") or "")
    title = doc.get("title") or ""
    action = doc.get("action") or ""
    xml_url = doc.get("full_text_xml_url")
    html_url = doc.get("html_url")
    pdf_url = doc.get("pdf_url")
    return {
        "document_number": doc.get("document_number"),
        "document_type": doc.get("type"),
        "title": title,
        "publication_date": doc.get("publication_date"),
        "action": action,
        "has_xml": bool(xml_url),
        "has_html": bool(html_url),
        "has_pdf": bool(pdf_url),
        "full_text_xml_url": xml_url,
        "html_url": html_url,
        "pdf_url": pdf_url,
        "fr_comment_count_screening_signal": doc.get("comment_count"),
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
            "plausible_candidates": [],
            "notes": [f"No {doc_label} documents found in Federal Register results."],
        }

    ranked = sort_fr_candidates(docs)
    plausible = []
    for doc in ranked:
        metrics = doc.get("title_alignment") or {}
        materially_aligned = metrics.get("overlap_count", 0) >= 2
        if materially_aligned and not doc.get("non_main_keyword_flag"):
            plausible.append(doc)

    notes = []
    if plausible:
        selected = plausible[0]
        if len(plausible) > 1:
            status = "ambiguous"
            notes.append(
                f"Multiple plausible {doc_label} documents matched the candidate title; selected the earliest best-aligned option."
            )
        else:
            status = "selected"
            notes.append(f"Selected the best-aligned {doc_label} document.")
        return {
            "status": status,
            "doc_label": doc_label,
            "selected": selected,
            "plausible_candidates": plausible,
            "notes": notes,
        }

    non_main_filtered = [doc for doc in ranked if not doc.get("non_main_keyword_flag")]
    selected = non_main_filtered[0] if non_main_filtered else ranked[0]
    notes.append(
        f"No materially aligned {doc_label} document found; selected the earliest non-excluded option for manual review."
    )
    return {
        "status": "weak_match",
        "doc_label": doc_label,
        "selected": selected,
        "plausible_candidates": non_main_filtered or ranked,
        "notes": notes,
    }


def fetch_fr_selected_doc_text(doc: dict) -> dict:
    if not doc:
        return {
            "status": "not_selected",
            "source": None,
            "message": "No Federal Register document was selected.",
            "text": None,
        }

    if doc.get("full_text_xml_url"):
        return fetch_text(doc["full_text_xml_url"], "federal_register_xml")
    if doc.get("html_url"):
        return fetch_text(doc["html_url"], "federal_register_html")
    return {
        "status": "no_machine_readable_text_url",
        "source": None,
        "message": "Selected Federal Register document has no XML or HTML URL.",
        "text": None,
    }


def check_federal_register(candidate: dict) -> dict:
    docket_id = candidate["docket_id"]
    params = {
        "conditions[docket_id]": docket_id,
        "fields[]": [
            "document_number",
            "type",
            "title",
            "publication_date",
            "full_text_xml_url",
            "html_url",
            "pdf_url",
            "action",
        ],
        "per_page": 100,
        "order": "oldest",
    }

    request_result = get_fr("documents", params)
    result = {
        "status": "ok",
        "source_facts": {},
        "inference": {},
        "failures": [],
        "unknowns": [],
        "selected_texts": {},
    }

    if request_result["status"] != "ok":
        result["status"] = "failed"
        result["failures"].append(request_result["message"])
        result["source_facts"]["request_status"] = request_result["status"]
        return result

    docs = request_result["body"].get("results", [])
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
    notices = [doc for doc in docs if doc.get("type") == "Notice"]
    other_docs = [
        doc for doc in docs
        if doc.get("type") not in ("Proposed Rule", "Rule", "Notice")
    ]

    proposed_choice = choose_main_fr_document(proposed_docs, "proposed rule")
    final_choice = choose_main_fr_document(final_docs, "final rule")

    selected_proposed = proposed_choice["selected"]
    selected_final = final_choice["selected"]
    proposed_text = fetch_fr_selected_doc_text(selected_proposed)
    final_text = fetch_fr_selected_doc_text(selected_final)

    if selected_proposed is None:
        result["failures"].append("No proposed rule document could be selected from Federal Register results.")
    elif proposed_choice["status"] != "selected":
        result["unknowns"].extend(proposed_choice["notes"])
    if selected_final is None:
        result["failures"].append("No final rule document could be selected from Federal Register results.")
    elif final_choice["status"] != "selected":
        result["unknowns"].extend(final_choice["notes"])

    if proposed_text["status"] != "ok":
        result["failures"].append(f"Proposed rule text fetch issue: {proposed_text['message']}")
    if final_text["status"] != "ok":
        result["failures"].append(f"Final rule text fetch issue: {final_text['message']}")

    result["source_facts"] = {
        "total_documents_returned": len(docs),
        "notice_count": len(notices),
        "other_document_count": len(other_docs),
        "all_proposed_rule_documents": proposed_docs,
        "all_final_rule_documents": final_docs,
        "selected_proposed_rule": selected_proposed,
        "selected_final_rule": selected_final,
        "selected_proposed_rule_text_fetch": {
            key: proposed_text.get(key)
            for key in ("status", "source", "http_status", "url", "raw_length", "cleaned_length", "preview", "message")
            if key in proposed_text
        },
        "selected_final_rule_text_fetch": {
            key: final_text.get(key)
            for key in ("status", "source", "http_status", "url", "raw_length", "cleaned_length", "preview", "message")
            if key in final_text
        },
    }
    result["inference"] = {
        "proposed_rule_pairing_status": proposed_choice["status"],
        "final_rule_pairing_status": final_choice["status"],
        "pairing_notes": proposed_choice["notes"] + final_choice["notes"],
        "proposed_rule_text_verified": proposed_text["status"] == "ok",
        "final_rule_text_verified": final_text["status"] == "ok",
    }
    result["selected_texts"] = {
        "proposed_rule_text": proposed_text.get("text"),
        "final_rule_text": final_text.get("text"),
    }

    if result["failures"]:
        result["status"] = "failed"
    elif result["unknowns"]:
        result["status"] = "needs_manual_review"

    return result


# ── Segmentation and preamble checks ───────────────────────────────────────────

def analyze_single_text_segmentation(text: str) -> dict:
    if not text:
        return {
            "status": "failed_to_fetch_text",
            "evidence": {
                "heading_like_markers": 0,
                "paragraph_like_blocks": 0,
                "named_section_markers": 0,
            },
            "snippet": None,
        }

    heading_matches = re.findall(
        r"(?:^|\n)\s*(?:[IVXLC]+\.\s+[A-Z]|[A-Z]\.\s+[A-Z]|[A-Z][A-Z0-9 ,;:'()/\-]{8,})",
        text,
    )
    named_section_matches = re.findall(
        r"(summary|background|supplementary information|final rule|response to comments|comments and responses)",
        text,
        flags=re.IGNORECASE,
    )
    paragraphs = [
        block.strip()
        for block in re.split(r"\n\s*\n", text)
        if len(normalize_whitespace(block)) >= 120
    ]

    status = "unclear"
    if len(heading_matches) >= 3 or len(paragraphs) >= 15 or len(named_section_matches) >= 3:
        status = "usable"
    elif len(heading_matches) >= 1 or len(paragraphs) >= 5 or len(named_section_matches) >= 1:
        status = "weak_but_usable"

    first_heading = heading_matches[0] if heading_matches else ""
    first_paragraph = paragraphs[0] if paragraphs else ""
    snippet_source = first_heading or first_paragraph

    return {
        "status": status,
        "evidence": {
            "heading_like_markers": len(heading_matches),
            "paragraph_like_blocks": len(paragraphs),
            "named_section_markers": len(named_section_matches),
        },
        "snippet": preview(snippet_source),
    }


def check_segmentation(federal_register_verification: dict) -> dict:
    proposed_text = federal_register_verification["selected_texts"].get("proposed_rule_text")
    final_text = federal_register_verification["selected_texts"].get("final_rule_text")

    proposed_result = analyze_single_text_segmentation(proposed_text)
    final_result = analyze_single_text_segmentation(final_text)

    statuses = {proposed_result["status"], final_result["status"]}
    overall_status = "usable"
    if "failed_to_fetch_text" in statuses:
        overall_status = "failed_to_fetch_text"
    elif "unclear" in statuses:
        overall_status = "unclear"
    elif "weak_but_usable" in statuses:
        overall_status = "weak_but_usable"

    failures = []
    unknowns = []
    if proposed_result["status"] == "failed_to_fetch_text":
        failures.append("Proposed rule text was unavailable for segmentation checks.")
    if final_result["status"] == "failed_to_fetch_text":
        failures.append("Final rule text was unavailable for segmentation checks.")
    if overall_status == "unclear":
        unknowns.append("Segmentation signals were weak enough that manual inspection is still advisable.")

    return {
        "status": overall_status,
        "heuristic_result": {
            "proposed_rule": proposed_result,
            "final_rule": final_result,
        },
        "failures": failures,
        "unknowns": unknowns,
    }


def check_preamble_comment_discussion(federal_register_verification: dict) -> dict:
    final_text = federal_register_verification["selected_texts"].get("final_rule_text")
    if not final_text:
        return {
            "status": "text_unavailable",
            "heuristic_result": {
                "matched_markers": [],
                "match_count": 0,
                "snippets": [],
            },
            "failures": ["Final rule text was unavailable for preamble comment-discussion checks."],
            "unknowns": [],
        }

    lowered = final_text.lower()
    matched_markers = []
    snippets = []
    total_matches = 0

    for marker in PREAMBLE_MARKERS:
        start = 0
        marker_matched = False
        while True:
            idx = lowered.find(marker, start)
            if idx == -1:
                break
            marker_matched = True
            total_matches += 1
            left = max(0, idx - 80)
            right = min(len(final_text), idx + len(marker) + 80)
            snippets.append(preview(final_text[left:right]))
            start = idx + len(marker)
            if len(snippets) >= 4:
                break
        if marker_matched:
            matched_markers.append(marker)
        if len(snippets) >= 4:
            break

    if len(matched_markers) >= 2 or total_matches >= 3:
        status = "present"
    elif len(matched_markers) == 1 or total_matches >= 1:
        status = "weak_signal"
    else:
        status = "not_detected"

    failures = []
    unknowns = []
    if status == "not_detected":
        failures.append("No final-rule preamble comment-discussion markers were detected.")
    elif status == "weak_signal":
        unknowns.append("Comment-discussion markers were detected only weakly; manual inspection is advisable.")

    return {
        "status": status,
        "heuristic_result": {
            "matched_markers": matched_markers,
            "match_count": total_matches,
            "snippets": snippets[:4],
        },
        "failures": failures,
        "unknowns": unknowns,
    }


# ── Regulations.gov verification ───────────────────────────────────────────────

def summarize_regs_doc(doc: dict, candidate_title: str) -> dict:
    attrs = doc.get("attributes") or {}
    return {
        "id": doc.get("id"),
        "object_id": attrs.get("objectId"),
        "document_type": attrs.get("documentType"),
        "title": attrs.get("title"),
        "posted_date": attrs.get("postedDate"),
        "comment_count_metadata": attrs.get("commentCount"),
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
        if not total_pages or page_number >= total_pages:
            break
        if page_number >= MAX_REGS_DOCUMENT_PAGES:
            sampled_all_pages = False
            break
        page_number += 1

    summarized = [summarize_regs_doc(doc, candidate_title) for doc in all_docs]
    return {
        "status": "ok",
        "message": "OK",
        "documents": summarized,
        "documents_sampled": len(summarized),
        "documents_total_reported": total_reported,
        "sampled_all_pages": sampled_all_pages,
        "http_status": 200,
    }


def check_comment_retrieval_for_doc(doc: dict) -> dict:
    object_id = doc.get("object_id")
    result = {
        "document_id": doc.get("id"),
        "document_title": doc.get("title"),
        "object_id": object_id,
        "document_type": doc.get("document_type"),
        "query_status": None,
        "comments_total_reported": None,
        "sample_docs_returned": 0,
        "sample_has_visible_text": False,
        "sample_text_preview": None,
        "message": None,
        "detail_check": {
            "status": "not_needed",
            "comment_id": None,
            "http_status": None,
            "has_visible_text": False,
            "text_preview": None,
            "message": "Detail comment lookup was not needed.",
        },
    }

    if not object_id:
        result["query_status"] = "unknown"
        result["message"] = "Document has no objectId; comment retrieval could not be tested for this document."
        return result

    response = get_regs("comments", {
        "filter[commentOnId]": object_id,
        "page[size]": 5,
        "page[number]": 1,
    })

    if response["status"] != "ok":
        result["query_status"] = response["status"]
        result["message"] = response["message"]
        return result

    body = response["body"] or {}
    comments = body.get("data") or []
    total_elements = (body.get("meta") or {}).get("totalElements")
    visible_texts = []
    first_comment_id = comments[0].get("id") if comments else None
    for comment in comments[:5]:
        attrs = comment.get("attributes") or {}
        text = extract_visible_comment_text(attrs)
        if text and text.strip():
            visible_texts.append(text.strip())

    result["comments_total_reported"] = total_elements
    result["sample_docs_returned"] = len(comments)
    result["sample_has_visible_text"] = bool(visible_texts)
    result["sample_text_preview"] = preview(visible_texts[0]) if visible_texts else None

    if visible_texts:
        result["query_status"] = "confirmed_text"
        result["message"] = "Visible comment text was confirmed in the sample payload."
        result["detail_check"] = {
            "status": "not_needed",
            "comment_id": None,
            "http_status": None,
            "has_visible_text": False,
            "text_preview": None,
            "message": "Detail comment lookup was not needed because the list payload already contained visible text.",
        }
    elif comments:
        detail_response = get_regs(f"comments/{first_comment_id}", {})
        if detail_response["status"] != "ok":
            result["query_status"] = detail_response["status"]
            result["message"] = (
                "Comments were returned by the list endpoint, but the detail lookup failed before text availability "
                "could be confirmed."
            )
            result["detail_check"] = {
                "status": detail_response["status"],
                "comment_id": first_comment_id,
                "http_status": detail_response.get("http_status"),
                "has_visible_text": False,
                "text_preview": None,
                "message": detail_response["message"],
            }
            return result

        detail_body = detail_response["body"] or {}
        detail_data = detail_body.get("data") or {}
        detail_attrs = detail_data.get("attributes") or {}
        detail_text = extract_visible_comment_text(detail_attrs)
        if detail_text:
            result["query_status"] = "confirmed_text"
            result["sample_has_visible_text"] = True
            result["sample_text_preview"] = preview(detail_text)
            result["message"] = "Visible comment text was confirmed only at the comment detail endpoint."
            result["detail_check"] = {
                "status": "confirmed_text",
                "comment_id": first_comment_id,
                "http_status": detail_response.get("http_status"),
                "has_visible_text": True,
                "text_preview": preview(detail_text),
                "message": "Detail endpoint contained visible comment text.",
            }
        else:
            result["query_status"] = "metadata_only"
            result["message"] = (
                "Comments were returned, and the detail endpoint also had no visible text; the comment may be attachment-only."
            )
            result["detail_check"] = {
                "status": "metadata_only",
                "comment_id": first_comment_id,
                "http_status": detail_response.get("http_status"),
                "has_visible_text": False,
                "text_preview": None,
                "message": "Detail endpoint also had no visible text; the comment may be attachment-only.",
            }
    else:
        result["query_status"] = "no_comments_returned"
        result["message"] = "Comment query completed successfully but returned no comments on the sampled page."
        result["detail_check"] = {
            "status": "not_needed",
            "comment_id": None,
            "http_status": None,
            "has_visible_text": False,
            "text_preview": None,
            "message": "Detail comment lookup was not needed because the list query returned no comments.",
        }

    return result


def determine_comment_retrievability(comment_checks: list) -> tuple:
    if any(check["query_status"] == "confirmed_text" for check in comment_checks):
        return "confirmed", []

    unresolved_statuses = {"auth_failure", "rate_limited", "network_error", "unexpected_http_status", "unknown", "not_found"}
    if any(check["query_status"] in unresolved_statuses for check in comment_checks):
        return "unresolved", [
            "At least one proposed-rule comment check was blocked by auth, rate limits, network issues, or missing objectId."
        ]

    if any(check["query_status"] == "metadata_only" for check in comment_checks):
        return "metadata_only", [
            "Comments were returned for at least one proposed-rule document, but visible text was not confirmed in the sample payload."
        ]

    if comment_checks:
        return "not_confirmed", []

    return "unresolved", ["No relevant proposed-rule documents were available for comment retrieval checks."]


def check_regulations_gov(candidate: dict) -> dict:
    docket_id = candidate["docket_id"]
    result = {
        "status": "ok",
        "source_facts": {},
        "inference": {},
        "failures": [],
        "unknowns": [],
    }

    docket_response = get_regs(f"dockets/{docket_id}", {})
    if docket_response["status"] == "auth_failure":
        result["status"] = "blocked_by_auth"
        result["unknowns"].append(docket_response["message"])
        result["source_facts"]["docket_request_status"] = docket_response["status"]
        result["inference"]["comment_retrievability_status"] = "unresolved"
        return result
    if docket_response["status"] != "ok":
        result["status"] = "failed"
        result["failures"].append(f"Docket metadata check failed: {docket_response['message']}")
        result["source_facts"]["docket_request_status"] = docket_response["status"]
        result["inference"]["comment_retrievability_status"] = "unresolved"
        return result

    docket_attrs = ((docket_response["body"] or {}).get("data") or {}).get("attributes") or {}
    documents_response = fetch_regs_documents(docket_id, candidate["title"])
    if documents_response["status"] == "auth_failure":
        result["status"] = "blocked_by_auth"
        result["unknowns"].append(documents_response["message"])
        result["source_facts"]["docket_meta"] = {
            "title": docket_attrs.get("title"),
            "agency": docket_attrs.get("agencyId"),
            "type": docket_attrs.get("docketType"),
        }
        result["source_facts"]["documents_request_status"] = documents_response["status"]
        result["inference"]["comment_retrievability_status"] = "unresolved"
        return result
    if documents_response["status"] != "ok":
        result["status"] = "failed"
        result["failures"].append(f"Document listing failed: {documents_response['message']}")
        result["source_facts"]["docket_meta"] = {
            "title": docket_attrs.get("title"),
            "agency": docket_attrs.get("agencyId"),
            "type": docket_attrs.get("docketType"),
        }
        result["source_facts"]["documents_request_status"] = documents_response["status"]
        result["inference"]["comment_retrievability_status"] = "unresolved"
        return result

    all_docs = documents_response["documents"]
    proposed_docs = [
        doc for doc in all_docs
        if doc.get("document_type") == "Proposed Rule" and not doc.get("withdrawn")
    ]
    sorted_proposed_docs = sort_fr_candidates([
        {
            "non_main_keyword_flag": False,
            "title_alignment": doc.get("title_alignment"),
            "has_xml": False,
            "has_html": False,
            "publication_date": doc.get("posted_date"),
            **doc,
        }
        for doc in proposed_docs
    ])

    comment_checks = []
    for doc in sorted_proposed_docs:
        comment_checks.append(check_comment_retrieval_for_doc(doc))

    comment_retrievability_status, status_notes = determine_comment_retrievability(comment_checks)

    if not documents_response["sampled_all_pages"]:
        result["unknowns"].append(
            "Regulations.gov document listing was capped at the configured page limit; additional documents may exist beyond the sampled set."
        )
    if not proposed_docs:
        result["unknowns"].append("No non-withdrawn Proposed Rule documents were found in the sampled Regulations.gov documents.")
    if status_notes:
        result["unknowns"].extend(status_notes)

    for check in comment_checks:
        if check["query_status"] in {"auth_failure", "rate_limited", "network_error", "unexpected_http_status", "unknown"}:
            result["unknowns"].append(
                f"Comment check for document {check['document_id']} was unresolved: {check['message']}"
            )

    if comment_retrievability_status == "not_confirmed":
        result["failures"].append(
            "No proposed-rule document produced visible comment text through a completed Regulations.gov comment query."
        )

    result["source_facts"] = {
        "docket_meta": {
            "title": docket_attrs.get("title"),
            "agency": docket_attrs.get("agencyId"),
            "type": docket_attrs.get("docketType"),
        },
        "documents_returned_in_query": documents_response["documents_sampled"],
        "documents_total_reported": documents_response["documents_total_reported"],
        "sampled_all_pages": documents_response["sampled_all_pages"],
        "all_sampled_documents": all_docs,
        "relevant_proposed_rule_documents": proposed_docs,
        "comment_retrieval_checks": comment_checks,
    }
    result["inference"] = {
        "comment_retrievability_status": comment_retrievability_status,
        "document_level_matching_basis": "Repeated proposed-rule commentOnId checks using objectId only.",
    }

    if result["status"] != "blocked_by_auth":
        if result["failures"]:
            result["status"] = "failed"
        elif result["unknowns"]:
            result["status"] = "needs_manual_review"

    return result


def build_title_note(candidate: dict, fr: dict, regs: dict) -> str | None:
    candidate_title = candidate.get("title") or ""
    normalized_candidate_title = normalize_title_for_compare(candidate_title)
    notes = []

    fr_selected_titles = []
    fr_source = fr.get("source_facts") or {}
    for key in ("selected_proposed_rule", "selected_final_rule"):
        selected = fr_source.get(key) or {}
        live_title = selected.get("title")
        if live_title and normalize_title_for_compare(live_title) != normalized_candidate_title:
            fr_selected_titles.append(live_title)

    regs_title = ((regs.get("source_facts") or {}).get("docket_meta") or {}).get("title")
    if regs_title and normalize_title_for_compare(regs_title) != normalized_candidate_title:
        notes.append(
            f'Regulations.gov docket title differs from confirmed shortlist title: "{regs_title}".'
        )

    if fr_selected_titles:
        notes.append(
            "Federal Register selected titles differ from confirmed shortlist title; "
            "review title drift before treating metadata as canonical."
        )

    if notes:
        return " ".join(notes)
    return None


# ── Final assessment ───────────────────────────────────────────────────────────

def assess_phase0(candidate: dict, fr: dict, regs: dict, segmentation: dict, preamble: dict) -> dict:
    failures = []
    unknowns = []

    failures.extend(fr.get("failures", []))
    failures.extend(regs.get("failures", []))
    failures.extend(segmentation.get("failures", []))
    failures.extend(preamble.get("failures", []))

    unknowns.extend(fr.get("unknowns", []))
    unknowns.extend(regs.get("unknowns", []))
    unknowns.extend(segmentation.get("unknowns", []))
    unknowns.extend(preamble.get("unknowns", []))

    proposed_text_verified = fr.get("inference", {}).get("proposed_rule_text_verified", False)
    final_text_verified = fr.get("inference", {}).get("final_rule_text_verified", False)
    comment_status = regs.get("inference", {}).get("comment_retrievability_status")
    segmentation_status = segmentation.get("status")
    preamble_status = preamble.get("status")

    if regs.get("status") == "blocked_by_auth":
        status = "blocked_by_auth"
    elif failures:
        status = "fails_phase0_step2_checks"
    elif (
        proposed_text_verified
        and final_text_verified
        and comment_status == "confirmed"
        and segmentation_status in {"usable", "weak_but_usable"}
        and preamble_status == "present"
        and not unknowns
    ):
        status = "meets_phase0_step2_checks"
    else:
        status = "needs_manual_review"

    rationale = []
    if status == "blocked_by_auth":
        rationale.append("Regulations.gov authentication must succeed before comment retrievability can be treated as conclusive.")
    elif status == "fails_phase0_step2_checks":
        rationale.append("At least one required Phase 0 Step 2 check failed.")
    elif status == "meets_phase0_step2_checks":
        rationale.append("All required Phase 0 Step 2 checks passed without unresolved items.")
    else:
        rationale.append("Core checks did not clearly fail, but at least one unresolved item remains.")

    if comment_status == "metadata_only":
        rationale.append("Comments were returned, but visible text was not confirmed in the sampled payload.")
    if preamble_status == "weak_signal":
        rationale.append("Final-rule comment discussion was detected only weakly.")
    if fr.get("inference", {}).get("proposed_rule_pairing_status") != "selected":
        rationale.append("Federal Register proposed-rule selection still needs manual confirmation.")
    if fr.get("inference", {}).get("final_rule_pairing_status") != "selected":
        rationale.append("Federal Register final-rule selection still needs manual confirmation.")

    return {
        "status": status,
        "candidate_docket_id": candidate["docket_id"],
        "rationale": rationale,
        "failures": failures,
        "unknowns": unknowns,
    }


# ── Output formatting ──────────────────────────────────────────────────────────

def print_doc_line(prefix: str, doc: dict):
    if not doc:
        print(f"{prefix}(none selected)")
        return

    metrics = doc.get("title_alignment") or {}
    overlap = metrics.get("overlap_tokens") or []
    overlap_text = ", ".join(overlap[:5]) if overlap else "none"
    text_flags = "".join(filter(None, [
        "[XML]" if doc.get("has_xml") else "",
        "[HTML]" if doc.get("has_html") else "",
        "[PDF]" if doc.get("has_pdf") else "",
    ])) or "[no XML/HTML/PDF URLs]"
    print(
        f"{prefix}{doc.get('publication_date') or doc.get('posted_date') or '?'}  "
        f"{doc.get('document_number') or doc.get('id') or '?'}  {text_flags}"
    )
    print(f"{prefix}title: {doc.get('title')}")
    print(f"{prefix}title overlap tokens: {overlap_text}")
    if doc.get("fr_comment_count_screening_signal") is not None:
        print(
            f"{prefix}FR comment_count screening signal: "
            f"{doc.get('fr_comment_count_screening_signal')}"
        )


def print_docket_report(entry: dict):
    candidate = entry["candidate"]
    title_note = entry.get("title_note")
    fr = entry["federal_register_verification"]
    regs = entry["regulations_gov_verification"]
    segmentation = entry["segmentation_check"]
    preamble = entry["preamble_comment_discussion_check"]
    judgment = entry["inferred_judgment"]
    pad = "   "

    print(f"── {candidate['docket_id']}  ({candidate['title']})")
    if title_note:
        print(f"{pad}Title note: {title_note}")

    print(f"{pad}Federal Register status: {fr['status']}")
    if fr.get("source_facts"):
        sf = fr["source_facts"]
        print(
            f"{pad}FR documents returned: {sf.get('total_documents_returned', 0)} total, "
            f"{len(sf.get('all_proposed_rule_documents', []))} proposed, "
            f"{len(sf.get('all_final_rule_documents', []))} final, "
            f"{sf.get('notice_count', 0)} notices"
        )
        print(
            f"{pad}Pairing statuses: proposed={fr['inference'].get('proposed_rule_pairing_status')}, "
            f"final={fr['inference'].get('final_rule_pairing_status')}"
        )
        print(f"{pad}Selected proposed rule:")
        print_doc_line(f"{pad}  ", sf.get("selected_proposed_rule"))
        print(f"{pad}Selected final rule:")
        print_doc_line(f"{pad}  ", sf.get("selected_final_rule"))
        proposed_fetch = sf.get("selected_proposed_rule_text_fetch", {})
        final_fetch = sf.get("selected_final_rule_text_fetch", {})
        print(f"{pad}Proposed text fetch: {proposed_fetch.get('status')}")
        print(f"{pad}Final text fetch: {final_fetch.get('status')}")

    print(f"{pad}Segmentation check: {segmentation['status']}")
    print(
        f"{pad}  Proposed evidence: {segmentation['heuristic_result']['proposed_rule']['evidence']}"
    )
    print(
        f"{pad}  Final evidence:    {segmentation['heuristic_result']['final_rule']['evidence']}"
    )

    print(f"{pad}Preamble/comment discussion check: {preamble['status']}")
    if preamble["heuristic_result"]["matched_markers"]:
        markers = ", ".join(preamble["heuristic_result"]["matched_markers"])
        print(f"{pad}  Matched markers: {markers}")
    if preamble["heuristic_result"]["snippets"]:
        print(f"{pad}  Snippet: \"{preamble['heuristic_result']['snippets'][0]}\"")

    print(f"{pad}Regulations.gov status: {regs['status']}")
    if regs.get("source_facts"):
        sf = regs["source_facts"]
        meta = sf.get("docket_meta") or {}
        print(
            f"{pad}Regs docket confirmed: {meta.get('title', '(unavailable)')} "
            f"[agency={meta.get('agency')}, type={meta.get('type')}]"
        )
        print(
            f"{pad}Regs documents sampled: {sf.get('documents_returned_in_query')} "
            f"(reported total={sf.get('documents_total_reported')}, "
            f"sampled_all_pages={sf.get('sampled_all_pages')})"
        )
        print(
            f"{pad}Comment retrievability inference: "
            f"{regs['inference'].get('comment_retrievability_status')}"
        )
        for check in sf.get("comment_retrieval_checks", []):
            total = check.get("comments_total_reported")
            total_text = f"{total:,}" if isinstance(total, int) else str(total)
            print(
                f"{pad}  commentOnId check {check['document_id']} "
                f"(objectId={check['object_id']}): {check['query_status']} "
                f"[total={total_text}]"
            )
            if check.get("sample_text_preview"):
                print(f"{pad}    sample: \"{check['sample_text_preview']}\"")
            detail_check = check.get("detail_check") or {}
            if detail_check:
                print(
                    f"{pad}    detail check: {detail_check.get('status')} "
                    f"(comment_id={detail_check.get('comment_id')}, http_status={detail_check.get('http_status')})"
                )
                if detail_check.get("text_preview"):
                    print(f"{pad}      detail sample: \"{detail_check['text_preview']}\"")
    else:
        print(f"{pad}Regs note: {regs['unknowns'][0] if regs['unknowns'] else regs['failures'][0]}")

    print(f"{pad}Final judgment: {judgment['status']}")
    for line in judgment["rationale"]:
        print(f"{pad}  rationale: {line}")
    if judgment["failures"]:
        print(f"{pad}Failures:")
        for failure in judgment["failures"]:
            print(f"{pad}  - {failure}")
    if judgment["unknowns"]:
        print(f"{pad}Unknowns:")
        for unknown in judgment["unknowns"]:
            print(f"{pad}  - {unknown}")
    print()


def print_summary_table(results: list):
    grouped = {
        "meets_phase0_step2_checks": [],
        "needs_manual_review": [],
        "blocked_by_auth": [],
        "fails_phase0_step2_checks": [],
    }
    for result in results:
        status = result["inferred_judgment"]["status"]
        grouped.setdefault(status, []).append(result)

    print("=" * 72)
    print("PHASE 0 STEP 2 SUMMARY")
    print("=" * 72)
    print()
    for status in (
        "meets_phase0_step2_checks",
        "needs_manual_review",
        "blocked_by_auth",
        "fails_phase0_step2_checks",
    ):
        print(f"{status}:")
        rows = grouped.get(status) or []
        if not rows:
            print("  (none)")
        for row in rows:
            print(f"  {row['candidate']['docket_id']}  {row['candidate']['title']}")
        print()


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    print("=" * 72)
    print("Phase 0 Step 2 Feasibility Spike — EPA Docket Verification")
    print("=" * 72)
    print("This run keeps Regulations.gov auth, rate limits, failures, and unknowns separate.")
    print()

    all_results = []
    for candidate in CANDIDATES:
        print(f"Checking {candidate['docket_id']} ...")
        fr = check_federal_register(candidate)
        segmentation = check_segmentation(fr)
        preamble = check_preamble_comment_discussion(fr)
        regs = check_regulations_gov(candidate)
        judgment = assess_phase0(candidate, fr, regs, segmentation, preamble)
        title_note = build_title_note(candidate, fr, regs)

        entry = {
            "candidate": candidate,
            "title_note": title_note,
            "federal_register_verification": {
                key: value for key, value in fr.items() if key != "selected_texts"
            },
            "regulations_gov_verification": regs,
            "segmentation_check": segmentation,
            "preamble_comment_discussion_check": preamble,
            "inferred_judgment": judgment,
            "failures": judgment["failures"],
            "unknowns": judgment["unknowns"],
        }
        all_results.append(entry)
        print_docket_report(entry)

    print_summary_table(all_results)

    out_path = "feasibility_results.json"
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(all_results, handle, indent=2, ensure_ascii=False)
    print(f"Full results written to: {out_path}")


if __name__ == "__main__":
    run()
