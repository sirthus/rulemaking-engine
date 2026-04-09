import { Link } from "react-router-dom";
import type { ChangeCard, InsightReport } from "../models";
import {
  type CardDisplayMetrics,
  changeTypeLabel,
  priorityChipClass,
  sizeChipClass,
} from "./ChangeCardRow";
import { CardInsightPanel, getCardInsightContext } from "./CardInsightPanel";
import { cardChangeSynopsis, InlineDiff } from "./InlineDiff";
import { WhyFlagged } from "./WhyFlagged";

interface ChangeDetailPaneProps {
  card: ChangeCard;
  metrics: CardDisplayMetrics;
  insightReport: InsightReport | null;
  docketId: string;
}

function copyCardReference(card: ChangeCard) {
  if (navigator.clipboard?.writeText) {
    void navigator.clipboard.writeText(
      `${card.card_id}: ${card.final_heading || card.proposed_heading || card.card_id}`
    ).catch(() => {});
  }
}

export function ChangeDetailPane({ card, metrics, insightReport, docketId }: ChangeDetailPaneProps) {
  const { priorityCard, linkedFindings, hasStalePriorityFindings } = getCardInsightContext(insightReport, card.card_id);
  const changeLabel = changeTypeLabel(card.change_type);
  const synopsis = cardChangeSynopsis(card, metrics);

  return (
    <div className="detail-pane">
      <div className="detail-pane-header">
        <div className="detail-pane-header-top">
          <div className="detail-pane-heading">
            <p className="eyebrow">{card.card_id}</p>
            <h2 className="detail-pane-title">{card.final_heading || card.proposed_heading || card.card_id}</h2>
            <p className="detail-heading-meta">{changeLabel}</p>
          </div>
          <div className="detail-actions">
            <button type="button" className="action-btn" onClick={() => copyCardReference(card)}>
              Copy ref
            </button>
            <Link className="action-btn" to={`/dockets/${docketId}/cards/${card.card_id}`}>
              Open full view
            </Link>
          </div>
        </div>
        <div className="chip-row detail-chip-row">
          <span className={`status-chip ${priorityChipClass(metrics)}`}>{metrics.priorityLabel}</span>
          <span className={`status-chip ${sizeChipClass(metrics)}`}>{metrics.sizeLabel}</span>
          {metrics.linkedComments > 0 ? (
            <span className="status-chip chip-comment-count">{metrics.linkedComments} comments</span>
          ) : null}
        </div>
      </div>

      <div className="detail-section">
        <InlineDiff card={card} synopsis={synopsis} />
      </div>

      <WhyFlagged card={card} metrics={metrics} />

      <CardInsightPanel
        insightReport={insightReport}
        priorityCard={priorityCard}
        linkedFindings={linkedFindings}
        hasStalePriorityFindings={hasStalePriorityFindings}
      />

      {(card.related_clusters || []).length > 0 ? (
        <div className="detail-section">
          <p className="eyebrow">Related Themes</p>
          {(card.related_clusters || []).map((cluster) => (
            <div key={cluster.cluster_id} className="detail-theme-row">
              <span>{cluster.label || cluster.cluster_id}</span>
              <span className="meta-line">{cluster.comment_count || 0} comments</span>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
