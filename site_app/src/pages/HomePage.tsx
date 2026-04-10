import { Link } from "react-router-dom";
import { AppChrome } from "../components/AppChrome";
import { ErrorView } from "../components/ErrorView";
import { LoadingView } from "../components/LoadingView";
import { docketStoryTitle, formatStamp } from "../constants";
import { useAsyncData } from "../hooks/useAsyncData";
import type { DocketIndex, ReleaseSummary, SnapshotManifest } from "../models";
import { loadDocketIndex, loadInsightPreviewTitles, loadManifest, loadReleaseSummary } from "../snapshot";

export default function HomePage() {
  const manifestState = useAsyncData<SnapshotManifest>(() => loadManifest(), []);
  const indexState = useAsyncData<DocketIndex>(() => loadDocketIndex(), []);
  const releaseSummaryState = useAsyncData<ReleaseSummary>(() => loadReleaseSummary(), []);
  const insightPreviewState = useAsyncData<Record<string, string>>(
    () => (indexState.status === "ready" ? loadInsightPreviewTitles(indexState.data.dockets) : Promise.resolve({})),
    [indexState.status === "ready" ? indexState.data.published_at : "pending"]
  );

  if (manifestState.status === "loading" || indexState.status === "loading") {
    return <LoadingView label="Loading docket index" />;
  }
  if (manifestState.status === "error") {
    return <ErrorView title="Unable to load snapshot manifest" message={manifestState.error} />;
  }
  if (indexState.status === "error") {
    return <ErrorView title="Unable to load docket index" message={indexState.error} />;
  }

  const manifest = manifestState.data;
  const docketIndex = indexState.data;
  const insightPreviewTitles = insightPreviewState.status === "ready" ? insightPreviewState.data : {};
  const totalCards = docketIndex.dockets.reduce((sum, docket) => sum + docket.total_change_cards, 0);
  const totalCommentThemes = docketIndex.dockets.reduce((sum, docket) => sum + docket.total_clusters, 0);

  return (
    <AppChrome>
      <div className="exec-band">
        <div className="exec-band-left">
          <p className="exec-kicker">Regulatory Intelligence</p>
          <h1 className="exec-title">Choose a docket</h1>
          <p className="exec-sub">Explore executive summaries, comment themes, and priority changes across published dockets.</p>
          <p className="exec-meta">Snapshot {formatStamp(manifest.snapshot.published_at)}</p>
        </div>
        <div className="exec-band-kpis">
          <div className="kpi-tile">
            <span className="kpi-label">Dockets</span>
            <strong className="kpi-value">{manifest.snapshot.docket_count}</strong>
          </div>
          <div className="kpi-tile">
            <span className="kpi-label">Changes</span>
            <strong className="kpi-value">{totalCards}</strong>
          </div>
          <div className="kpi-tile">
            <span className="kpi-label">Themes</span>
            <strong className="kpi-value">{totalCommentThemes}</strong>
          </div>
          {releaseSummaryState.status === "ready" ? (
            <>
              <div className="kpi-tile">
                <span className="kpi-label">Eval</span>
                <strong className="kpi-value">
                  {releaseSummaryState.data.evaluation.available}/{releaseSummaryState.data.docket_count}
                </strong>
              </div>
              <div className="kpi-tile">
                <span className="kpi-label">Insights</span>
                <strong className="kpi-value">
                  {releaseSummaryState.data.insights.available}/{releaseSummaryState.data.docket_count}
                </strong>
              </div>
            </>
          ) : null}
        </div>
      </div>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Available Dockets</p>
            <h2>Select a docket to begin</h2>
          </div>
        </div>
        <div className="docket-selector">
          {docketIndex.dockets.map((docket) => {
            const storyTitle = docketStoryTitle(docket.docket_id, docket.display_title);
            const previewTitle = docket.top_finding_title || insightPreviewTitles[docket.docket_id] || null;

            return (
              <Link
                key={docket.docket_id}
                className="docket-row"
                to={`/dockets/${docket.docket_id}`}
                aria-label={`Open ${storyTitle}`}
              >
                <div className="docket-row-id">
                  <span className="docket-row-eyebrow">{docket.docket_id}</span>
                  <span className="docket-row-title">{storyTitle}</span>
                </div>
                <div className="docket-row-stats">
                  <span className="docket-stat">
                    <strong>{docket.total_change_cards}</strong> changes
                  </span>
                  <span className="docket-stat">
                    <strong>{docket.total_clusters}</strong> themes
                  </span>
                  <span className="docket-stat">
                    <strong>{docket.labeled_clusters}</strong> labeled
                  </span>
                </div>
                {previewTitle ? (
                  <span className="docket-row-preview">{previewTitle}</span>
                ) : (
                  <span className="docket-row-preview meta-line">
                    {docket.insight_available ? "Insight report available" : "No insight preview"}
                  </span>
                )}
                <div className="docket-row-badges">
                  <span className={`status-chip ${docket.insight_available ? "available" : "not_available"}`}>
                    {docket.insight_available ? "Insights" : "No insights"}
                  </span>
                  <span className={`status-chip ${docket.evaluation_available ? "available" : "not_available"}`}>
                    {docket.evaluation_available ? "Eval" : "No eval"}
                  </span>
                </div>
                <span className="docket-row-arrow" aria-hidden="true">
                  &rsaquo;
                </span>
              </Link>
            );
          })}
        </div>
      </section>
    </AppChrome>
  );
}
