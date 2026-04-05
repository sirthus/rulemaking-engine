#!/usr/bin/env python3

import json
import os
import re
import unicodedata
from collections import defaultdict


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

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

CFR_SECTION_SIGN_RE = re.compile(r"(?:§|\xa7|&#167;|&sect;)\s*(\d+\.\d+)", re.IGNORECASE)
PLAIN_CFR_RE = re.compile(r"\bsection\s+(\d{2,}\.\d+)\b", re.IGNORECASE)


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


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    return normalize_whitespace(text.lower())


def strip_outline_prefix(heading: str) -> str:
    original_heading = unicodedata.normalize("NFKC", heading or "").strip()
    if original_heading.startswith("§") or re.match(r"^\d{2,}\.\d+\b", original_heading):
        return original_heading
    return re.sub(r"^(?:[IVXivx]+|[A-Za-z]|\d)\.\s+", "", original_heading)


def normalize_heading(heading: str) -> str:
    heading = normalize_text(strip_outline_prefix(heading))
    heading = heading.replace("§", " ")
    heading = re.sub(r"[^a-z0-9\s]+", " ", heading)
    return normalize_whitespace(heading)


def heading_tokens(heading: str) -> set[str]:
    normalized = normalize_heading(heading)
    return {
        token
        for token in normalized.split()
        if len(token) >= 2 and token not in STOPWORDS
    }


def body_tokens(text: str) -> set[str]:
    normalized = normalize_text(text)
    return {
        token
        for token in re.findall(r"\b[a-z]{4,}\b", normalized)
        if token not in STOPWORDS
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def truncate_snippet(text: str, limit: int = 500) -> str:
    text = normalize_whitespace(text)
    if len(text) <= limit:
        return text

    cutoff = limit
    if cutoff < len(text) and not text[cutoff].isspace():
        while cutoff > 0 and not text[cutoff - 1].isspace():
            cutoff -= 1
    if cutoff == 0:
        cutoff = limit

    return f"{text[:cutoff].rstrip()} [...]"


def extract_cfr_numbers(*texts: str) -> list[str]:
    numbers = []
    seen = set()

    for text in texts:
        normalized = unicodedata.normalize("NFKC", text or "")
        for pattern in (CFR_SECTION_SIGN_RE, PLAIN_CFR_RE):
            for number in pattern.findall(normalized):
                if number in seen:
                    continue
                seen.add(number)
                numbers.append(number)

    return numbers


def comment_relationship_label(attribution_method: str, confidence: str) -> str:
    if attribution_method == "citation" and confidence == "high":
        return "related concern cited in comment"
    if attribution_method == "keyword" and confidence == "medium":
        return "related concern present in comments"
    if attribution_method == "keyword" and confidence == "low":
        return "possible related concern in comments"
    return "ambiguous relationship"


def format_optional(value) -> str:
    return "null" if value is None else str(value)


def comment_signal_points(comment: dict) -> int:
    attribution_method = comment.get("attribution_method")
    confidence = comment.get("confidence")

    if attribution_method == "citation" and confidence == "high":
        return 3
    if attribution_method == "keyword" and confidence == "medium":
        return 2
    if attribution_method == "keyword" and confidence == "low":
        return 1
    return 1


def preamble_signal_points(link: dict) -> int:
    if link.get("link_type") == "cfr_citation":
        return 3
    if link.get("link_type") == "keyword":
        return 1
    return 0


def confidence_rank(confidence: str) -> int:
    return {
        "none": 0,
        "low": 1,
        "medium": 2,
        "high": 3,
    }.get(confidence or "none", 0)


def best_comment_signal(comment_records: list[dict]) -> tuple[str, str]:
    if not comment_records:
        return "none", "none"

    ranked = sorted(
        comment_records,
        key=lambda comment: (
            comment_signal_points(comment),
            confidence_rank(comment.get("confidence")),
            1 if comment.get("attribution_method") == "citation" else 0,
        ),
        reverse=True,
    )
    best = ranked[0]
    return best.get("attribution_method") or "unknown", best.get("confidence") or "none"


def load_dedup_metadata(base_dir: str) -> dict:
    dedup_path = os.path.join(base_dir, "comment_dedup.json")
    try:
        payload = read_json(dedup_path)
    except (FileNotFoundError, OSError):
        return {
            "dedup_available": False,
            "comment_to_family_id": {},
            "family_member_count": {},
            "family_canonical": {},
        }

    comment_to_family_id = {}
    family_member_count = {}
    family_canonical = {}
    for family in payload.get("families", []):
        family_id = family.get("family_id")
        if not family_id:
            continue
        family_member_count[family_id] = family.get("member_count", 1)
        family_canonical[family_id] = family.get("canonical_comment_id")
        for comment_id in family.get("member_ids", []):
            comment_to_family_id[comment_id] = family_id

    return {
        "dedup_available": True,
        "comment_to_family_id": comment_to_family_id,
        "family_member_count": family_member_count,
        "family_canonical": family_canonical,
    }


def build_alignment_signal(card: dict, dedup_metadata: dict) -> dict:
    related_comments = card.get("related_comments", [])
    preamble_links = card.get("preamble_links", [])
    dedup_available = dedup_metadata["dedup_available"]

    family_ids = []
    family_to_max_points = {}
    for index, comment in enumerate(related_comments):
        comment_id = comment.get("comment_id")
        if comment_id is None:
            family_id = f"_null_{index}"
        else:
            family_id = dedup_metadata["comment_to_family_id"].get(comment_id) if dedup_available else None
        if family_id is None:
            family_id = comment_id
        family_ids.append(family_id)
        family_to_max_points[family_id] = max(
            family_to_max_points.get(family_id, 0),
            comment_signal_points(comment),
        )

    if dedup_available:
        score = sum(family_to_max_points.values())
    else:
        score = sum(comment_signal_points(comment) for comment in related_comments)
    score += sum(preamble_signal_points(link) for link in preamble_links)

    if score == 0:
        level = "none"
    elif score <= 2:
        level = "low"
    elif score <= 5:
        level = "medium"
    else:
        level = "high"

    comment_count = len(related_comments)
    unique_comment_count = len(set(family_ids)) if dedup_available else None
    largest_family_size = None
    if dedup_available and family_ids:
        largest_family_size = max(
            dedup_metadata["family_member_count"].get(family_id, 1)
            for family_id in set(family_ids)
        )
    best_attribution_confidence = "none"
    if related_comments:
        best_attribution_confidence = max(
            (comment.get("confidence") or "none" for comment in related_comments),
            key=confidence_rank,
        )

    preamble_link_count = len(preamble_links)
    best_link_type = "none"
    if any(link.get("link_type") == "cfr_citation" for link in preamble_links):
        best_link_type = "cfr_citation"
    elif any(link.get("link_type") == "keyword" for link in preamble_links):
        best_link_type = "keyword"

    best_comment_method, best_comment_confidence = best_comment_signal(related_comments)
    if comment_count == 0 and preamble_link_count == 0:
        evidence_note = "No substantive inline comments or preamble discussion linked to this section."
    else:
        if comment_count == 0:
            comment_note = "No inline comments"
        elif dedup_available and unique_comment_count != comment_count:
            comment_note = (
                f"{comment_count} comments ({unique_comment_count} unique arguments) attributed "
                f"(best: {best_comment_method}/{best_comment_confidence})"
            )
        elif comment_count == 1 and best_comment_method == "citation" and best_comment_confidence == "high":
            comment_note = "1 comment attributed by citation (high confidence)"
        elif comment_count == 1:
            comment_note = f"1 comment attributed (best: {best_comment_method}/{best_comment_confidence})"
        else:
            comment_note = f"{comment_count} comments attributed (best: {best_comment_method}/{best_comment_confidence})"

        if preamble_link_count == 0:
            preamble_note = "no preamble discussion linked."
        elif preamble_link_count == 1 and best_link_type == "cfr_citation":
            preamble_note = "1 preamble section linked by CFR citation."
        elif preamble_link_count == 1:
            preamble_note = "1 preamble section linked by keyword overlap."
        elif best_link_type == "cfr_citation":
            preamble_note = f"{preamble_link_count} preamble sections linked (CFR citation)."
        else:
            preamble_note = f"{preamble_link_count} preamble sections linked (keyword overlap)."

        evidence_note = f"{comment_note}; {preamble_note}"

    return {
        "level": level,
        "score": score,
        "features": {
            "comment_count": comment_count,
            "unique_comment_count": unique_comment_count,
            "largest_family_size": largest_family_size,
            "best_attribution_confidence": best_attribution_confidence,
            "preamble_link_count": preamble_link_count,
            "best_link_type": best_link_type,
        },
        "evidence_note": evidence_note,
    }


def load_docket_inputs(docket_id: str) -> dict:
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    section_alignment = read_json(os.path.join(base_dir, "section_alignment.json"))
    comment_attribution = read_json(os.path.join(base_dir, "comment_attribution.json"))
    proposed_sections = read_json(os.path.join(base_dir, "proposed_rule.json"))
    final_sections = read_json(os.path.join(base_dir, "final_rule.json"))
    comments = read_json(os.path.join(base_dir, "comments.json"))
    dedup_metadata = load_dedup_metadata(base_dir)

    return {
        "base_dir": base_dir,
        "section_alignment": section_alignment,
        "comment_attribution": comment_attribution,
        "proposed_by_id": {section["section_id"]: section for section in proposed_sections},
        "final_by_id": {section["section_id"]: section for section in final_sections},
        "comments_by_id": {comment["comment_id"]: comment for comment in comments},
        "final_sections": final_sections,
        "dedup_metadata": dedup_metadata,
    }


def build_comment_index(comment_attribution: list[dict], comments_by_id: dict) -> dict[str, list[dict]]:
    index = defaultdict(list)

    for record in comment_attribution:
        if record.get("classification") != "substantive_inline":
            continue
        if record.get("comment_id") not in comments_by_id:
            continue
        for target_section_id in record.get("target_sections", []):
            index[target_section_id].append(record)

    return index


def build_preamble_index(final_sections: list[dict]):
    preamble_sections = []
    cfr_index = defaultdict(list)

    for order, section in enumerate(final_sections):
        if section.get("source") != "preamble":
            continue

        enriched = {
            "section_id": section.get("section_id"),
            "heading": section.get("heading"),
            "body_text": section.get("body_text") or "",
            "order": order,
            "body_tokens": body_tokens((section.get("body_text") or "")[:3000]),
        }
        preamble_sections.append(enriched)

        for cfr_number in extract_cfr_numbers(section.get("heading"), section.get("body_text")):
            cfr_index[cfr_number].append(enriched["section_id"])

    return preamble_sections, cfr_index


def build_related_comments(card: dict, comment_index: dict[str, list[dict]]) -> list[dict]:
    if card["change_type"] == "added":
        return []

    related = []
    proposed_section_id = card["proposed_section_id"]
    for record in comment_index.get(proposed_section_id, []):
        related.append(
            {
                "comment_id": record.get("comment_id"),
                "attribution_method": record.get("attribution_method"),
                "confidence": record.get("confidence"),
                "relationship_label": comment_relationship_label(
                    record.get("attribution_method"),
                    record.get("confidence"),
                ),
            }
        )
    return related


def build_preamble_links(cards: list[dict], preamble_sections: list[dict], preamble_cfr_index: dict[str, list[str]]):
    preamble_by_id = {section["section_id"]: section for section in preamble_sections}

    for card in cards:
        try:
            cfr_links = []
            linked_preamble_ids = set()

            for cfr_number in card["_card_cfr_numbers"]:
                for preamble_section_id in preamble_cfr_index.get(cfr_number, []):
                    if preamble_section_id in linked_preamble_ids:
                        continue
                    linked_preamble_ids.add(preamble_section_id)
                    preamble_section = preamble_by_id[preamble_section_id]
                    cfr_links.append(
                        {
                            "preamble_section_id": preamble_section_id,
                            "preamble_heading": preamble_section.get("heading"),
                            "link_type": "cfr_citation",
                            "link_score": 1.0,
                            "relationship_label": "same section cited in preamble discussion",
                            "_order": preamble_section["order"],
                        }
                    )

            cfr_links.sort(key=lambda link: (link["_order"], link["preamble_section_id"]))

            keyword_links = []
            if card["_heading_tokens"]:
                for preamble_section in preamble_sections:
                    preamble_section_id = preamble_section["section_id"]
                    if preamble_section_id in linked_preamble_ids:
                        continue
                    score = jaccard(card["_heading_tokens"], preamble_section["body_tokens"])
                    if score < 0.15:
                        continue
                    keyword_links.append(
                        {
                            "preamble_section_id": preamble_section_id,
                            "preamble_heading": preamble_section.get("heading"),
                            "link_type": "keyword",
                            "link_score": round(score, 4),
                            "relationship_label": "same issue discussed in preamble",
                            "_order": preamble_section["order"],
                        }
                    )

            keyword_links.sort(
                key=lambda link: (-link["link_score"], link["_order"], link["preamble_section_id"])
            )

            selected_links = (cfr_links + keyword_links)[:5]
            for link in selected_links:
                link.pop("_order", None)
            card["preamble_links"] = selected_links
        except Exception as exc:
            print_line("CARDS", card.get("docket_id", "unknown"), f"warning: preamble linkage skipped for {card.get('card_id', 'unknown_card')}: {exc}")
            card["preamble_links"] = []


def generate_cards_for_docket(docket_id: str) -> tuple[list[dict], dict, dict]:
    inputs = load_docket_inputs(docket_id)
    changed_alignment_records = [
        record
        for record in inputs["section_alignment"]
        if record.get("change_type") in {"modified", "added", "removed"}
    ]
    substantive_inline_records = [
        record
        for record in inputs["comment_attribution"]
        if record.get("classification") == "substantive_inline"
    ]
    comment_index = build_comment_index(
        inputs["comment_attribution"],
        inputs["comments_by_id"],
    )
    preamble_sections, preamble_cfr_index = build_preamble_index(inputs["final_sections"])

    cards = []
    changed_card_sequence = 0

    for record in inputs["section_alignment"]:
        change_type = record.get("change_type")
        if change_type not in {"modified", "added", "removed"}:
            continue

        changed_card_sequence += 1
        card_id = f"{docket_id}_card_{changed_card_sequence:04d}"

        try:
            proposed_section_id = record.get("proposed_section_id")
            final_section_id = record.get("final_section_id")
            proposed_section = inputs["proposed_by_id"].get(proposed_section_id) if proposed_section_id else None
            final_section = inputs["final_by_id"].get(final_section_id) if final_section_id else None

            linkage_heading = None
            if final_section is not None and final_section.get("source") == "regulatory_text":
                linkage_heading = final_section.get("heading")
            elif proposed_section is not None and proposed_section.get("source") == "regulatory_text":
                linkage_heading = proposed_section.get("heading")
            else:
                linkage_heading = record.get("final_heading") or record.get("proposed_heading")

            card = {
                "card_id": card_id,
                "docket_id": docket_id,
                "change_type": change_type,
                "match_type": record.get("match_type"),
                "heading_similarity": record.get("heading_similarity"),
                "proposed_section_id": proposed_section_id,
                "final_section_id": final_section_id,
                "proposed_heading": record.get("proposed_heading"),
                "final_heading": record.get("final_heading"),
                "proposed_text_snippet": ""
                if proposed_section is None
                else truncate_snippet(proposed_section.get("body_text") or ""),
                "final_text_snippet": ""
                if final_section is None
                else truncate_snippet(final_section.get("body_text") or ""),
                "related_comments": [],
                "preamble_links": [],
                "alignment_signal": {},
                "review_status": "pending",
                "_heading_tokens": heading_tokens(linkage_heading or ""),
                "_card_cfr_numbers": [],
            }

            if change_type in {"modified", "added"} and linkage_heading:
                card["_card_cfr_numbers"] = extract_cfr_numbers(linkage_heading)

            card["related_comments"] = build_related_comments(card, comment_index)
            cards.append(card)
        except Exception as exc:
            print_line("CARDS", docket_id, f"warning: skipped {card_id}: {exc}")
            continue

    build_preamble_links(cards, preamble_sections, preamble_cfr_index)
    for card in cards:
        card["alignment_signal"] = build_alignment_signal(card, inputs["dedup_metadata"])

    for card in cards:
        card.pop("_heading_tokens", None)
        card.pop("_card_cfr_numbers", None)

    summary = {
        "modified": sum(1 for card in cards if card["change_type"] == "modified"),
        "added": sum(1 for card in cards if card["change_type"] == "added"),
        "removed": sum(1 for card in cards if card["change_type"] == "removed"),
        "commented": sum(1 for card in cards if card["related_comments"]),
        "preamble_linked": sum(1 for card in cards if card["preamble_links"]),
    }
    stats = {
        "alignment_records": len(inputs["section_alignment"]),
        "changed_sections": len(changed_alignment_records),
        "substantive_inline_records": len(substantive_inline_records),
        "preamble_sections_indexed": len(preamble_sections),
    }
    return cards, summary, stats


def render_card_report(card: dict) -> str:
    signal_features = card["alignment_signal"]["features"]
    signal_summary = f"  comment_count={signal_features['comment_count']}  "
    if signal_features["unique_comment_count"] is not None:
        signal_summary += f"unique_comment_count={signal_features['unique_comment_count']}  "
    signal_summary += (
        f"best_attribution={signal_features['best_attribution_confidence']}  "
        f"preamble_link_count={signal_features['preamble_link_count']}  "
        f"best_link_type={signal_features['best_link_type']}"
    )

    lines = [
        "=" * 80,
        f"CARD: {card['card_id']}",
        f"TYPE: {card['change_type']}  |  MATCH: {card['match_type']}  |  HEADING SIM: {float(card['heading_similarity']):.2f}",
        f'PROPOSED: {format_optional(card["proposed_section_id"])}  "{format_optional(card["proposed_heading"])}"',
        f'FINAL:    {format_optional(card["final_section_id"])}  "{format_optional(card["final_heading"])}"',
        "",
        "PROPOSED TEXT:",
        f"  {card['proposed_text_snippet']}",
        "",
        "FINAL TEXT:",
        f"  {card['final_text_snippet']}",
        "",
    ]

    if card["related_comments"]:
        lines.append(f"RELATED COMMENTS ({len(card['related_comments'])}):")
        for comment in card["related_comments"]:
            lines.append(
                f"  {comment['comment_id']}  [{comment['attribution_method']} / {comment['confidence']}]  {comment['relationship_label']}"
            )
    else:
        lines.append("RELATED COMMENTS (0): none")

    lines.append("")

    if card["preamble_links"]:
        lines.append(f"PREAMBLE LINKS ({len(card['preamble_links'])}):")
        for link in card["preamble_links"]:
            lines.append(
                f"  {link['preamble_section_id']}  [{link['link_type']} / {link['link_score']:.4f}]"
            )
            lines.append(f'    "{format_optional(link["preamble_heading"])}"')
            lines.append(f"    {link['relationship_label']}")
    else:
        lines.append("PREAMBLE LINKS (0): none")

    lines.extend(
        [
            "",
            f"ALIGNMENT SIGNAL: {card['alignment_signal']['level']}  (score {card['alignment_signal']['score']})",
            signal_summary,
            f"  {card['alignment_signal']['evidence_note']}",
            "",
            f"REVIEW STATUS: {card['review_status']}",
            "=" * 80,
        ]
    )
    return "\n".join(lines)


def render_report(cards: list[dict], docket_summaries: list[tuple[str, dict]]) -> str:
    report_parts = []

    for card in cards:
        report_parts.append(render_card_report(card))

    report_parts.append("=== Phase 5 change cards complete ===")
    for docket_id, summary in docket_summaries:
        report_parts.append(
            f"{docket_id}   modified {summary['modified']} | "
            f"added {summary['added']} | "
            f"removed {summary['removed']} | "
            f"commented {summary['commented']} | "
            f"preamble-linked {summary['preamble_linked']}"
        )

    return "\n".join(report_parts) + "\n"


def main():
    docket_outputs = []
    docket_summaries = []

    for docket_id in DOCKET_IDS:
        base_dir = os.path.join(CORPUS_DIR, docket_id)
        json_path = os.path.join(base_dir, "change_cards.json")
        report_path = os.path.join(base_dir, "change_cards_report.txt")

        try:
            print_line("CARDS", docket_id, "loading inputs...")
            cards, summary, stats = generate_cards_for_docket(docket_id)
            print_line(
                "CARDS",
                docket_id,
                f"{stats['alignment_records']} alignment records \u2192 {stats['changed_sections']} changed sections",
            )
            print_line(
                "CARDS",
                docket_id,
                f"{stats['substantive_inline_records']} attribution records (substantive inline)",
            )
            print_line(
                "CARDS",
                docket_id,
                f"indexing {stats['preamble_sections_indexed']} preamble sections for linkage...",
            )
            print_line(
                "CARDS",
                docket_id,
                f"generated {len(cards)} change cards ({summary['commented']} commented, {summary['preamble_linked']} preamble-linked)",
            )

            atomic_write_json(json_path, cards)
            docket_outputs.append((docket_id, base_dir, cards))
            docket_summaries.append((docket_id, summary))
            print_line("CARDS", docket_id, f"written  {os.path.relpath(json_path, ROOT_DIR)}")
        except (FileNotFoundError, OSError) as exc:
            path = getattr(exc, "filename", None) or str(exc)
            print_line("CARDS", docket_id, f"error: skipping docket due to file I/O problem: {path}")
            continue

    for _docket_id, base_dir, cards in docket_outputs:
        report_path = os.path.join(base_dir, "change_cards_report.txt")
        try:
            atomic_write_text(report_path, render_report(cards, docket_summaries))
            print_line("CARDS", _docket_id, f"written  {os.path.relpath(report_path, ROOT_DIR)}")
        except OSError as exc:
            path = getattr(exc, "filename", None) or str(exc)
            print_line("CARDS", _docket_id, f"error: could not write report: {path}")


if __name__ == "__main__":
    main()
