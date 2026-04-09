import type { ChangeCard } from "../models";
import type { CardDisplayMetrics } from "./ChangeCardRow";

export function WhyFlagged({ card, metrics }: { card: ChangeCard; metrics: CardDisplayMetrics }) {
  const reasons: string[] = [];

  if (metrics.linkedComments > 0) {
    reasons.push(
      `${metrics.linkedComments} commenter${metrics.linkedComments > 1 ? "s" : ""} engaged with this section`
    );
  }
  if (metrics.sizeRank >= 3) {
    reasons.push("substantive text revision (large change magnitude)");
  }
  if (metrics.preambleLinks > 0) {
    reasons.push(
      `cited in ${metrics.preambleLinks} preamble section${metrics.preambleLinks > 1 ? "s" : ""}`
    );
  }
  const level = card.alignment_signal?.level;
  if (level && level !== "none") {
    reasons.push(`${level} alignment signal between comments and final text`);
  }

  if (reasons.length === 0) {
    return null;
  }

  return (
    <div className="why-flagged detail-section">
      <p className="eyebrow">Why this was prioritized</p>
      <ul className="why-list">
        {reasons.map((reason) => (
          <li key={reason}>{reason}</li>
        ))}
      </ul>
    </div>
  );
}
