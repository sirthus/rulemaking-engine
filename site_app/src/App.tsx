import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, Navigate, Route, Routes, useParams, useSearchParams } from "react-router-dom";
import { AppChrome } from "./components/AppChrome";
import { Breadcrumb } from "./components/Breadcrumb";
import {
  type CardSort,
  cardDisplayMetrics,
  changeTypeLabel,
  compareCardsByDisplayMetrics,
  isPrimaryCard,
  priorityChipClass,
  sizeChipClass,
} from "./components/ChangeCardRow";
import { ChangeDetailPane } from "./components/ChangeDetailPane";
import { ChangeListRow } from "./components/ChangeListRow";
import { CardInsightPanel, getCardInsightContext, preambleLinkKey } from "./components/CardInsightPanel";
import { ErrorView } from "./components/ErrorView";
import { FilterBar } from "./components/FilterBar";
import { FindingEvidenceLine } from "./components/FindingEvidenceLine";
import { cardChangeSynopsis, InlineDiff } from "./components/InlineDiff";
import { InsightLoadingPanel, LoadingView } from "./components/LoadingView";
import { ThemeRow, type ThemeSignalBreakdown } from "./components/ThemeCard";
import type {
  ClusterSummary,
  DocketIndex,
  EvalReport,
  InsightReport,
  ReleaseSummary,
  Report,
  SnapshotManifest,
} from "./models";
import {
  loadDocketIndex,
  loadEvalReport,
  loadInsightReport,
  loadManifest,
  loadReleaseSummary,
  loadReport,
  summarizeMetricBlock,
} from "./snapshot";

type LoadState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

const DOCKET_STORY_TITLES: Record<string, string> = {
  "EPA-HQ-OAR-2018-0225": "Good Neighbor Obligations for the 2008 Ozone NAAQS",
  "EPA-HQ-OAR-2020-0272": "Revised CSAPR Update for the 2008 Ozone NAAQS",
  "EPA-HQ-OAR-2020-0430": "Primary Copper Smelting NESHAP Reviews",
};

function useAsyncData<T>(loader: () => Promise<T>, deps: unknown[]): LoadState<T> {
  const [state, setState] = useState<LoadState<T>>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    loader()
      .then((data) => {
        if (!cancelled) {
          setState({ status: "ready", data });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setState({ status: "error", error: error instanceof Error ? error.message : String(error) });
        }
      });

    return () => {
      cancelled = true;
    };
  }, deps);

  return state;
}

function useDocketInsightStates(docketIds: string[]): Record<string, LoadState<InsightReport | null>> {
  const [states, setStates] = useState<Record<string, LoadState<InsightReport | null>>>({});

  useEffect(() => {
    let cancelled = false;
    setStates(Object.fromEntries(docketIds.map((docketId) => [docketId, { status: "loading" }])));

    for (const docketId of docketIds) {
      loadInsightReport(docketId)
        .then((data) => {
          if (!cancelled) {
            setStates((current) => ({ ...current, [docketId]: { status: "ready", data } }));
          }
        })
        .catch((error: unknown) => {
          if (!cancelled) {
            setStates((current) => ({
              ...current,
              [docketId]: { status: "error", error: error instanceof Error ? error.message : String(error) },
            }));
          }
        });
    }

    return () => {
      cancelled = true;
    };
  }, [docketIds.join("|")]);

  return states;
}

function formatStamp(value?: string): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function normalizeCardSort(value: string | null): CardSort {
  return value === "size" ? "size" : "priority";
}

function docketStoryTitle(docketId: string, fallback?: string): string {
  return DOCKET_STORY_TITLES[docketId] || fallback || docketId;
}

function clusterSearchText(cluster: Pick<ClusterSummary, "label" | "label_description" | "top_keywords">): string {
  return [cluster.label || "", cluster.label_description || "", ...(cluster.top_keywords || [])].join(" ").toLowerCase();
}

function docketTabLabel(tab: string): string {
  if (tab === "overview") {
    return "Overview";
  }
  if (tab === "themes") {
    return "Comment Themes";
  }
  return "Priority Changes";
}

function PriorityDistBar({ commentLinked, total }: { commentLinked: number; total: number }) {
  if (total === 0) {
    return null;
  }

  const unlinked = Math.max(total - commentLinked, 0);
  const linkedPct = Math.round((commentLinked / total) * 100);

  return (
    <div className="priority-dist-bar">
      <div className="priority-dist-meta">
        <span className="priority-dist-label">Linked changes</span>
        <p className="priority-dist-legend">
          <strong>{commentLinked}</strong> of {total} · {linkedPct}%
        </p>
      </div>
      <div className="priority-dist-track" aria-hidden="true">
        <div
          className="priority-dist-seg priority-dist-seg-linked"
          style={{ flex: commentLinked }}
          title={`${commentLinked} linked changes`}
        />
        <div
          className="priority-dist-seg priority-dist-seg-unlinked"
          style={{ flex: unlinked }}
          title={`${unlinked} without comment linkage`}
        />
      </div>
    </div>
  );
}

function EmptyState({
  title,
  copy = "Try clearing a filter or broadening your search terms.",
}: {
  title: string;
  copy?: string;
}) {
  return (
    <div className="empty-state" role="status">
      <div className="empty-state-icon" aria-hidden="true">
        ⌕
      </div>
      <p className="empty-state-title">{title}</p>
      <p className="empty-state-copy">{copy}</p>
    </div>
  );
}

function HomePage() {
  const manifestState = useAsyncData<SnapshotManifest>(() => loadManifest(), []);
  const indexState = useAsyncData<DocketIndex>(() => loadDocketIndex(), []);
  const releaseSummaryState = useAsyncData<ReleaseSummary>(() => loadReleaseSummary(), []);
  const homeDocketIds = indexState.status === "ready" ? indexState.data.dockets.map((docket) => docket.docket_id) : [];
  const insightPreviewStates = useDocketInsightStates(homeDocketIds);

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
  const totalCards = docketIndex.dockets.reduce((sum, docket) => sum + docket.total_change_cards, 0);
  const totalCommentThemes = docketIndex.dockets.reduce((sum, docket) => sum + docket.total_clusters, 0);

  return (
    <AppChrome>
      <div className="exec-band">
        <div className="exec-band-left">
          <p className="exec-kicker">Regulatory Intelligence</p>
          <h1 className="exec-title">Choose a docket</h1>
          <p className="exec-sub">
            Select a docket to read the executive summary, inspect comment themes, and review priority changes with
            evidence links.
          </p>
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
            const insightState = insightPreviewStates[docket.docket_id] || { status: "loading" };
            const insightReport = insightState.status === "ready" ? insightState.data : null;
            const storyTitle = docketStoryTitle(docket.docket_id, docket.display_title);

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
                {insightState.status === "loading" ? (
                  <span className="docket-row-preview meta-line">Loading...</span>
                ) : insightReport ? (
                  <span className="docket-row-preview">{insightReport.top_findings[0]?.title || "-"}</span>
                ) : (
                  <span className="docket-row-preview meta-line">No insight preview</span>
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

function DocketPage() {
  const params = useParams<{ docketId: string }>();
  const docketId = params.docketId ?? "";
  const reportState = useAsyncData<Report>(() => loadReport(docketId), [docketId]);
  const evalState = useAsyncData<EvalReport>(() => loadEvalReport(docketId), [docketId]);
  const insightState = useAsyncData<InsightReport | null>(() => loadInsightReport(docketId), [docketId]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [showLowerSignalCards, setShowLowerSignalCards] = useState(false);
  const [showEval, setShowEval] = useState(false);
  const [headerInView, setHeaderInView] = useState(true);
  const headerRef = useRef<HTMLDivElement | null>(null);
  const detailPaneRef = useRef<HTMLDivElement | null>(null);
  const tab = searchParams.get("tab") || "changes";
  const selectedCardId = searchParams.get("card") || null;

  useEffect(() => {
    if (selectedCardId && detailPaneRef.current) {
      detailPaneRef.current.scrollTop = 0;
    }
  }, [selectedCardId]);

  useEffect(() => {
    if (!selectedCardId) {
      return;
    }

    const row = document.querySelector<HTMLElement>(`[data-card-id="${selectedCardId}"]`);
    row?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [selectedCardId]);

  useEffect(() => {
    const header = headerRef.current;
    if (!header || typeof IntersectionObserver === "undefined") {
      return;
    }

    const observer = new IntersectionObserver(([entry]) => {
      setHeaderInView(entry.isIntersecting);
    });
    observer.observe(header);

    return () => observer.disconnect();
  }, []);

  if (reportState.status === "loading" || evalState.status === "loading") {
    return <LoadingView label={`Loading ${docketId}`} />;
  }
  if (reportState.status === "error") {
    return <ErrorView title={`Unable to load ${docketId}`} message={reportState.error} />;
  }
  if (evalState.status === "error") {
    return <ErrorView title={`Unable to load evaluation for ${docketId}`} message={evalState.error} />;
  }

  const report = reportState.data;
  const evalReport = evalState.data;
  const insightReport = insightState.status === "ready" ? insightState.data : null;
  const clusterById = new Map(report.clusters.map((cluster) => [cluster.cluster_id, cluster]));
  const changeType = searchParams.get("changeType") || "all";
  const signal = searchParams.get("signal") || "all";
  const clusterState = searchParams.get("clusterState") || "all";
  const clusterQueryRaw = searchParams.get("clusterQuery") || "";
  const clusterQuery = clusterQueryRaw.trim().toLowerCase();
  const cardSort = normalizeCardSort(searchParams.get("cardSort"));
  const visibleTopFindings = insightReport
    ? insightReport.top_findings.filter((finding) => finding.card_ids.length > 0).slice(0, 5)
    : [];

  const filteredClusters = report.clusters.filter((cluster) => {
    const hasLabel = Boolean(cluster.label);
    const matchesState =
      clusterState === "all" ||
      (clusterState === "labeled" && hasLabel) ||
      (clusterState === "unlabeled" && !hasLabel);
    const matchesQuery = !clusterQuery || clusterSearchText(cluster).includes(clusterQuery);
    return matchesState && matchesQuery;
  });

  const cardMetrics = new Map(report.change_cards.map((card) => [card.card_id, cardDisplayMetrics(card)]));
  const filteredCards = report.change_cards
    .filter((card) => {
      const signalLevel = card.alignment_signal?.level || "none";
      const relatedClusters = card.related_clusters || [];
      const hasLabeledCluster = relatedClusters.some((cluster) => Boolean(cluster.label));
      const matchesClusterState =
        clusterState === "all" ||
        (clusterState === "labeled" && hasLabeledCluster) ||
        (clusterState === "unlabeled" && !hasLabeledCluster);
      const matchesClusterQuery =
        !clusterQuery ||
        relatedClusters.some((cluster) => {
          const reportCluster = clusterById.get(cluster.cluster_id);
          return clusterSearchText({
            label: cluster.label ?? reportCluster?.label ?? null,
            label_description: cluster.label_description ?? reportCluster?.label_description ?? null,
            top_keywords: reportCluster?.top_keywords || [],
          }).includes(clusterQuery);
        });

      return (
        (changeType === "all" || card.change_type === changeType) &&
        (signal === "all" || signalLevel === signal) &&
        matchesClusterState &&
        matchesClusterQuery
      );
    })
    .sort((a, b) =>
      compareCardsByDisplayMetrics(a, b, cardMetrics.get(a.card_id)!, cardMetrics.get(b.card_id)!, cardSort)
    );

  const commentLinkedCardCount = report.change_cards.filter((card) => {
    const metrics = cardMetrics.get(card.card_id)!;
    return !metrics.isDocketProcess && metrics.linkedComments > 0;
  }).length;

  const primaryCards = filteredCards.filter((card) => {
    const metrics = cardMetrics.get(card.card_id)!;
    return isPrimaryCard(metrics);
  });

  const foldedCards = filteredCards.filter((card) => {
    const metrics = cardMetrics.get(card.card_id)!;
    return !isPrimaryCard(metrics);
  });

  const visibleChangeRows = showLowerSignalCards ? [...primaryCards, ...foldedCards] : primaryCards;
  const selectedCard = selectedCardId
    ? report.change_cards.find((card) => card.card_id === selectedCardId) ?? null
    : null;
  const changeTypes = Array.from(new Set(report.change_cards.map((card) => card.change_type).filter(Boolean)));

  function updateFilter(name: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (!value || value === "all") {
      next.delete(name);
    } else {
      next.set(name, value);
    }
    setSearchParams(next, { replace: true });
  }

  function resetChangeFilters() {
    const next = new URLSearchParams(searchParams);
    ["changeType", "signal", "cardSort", "clusterQuery", "clusterState"].forEach((name) => next.delete(name));
    setSearchParams(next, { replace: true });
  }

  function setTab(value: string) {
    const next = new URLSearchParams(searchParams);
    next.set("tab", value);
    if (value !== "changes") {
      next.delete("card");
    }
    setSearchParams(next, { replace: true });
  }

  function selectCard(cardId: string) {
    const next = new URLSearchParams(searchParams);
    next.set("card", cardId);
    next.set("tab", "changes");
    setSearchParams(next, { replace: true });
  }

  function handleListKeyDown(event: KeyboardEvent<HTMLDivElement>, currentIndex: number) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const nextCard = visibleChangeRows[currentIndex + 1];
      if (nextCard) {
        selectCard(nextCard.card_id);
      }
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      const previousCard = visibleChangeRows[currentIndex - 1];
      if (previousCard) {
        selectCard(previousCard.card_id);
      }
    }
  }

  function toggleEval() {
    setShowEval((value) => !value);
  }

  function clusterMetrics(clusterId: string): { breakdown: ThemeSignalBreakdown; linkedCardCount: number } {
    const linkedCards = report.change_cards.filter((card) =>
      (card.related_clusters || []).some((cluster) => cluster.cluster_id === clusterId)
    );
    const breakdown: ThemeSignalBreakdown = { high: 0, medium: 0, low: 0, none: 0, total: linkedCards.length };

    for (const card of linkedCards) {
      const level = card.alignment_signal?.level || "none";
      if (level === "high" || level === "medium" || level === "low" || level === "none") {
        breakdown[level] += 1;
      } else {
        breakdown.none += 1;
      }
    }

    return { breakdown, linkedCardCount: linkedCards.length };
  }

  return (
    <AppChrome>
      {!headerInView ? (
        <div className="docket-context-bar">
          <span className="docket-context-id">{report.docket_id}</span>
          <span className="docket-context-tab">{docketTabLabel(tab)}</span>
          <span className="docket-context-count">
            {tab === "changes" ? `${filteredCards.length} changes` : `${filteredClusters.length} themes`}
          </span>
        </div>
      ) : null}

      <Breadcrumb items={[{ label: "Home", href: "/" }, { label: report.docket_id }]} />

      <div className="docket-header" ref={headerRef}>
        <div className="docket-header-top">
          <div className="docket-title-block">
            <p className="eyebrow">Docket</p>
            <h1 className="docket-title">{docketStoryTitle(report.docket_id)}</h1>
            <p className="eyebrow docket-subid">{report.docket_id}</p>
          </div>
          <PriorityDistBar commentLinked={commentLinkedCardCount} total={report.summary.total_change_cards} />
        </div>
        <div className="docket-stat-strip">
          <div className="docket-stat-item">
            <strong>{report.summary.total_canonical_comments}</strong>
            <span>Unique comments</span>
          </div>
          <div className="docket-stat-item">
            <strong>{report.summary.total_clusters}</strong>
            <span>Themes</span>
          </div>
          <div className="docket-stat-item">
            <strong>{commentLinkedCardCount}</strong>
            <span>Linked changes</span>
          </div>
          <div className="docket-stat-item">
            <strong>{report.summary.total_change_cards}</strong>
            <span>Total changes</span>
          </div>
        </div>
      </div>

      <section className="panel workspace-surface">
        <nav className="tab-bar" aria-label="Docket sections">
          <button
            type="button"
            className={`tab-btn${tab === "overview" ? " active" : ""}`}
            onClick={() => setTab("overview")}
            aria-selected={tab === "overview"}
          >
            Overview
          </button>
          <button
            type="button"
            className={`tab-btn${tab === "changes" ? " active" : ""}`}
            onClick={() => setTab("changes")}
            aria-selected={tab === "changes"}
          >
            Priority Changes
            <span className="tab-count">{filteredCards.length}</span>
          </button>
          <button
            type="button"
            className={`tab-btn${tab === "themes" ? " active" : ""}`}
            onClick={() => setTab("themes")}
            aria-selected={tab === "themes"}
          >
            Comment Themes
            <span className="tab-count">{filteredClusters.length}</span>
          </button>
        </nav>

        {tab === "overview" ? (
          <div className="tab-panel">
            {insightState.status === "loading" ? (
              <InsightLoadingPanel title="Loading Docket Analysis" />
            ) : insightReport ? (
              <section className="panel insight-banner">
                <div className="section-header">
                  <div>
                    <p className="eyebrow">Insight Report</p>
                    <h2>Docket Analysis</h2>
                  </div>
                </div>

                <p className="insight-summary">{insightReport.executive_summary}</p>

                <div className="rule-story-grid">
                  <div className="rule-story-cell">
                    <p className="eyebrow">What Changed</p>
                    <p>{insightReport.rule_story.what_changed}</p>
                  </div>
                  <div className="rule-story-cell">
                    <p className="eyebrow">Commenter Themes</p>
                    <p>{insightReport.rule_story.what_commenters_emphasized}</p>
                  </div>
                  <div className="rule-story-cell">
                    <p className="eyebrow">Comment Alignment</p>
                    <p>{insightReport.rule_story.where_final_text_aligned}</p>
                  </div>
                </div>

                {visibleTopFindings.length > 0 ? (
                  <div className="finding-list">
                    <p className="eyebrow">Top Findings</p>
                    {visibleTopFindings.map((finding) => (
                      <article key={finding.finding_id} className="finding-card">
                        <h3 className="finding-title">{finding.title}</h3>
                        <p className="meta-line">
                          {finding.card_ids.length} change card{finding.card_ids.length === 1 ? "" : "s"}
                        </p>
                        <p className="finding-summary">{finding.summary}</p>
                        <p className="finding-summary">{finding.why_it_matters}</p>
                        <FindingEvidenceLine finding={finding} />
                      </article>
                    ))}
                  </div>
                ) : null}

                <p className="meta-line insight-caveats">{insightReport.rule_story.caveats}</p>
              </section>
            ) : (
              <EmptyState title="No insight report is published for this docket" />
            )}

            <section className={`panel eval-panel ${evalReport.status}`}>
              <div className="eval-panel-header" onClick={toggleEval}>
                <div>
                  <p className="eyebrow">Snapshot Quality</p>
                  <h2>Snapshot quality details</h2>
                </div>
                <button
                  type="button"
                  className="eval-toggle-btn"
                  aria-expanded={showEval}
                  aria-controls="eval-quality-body"
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleEval();
                  }}
                >
                  {showEval ? "Collapse" : "Expand"}
                </button>
              </div>
              <div id="eval-quality-body" style={{ display: showEval ? "block" : "none" }}>
                <div className="quality-details">
                  <h2>
                    {evalReport.status === "available"
                      ? "Blind/seed evaluation available"
                      : "Evaluation not yet annotated"}
                  </h2>
                  {evalReport.status === "available" ? (
                    <p>
                      {evalReport.gold_set_provenance?.annotation_method || "unknown"} by{" "}
                      {evalReport.gold_set_provenance?.annotator || evalReport.gold_set_annotator || "unknown"} on{" "}
                      {formatStamp(evalReport.gold_set_provenance?.annotated_at)}
                    </p>
                  ) : (
                    <p>The site shows the current docket output, but no committed blind gold set is available yet.</p>
                  )}
                  {evalReport.status === "available" ? (
                    <ul className="metric-list">
                      {summarizeMetricBlock(evalReport.alignment_metrics).slice(0, 3).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            </section>
          </div>
        ) : null}

        {tab === "changes" ? (
          <>
            <FilterBar
              changeType={changeType}
              signal={signal}
              cardSort={cardSort}
              clusterQuery={clusterQueryRaw}
              changeTypes={changeTypes}
              resultCount={filteredCards.length}
              totalCount={report.change_cards.length}
              onFilter={updateFilter}
              onReset={resetChangeFilters}
            />

            <div className="review-workspace">
              <div className="review-list-pane" role="list">
                <div className="review-list-header">
                  <h2>{primaryCards.length} change{primaryCards.length === 1 ? "" : "s"} shown</h2>
                </div>

                {primaryCards.map((card, index) => (
                  <ChangeListRow
                    key={card.card_id}
                    card={card}
                    metrics={cardMetrics.get(card.card_id)!}
                    selected={card.card_id === selectedCardId}
                    index={index + 1}
                    onClick={() => selectCard(card.card_id)}
                    onKeyDown={(event) => handleListKeyDown(event, index)}
                  />
                ))}

                {filteredCards.length === 0 ? <EmptyState title="No changes match these filters" /> : null}
                {filteredCards.length > 0 && primaryCards.length === 0 ? (
                  <p className="review-list-note">Only lower-signal or docket-process cards match the current filters.</p>
                ) : null}

                {foldedCards.length > 0 ? (
                  <button
                    type="button"
                    className="inline-action fold-control"
                    onClick={() => setShowLowerSignalCards((value) => !value)}
                  >
                    {showLowerSignalCards
                      ? "Hide lower-signal and docket-process cards"
                      : `Show ${foldedCards.length} lower-signal and docket-process card${foldedCards.length === 1 ? "" : "s"}`}
                  </button>
                ) : null}

                {showLowerSignalCards && foldedCards.length > 0 ? (
                  <div className="folded-card-group">
                    <div>
                      <p className="eyebrow">Lower-signal and docket-process cards</p>
                      <h3>{foldedCards.length} card{foldedCards.length === 1 ? "" : "s"} available</h3>
                    </div>
                    {foldedCards.map((card, index) => (
                      <ChangeListRow
                        key={card.card_id}
                        card={card}
                        metrics={cardMetrics.get(card.card_id)!}
                        selected={card.card_id === selectedCardId}
                        index={primaryCards.length + index + 1}
                        onClick={() => selectCard(card.card_id)}
                        onKeyDown={(event) => handleListKeyDown(event, primaryCards.length + index)}
                      />
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="review-detail-pane" ref={detailPaneRef}>
                {selectedCard ? (
                  <ChangeDetailPane
                    card={selectedCard}
                    metrics={cardMetrics.get(selectedCard.card_id)!}
                    insightReport={insightReport}
                    docketId={docketId}
                  />
                ) : (
                  <div className="review-detail-empty">
                    <p>Select a change from the list to review it here.</p>
                  </div>
                )}
              </div>
            </div>
          </>
        ) : null}

        {tab === "themes" ? (
          <div className="tab-panel">
            <div className="themes-toolbar">
              <div>
                <p className="eyebrow">Comment Themes</p>
                <h2>{filteredClusters.length} comment themes</h2>
              </div>
              <label className="filter-field">
                <span className="filter-label">Theme state</span>
                <select value={clusterState} onChange={(event) => updateFilter("clusterState", event.target.value)}>
                  <option value="all">All</option>
                  <option value="labeled">Labeled only</option>
                  <option value="unlabeled">Unlabeled only</option>
                </select>
              </label>
              <label className="filter-field filter-search">
                <span className="filter-label">Theme search</span>
                <input
                  value={clusterQueryRaw}
                  onChange={(event) => updateFilter("clusterQuery", event.target.value)}
                  placeholder="Search labels, descriptions, or keywords"
                />
              </label>
            </div>

            <div className="theme-list">
              {filteredClusters.map((cluster, index) => {
                const { breakdown, linkedCardCount } = clusterMetrics(cluster.cluster_id);
                return (
                  <ThemeRow
                    key={cluster.cluster_id}
                    cluster={cluster}
                    signalBreakdown={breakdown}
                    linkedCardCount={linkedCardCount}
                    rank={index + 1}
                    docketId={report.docket_id}
                  />
                );
              })}
              {filteredClusters.length === 0 ? <EmptyState title="No comment themes match these filters" /> : null}
            </div>
          </div>
        ) : null}
      </section>
    </AppChrome>
  );
}

function CardDetailPage() {
  const params = useParams<{ docketId: string; cardId: string }>();
  const docketId = params.docketId ?? "";
  const cardId = params.cardId ?? "";
  const reportState = useAsyncData<Report>(() => loadReport(docketId), [docketId]);
  const insightState = useAsyncData<InsightReport | null>(() => loadInsightReport(docketId), [docketId]);

  if (reportState.status === "loading") {
    return <LoadingView label={`Loading card ${cardId}`} />;
  }
  if (reportState.status === "error") {
    return <ErrorView title={`Unable to load ${cardId}`} message={reportState.error} />;
  }

  const report = reportState.data;
  const card = report.change_cards.find((item) => item.card_id === cardId);
  if (!card) {
    return <Navigate to={`/dockets/${docketId}`} replace />;
  }

  const insightReport = insightState.status === "ready" ? insightState.data : null;
  const detailMetrics = cardDisplayMetrics(card);
  const detailChangeType = changeTypeLabel(card.change_type);
  const detailSynopsis = cardChangeSynopsis(card, detailMetrics);
  const preambleLinks = card.preamble_links || [];
  const cardLabel = card.final_heading || card.proposed_heading || card.card_id;
  const { priorityCard, linkedFindings, hasStalePriorityFindings } = getCardInsightContext(insightReport, cardId);
  const findingClusterIds = new Set(linkedFindings.flatMap((finding) => finding.cluster_ids));

  return (
    <AppChrome>
      <Breadcrumb
        items={[
          { label: "Home", href: "/" },
          { label: docketId, href: `/dockets/${docketId}` },
          { label: cardLabel },
        ]}
      />

      <section className="panel">
        <p className="eyebrow">{card.card_id}</p>
        <h1>{cardLabel}</h1>
        <p className="detail-heading-meta">{detailChangeType}</p>
        <div className="chip-row">
          <span className={`status-chip ${priorityChipClass(detailMetrics)}`}>{detailMetrics.priorityLabel}</span>
          <span className={`status-chip ${sizeChipClass(detailMetrics)}`}>{detailMetrics.sizeLabel}</span>
          {detailMetrics.linkedComments > 0 ? (
            <span className="status-chip chip-comment-count">{detailMetrics.linkedComments} comments</span>
          ) : null}
        </div>
      </section>

      {insightState.status === "loading" ? <InsightLoadingPanel title="Loading Card Insight" /> : null}

      {insightState.status !== "loading" ? (
        <CardInsightPanel
          insightReport={insightReport}
          priorityCard={priorityCard}
          linkedFindings={linkedFindings}
          hasStalePriorityFindings={hasStalePriorityFindings}
        />
      ) : null}

      <section className="panel">
        <p className="eyebrow">Text comparison</p>
        <InlineDiff card={card} synopsis={detailSynopsis} />
      </section>

      <section className="panel">
        <p className="eyebrow">Evidence note</p>
        {card.alignment_signal?.level && card.alignment_signal.level !== "none" ? (
          <p className="meta-line">Comment signal: {card.alignment_signal.level}</p>
        ) : null}
        <p>{card.alignment_signal?.evidence_note || "No evidence note available."}</p>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Related comment themes</p>
            <h2>{(card.related_clusters || []).length} linked comment themes</h2>
          </div>
        </div>
        <div className="cluster-list">
          {(card.related_clusters || []).map((cluster) => (
            <article key={cluster.cluster_id} className="cluster-card">
              <div className="cluster-header">
                <h3>{cluster.label || cluster.cluster_id}</h3>
                {findingClusterIds.has(cluster.cluster_id) ? (
                  <span className="status-chip available">linked finding</span>
                ) : null}
              </div>
              <p>{cluster.label_description || "No label description available."}</p>
              <p className="meta-line">Comments linked: {cluster.comment_count || 0}</p>
            </article>
          ))}
          {(card.related_clusters || []).length === 0 ? <p>No related comment themes recorded for this card.</p> : null}
        </div>
      </section>

      {preambleLinks.length > 0 ? (
        <section className="panel">
          <div className="section-header">
            <div>
              <p className="eyebrow">Preamble links</p>
              <h2>{preambleLinks.length} linked sections</h2>
            </div>
          </div>
          <div className="cluster-list">
            {preambleLinks.map((link, index) => (
              <article key={preambleLinkKey(link, index)} className="cluster-card">
                <h3>{link.preamble_heading || link.preamble_section_id || "Preamble section"}</h3>
                <p>{link.relationship_label || "No relationship label recorded."}</p>
                <p className="meta-line">
                  {link.link_type || "unknown"} | score {typeof link.link_score === "number" ? link.link_score : "n/a"}
                </p>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </AppChrome>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/dockets/:docketId" element={<DocketPage />} />
      <Route path="/dockets/:docketId/cards/:cardId" element={<CardDetailPage />} />
    </Routes>
  );
}
