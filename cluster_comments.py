#!/usr/bin/env python3

import html
import json
import math
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

COMMENTER_TYPES = [
    "individual",
    "business",
    "trade_association",
    "ngo_advocacy",
    "academic",
    "government",
    "unknown",
]

# Core + rulemaking-domain stopwords are used here so shared words like "rule",
# "comment", and "EPA" do not dominate clustering or theme keyword extraction.
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
    "also",
    "have",
    "has",
    "been",
    "were",
    "will",
    "would",
    "should",
    "could",
    "their",
    "they",
    "them",
    "when",
    "where",
    "such",
    "more",
    "than",
    "rule",
    "rulemaking",
    "comment",
    "comments",
    "section",
    "sections",
    "final",
    "proposed",
    "federal",
    "register",
    "agency",
    "epa",
}

TOKEN_RE = re.compile(r"\b[a-z]{4,}\b")
HTML_TAG_RE = re.compile(r"<[^>]+>")

COMMENTER_RULES = [
    (
        "government",
        [
            "epa",
            "state of",
            "department of",
            "office of",
            "bureau of",
            "agency",
            "division",
            "administration",
            "commission",
            "district",
            "county",
            "city of",
            "town of",
            "u.s. ",
            "united states",
        ],
    ),
    (
        "trade_association",
        [
            "association",
            "council",
            "federation",
            "alliance",
            "chamber of",
            "coalition",
            "consortium",
            "industry",
        ],
    ),
    (
        "academic",
        [
            "university",
            "college",
            "school of",
            "institute",
            "research institute",
            "professor",
            "dr.",
        ],
    ),
    (
        "ngo_advocacy",
        [
            "fund",
            "foundation",
            "society",
            "center for",
            "centre for",
            "action",
            "earthjustice",
            "sierra",
            "clean air",
            "environmental defense",
            "conservation",
            "advocacy",
        ],
    ),
    (
        "business",
        [
            " inc.",
            " inc,",
            " llc",
            " corp.",
            " corporation",
            " company",
            " co.",
            " ltd.",
            " limited",
            "industries",
            "services",
            "solutions",
            "technologies",
            "manufacturing",
        ],
    ),
]


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


def normalize_text(text: str) -> str:
    unescaped = html.unescape(text or "")
    without_tags = HTML_TAG_RE.sub(" ", unescaped)
    return re.sub(r"\s+", " ", without_tags.lower()).strip()


class UnionFind:
    def __init__(self, items: list[str]):
        self.parent = {item: item for item in items}
        self.rank = {item: 0 for item in items}

    def find(self, item: str) -> str:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: str, right: str):
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return

        left_rank = self.rank[left_root]
        right_rank = self.rank[right_root]
        if left_rank < right_rank:
            self.parent[left_root] = right_root
        elif left_rank > right_rank:
            self.parent[right_root] = left_root
        else:
            self.parent[right_root] = left_root
            self.rank[left_root] += 1


def classify_commenter_type(submitter_name: str | None) -> str:
    normalized = normalize_text(submitter_name)
    if not normalized:
        return "unknown"

    for commenter_type, needles in COMMENTER_RULES:
        if any(needle in normalized for needle in needles):
            return commenter_type

    if " " in normalized:
        return "individual"
    return "unknown"


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text) if token not in STOPWORDS]


def keyword_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def top_local_keywords(tokens: list[str], limit: int = 15) -> list[str]:
    counts = Counter(tokens)
    return [
        token
        for token, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def tfidf_keywords(tokenized_documents: dict[str, list[str]]) -> tuple[dict[str, dict[str, float]], dict[str, list[str]]]:
    document_count = len(tokenized_documents)
    document_frequency = Counter()
    for tokens in tokenized_documents.values():
        for token in set(tokens):
            document_frequency[token] += 1

    keyword_scores = {}
    keyword_lists = {}
    for canonical_id, tokens in tokenized_documents.items():
        total_tokens = max(1, len(tokens))
        token_counts = Counter(tokens)
        scores = {}
        for token, count in token_counts.items():
            tf = count / total_tokens
            idf = math.log((1 + document_count) / (1 + document_frequency[token])) + 1.0
            scores[token] = tf * idf
        top_items = sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:15]
        keyword_scores[canonical_id] = dict(top_items)
        keyword_lists[canonical_id] = [token for token, _score in top_items]

    return keyword_scores, keyword_lists


def zero_type_counts() -> dict[str, int]:
    return {commenter_type: 0 for commenter_type in COMMENTER_TYPES}


def cluster_payload_for_docket(docket_id: str) -> dict | None:
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    comments_path = os.path.join(base_dir, "comments.json")
    dedup_path = os.path.join(base_dir, "comment_dedup.json")
    output_path = os.path.join(base_dir, "comment_themes.json")

    try:
        comments = read_json(comments_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("THEMES", docket_id, f"error: could not read comments input {path}")
        return None

    try:
        dedup = read_json(dedup_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("THEMES", docket_id, f"error: missing required dedup input {path}")
        return None

    comments_by_id = {comment.get("comment_id"): comment for comment in comments}
    commenter_types = {}
    commenter_type_counts = zero_type_counts()
    for comment in comments:
        comment_id = comment.get("comment_id")
        commenter_type = classify_commenter_type(comment.get("submitter_name"))
        commenter_types[comment_id] = commenter_type
        commenter_type_counts[commenter_type] += 1

    canonical_entries = []
    family_member_count = {}
    for family in dedup.get("families", []):
        canonical_id = family.get("canonical_comment_id")
        if canonical_id not in comments_by_id:
            print_line("THEMES", docket_id, f"warning: canonical comment missing from comments.json: {canonical_id}")
            continue
        comment = comments_by_id[canonical_id]
        normalized_text = normalize_text(comment.get("text") or "")
        entry = {
            "canonical_comment_id": canonical_id,
            "family_member_count": family.get("member_count", 1),
            "classification": comment.get("classification"),
            "normalized_text": normalized_text,
            "commenter_type": commenter_types.get(canonical_id, "unknown"),
        }
        canonical_entries.append(entry)
        family_member_count[canonical_id] = entry["family_member_count"]

    eligible_entries = []
    singleton_entries = []
    eligible_tokens = {}
    singleton_keywords = {}
    for entry in canonical_entries:
        tokens = tokenize(entry["normalized_text"])
        is_eligible = (
            entry["classification"] == "substantive_inline"
            and len(entry["normalized_text"]) >= 50
        )
        if is_eligible:
            eligible_entries.append(entry)
            eligible_tokens[entry["canonical_comment_id"]] = tokens
        else:
            singleton_entries.append(entry)
            singleton_keywords[entry["canonical_comment_id"]] = top_local_keywords(tokens)

    keyword_scores, keyword_lists = tfidf_keywords(eligible_tokens) if eligible_entries else ({}, {})

    union_find = UnionFind([entry["canonical_comment_id"] for entry in eligible_entries])
    eligible_ids = [entry["canonical_comment_id"] for entry in eligible_entries]
    for left_index in range(len(eligible_ids)):
        left_id = eligible_ids[left_index]
        left_keywords = set(keyword_lists.get(left_id, []))
        for right_index in range(left_index + 1, len(eligible_ids)):
            right_id = eligible_ids[right_index]
            right_keywords = set(keyword_lists.get(right_id, []))
            if keyword_jaccard(left_keywords, right_keywords) >= 0.15:
                union_find.union(left_id, right_id)

    cluster_members = defaultdict(list)
    for canonical_id in eligible_ids:
        cluster_members[union_find.find(canonical_id)].append(canonical_id)
    for entry in singleton_entries:
        cluster_members[entry["canonical_comment_id"]].append(entry["canonical_comment_id"])

    canonical_entry_by_id = {
        entry["canonical_comment_id"]: entry
        for entry in canonical_entries
    }

    clusters = []
    for member_ids in cluster_members.values():
        sorted_members = sorted(member_ids)
        commenter_distribution = zero_type_counts()
        total_raw_comments = 0
        aggregate_keyword_scores = Counter()
        non_clustering_singleton = len(member_ids) == 1 and member_ids[0] in singleton_keywords

        for canonical_id in sorted_members:
            entry = canonical_entry_by_id[canonical_id]
            member_count = family_member_count.get(canonical_id, 1)
            commenter_distribution[entry["commenter_type"]] += member_count
            total_raw_comments += member_count
            if canonical_id in keyword_scores:
                aggregate_keyword_scores.update(keyword_scores[canonical_id])

        if non_clustering_singleton:
            top_keywords = singleton_keywords.get(sorted_members[0], [])
        else:
            top_keywords = [
                token
                for token, _score in sorted(
                    aggregate_keyword_scores.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:20]
            ]

        clusters.append(
            {
                "canonical_count": len(sorted_members),
                "total_raw_comments": total_raw_comments,
                "member_canonical_ids": sorted_members,
                "top_keywords": top_keywords,
                "commenter_type_distribution": commenter_distribution,
                "label": None,
            }
        )

    clusters.sort(
        key=lambda cluster: (
            -cluster["total_raw_comments"],
            -cluster["canonical_count"],
            cluster["member_canonical_ids"][0],
        )
    )

    for index, cluster in enumerate(clusters, start=1):
        cluster["cluster_id"] = f"{docket_id}_cluster_{index:04d}"

    payload = {
        "docket_id": docket_id,
        "generated_at": utc_now_iso(),
        "total_comments": len(comments),
        "total_canonical_comments": len(canonical_entries),
        "clustering_eligible_canonicals": len(eligible_entries),
        "non_clustering_singletons": len(singleton_entries),
        "total_clusters": len(clusters),
        "commenter_type_counts": commenter_type_counts,
        "commenter_types": commenter_types,
        "clusters": clusters,
    }

    atomic_write_json(output_path, payload)

    mix = "  ".join(
        f"{commenter_type_counts[commenter_type]} {commenter_type}"
        for commenter_type in COMMENTER_TYPES
    )
    print_line(
        "THEMES",
        docket_id,
        f"{len(canonical_entries)} canonical comments -> {len(clusters)} clusters  "
        f"({len(eligible_entries)} eligible, {len(singleton_entries)} singletons)",
    )
    print_line("THEMES", docket_id, f"commenter mix: {mix}")
    print_line("THEMES", docket_id, f"written  corpus/{docket_id}/comment_themes.json")
    return payload


def main():
    summaries = []
    for docket_id in DOCKET_IDS:
        payload = cluster_payload_for_docket(docket_id)
        if payload is not None:
            summaries.append(payload)

    print("=== Phase 6 comment clustering complete ===")
    for payload in summaries:
        print(
            f"{payload['docket_id']}   {payload['total_comments']} comments  "
            f"{payload['total_canonical_comments']} canonical  {payload['total_clusters']} clusters"
        )


if __name__ == "__main__":
    main()
