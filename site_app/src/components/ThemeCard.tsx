import { memo } from "react";
import { Link } from "react-router-dom";
import type { ClusterSummary } from "../models";

export interface ThemeSignalBreakdown {
  high: number;
  medium: number;
  low: number;
  none: number;
  total: number;
}

interface ThemeRowProps {
  cluster: ClusterSummary;
  signalBreakdown: ThemeSignalBreakdown;
  linkedCardCount: number;
  rank: number;
  docketId: string;
}

export const ThemeRow = memo(
  function ThemeRow({ cluster, signalBreakdown, linkedCardCount, rank, docketId }: ThemeRowProps) {
    const visibleKeywords = cluster.top_keywords.slice(0, 2);
    const hiddenCount = Math.max(cluster.top_keywords.length - visibleKeywords.length, 0);
    const themeLabel = cluster.label || cluster.cluster_id || "this theme";
    const themeQuery = new URLSearchParams({
      tab: "changes",
      clusterQuery: cluster.label || cluster.cluster_id,
    }).toString();
    const content = (
      <>
        <span className="theme-rank">{rank}</span>
        <div className="theme-row-left">
          <h3 className="theme-row-title">{cluster.label || "Unlabeled theme"}</h3>
          <p className="theme-row-desc">{cluster.label_description || "No description."}</p>
          {visibleKeywords.length > 0 ? (
            <div className="theme-row-keywords">
              {visibleKeywords.map((keyword) => (
                <span key={keyword} className="keyword-pill">
                  {keyword}
                </span>
              ))}
              {hiddenCount > 0 ? <span className="keyword-overflow">+{hiddenCount}</span> : null}
            </div>
          ) : null}
        </div>
        <div className="theme-row-metrics">
          <div className="theme-row-nums">
            <div className="theme-num">
              <strong>{cluster.canonical_count}</strong>
              <span>Arguments</span>
            </div>
            <div className="theme-num">
              <strong>{linkedCardCount}</strong>
              <span>Changes</span>
            </div>
          </div>
          <div className="theme-signal-bar" aria-label="Signal distribution">
            {signalBreakdown.high > 0 ? (
              <div className="signal-seg signal-high" style={{ flex: signalBreakdown.high }} />
            ) : null}
            {signalBreakdown.medium > 0 ? (
              <div className="signal-seg signal-medium" style={{ flex: signalBreakdown.medium }} />
            ) : null}
            {signalBreakdown.low > 0 ? <div className="signal-seg signal-low" style={{ flex: signalBreakdown.low }} /> : null}
            {signalBreakdown.total === 0 || signalBreakdown.none > 0 ? (
              <div
                className="signal-seg signal-none"
                style={{ flex: signalBreakdown.total === 0 ? 1 : signalBreakdown.none }}
              />
            ) : null}
          </div>
          <p className="theme-signal-legend">
            {signalBreakdown.high}H · {signalBreakdown.medium}M · {signalBreakdown.low}L
          </p>
        </div>
        <span className="theme-row-arrow" aria-hidden="true">
          &rarr;
        </span>
      </>
    );

    if (!docketId) {
      return <div className="theme-row">{content}</div>;
    }

    return (
      <Link
        className="theme-row"
        to={`/dockets/${docketId}?${themeQuery}`}
        title="View linked changes"
        aria-label={`View changes linked to ${themeLabel}`}
      >
        {content}
      </Link>
    );
  },
  (previous, next) =>
    previous.cluster === next.cluster &&
    previous.linkedCardCount === next.linkedCardCount &&
    previous.rank === next.rank &&
    previous.docketId === next.docketId &&
    previous.signalBreakdown.high === next.signalBreakdown.high &&
    previous.signalBreakdown.medium === next.signalBreakdown.medium &&
    previous.signalBreakdown.low === next.signalBreakdown.low &&
    previous.signalBreakdown.none === next.signalBreakdown.none &&
    previous.signalBreakdown.total === next.signalBreakdown.total
);
