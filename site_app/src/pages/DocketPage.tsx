import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { AppChrome } from "../components/AppChrome";
import { Breadcrumb } from "../components/Breadcrumb";
import {
  cardDisplayMetrics,
  compareCardsByDisplayMetrics,
  isPrimaryCard,
} from "../components/ChangeCardRow";
import { ChangeDetailPane } from "../components/ChangeDetailPane";
import { ChangeListRow } from "../components/ChangeListRow";
import { ErrorView } from "../components/ErrorView";
import { FilterBar } from "../components/FilterBar";
import { FindingEvidenceLine } from "../components/FindingEvidenceLine";
import { InsightLoadingPanel, LoadingView } from "../components/LoadingView";
import { ThemeRow, type ThemeSignalBreakdown } from "../components/ThemeCard";
import {
  CLUSTER_STATE_LABELED,
  CLUSTER_STATE_UNLABELED,
  DEFAULT_TAB,
  FILTER_ALL,
  TAB_CHANGES,
  TAB_OVERVIEW,
  TAB_THEMES,
  clusterSearchText,
  docketStoryTitle,
  docketTabLabel,
  formatStamp,
  normalizeCardSort,
} from "../constants";
import { useAsyncData } from "../hooks/useAsyncData";
import type { EvalReport, InsightReport, Report } from "../models";
import { loadEvalReport, loadInsightReport, loadReport, summarizeMetricBlock } from "../snapshot";

type ClusterMetricSummary = {
  breakdown: ThemeSignalBreakdown;
  linkedCardCount: number;
};

const EMPTY_CLUSTER_METRICS: ClusterMetricSummary = {
  breakdown: { high: 0, medium: 0, low: 0, none: 0, total: 0 },
  linkedCardCount: 0,
};

const EMPTY_REPORT: Report = {
  schema_version: "v1",
  docket_id: "",
  generated_at: "",
  generator: "",
  summary: {
    total_comments: 0,
    total_canonical_comments: 0,
    total_clusters: 0,
    labeled_clusters: 0,
    total_change_cards: 0,
    change_type_counts: {},
    alignment_signal_counts: {},
    review_status_counts: {},
  },
  clusters: [],
  change_cards: [],
};

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

function buildClusterMetricsMap(report: Report): Map<string, ClusterMetricSummary> {
  const metricsMap = new Map<string, ClusterMetricSummary>();

  for (const cluster of report.clusters) {
    metricsMap.set(cluster.cluster_id, {
      breakdown: { high: 0, medium: 0, low: 0, none: 0, total: 0 },
      linkedCardCount: 0,
    });
  }

  for (const card of report.change_cards) {
    const rawLevel = card.alignment_signal?.level || "none";
    const level = rawLevel === "high" || rawLevel === "medium" || rawLevel === "low" ? rawLevel : "none";

    for (const cluster of card.related_clusters || []) {
      const current = metricsMap.get(cluster.cluster_id) || {
        breakdown: { high: 0, medium: 0, low: 0, none: 0, total: 0 },
        linkedCardCount: 0,
      };
      current.linkedCardCount += 1;
      current.breakdown.total += 1;
      current.breakdown[level] += 1;
      metricsMap.set(cluster.cluster_id, current);
    }
  }

  return metricsMap;
}

export default function DocketPage() {
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

  const report = reportState.status === "ready" ? reportState.data : EMPTY_REPORT;
  const evalReport = evalState.status === "ready" ? evalState.data : null;
  const insightReport = insightState.status === "ready" ? insightState.data : null;
  const tab = searchParams.get("tab") || DEFAULT_TAB;
  const changeType = searchParams.get("changeType") || FILTER_ALL;
  const signal = searchParams.get("signal") || FILTER_ALL;
  const clusterState = searchParams.get("clusterState") || FILTER_ALL;
  const clusterQueryRaw = searchParams.get("clusterQuery") || "";
  const clusterQuery = clusterQueryRaw.trim().toLowerCase();
  const cardSort = normalizeCardSort(searchParams.get("cardSort"));

  const clusterById = useMemo(
    () => new Map(report.clusters.map((cluster) => [cluster.cluster_id, cluster])),
    [report.clusters]
  );
  const clusterSearchTextMap = useMemo(
    () => new Map(report.clusters.map((cluster) => [cluster.cluster_id, clusterSearchText(cluster)])),
    [report.clusters]
  );
  const cardMetrics = useMemo(
    () => new Map(report.change_cards.map((card) => [card.card_id, cardDisplayMetrics(card)])),
    [report.change_cards]
  );
  const clusterMetricsMap = useMemo(() => buildClusterMetricsMap(report), [report]);

  const filteredClusters = useMemo(
    () =>
      report.clusters.filter((cluster) => {
        const hasLabel = Boolean(cluster.label);
        const matchesState =
          clusterState === FILTER_ALL ||
          (clusterState === CLUSTER_STATE_LABELED && hasLabel) ||
          (clusterState === CLUSTER_STATE_UNLABELED && !hasLabel);
        const matchesQuery = !clusterQuery || (clusterSearchTextMap.get(cluster.cluster_id) || "").includes(clusterQuery);
        return matchesState && matchesQuery;
      }),
    [clusterQuery, clusterSearchTextMap, clusterState, report.clusters]
  );

  const filteredCards = useMemo(() => {
    const cards = report.change_cards.filter((card) => {
      const signalLevel = card.alignment_signal?.level || "none";
      const relatedClusters = card.related_clusters || [];
      const hasLabeledCluster = relatedClusters.some((cluster) => Boolean(cluster.label));
      const matchesClusterState =
        clusterState === FILTER_ALL ||
        (clusterState === CLUSTER_STATE_LABELED && hasLabeledCluster) ||
        (clusterState === CLUSTER_STATE_UNLABELED && !hasLabeledCluster);
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
        (changeType === FILTER_ALL || card.change_type === changeType) &&
        (signal === FILTER_ALL || signalLevel === signal) &&
        matchesClusterState &&
        matchesClusterQuery
      );
    });

    cards.sort((a, b) =>
      compareCardsByDisplayMetrics(a, b, cardMetrics.get(a.card_id)!, cardMetrics.get(b.card_id)!, cardSort)
    );

    return cards;
  }, [cardMetrics, cardSort, changeType, clusterById, clusterQuery, clusterState, report.change_cards, signal]);

  const commentLinkedCardCount = useMemo(
    () =>
      report.change_cards.filter((card) => {
        const metrics = cardMetrics.get(card.card_id)!;
        return !metrics.isDocketProcess && metrics.linkedComments > 0;
      }).length,
    [cardMetrics, report.change_cards]
  );
  const primaryCards = useMemo(
    () => filteredCards.filter((card) => isPrimaryCard(cardMetrics.get(card.card_id)!)),
    [cardMetrics, filteredCards]
  );
  const foldedCards = useMemo(
    () => filteredCards.filter((card) => !isPrimaryCard(cardMetrics.get(card.card_id)!)),
    [cardMetrics, filteredCards]
  );
  const visibleChangeRows = useMemo(
    () => (showLowerSignalCards ? [...primaryCards, ...foldedCards] : primaryCards),
    [foldedCards, primaryCards, showLowerSignalCards]
  );
  const selectedCard = useMemo(
    () => (selectedCardId ? report.change_cards.find((card) => card.card_id === selectedCardId) ?? null : null),
    [report.change_cards, selectedCardId]
  );
  const changeTypes = useMemo(
    () => Array.from(new Set(report.change_cards.map((card) => card.change_type).filter(Boolean))),
    [report.change_cards]
  );
  const visibleTopFindings = useMemo(
    () => (insightReport ? insightReport.top_findings.filter((finding) => finding.card_ids.length > 0).slice(0, 5) : []),
    [insightReport]
  );

  const updateFilter = useCallback(
    (name: string, value: string) => {
      const next = new URLSearchParams(searchParams);
      if (!value || value === FILTER_ALL) {
        next.delete(name);
      } else {
        next.set(name, value);
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const resetChangeFilters = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    ["changeType", "signal", "cardSort", "clusterQuery", "clusterState"].forEach((name) => next.delete(name));
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const setTab = useCallback(
    (value: string) => {
      const next = new URLSearchParams(searchParams);
      next.set("tab", value);
      if (value !== TAB_CHANGES) {
        next.delete("card");
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const selectCard = useCallback(
    (cardId: string) => {
      const next = new URLSearchParams(searchParams);
      next.set("card", cardId);
      next.set("tab", TAB_CHANGES);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams]
  );

  const handleListKeyDown = useCallback(
    (event: KeyboardEvent<HTMLDivElement>, currentIndex: number) => {
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
    },
    [selectCard, visibleChangeRows]
  );

  if (reportState.status === "loading" || evalState.status === "loading") {
    return <LoadingView label={`Loading ${docketId}`} />;
  }
  if (reportState.status === "error") {
    return <ErrorView title={`Unable to load ${docketId}`} message={reportState.error} />;
  }
  if (evalState.status === "error") {
    return <ErrorView title={`Unable to load evaluation for ${docketId}`} message={evalState.error} />;
  }
  const resolvedEvalReport = evalState.data;

  return (
    <AppChrome>
      {!headerInView ? (
        <div className="docket-context-bar">
          <span className="docket-context-id">{report.docket_id}</span>
          <span className="docket-context-tab">{docketTabLabel(tab)}</span>
          <span className="docket-context-count">
            {tab === TAB_CHANGES ? `${filteredCards.length} changes` : `${filteredClusters.length} themes`}
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
            className={`tab-btn${tab === TAB_OVERVIEW ? " active" : ""}`}
            onClick={() => setTab(TAB_OVERVIEW)}
            aria-selected={tab === TAB_OVERVIEW}
          >
            Overview
          </button>
          <button
            type="button"
            className={`tab-btn${tab === TAB_CHANGES ? " active" : ""}`}
            onClick={() => setTab(TAB_CHANGES)}
            aria-selected={tab === TAB_CHANGES}
          >
            Priority Changes
            <span className="tab-count">{filteredCards.length}</span>
          </button>
          <button
            type="button"
            className={`tab-btn${tab === TAB_THEMES ? " active" : ""}`}
            onClick={() => setTab(TAB_THEMES)}
            aria-selected={tab === TAB_THEMES}
          >
            Comment Themes
            <span className="tab-count">{filteredClusters.length}</span>
          </button>
        </nav>

        {tab === TAB_OVERVIEW ? (
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

            <section className={`panel eval-panel ${resolvedEvalReport.status}`}>
              <div className="eval-panel-header" onClick={() => setShowEval((value) => !value)}>
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
                    setShowEval((value) => !value);
                  }}
                >
                  {showEval ? "Collapse" : "Expand"}
                </button>
              </div>
              <div id="eval-quality-body" style={{ display: showEval ? "block" : "none" }}>
                <div className="quality-details">
                  <h2>
                    {resolvedEvalReport.status === "available"
                      ? "Blind/seed evaluation available"
                      : "Evaluation not yet annotated"}
                  </h2>
                  {resolvedEvalReport.status === "available" ? (
                    <p>
                      {resolvedEvalReport.gold_set_provenance?.annotation_method || "unknown"} by{" "}
                      {resolvedEvalReport.gold_set_provenance?.annotator || resolvedEvalReport.gold_set_annotator || "unknown"} on{" "}
                      {formatStamp(resolvedEvalReport.gold_set_provenance?.annotated_at)}
                    </p>
                  ) : (
                    <p>The site shows the current docket output, but no committed blind gold set is available yet.</p>
                  )}
                  {resolvedEvalReport.status === "available" ? (
                    <ul className="metric-list">
                      {summarizeMetricBlock(resolvedEvalReport.alignment_metrics).slice(0, 3).map((line) => (
                        <li key={line}>{line}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              </div>
            </section>
          </div>
        ) : null}

        {tab === TAB_CHANGES ? (
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

        {tab === TAB_THEMES ? (
          <div className="tab-panel">
            <div className="themes-toolbar">
              <div>
                <p className="eyebrow">Comment Themes</p>
                <h2>{filteredClusters.length} comment themes</h2>
              </div>
              <label className="filter-field">
                <span className="filter-label">Theme state</span>
                <select value={clusterState} onChange={(event) => updateFilter("clusterState", event.target.value)}>
                  <option value={FILTER_ALL}>All</option>
                  <option value={CLUSTER_STATE_LABELED}>Labeled only</option>
                  <option value={CLUSTER_STATE_UNLABELED}>Unlabeled only</option>
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
                const metrics = clusterMetricsMap.get(cluster.cluster_id) || EMPTY_CLUSTER_METRICS;
                return (
                  <ThemeRow
                    key={cluster.cluster_id}
                    cluster={cluster}
                    signalBreakdown={metrics.breakdown}
                    linkedCardCount={metrics.linkedCardCount}
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
