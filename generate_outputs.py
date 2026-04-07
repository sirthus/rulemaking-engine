#!/usr/bin/env python3

import argparse
import csv
import html as html_module
import json
import os
from datetime import datetime, timezone


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_DIR = os.path.join(ROOT_DIR, "corpus")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")

DOCKET_IDS = [
    "EPA-HQ-OAR-2020-0272",
    "EPA-HQ-OAR-2018-0225",
    "EPA-HQ-OAR-2020-0430",
]

CSV_COLUMNS = [
    "docket_id",
    "card_id",
    "change_type",
    "match_type",
    "heading_similarity",
    "proposed_section_id",
    "final_section_id",
    "proposed_heading",
    "final_heading",
    "proposed_text_snippet",
    "final_text_snippet",
    "alignment_signal_level",
    "alignment_score",
    "related_comment_count",
    "related_cluster_count",
    "top_cluster_label",
    "preamble_link_count",
    "evidence_note",
    "review_status",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: str):
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_write_text(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        handle.write(text)
    os.replace(tmp_path, path)


def atomic_write_json(path: str, payload) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2))


def atomic_write_csv(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    field: "" if row.get(field) is None else row.get(field)
                    for field in CSV_COLUMNS
                }
            )
    os.replace(tmp_path, path)


def print_line(prefix: str, docket_id: str, message: str) -> None:
    print(f"[{prefix}]  {docket_id}  {message}")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate consolidated JSON, CSV, and HTML outputs.")
    parser.add_argument("--docket", choices=DOCKET_IDS, help="Process a single docket.")
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Root directory for generated output files.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output files instead of skipping completed dockets.",
    )
    return parser.parse_args()


def escape_html(value) -> str:
    return html_module.escape("" if value is None else str(value))


def relative_display_path(path: str) -> str:
    try:
        return os.path.relpath(path, ROOT_DIR)
    except ValueError:
        return path


def load_optional_json(path: str):
    try:
        return read_json(path)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def build_cluster_lookups(themes: dict) -> tuple[dict[str, dict], dict[str, str]]:
    clusters_by_id = {}
    comment_to_cluster = {}

    for cluster in themes.get("clusters", []):
        cluster_id = cluster.get("cluster_id")
        if not cluster_id:
            continue

        clusters_by_id[cluster_id] = cluster
        for comment_id in cluster.get("member_canonical_ids", []):
            if comment_id:
                comment_to_cluster[comment_id] = cluster_id

    return clusters_by_id, comment_to_cluster


def export_clusters(themes: dict) -> list[dict]:
    exported = []
    for cluster in themes.get("clusters", []):
        exported.append(
            {
                "cluster_id": cluster.get("cluster_id"),
                "label": cluster.get("label"),
                "label_description": cluster.get("label_description"),
                "canonical_count": cluster.get("canonical_count"),
                "total_raw_comments": cluster.get("total_raw_comments"),
                "top_keywords": cluster.get("top_keywords", []),
                "commenter_type_distribution": cluster.get("commenter_type_distribution", {}),
            }
        )
    return exported


def derive_related_clusters(card: dict, clusters_by_id: dict[str, dict], comment_to_cluster: dict[str, str]) -> list[dict]:
    grouped = {}

    for related_comment in card.get("related_comments", []) or []:
        comment_id = related_comment.get("comment_id")
        if not comment_id:
            continue

        cluster_id = comment_to_cluster.get(comment_id)
        if not cluster_id:
            continue

        if cluster_id not in grouped:
            grouped[cluster_id] = {
                "cluster_id": cluster_id,
                "comment_count": 0,
                "relationship_labels": [],
            }

        grouped[cluster_id]["comment_count"] += 1
        relationship_label = related_comment.get("relationship_label")
        if relationship_label and relationship_label not in grouped[cluster_id]["relationship_labels"]:
            grouped[cluster_id]["relationship_labels"].append(relationship_label)

    related_clusters = []
    for cluster_id, grouped_cluster in grouped.items():
        cluster = clusters_by_id.get(cluster_id, {})
        related_clusters.append(
            {
                "cluster_id": cluster_id,
                "label": cluster.get("label"),
                "label_description": cluster.get("label_description"),
                "comment_count": grouped_cluster["comment_count"],
                "canonical_count": cluster.get("canonical_count", 0),
                "relationship_labels": grouped_cluster["relationship_labels"],
            }
        )

    related_clusters.sort(
        key=lambda cluster: (
            -(cluster.get("canonical_count") or 0),
            cluster.get("cluster_id") or "",
        )
    )
    return related_clusters


def build_export_card(card: dict, related_clusters: list[dict]) -> dict:
    alignment_signal = card.get("alignment_signal") or {}

    exported_preamble_links = []
    for link in card.get("preamble_links", []) or []:
        exported_preamble_links.append(
            {
                "preamble_section_id": link.get("preamble_section_id"),
                "preamble_heading": link.get("preamble_heading"),
                "link_type": link.get("link_type"),
                "link_score": link.get("link_score"),
                "relationship_label": link.get("relationship_label"),
            }
        )

    return {
        "card_id": card.get("card_id"),
        "change_type": card.get("change_type"),
        "match_type": card.get("match_type"),
        "heading_similarity": card.get("heading_similarity"),
        "proposed_section_id": card.get("proposed_section_id"),
        "final_section_id": card.get("final_section_id"),
        "proposed_heading": card.get("proposed_heading"),
        "final_heading": card.get("final_heading"),
        "proposed_text_snippet": card.get("proposed_text_snippet"),
        "final_text_snippet": card.get("final_text_snippet"),
        "alignment_signal": {
            "level": alignment_signal.get("level") or "none",
            "score": alignment_signal.get("score") or 0,
            "features": alignment_signal.get("features") or {},
            "evidence_note": alignment_signal.get("evidence_note") or "",
        },
        "related_clusters": related_clusters,
        "preamble_links": exported_preamble_links,
        "review_status": card.get("review_status"),
    }


def count_values(values: list[str], defaults: list[str]) -> dict:
    counts = {value: 0 for value in defaults}
    for value in values:
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def compute_comment_attribution_stats(comment_attribution: list[dict]) -> dict:
    substantive_inline = sum(
        1
        for record in comment_attribution
        if record.get("classification") == "substantive_inline"
    )
    attributed_records = [
        record
        for record in comment_attribution
        if record.get("classification") == "substantive_inline"
        and record.get("attribution_method") in {"citation", "keyword"}
    ]
    by_method = {
        "citation": sum(1 for record in attributed_records if record.get("attribution_method") == "citation"),
        "keyword": sum(1 for record in attributed_records if record.get("attribution_method") == "keyword"),
    }
    unattributed = substantive_inline - len(attributed_records)
    attribution_rate_pct = (
        round((len(attributed_records) / substantive_inline) * 100.0, 1)
        if substantive_inline
        else 0.0
    )
    return {
        "substantive_inline": substantive_inline,
        "attributed": len(attributed_records),
        "unattributed": unattributed,
        "attribution_rate_pct": attribution_rate_pct,
        "by_method": by_method,
    }


def build_summary(
    themes: dict,
    raw_cards: list[dict],
    change_cards_missing: bool,
    comment_attribution,
    alignment_log,
    label_run,
) -> dict:
    clusters = themes.get("clusters", [])

    summary = {
        "total_comments": themes.get("total_comments", 0),
        "total_canonical_comments": themes.get("total_canonical_comments", 0),
        "total_clusters": themes.get("total_clusters", len(clusters)),
        "labeled_clusters": sum(1 for cluster in clusters if (cluster.get("label") or "").strip()),
        "total_change_cards": len(raw_cards),
        "change_type_counts": count_values(
            [card.get("change_type") for card in raw_cards],
            ["modified", "added", "removed"],
        ),
        "alignment_signal_counts": count_values(
            [
                (card.get("alignment_signal") or {}).get("level") or "none"
                for card in raw_cards
            ],
            ["high", "medium", "low", "none"],
        ),
        "review_status_counts": count_values(
            [card.get("review_status") for card in raw_cards],
            ["pending", "confirmed", "rejected"],
        ),
    }

    if change_cards_missing:
        summary["notes"] = [
            "change_cards.json not found; generated outputs without change cards."
        ]

    if isinstance(alignment_log, dict):
        section_alignment = alignment_log.get("section_alignment")
        if isinstance(section_alignment, dict):
            summary["alignment_stats"] = section_alignment

        logged_comment_attribution = alignment_log.get("comment_attribution")
        if isinstance(logged_comment_attribution, dict):
            summary["comment_attribution_stats"] = logged_comment_attribution

    if "comment_attribution_stats" not in summary and isinstance(comment_attribution, list):
        summary["comment_attribution_stats"] = compute_comment_attribution_stats(comment_attribution)

    labeling_source = label_run if isinstance(label_run, dict) else themes.get("processing_run")
    if isinstance(labeling_source, dict) and labeling_source.get("phase") == "7":
        summary["labeling"] = {
            "runtime": labeling_source.get("runtime") or "ollama",
            "model": labeling_source.get("model"),
            "prompt_version": labeling_source.get("prompt_version"),
            "labeled_at": labeling_source.get("completed_at") or labeling_source.get("labeled_at"),
            "total_input_tokens": labeling_source.get("total_input_tokens", 0),
            "total_output_tokens": labeling_source.get("total_output_tokens", 0),
            "no_think": bool(labeling_source.get("no_think")),
        }

    return summary


def build_csv_rows(raw_cards: list[dict], exported_cards: list[dict]) -> list[dict]:
    rows = []

    for raw_card, exported_card in zip(raw_cards, exported_cards):
        top_cluster = exported_card["related_clusters"][0] if exported_card["related_clusters"] else {}
        alignment_signal = exported_card["alignment_signal"]
        rows.append(
            {
                "docket_id": raw_card.get("docket_id"),
                "card_id": exported_card.get("card_id"),
                "change_type": exported_card.get("change_type"),
                "match_type": exported_card.get("match_type"),
                "heading_similarity": exported_card.get("heading_similarity"),
                "proposed_section_id": exported_card.get("proposed_section_id"),
                "final_section_id": exported_card.get("final_section_id"),
                "proposed_heading": exported_card.get("proposed_heading"),
                "final_heading": exported_card.get("final_heading"),
                "proposed_text_snippet": exported_card.get("proposed_text_snippet"),
                "final_text_snippet": exported_card.get("final_text_snippet"),
                "alignment_signal_level": alignment_signal.get("level"),
                "alignment_score": alignment_signal.get("score"),
                "related_comment_count": len(raw_card.get("related_comments", []) or []),
                "related_cluster_count": len(exported_card["related_clusters"]),
                "top_cluster_label": top_cluster.get("label") or "",
                "preamble_link_count": len(exported_card.get("preamble_links", []) or []),
                "evidence_note": alignment_signal.get("evidence_note"),
                "review_status": exported_card.get("review_status"),
            }
        )

    return rows


def effective_heading(card: dict) -> str:
    proposed_heading = card.get("proposed_heading")
    final_heading = card.get("final_heading")

    if proposed_heading and final_heading:
        if proposed_heading == final_heading:
            return proposed_heading
        return f"{proposed_heading} \u2192 {final_heading}"

    if proposed_heading:
        return proposed_heading
    if final_heading:
        return final_heading
    return card.get("card_id") or ""


def format_commenter_mix(commenter_type_distribution: dict) -> str:
    if not isinstance(commenter_type_distribution, dict):
        return ""

    nonzero_items = [
        f"{commenter_type}: {count}"
        for commenter_type, count in commenter_type_distribution.items()
        if count
    ]
    if nonzero_items:
        return ", ".join(nonzero_items)

    all_items = [
        f"{commenter_type}: {count}"
        for commenter_type, count in commenter_type_distribution.items()
    ]
    return ", ".join(all_items)


def format_feature_value(value) -> str:
    if value is None:
        return "null"
    return str(value)


def render_html_report(report: dict) -> str:
    docket_id = report["docket_id"]
    generated_at = report["generated_at"]
    summary = report["summary"]
    clusters = report["clusters"]
    cards = report["change_cards"]

    cluster_rows = []
    for cluster in clusters:
        cluster_rows.append(
            "\n".join(
                [
                    "        <tr>",
                    f"          <td>{escape_html(cluster.get('label') or cluster.get('cluster_id') or '')}</td>",
                    f"          <td>{escape_html(cluster.get('label_description') or '')}</td>",
                    f"          <td>{escape_html(cluster.get('canonical_count'))}</td>",
                    f"          <td>{escape_html(cluster.get('total_raw_comments'))}</td>",
                    f"          <td>{escape_html(', '.join(cluster.get('top_keywords', []) or []))}</td>",
                    f"          <td>{escape_html(format_commenter_mix(cluster.get('commenter_type_distribution', {})))}</td>",
                    "        </tr>",
                ]
            )
        )
    cluster_rows_html = "\n".join(cluster_rows)

    card_blocks = []
    for card in cards:
        alignment_signal = card.get("alignment_signal") or {}
        signal_level = alignment_signal.get("level") or "none"
        signal_score = alignment_signal.get("score") or 0
        features = alignment_signal.get("features") or {}
        related_clusters = card.get("related_clusters") or []
        preamble_links = card.get("preamble_links") or []

        if not related_clusters:
            related_clusters_html = '            <p class="empty">No related comment themes.</p>'
        else:
            rendered_clusters = []
            for related_cluster in related_clusters:
                relationship_labels = ", ".join(related_cluster.get("relationship_labels", []) or [])
                rendered_clusters.append(
                    "\n".join(
                        [
                            '            <div class="cluster-item">',
                            f"              <p class=\"cluster-label\"><strong>{escape_html(related_cluster.get('label') or related_cluster.get('cluster_id') or '')}</strong></p>",
                            f"              <p>{escape_html(related_cluster.get('label_description') or '')}</p>",
                            f"              <p>{escape_html(related_cluster.get('comment_count'))} related comment(s) \u00b7 {escape_html(related_cluster.get('canonical_count'))} unique arguments in cluster</p>",
                            f"              <p class=\"relationship-labels\"><em>{escape_html(relationship_labels)}</em></p>",
                            "            </div>",
                        ]
                    )
                )
            related_clusters_html = "\n".join(rendered_clusters)

        if not preamble_links:
            preamble_links_html = '            <p class="empty">No preamble links found.</p>'
        else:
            rendered_preamble_links = []
            for link in preamble_links:
                heading = link.get("preamble_heading")
                heading_text = f" \u00b7 {heading}" if heading else ""
                link_score = link.get("link_score")
                score_text = ""
                if isinstance(link_score, (int, float)):
                    score_text = f" \u00b7 score {link_score:.4f}"
                rendered_preamble_links.append(
                    "\n".join(
                        [
                            '            <div class="preamble-item">',
                            f"              <p><code>{escape_html(link.get('preamble_section_id') or '')}</code>{escape_html(heading_text)} <span class=\"badge\">{escape_html(link.get('link_type') or '')}</span></p>",
                            f"              <p>{escape_html(link.get('relationship_label') or '')}{escape_html(score_text)}</p>",
                            "            </div>",
                        ]
                    )
                )
            preamble_links_html = "\n".join(rendered_preamble_links)

        feature_items_html = "\n".join(
            f"              <li>{escape_html(feature_name)}: {escape_html(format_feature_value(feature_value))}</li>"
            for feature_name, feature_value in features.items()
        )

        card_blocks.append(
            "\n".join(
                [
                    f'      <details class="card" data-change-type="{escape_html(card.get("change_type") or "")}" data-signal="{escape_html(signal_level)}">',
                    "        <summary>",
                    f'          <span class="card-id">{escape_html(card.get("card_id") or "")}</span>',
                    f'          <span class="badge change-{escape_html(card.get("change_type") or "")}">{escape_html(card.get("change_type") or "")}</span>',
                    f'          <span class="badge signal-{escape_html(signal_level)}">{escape_html(signal_level.upper())}</span>',
                    f'          <span class="heading-text">{escape_html(effective_heading(card))}</span>',
                    "        </summary>",
                    '        <div class="card-body">',
                    '          <div class="text-compare">',
                    '            <div class="text-block proposed">',
                    f'              <h4>Proposed (<code>{escape_html(card.get("proposed_section_id") or "")}</code>)</h4>',
                    f'              <pre>{escape_html(card.get("proposed_text_snippet") or "")}</pre>',
                    "            </div>",
                    '            <div class="text-block final">',
                    f'              <h4>Final (<code>{escape_html(card.get("final_section_id") or "")}</code>)</h4>',
                    f'              <pre>{escape_html(card.get("final_text_snippet") or "")}</pre>',
                    "            </div>",
                    "          </div>",
                    '          <div class="related-clusters">',
                    f'            <h4>Related Comment Themes ({len(related_clusters)})</h4>',
                    related_clusters_html,
                    "          </div>",
                    '          <div class="preamble-links">',
                    f'            <h4>Preamble Discussion ({len(preamble_links)})</h4>',
                    preamble_links_html,
                    "          </div>",
                    '          <div class="signal-detail">',
                    f'            <h4>Alignment Signal: <span class="badge signal-{escape_html(signal_level)}">{escape_html(signal_level.upper())}</span> (score {escape_html(signal_score)})</h4>',
                    f'            <p class="evidence-note">{escape_html(alignment_signal.get("evidence_note") or "")}</p>',
                    '            <ul class="features">',
                    feature_items_html,
                    "            </ul>",
                    "          </div>",
                    '          <div class="review-status">',
                    f'            <strong>Review status:</strong> {escape_html(card.get("review_status") or "")}',
                    "          </div>",
                    "        </div>",
                    "      </details>",
                ]
            )
        )
    card_blocks_html = "\n".join(card_blocks)

    summary_notes_html = ""
    if summary.get("notes"):
        notes = "\n".join(
            f'      <p class="note">{escape_html(note)}</p>'
            for note in summary["notes"]
        )
        summary_notes_html = f"\n{notes}"

    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{
      font-family: system-ui, sans-serif;
      max-width: 1100px;
      margin: 0 auto;
      padding: 1rem 2rem;
      color: #222;
      background: #fff;
    }}
    header {{
      margin-bottom: 2rem;
    }}
    .subtitle,
    .generated,
    .note,
    .empty {{
      color: #555;
    }}
    pre {{
      white-space: pre-wrap;
      max-height: 200px;
      overflow-y: auto;
      background: #f5f5f5;
      padding: .5rem;
      border-radius: 4px;
    }}
    .text-compare {{
      display: flex;
      gap: 1rem;
    }}
    .text-block {{
      flex: 1;
      min-width: 0;
    }}
    .signal-high {{
      background: #2e7d32;
      color: #fff;
    }}
    .signal-medium {{
      background: #e65100;
      color: #fff;
    }}
    .signal-low {{
      background: #757575;
      color: #fff;
    }}
    .signal-none {{
      background: #e0e0e0;
      color: #333;
    }}
    .change-modified {{
      background: #1565c0;
      color: #fff;
    }}
    .change-added {{
      background: #00695c;
      color: #fff;
    }}
    .change-removed {{
      background: #b71c1c;
      color: #fff;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 3px;
      font-size: .8em;
      font-weight: 600;
      margin-right: 4px;
    }}
    details.card {{
      border: 1px solid #ddd;
      border-radius: 5px;
      margin-bottom: .75rem;
      padding: .5rem;
    }}
    details.card > summary {{
      cursor: pointer;
      list-style: none;
      padding: .25rem;
    }}
    .card-body {{
      margin-top: .75rem;
      padding-top: .75rem;
      border-top: 1px solid #eee;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
    }}
    th,
    td {{
      text-align: left;
      padding: .4rem .6rem;
      border-bottom: 1px solid #ddd;
      vertical-align: top;
    }}
    #filter-bar {{
      margin-bottom: 1rem;
      display: flex;
      gap: 1.5rem;
      align-items: center;
      flex-wrap: wrap;
    }}
    .cluster-item,
    .preamble-item,
    .signal-detail,
    .review-status,
    .related-clusters,
    .preamble-links {{
      margin-top: 1rem;
    }}
    .cluster-item p,
    .preamble-item p {{
      margin: .3rem 0;
    }}
    .features {{
      margin: .5rem 0 0 1.2rem;
      padding: 0;
    }}
    .stats-table {{
      max-width: 700px;
    }}
    @media (max-width: 800px) {{
      body {{
        padding: 1rem;
      }}
      .text-compare {{
        flex-direction: column;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{docket_id}</h1>
    <p class="subtitle">Rule Change Analysis</p>
    <p class="generated">Generated {generated_at} · generate_outputs.py</p>
  </header>

  <section id="summary">
    <h2>Summary</h2>
    <table class="stats-table">
      <tbody>
        <tr><th>Total public comments</th><td>{total_comments}</td></tr>
        <tr><th>Unique arguments (canonical)</th><td>{total_canonical_comments}</td></tr>
        <tr><th>Comment themes (clusters)</th><td>{total_clusters} ({labeled_clusters} labeled)</td></tr>
        <tr><th>Change cards</th><td>{total_change_cards}</td></tr>
        <tr><th>Changes: modified / added / removed</th><td>{modified} / {added} / {removed}</td></tr>
        <tr><th>Alignment signal: high / medium / low / none</th><td>{high} / {medium} / {low} / {none}</td></tr>
      </tbody>
    </table>{summary_notes}
  </section>

  <section id="clusters">
    <h2>Comment Themes ({cluster_count} clusters)</h2>
    <table class="clusters-table">
      <thead>
        <tr>
          <th>Label</th>
          <th>Description</th>
          <th>Unique Args</th>
          <th>Total Submissions</th>
          <th>Top Keywords</th>
          <th>Commenter Mix</th>
        </tr>
      </thead>
      <tbody>
{cluster_rows}
      </tbody>
    </table>
  </section>

  <section id="cards">
    <h2>Change Cards ({card_count} cards)</h2>
    <div id="filter-bar">
      <label>Change type:
        <select id="filter-change-type">
          <option value="all">all</option>
          <option value="modified">modified</option>
          <option value="added">added</option>
          <option value="removed">removed</option>
        </select>
      </label>
      <label>Alignment signal:
        <select id="filter-signal">
          <option value="all">all</option>
          <option value="high">high</option>
          <option value="medium">medium</option>
          <option value="low">low</option>
          <option value="none">none</option>
        </select>
      </label>
    </div>

    <div id="cards-container">
{card_blocks}
    </div>

    <p id="no-cards-msg" hidden>No cards match the current filters.</p>
  </section>

  <script>
  (function () {{
    const selType = document.getElementById('filter-change-type');
    const selSignal = document.getElementById('filter-signal');
    const noMsg = document.getElementById('no-cards-msg');

    function applyFilters() {{
      const typeVal = selType.value;
      const signalVal = selSignal.value;
      let visible = 0;
      document.querySelectorAll('.card').forEach(function (card) {{
        const show =
          (typeVal === 'all' || card.dataset.changeType === typeVal) &&
          (signalVal === 'all' || card.dataset.signal === signalVal);
        card.hidden = !show;
        if (show) visible++;
      }});
      noMsg.hidden = visible > 0;
    }}

    selType.addEventListener('change', applyFilters);
    selSignal.addEventListener('change', applyFilters);
    applyFilters();
  }})();
  </script>
</body>
</html>
""".format(
        title=escape_html(f"{docket_id} - Rule Change Analysis"),
        docket_id=escape_html(docket_id),
        generated_at=escape_html(generated_at),
        total_comments=escape_html(summary.get("total_comments", 0)),
        total_canonical_comments=escape_html(summary.get("total_canonical_comments", 0)),
        total_clusters=escape_html(summary.get("total_clusters", 0)),
        labeled_clusters=escape_html(summary.get("labeled_clusters", 0)),
        total_change_cards=escape_html(summary.get("total_change_cards", 0)),
        modified=escape_html(summary.get("change_type_counts", {}).get("modified", 0)),
        added=escape_html(summary.get("change_type_counts", {}).get("added", 0)),
        removed=escape_html(summary.get("change_type_counts", {}).get("removed", 0)),
        high=escape_html(summary.get("alignment_signal_counts", {}).get("high", 0)),
        medium=escape_html(summary.get("alignment_signal_counts", {}).get("medium", 0)),
        low=escape_html(summary.get("alignment_signal_counts", {}).get("low", 0)),
        none=escape_html(summary.get("alignment_signal_counts", {}).get("none", 0)),
        summary_notes=summary_notes_html,
        cluster_count=escape_html(len(clusters)),
        cluster_rows=cluster_rows_html,
        card_count=escape_html(len(cards)),
        card_blocks=card_blocks_html,
    )


def process_docket(docket_id: str, output_dir: str, force: bool) -> dict | None:
    base_dir = os.path.join(CORPUS_DIR, docket_id)
    output_base_dir = os.path.join(output_dir, docket_id)
    json_output_path = os.path.join(output_base_dir, "report.json")
    csv_output_path = os.path.join(output_base_dir, "report.csv")
    html_output_path = os.path.join(output_base_dir, "report.html")

    if not force and all(
        os.path.exists(path)
        for path in (json_output_path, csv_output_path, html_output_path)
    ):
        print_line("OUT", docket_id, "skipping; outputs already exist")
        return None

    themes_path = os.path.join(base_dir, "comment_themes.json")
    try:
        themes = read_json(themes_path)
    except (FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        path = getattr(exc, "filename", None) or str(exc)
        print_line("ERROR", docket_id, f"missing required theme input {path}")
        return None

    change_cards = load_optional_json(os.path.join(base_dir, "change_cards.json"))
    change_cards_missing = change_cards is None
    if change_cards_missing:
        print_line("WARN", docket_id, "missing change_cards.json; writing partial outputs")
        change_cards = []

    raw_cards = change_cards if isinstance(change_cards, list) else []
    comment_attribution = load_optional_json(os.path.join(base_dir, "comment_attribution.json"))
    alignment_log = load_optional_json(os.path.join(base_dir, "alignment_log.json"))
    label_run = load_optional_json(os.path.join(base_dir, "label_run.json"))

    clusters_by_id, comment_to_cluster = build_cluster_lookups(themes)
    exported_clusters = export_clusters(themes)

    exported_cards = []
    for card in raw_cards:
        related_clusters = derive_related_clusters(card, clusters_by_id, comment_to_cluster)
        exported_cards.append(build_export_card(card, related_clusters))

    report_payload = {
        "schema_version": "v1",
        "docket_id": docket_id,
        "generated_at": utc_now_iso(),
        "generator": "generate_outputs.py",
        "summary": build_summary(
            themes,
            raw_cards,
            change_cards_missing,
            comment_attribution,
            alignment_log,
            label_run,
        ),
        "clusters": exported_clusters,
        "change_cards": exported_cards,
    }

    csv_rows = build_csv_rows(raw_cards, exported_cards)
    html_output = render_html_report(report_payload)

    atomic_write_json(json_output_path, report_payload)
    atomic_write_csv(csv_output_path, csv_rows)
    atomic_write_text(html_output_path, html_output)

    print_line("OUT", docket_id, f"written  {relative_display_path(json_output_path)}")
    print_line("OUT", docket_id, f"written  {relative_display_path(csv_output_path)}")
    print_line("OUT", docket_id, f"written  {relative_display_path(html_output_path)}")

    return {
        "docket_id": docket_id,
        "cluster_count": len(exported_clusters),
        "change_card_count": len(exported_cards),
    }


def main():
    args = parse_args()
    docket_ids = [args.docket] if args.docket else DOCKET_IDS
    output_dir = os.path.abspath(args.output_dir)

    summaries = []
    for docket_id in docket_ids:
        summary = process_docket(docket_id, output_dir, args.force)
        if summary is not None:
            summaries.append(summary)

    print("=== Output generation complete ===")
    for summary in summaries:
        print(
            f"{summary['docket_id']}   {summary['cluster_count']} clusters  {summary['change_card_count']} cards"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
