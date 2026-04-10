import { memo, type KeyboardEvent } from "react";
import type { ChangeCard } from "../models";
import type { CardDisplayMetrics } from "./ChangeCardRow";
import { priorityChipClass, sizeChipClass } from "./ChangeCardRow";

interface ChangeListRowProps {
  card: ChangeCard;
  metrics: CardDisplayMetrics;
  selected: boolean;
  index: number;
  onClick: () => void;
  onKeyDown?: (event: KeyboardEvent<HTMLDivElement>) => void;
}

function whyPreview(card: ChangeCard, metrics: CardDisplayMetrics): string {
  const parts: string[] = [];

  if (metrics.linkedComments > 0) {
    parts.push(`${metrics.linkedComments} comment${metrics.linkedComments === 1 ? "" : "s"}`);
  }
  if (metrics.sizeRank >= 3) {
    parts.push("large change");
  }

  const level = card.alignment_signal?.level;
  if (level === "high") {
    parts.push("high signal");
  } else if (level === "medium") {
    parts.push("mid signal");
  }

  return parts.join(" · ") || "no comment linkage";
}

export const ChangeListRow = memo(
  function ChangeListRow({ card, metrics, selected, index, onClick, onKeyDown }: ChangeListRowProps) {
    return (
      <div
        role="listitem"
        className={`list-row${selected ? " list-row-selected" : ""}`}
        data-card-id={card.card_id}
        onClick={onClick}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            onClick();
            return;
          }
          onKeyDown?.(event);
        }}
        tabIndex={0}
        aria-selected={selected}
      >
        <span className="list-row-index">{index}</span>
        <div className="list-row-main">
          <p className="list-row-title">{card.final_heading || card.proposed_heading || card.card_id}</p>
          <p className="list-row-why">{whyPreview(card, metrics)}</p>
          <div className="list-row-meta">
            <span className={`status-chip ${priorityChipClass(metrics)}`}>{metrics.priorityLabel}</span>
            <span className={`status-chip ${sizeChipClass(metrics)}`}>{metrics.sizeLabel}</span>
          </div>
        </div>
        {metrics.linkedComments > 0 ? (
          <span className="list-row-count">{metrics.linkedComments}</span>
        ) : (
          <span className="list-row-count list-row-count-empty" aria-hidden="true" />
        )}
      </div>
    );
  },
  (previous, next) =>
    previous.card === next.card &&
    previous.metrics === next.metrics &&
    previous.selected === next.selected &&
    previous.index === next.index
);
