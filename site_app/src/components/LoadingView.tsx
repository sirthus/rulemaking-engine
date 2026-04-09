import type { CSSProperties } from "react";

const loadingCardGridStyle = {
  display: "grid",
  gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))",
  gap: "1rem",
  marginTop: "1rem",
} satisfies CSSProperties;

const insightSkeletonStyle = {
  marginTop: "0.75rem",
} satisfies CSSProperties;

export function LoadingView({ label }: { label: string }) {
  return (
    <section className="panel loading-panel" aria-busy="true" aria-label={label}>
      <div className="skeleton skeleton-line short" />
      <div className="skeleton skeleton-heading" />
      <div className="skeleton skeleton-line medium" />
      <div className="skeleton skeleton-line full" />
      <div style={loadingCardGridStyle}>
        {[1, 2, 3].map((item) => (
          <div key={item} className="skeleton-card">
            <div className="skeleton skeleton-line short" />
            <div className="skeleton skeleton-line medium" />
          </div>
        ))}
      </div>
    </section>
  );
}

export function InsightLoadingPanel({ title }: { title: string }) {
  return (
    <section className="panel insight-banner" aria-busy="true">
      <p className="eyebrow">Insight Report</p>
      <h2>{title}</h2>
      <p className="meta-line">Loading insight report...</p>
      <div className="skeleton skeleton-line full" style={insightSkeletonStyle} />
      <div className="skeleton skeleton-line medium" />
    </section>
  );
}
