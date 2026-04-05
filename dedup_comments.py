#!/usr/bin/env python3

import hashlib
import json
import os
import re
import zlib
from collections import defaultdict


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

FAMILY_TYPE_ORDER = {
    "form_letter": 0,
    "near_duplicate": 1,
    "exact_duplicate": 2,
    "unique": 3,
}


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
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def char_5grams(text: str) -> set[str]:
    if len(text) < 5:
        return set()
    return {text[index:index + 5] for index in range(len(text) - 4)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def length_buckets(text: str) -> set[int]:
    if not text:
        return {0}
    return {len(text) // 100, (len(text) + 50) // 100}


def build_bucket_keys(normalized_text: str, grams: set[str]) -> set[str]:
    if not normalized_text or not grams:
        return set()

    keys = set()
    prefix = normalized_text[:3]
    first_gram = normalized_text[:5] if len(normalized_text) >= 5 else normalized_text
    last_gram = normalized_text[-5:] if len(normalized_text) >= 5 else normalized_text

    for bucket in length_buckets(normalized_text):
        keys.add(f"prefix:{prefix}:{bucket}")
        keys.add(f"edge:{first_gram}:{last_gram}:{bucket}")
        for salt in ("a", "b", "c", "d"):
            signature = min(
                zlib.crc32(f"{salt}:{gram}".encode("utf-8"))
                for gram in grams
            )
            keys.add(f"minhash:{salt}:{signature}:{bucket}")

    return keys


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


def canonical_sort_key(member: dict):
    posted_date = member.get("posted_date") or "9999-99-99"
    return (-len(member["normalized_text"]), posted_date, member["comment_id"])


def build_family_payload(docket_id: str, comments: list[dict]) -> dict:
    enriched_comments = []
    hash_groups = defaultdict(list)

    for comment in comments:
        normalized = normalize_text(comment.get("text") or "")
        sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        enriched = {
            "comment_id": comment.get("comment_id"),
            "posted_date": comment.get("posted_date"),
            "normalized_text": normalized,
            "sha256": sha256,
            "grams": char_5grams(normalized),
        }
        enriched_comments.append(enriched)
        if normalized:
            hash_groups[sha256].append(enriched["comment_id"])

    union_find = UnionFind([comment["comment_id"] for comment in enriched_comments])
    comments_by_id = {comment["comment_id"]: comment for comment in enriched_comments}

    representative_ids = []
    seen_hashes = set()
    for comment in enriched_comments:
        if not comment["normalized_text"]:
            continue
        if comment["sha256"] in seen_hashes:
            continue
        seen_hashes.add(comment["sha256"])
        representative_ids.append(comment["comment_id"])

    bucket_to_ids = defaultdict(list)
    for comment_id in representative_ids:
        comment = comments_by_id[comment_id]
        for bucket_key in build_bucket_keys(comment["normalized_text"], comment["grams"]):
            bucket_to_ids[bucket_key].append(comment_id)

    candidate_pairs = set()
    for member_ids in bucket_to_ids.values():
        deduped_ids = sorted(set(member_ids))
        if len(deduped_ids) < 2:
            continue
        for left_index in range(len(deduped_ids)):
            for right_index in range(left_index + 1, len(deduped_ids)):
                candidate_pairs.add((deduped_ids[left_index], deduped_ids[right_index]))

    for left_id, right_id in sorted(candidate_pairs):
        left = comments_by_id[left_id]
        right = comments_by_id[right_id]
        if jaccard(left["grams"], right["grams"]) >= 0.80:
            union_find.union(left_id, right_id)

    for member_ids in hash_groups.values():
        if len(member_ids) < 2:
            continue
        anchor = member_ids[0]
        for member_id in member_ids[1:]:
            union_find.union(anchor, member_id)

    family_members = defaultdict(list)
    for comment in enriched_comments:
        family_members[union_find.find(comment["comment_id"])].append(comment["comment_id"])

    families = []
    for member_ids in family_members.values():
        members = [comments_by_id[member_id] for member_id in member_ids]
        hashes = {member["sha256"] for member in members}
        member_count = len(members)

        if len(hashes) == 1:
            family_type = "exact_duplicate" if member_count > 1 else "unique"
        elif member_count >= 3:
            family_type = "form_letter"
        elif member_count == 2:
            family_type = "near_duplicate"
        else:
            family_type = "unique"

        canonical = sorted(members, key=canonical_sort_key)[0]
        families.append(
            {
                "family_type": family_type,
                "canonical_comment_id": canonical["comment_id"],
                "member_count": member_count,
                "member_ids": sorted(member["comment_id"] for member in members),
            }
        )

    families.sort(
        key=lambda family: (
            FAMILY_TYPE_ORDER[family["family_type"]],
            -family["member_count"],
            family["canonical_comment_id"],
        )
    )

    for index, family in enumerate(families, start=1):
        family["family_id"] = f"{docket_id}_family_{index:04d}"

    counts = defaultdict(int)
    for family in families:
        counts[family["family_type"]] += 1

    return {
        "docket_id": docket_id,
        "total_comments": len(comments),
        "unique_families": len(families),
        "exact_duplicate_families": counts["exact_duplicate"],
        "near_duplicate_families": counts["near_duplicate"],
        "form_letter_families": counts["form_letter"],
        "unique_comment_families": counts["unique"],
        "families": families,
    }


def process_docket(docket_id: str) -> dict | None:
    comments_path = os.path.join(CORPUS_DIR, docket_id, "comments.json")
    output_path = os.path.join(CORPUS_DIR, docket_id, "comment_dedup.json")

    try:
        comments = read_json(comments_path)
    except FileNotFoundError:
        print_line("DEDUP", docket_id, f"error: missing required input {comments_path}")
        return None
    except OSError as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("DEDUP", docket_id, f"error: could not read comments input {path}")
        return None

    payload = build_family_payload(docket_id, comments)
    atomic_write_json(output_path, payload)

    print_line(
        "DEDUP",
        docket_id,
        f"{payload['total_comments']} comments → {payload['unique_families']} families  "
        f"({payload['exact_duplicate_families']} exact, {payload['near_duplicate_families']} near-dup, "
        f"{payload['form_letter_families']} form-letter, {payload['unique_comment_families']} unique)",
    )
    print_line("DEDUP", docket_id, f"written  corpus/{docket_id}/comment_dedup.json")
    return payload


def main():
    summaries = []

    for docket_id in DOCKET_IDS:
        payload = process_docket(docket_id)
        if payload is not None:
            summaries.append(payload)

    print("=== Phase 5 deduplication complete ===")
    for payload in summaries:
        print(
            f"{payload['docket_id']}   {payload['total_comments']} comments → {payload['unique_families']} families  "
            f"({payload['form_letter_families']} form-letter, {payload['near_duplicate_families']} near-dup, "
            f"{payload['exact_duplicate_families']} exact, {payload['unique_comment_families']} unique)"
        )


if __name__ == "__main__":
    main()
