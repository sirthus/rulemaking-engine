from datetime import datetime

import generate_insights


def sample_report():
    return {
        "schema_version": "v1",
        "docket_id": "TEST-DOCKET",
        "clusters": [
            {
                "cluster_id": "cluster-schedule",
                "label": "Schedule Compliance",
                "label_description": "Submitters discussed schedule compliance.",
                "canonical_count": 3,
            },
            {
                "cluster_id": "cluster-cost",
                "label": "Comment Cost Burden",
                "label_description": "Submitters said costs drove planning changes.",
                "canonical_count": 7,
            },
            {
                "cluster_id": "cluster-null",
                "label": None,
                "label_description": "This unlabeled theme should not be emitted.",
                "canonical_count": 20,
            },
        ],
        "change_cards": [
            {
                "card_id": "card-1",
                "section_title": "Schedule section",
                "change_type": "modified",
                "proposed_section_id": "section-1",
                "alignment_signal": {
                    "level": "high",
                    "score": 5,
                    "evidence_note": "Schedule comments prompted close review.",
                },
                "related_clusters": [{"cluster_id": "cluster-schedule"}],
            },
            {
                "card_id": "card-2",
                "section_title": "Cost section",
                "change_type": "added",
                "proposed_section_id": "section-2",
                "alignment_signal": {
                    "level": "medium",
                    "score": 9,
                    "evidence_note": "Cost comments were linked.",
                },
                "related_clusters": [{"cluster_id": "cluster-cost"}],
            },
            {
                "card_id": "card-3",
                "section_title": "Unlabeled section",
                "change_type": "removed",
                "proposed_section_id": "section-3",
                "alignment_signal": {
                    "level": "low",
                    "score": 1,
                    "evidence_note": "Low signal.",
                },
                "related_clusters": [{"cluster_id": "cluster-null"}],
            },
            {
                "card_id": "card-4",
                "section_title": "Residual section",
                "change_type": "modified",
                "proposed_section_id": "section-4",
                "alignment_signal": {
                    "level": "high",
                    "score": 7,
                    "evidence_note": "Residual signal.",
                },
                "related_clusters": [],
            },
            {
                "card_id": "card-5",
                "section_title": "No related clusters section",
                "change_type": "modified",
                "proposed_section_id": "section-5",
                "alignment_signal": {
                    "level": "none",
                    "score": 0,
                    "evidence_note": "No signal.",
                },
                "related_clusters": [],
            },
        ],
    }


def build_report(eval_report=None):
    return generate_insights.build_insight_report(
        sample_report(),
        eval_report=eval_report,
        generated_at="2026-04-07T12:00:00+00:00",
    )


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)


def test_schema_shape():
    report = build_report(eval_report={"status": "available"})
    finding_keys = {
        "finding_id",
        "title",
        "summary",
        "why_it_matters",
        "evidence_note",
        "evidence_card_id",
        "evidence_section_title",
        "evidence_card_score",
        "evidence_cluster_comment_count",
        "card_ids",
        "cluster_ids",
    }

    assert set(report) == {
        "schema_version",
        "docket_id",
        "generated_at",
        "generator",
        "executive_summary",
        "top_findings",
        "rule_story",
        "priority_cards",
        "provenance",
    }
    assert all(set(finding) == finding_keys for finding in report["top_findings"])
    assert set(report["priority_cards"][0]) == {
        "card_id",
        "section_title",
        "change_type",
        "score",
        "alignment_level",
        "finding_ids",
    }


def test_priority_cards_ranking():
    report = build_report(eval_report={"status": "available"})

    assert [card["card_id"] for card in report["priority_cards"]] == [
        "card-2",
        "card-4",
        "card-1",
        "card-3",
        "card-5",
    ]
    assert [card["score"] for card in report["priority_cards"]] == [9, 7, 5, 1, 0]


def test_findings_ranking():
    report = build_report(eval_report={"status": "available"})

    assert [finding["title"] for finding in report["top_findings"]] == [
        "Comment Cost Burden",
        "Schedule Compliance",
        "Unclustered Regulatory Changes",
    ]


def test_null_label_clusters_excluded():
    report = build_report(eval_report={"status": "available"})

    assert "cluster-null" not in [
        cluster_id
        for finding in report["top_findings"]
        for cluster_id in finding["cluster_ids"]
    ]


def test_missing_eval_report():
    report = build_report(eval_report=None)

    assert report["provenance"]["eval_available"] is False


def test_no_causal_language():
    report = build_report(eval_report={"status": "available"})
    banned_terms = [
        "caused",
        "led to",
        "resulted in",
        "because of",
        "triggered",
        "drove",
        "prompted",
        "due to",
        "in response to",
    ]

    for value in walk_strings(report):
        lowered = value.lower()
        for term in banned_terms:
            assert term not in lowered


def test_sanitize_causal_language_removes_banned_phrases():
    assert generate_insights.sanitize_causal_language("Comments prompted a review.") == (
        "Comments coincided with a review."
    )
    assert generate_insights.sanitize_causal_language("Comments led\tto edits.") == (
        "Comments aligned with edits."
    )
    assert generate_insights.sanitize_causal_language("Comments due\u00a0to timing.") == (
        "Comments with timing."
    )


def test_provenance_metadata():
    report = generate_insights.build_insight_report(sample_report(), eval_report={"status": "available"})

    datetime.fromisoformat(report["generated_at"])
    assert report["generator"] == "generate_insights.py"
    assert report["provenance"]["source_report"] == "outputs/TEST-DOCKET/report.json"
    assert report["provenance"]["eval_available"] is True
    assert report["provenance"]["card_count"] == 5
    assert report["provenance"]["cluster_count"] == 3
    assert report["provenance"]["finding_count"] == 3


def test_residual_finding():
    report = build_report(eval_report={"status": "available"})
    residual = report["top_findings"][-1]

    assert residual["title"] == "Unclustered Regulatory Changes"
    assert residual["card_ids"] == ["card-4"]
    assert residual["cluster_ids"] == []
    assert "card-4" not in {
        card_id
        for finding in report["top_findings"][:-1]
        for card_id in finding["card_ids"]
    }


def test_no_related_clusters_cards():
    report = build_report(eval_report={"status": "available"})
    priority_cards = {
        card["card_id"]: card
        for card in report["priority_cards"]
    }

    assert "card-5" in priority_cards
    assert priority_cards["card-5"]["finding_ids"] == []


def test_finding_evidence_is_cluster_specific():
    report = generate_insights.build_insight_report(
        {
            "schema_version": "v1",
            "docket_id": "TEST-DOCKET",
            "clusters": [
                {
                    "cluster_id": "cluster-large",
                    "label": "Large Theme",
                    "label_description": "Large theme.",
                    "canonical_count": 5,
                },
                {
                    "cluster_id": "cluster-small",
                    "label": "Small Theme",
                    "label_description": "Small theme.",
                    "canonical_count": 4,
                },
            ],
            "change_cards": [
                {
                    "card_id": "card-shared",
                    "section_title": "Written comments",
                    "change_type": "modified",
                    "proposed_section_id": "section-1",
                    "alignment_signal": {
                        "level": "high",
                        "score": 82,
                        "evidence_note": "41 comments attributed (best: keyword/medium); no preamble discussion linked.",
                    },
                    "related_clusters": [
                        {"cluster_id": "cluster-large", "comment_count": 20},
                        {"cluster_id": "cluster-small", "comment_count": 1},
                    ],
                }
            ],
        },
        eval_report={"status": "available"},
        generated_at="2026-04-07T12:00:00+00:00",
    )

    large_finding = report["top_findings"][0]
    small_finding = report["top_findings"][1]

    assert large_finding["evidence_card_id"] == "card-shared"
    assert small_finding["evidence_card_id"] == "card-shared"
    assert large_finding["evidence_section_title"] == "Written comments"
    assert large_finding["evidence_card_score"] == 82
    assert large_finding["evidence_cluster_comment_count"] == 20
    assert small_finding["evidence_cluster_comment_count"] == 1
    assert "41 comments attributed" not in large_finding["evidence_note"]
    assert "41 comments attributed" not in small_finding["evidence_note"]
    assert "20 comment(s) from this theme linked to the card" in large_finding["evidence_note"]
    assert "1 comment(s) from this theme linked to the card" in small_finding["evidence_note"]
    assert large_finding["evidence_note"] != small_finding["evidence_note"]
