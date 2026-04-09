import { Link } from "react-router-dom";
import type { ChangeCard } from "../models";
import { ChangeSnippet, diffSnippets, tokenizeSnippet } from "./ChangeSnippet";

const ALIGNMENT_LEVEL_RANK: Record<string, number> = {
  high: 3,
  medium: 2,
  low: 1,
  none: 0,
};

export type CardSort = "priority" | "size";

export interface CardDisplayMetrics {
  linkedComments: number;
  preambleLinks: number;
  priorityRank: number;
  priorityLabel: string;
  sizeRank: number;
  sizeLabel: string;
  changedTokens: number;
  isDocketProcess: boolean;
}

export function linkedCommentCount(card: ChangeCard): number {
  const featureCount = card.alignment_signal?.features?.comment_count;
  if (typeof featureCount === "number" && Number.isFinite(featureCount)) {
    return featureCount;
  }

  return (card.related_clusters || []).reduce((sum, cluster) => {
    const count = cluster.comment_count;
    return typeof count === "number" && Number.isFinite(count) ? sum + count : sum;
  }, 0);
}

export function alignmentScore(card: ChangeCard): number {
  const score = card.alignment_signal?.score;
  return typeof score === "number" && Number.isFinite(score) ? score : 0;
}

export function alignmentLevelRank(card: ChangeCard): number {
  return ALIGNMENT_LEVEL_RANK[card.alignment_signal?.level || "none"] ?? 0;
}

export function preambleLinkCount(card: ChangeCard): number {
  return (card.preamble_links || []).length;
}

export function changedTokenCount(card: ChangeCard): number {
  const proposed = card.proposed_text_snippet || "";
  const final = card.final_text_snippet || "";
  const changeType = (card.change_type || "").toLowerCase();

  if (changeType === "added") {
    return tokenizeSnippet(final).length;
  }
  if (changeType === "removed") {
    return tokenizeSnippet(proposed).length;
  }

  const diff = diffSnippets(proposed, final);
  return (
    diff.proposed.filter((piece) => piece.kind === "removed").length +
    diff.final.filter((piece) => piece.kind === "added").length
  );
}

export function isDocketProcessCard(card: ChangeCard): boolean {
  const headings = [card.final_heading, card.proposed_heading]
    .filter((value): value is string => Boolean(value))
    .map((value) => value.trim().toLowerCase());
  const bodyText = [card.proposed_text_snippet, card.final_text_snippet]
    .filter((value): value is string => Boolean(value))
    .join(" ")
    .toLowerCase();
  const searchableText = [...headings, bodyText].join(" ");

  const hasProcessHeading = headings.some((heading) => {
    const normalized = heading.replace(/\s+/g, " ");
    return (
      normalized.startsWith("addresses:") ||
      normalized === "addresses" ||
      normalized.startsWith("dates:") ||
      normalized === "dates" ||
      normalized.includes("written comments") ||
      normalized.includes("participation in virtual public hearing")
    );
  });

  return (
    hasProcessHeading ||
    searchableText.includes("submit your comments") ||
    searchableText.includes("regulations.gov") ||
    searchableText.includes("public hearing")
  );
}

export function cardDisplayMetrics(card: ChangeCard): CardDisplayMetrics {
  const linkedComments = linkedCommentCount(card);
  const preambleLinks = preambleLinkCount(card);
  const alignmentRank = alignmentLevelRank(card);
  const changedTokens = changedTokenCount(card);
  const changeType = (card.change_type || "").toLowerCase();
  const isOneSidedChange = changeType === "added" || changeType === "removed";
  const isDocketProcess = isDocketProcessCard(card);
  let priorityRank = 1;
  let priorityLabel = linkedComments === 0 && preambleLinks === 0 ? "No comment signal" : "Low priority";

  if (isDocketProcess) {
    priorityRank = 0;
    priorityLabel = "Docket process";
  } else if (linkedComments >= 10 || (linkedComments > 0 && alignmentRank >= ALIGNMENT_LEVEL_RANK.high)) {
    priorityRank = 3;
    priorityLabel = "High priority";
  } else if (linkedComments > 0 || preambleLinks > 0) {
    priorityRank = 2;
    priorityLabel = "Medium priority";
  }

  let sizeRank = 1;
  let sizeLabel = "Minor change";
  if (changedTokens >= 20 || (isOneSidedChange && changedTokens >= 20)) {
    sizeRank = 3;
    sizeLabel = "Large change";
  } else if (changedTokens >= 6 || (isOneSidedChange && changedTokens >= 5)) {
    sizeRank = 2;
    sizeLabel = "Moderate change";
  }

  return {
    linkedComments,
    preambleLinks,
    priorityRank,
    priorityLabel,
    sizeRank,
    sizeLabel,
    changedTokens,
    isDocketProcess,
  };
}

export function isPrimaryCard(metrics: CardDisplayMetrics): boolean {
  return !metrics.isDocketProcess && metrics.priorityRank >= 2;
}

export function compareCardsByDisplayMetrics(
  a: ChangeCard,
  b: ChangeCard,
  aMetrics: CardDisplayMetrics,
  bMetrics: CardDisplayMetrics,
  sort: CardSort
): number {
  const processOrder = Number(aMetrics.isDocketProcess) - Number(bMetrics.isDocketProcess);
  if (processOrder !== 0) {
    return processOrder;
  }

  const primary =
    sort === "size"
      ? bMetrics.sizeRank - aMetrics.sizeRank || bMetrics.priorityRank - aMetrics.priorityRank
      : bMetrics.priorityRank - aMetrics.priorityRank || bMetrics.sizeRank - aMetrics.sizeRank;

  return (
    primary ||
    bMetrics.linkedComments - aMetrics.linkedComments ||
    bMetrics.changedTokens - aMetrics.changedTokens ||
    alignmentScore(b) - alignmentScore(a) ||
    a.card_id.localeCompare(b.card_id)
  );
}

export function priorityChipClass(metrics: CardDisplayMetrics): string {
  if (metrics.isDocketProcess) {
    return "chip-priority-process";
  }
  if (metrics.priorityRank >= 3) {
    return "chip-priority-high";
  }
  if (metrics.priorityRank >= 2) {
    return "chip-priority-medium";
  }
  return "chip-priority-low";
}

export function sizeChipClass(metrics: CardDisplayMetrics): string {
  if (metrics.sizeRank >= 3) {
    return "chip-size-large";
  }
  if (metrics.sizeRank >= 2) {
    return "chip-size-moderate";
  }
  return "chip-size-minor";
}

export function changeTypeLabel(changeType?: string): string {
  const normalized = (changeType || "modified").trim().toLowerCase();

  if (normalized === "added") {
    return "Added";
  }
  if (normalized === "removed") {
    return "Removed";
  }
  return "Modified";
}

export function ChangeCardRow({
  docketId,
  card,
  metrics,
}: {
  docketId: string;
  card: ChangeCard;
  metrics: CardDisplayMetrics;
}) {
  const commentCount = metrics.linkedComments;
  const preambleCount = metrics.preambleLinks;

  return (
    <article className="change-card">
      <div className="change-card-header">
        <div>
          <p className="eyebrow">{card.card_id}</p>
          <h3>{card.final_heading || card.proposed_heading || "Untitled section"}</h3>
        </div>
        <div className="chip-row">
          <span className={`status-chip ${priorityChipClass(metrics)}`}>{metrics.priorityLabel}</span>
          <span className={`status-chip ${sizeChipClass(metrics)}`}>{metrics.sizeLabel}</span>
          <span className="status-chip available">{card.change_type || "unknown"}</span>
          <span className={`status-chip ${commentCount > 0 ? "available" : "not_available"}`}>
            {commentCount > 0 ? `${commentCount} linked comments` : "No linked comments"}
          </span>
        </div>
      </div>
      <p className="meta-line">{card.alignment_signal?.evidence_note || "No evidence note available."}</p>
      <div className="card-grid">
        <div>
          <h4>Proposed</h4>
          <ChangeSnippet card={card} side="proposed" preview />
        </div>
        <div>
          <h4>Final</h4>
          <ChangeSnippet card={card} side="final" preview />
        </div>
      </div>
      <p className="meta-line">
        Related comment themes: {(card.related_clusters || []).length}
        {preambleCount > 0 ? ` | Preamble links: ${preambleCount}` : ""}
      </p>
      <Link className="action-link" to={`/dockets/${docketId}/cards/${card.card_id}`}>
        Open card detail
      </Link>
    </article>
  );
}
