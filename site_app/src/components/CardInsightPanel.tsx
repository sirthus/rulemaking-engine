import { useState } from "react";
import type { InsightFinding, InsightPriorityCard, InsightReport, PreambleLink } from "../models";
import { changeTypeLabel } from "./ChangeCardRow";
import { FindingEvidenceLine } from "./FindingEvidenceLine";

const LINKED_FINDING_LIMIT = 5;

export interface CardInsightContext {
  priorityCard: InsightPriorityCard | null;
  linkedFindings: InsightFinding[];
  hasStalePriorityFindings: boolean;
}

export function getCardInsightContext(insightReport: InsightReport | null, cardId: string): CardInsightContext {
  if (!insightReport) {
    return { priorityCard: null, linkedFindings: [], hasStalePriorityFindings: false };
  }

  const priorityCard = insightReport.priority_cards.find((item) => item.card_id === cardId) || null;
  if (priorityCard) {
    const findingsById = new Map(insightReport.top_findings.map((finding) => [finding.finding_id, finding]));
    const linkedFindings = priorityCard.finding_ids
      .map((findingId) => findingsById.get(findingId))
      .filter((finding): finding is InsightFinding => Boolean(finding));
    if (linkedFindings.length > 0) {
      return {
        priorityCard,
        linkedFindings,
        hasStalePriorityFindings: linkedFindings.length < priorityCard.finding_ids.length,
      };
    }
  }

  return {
    priorityCard,
    linkedFindings: insightReport.top_findings.filter((finding) => finding.card_ids.includes(cardId)),
    hasStalePriorityFindings: Boolean(priorityCard?.finding_ids.length),
  };
}

export function preambleLinkKey(link: PreambleLink, index: number): string {
  const parts = [
    link.preamble_section_id,
    link.preamble_heading,
    link.link_type,
    link.relationship_label,
    typeof link.link_score === "number" ? String(link.link_score) : undefined,
  ].filter((part): part is string => Boolean(part));

  return parts.length > 0 ? parts.join("|") : `link-${index}`;
}

export function CardInsightPanel({
  insightReport,
  priorityCard,
  linkedFindings,
  hasStalePriorityFindings,
}: {
  insightReport: InsightReport | null;
  priorityCard: InsightPriorityCard | null;
  linkedFindings: InsightFinding[];
  hasStalePriorityFindings: boolean;
}) {
  const [showAllFindings, setShowAllFindings] = useState(false);

  if (!insightReport) {
    return null;
  }

  const canToggleFindings = linkedFindings.length > LINKED_FINDING_LIMIT;
  const visibleFindings = showAllFindings ? linkedFindings : linkedFindings.slice(0, LINKED_FINDING_LIMIT);
  const hiddenFindingCount = Math.max(linkedFindings.length - visibleFindings.length, 0);
  const priorityChangeType = priorityCard ? changeTypeLabel(priorityCard.change_type) : null;

  return (
    <section className="panel insight-banner">
      <div className="section-header">
        <div>
          <p className="eyebrow">Insight Drilldown</p>
          <h2>Why This Card Matters</h2>
        </div>
        {priorityCard ? (
          <div className="chip-row">
            <span className="status-chip available">Card priority {priorityCard.score}</span>
            <span className="status-chip">Comment signal: {priorityCard.alignment_level || "none"}</span>
          </div>
        ) : null}
      </div>

      {priorityCard ? (
        <p className="meta-line">
          Priority card section: {priorityCard.section_title || "Untitled section"}
          {priorityChangeType ? ` · ${priorityChangeType}` : ""}
        </p>
      ) : null}

      {visibleFindings.length > 0 ? (
        <div className="finding-list detail-finding-list">
          {visibleFindings.map((finding) => (
            <article key={finding.finding_id} className="finding-card">
              <h3 className="finding-title">{finding.title}</h3>
              <p className="finding-summary">{finding.why_it_matters}</p>
              <FindingEvidenceLine finding={finding} />
            </article>
          ))}
        </div>
      ) : (
        <p>
          {hasStalePriorityFindings
            ? "Card priority is available, but referenced findings are not in this snapshot."
            : "No insight finding linked for this card."}
        </p>
      )}

      {hiddenFindingCount > 0 ? (
        <p className="meta-line">
          {hiddenFindingCount} more linked finding{hiddenFindingCount === 1 ? "" : "s"} not shown.
        </p>
      ) : null}
      {canToggleFindings ? (
        <button type="button" className="inline-action" onClick={() => setShowAllFindings((value) => !value)}>
          {showAllFindings ? `Show first ${LINKED_FINDING_LIMIT} findings` : `Show all ${linkedFindings.length} linked findings`}
        </button>
      ) : null}
    </section>
  );
}
