import { useEffect, useState, type ReactNode } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useParams,
  useSearchParams,
} from "react-router-dom";
import type {
  ChangeCard,
  DocketIndex,
  EvalReport,
  InsightFinding,
  InsightPriorityCard,
  InsightReport,
  PreambleLink,
  Report,
  SnapshotManifest,
} from "./models";
import {
  loadDocketIndex,
  loadEvalReport,
  loadInsightReport,
  loadManifest,
  loadReport,
  summarizeMetricBlock,
} from "./snapshot";

type LoadState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

const LINKED_FINDING_LIMIT = 5;
const ALIGNMENT_LEVEL_RANK: Record<string, number> = {
  high: 3,
  medium: 2,
  low: 1,
  none: 0,
};

const DOCKET_STORY_TITLES: Record<string, string> = {
  "EPA-HQ-OAR-2018-0225": "Good Neighbor Obligations for the 2008 Ozone NAAQS",
  "EPA-HQ-OAR-2020-0272": "Revised CSAPR Update for the 2008 Ozone NAAQS",
  "EPA-HQ-OAR-2020-0430": "Primary Copper Smelting NESHAP Reviews",
};

type CardSort = "priority" | "size";

interface CardInsightContext {
  priorityCard: InsightPriorityCard | null;
  linkedFindings: InsightFinding[];
  hasStalePriorityFindings: boolean;
}

interface CardDisplayMetrics {
  linkedComments: number;
  preambleLinks: number;
  priorityRank: number;
  priorityLabel: string;
  sizeRank: number;
  sizeLabel: string;
  changedTokens: number;
  isDocketProcess: boolean;
}

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

function linkedCommentCount(card: ChangeCard): number {
  const featureCount = card.alignment_signal?.features?.comment_count;
  if (typeof featureCount === "number" && Number.isFinite(featureCount)) {
    return featureCount;
  }

  return (card.related_clusters || []).reduce((sum, cluster) => {
    const count = cluster.comment_count;
    return typeof count === "number" && Number.isFinite(count) ? sum + count : sum;
  }, 0);
}

function alignmentScore(card: ChangeCard): number {
  const score = card.alignment_signal?.score;
  return typeof score === "number" && Number.isFinite(score) ? score : 0;
}

function alignmentLevelRank(card: ChangeCard): number {
  return ALIGNMENT_LEVEL_RANK[card.alignment_signal?.level || "none"] ?? 0;
}

function preambleLinkCount(card: ChangeCard): number {
  return (card.preamble_links || []).length;
}

function changedTokenCount(card: ChangeCard): number {
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

function isDocketProcessCard(card: ChangeCard): boolean {
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

function cardDisplayMetrics(card: ChangeCard): CardDisplayMetrics {
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

function isPrimaryCard(metrics: CardDisplayMetrics): boolean {
  return !metrics.isDocketProcess && metrics.priorityRank >= 2;
}

function normalizeCardSort(value: string | null): CardSort {
  return value === "size" ? "size" : "priority";
}

function compareCardsByDisplayMetrics(
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

function priorityChipClass(metrics: CardDisplayMetrics): string {
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

function sizeChipClass(metrics: CardDisplayMetrics): string {
  if (metrics.sizeRank >= 3) {
    return "chip-size-large";
  }
  if (metrics.sizeRank >= 2) {
    return "chip-size-moderate";
  }
  return "chip-size-minor";
}

function docketStoryTitle(docketId: string, fallback?: string): string {
  return DOCKET_STORY_TITLES[docketId] || fallback || docketId;
}

function findingEvidenceLine(finding: InsightFinding): string | null {
  const hasStructuredEvidence =
    Boolean(finding.evidence_section_title) ||
    Boolean(finding.evidence_card_id) ||
    typeof finding.evidence_cluster_comment_count === "number";

  if (hasStructuredEvidence) {
    const linkedChange = finding.evidence_section_title || finding.evidence_card_id || "linked change card";
    const parts = [`Top linked change: ${linkedChange}`];
    if (typeof finding.evidence_cluster_comment_count === "number") {
      const count = finding.evidence_cluster_comment_count;
      parts.push(`${count} theme comment${count === 1 ? "" : "s"} linked`);
    }
    return parts.join("; ");
  }

  return finding.evidence_note || null;
}

interface DiffPiece {
  text: string;
  kind: "unchanged" | "added" | "removed";
}

function tokenizeSnippet(text: string): string[] {
  return text.match(/\S+\s*/g) || [];
}

function diffSnippets(proposed: string, final: string): { proposed: DiffPiece[]; final: DiffPiece[] } {
  const proposedTokens = tokenizeSnippet(proposed);
  const finalTokens = tokenizeSnippet(final);
  const table = Array.from({ length: proposedTokens.length + 1 }, () =>
    Array.from({ length: finalTokens.length + 1 }, () => 0)
  );

  for (let i = proposedTokens.length - 1; i >= 0; i -= 1) {
    for (let j = finalTokens.length - 1; j >= 0; j -= 1) {
      table[i][j] =
        proposedTokens[i].trim() === finalTokens[j].trim()
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }

  const proposedPieces: DiffPiece[] = [];
  const finalPieces: DiffPiece[] = [];
  let i = 0;
  let j = 0;

  while (i < proposedTokens.length && j < finalTokens.length) {
    if (proposedTokens[i].trim() === finalTokens[j].trim()) {
      proposedPieces.push({ text: proposedTokens[i], kind: "unchanged" });
      finalPieces.push({ text: finalTokens[j], kind: "unchanged" });
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      proposedPieces.push({ text: proposedTokens[i], kind: "removed" });
      i += 1;
    } else {
      finalPieces.push({ text: finalTokens[j], kind: "added" });
      j += 1;
    }
  }

  while (i < proposedTokens.length) {
    proposedPieces.push({ text: proposedTokens[i], kind: "removed" });
    i += 1;
  }
  while (j < finalTokens.length) {
    finalPieces.push({ text: finalTokens[j], kind: "added" });
    j += 1;
  }

  return { proposed: proposedPieces, final: finalPieces };
}

function renderDiffPieces(pieces: DiffPiece[]): ReactNode {
  return pieces.map((piece, index) => {
    if (piece.kind === "added") {
      return (
        <ins key={`${piece.kind}-${index}`} className="diff-added">
          {piece.text}
        </ins>
      );
    }
    if (piece.kind === "removed") {
      return (
        <del key={`${piece.kind}-${index}`} className="diff-removed">
          {piece.text}
        </del>
      );
    }
    return <span key={`${piece.kind}-${index}`}>{piece.text}</span>;
  });
}

function ChangeSnippet({
  card,
  side,
  preview = false,
}: {
  card: ChangeCard;
  side: "proposed" | "final";
  preview?: boolean;
}) {
  const proposed = card.proposed_text_snippet || "";
  const final = card.final_text_snippet || "";
  const changeType = (card.change_type || "").toLowerCase();
  const className = `diff-text${preview ? " snippet-preview" : ""}`;

  if (changeType === "added" && side === "proposed" && !proposed.trim()) {
    return <p className="meta-line">No proposed text in this card</p>;
  }
  if (changeType === "removed" && side === "final" && !final.trim()) {
    return <p className="meta-line">No final text in this card</p>;
  }
  if (side === "proposed" && !proposed.trim()) {
    return <p className="meta-line">n/a</p>;
  }
  if (side === "final" && !final.trim()) {
    return <p className="meta-line">n/a</p>;
  }

  if (changeType === "added" && side === "final") {
    const addedPieces: DiffPiece[] = tokenizeSnippet(final).map((text) => ({ text, kind: "added" }));
    return <p className={className}>{renderDiffPieces(addedPieces)}</p>;
  }
  if (changeType === "removed" && side === "proposed") {
    const removedPieces: DiffPiece[] = tokenizeSnippet(proposed).map((text) => ({ text, kind: "removed" }));
    return <p className={className}>{renderDiffPieces(removedPieces)}</p>;
  }

  const diff = diffSnippets(proposed, final);
  return <p className={className}>{renderDiffPieces(side === "proposed" ? diff.proposed : diff.final)}</p>;
}

function AppChrome({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <Link className="brand" to="/">
            Rulemaking Engine
          </Link>
        </div>
      </header>
      <main>{children}</main>
    </div>
  );
}

function LoadingView({ label }: { label: string }) {
  return (
    <section className="panel loading-panel">
      <p className="eyebrow">Loading</p>
      <h1>{label}</h1>
      <p>Fetching the published snapshot...</p>
    </section>
  );
}

function ErrorView({ title, message }: { title: string; message: string }) {
  return (
    <section className="panel error-panel">
      <p className="eyebrow">Snapshot Error</p>
      <h1>{title}</h1>
      <p>{message}</p>
    </section>
  );
}

function InsightLoadingPanel({ title }: { title: string }) {
  return (
    <section className="panel insight-banner">
      <p className="eyebrow">Insight Report</p>
      <h2>{title}</h2>
      <p className="meta-line">Loading insight report...</p>
    </section>
  );
}

function HomePage() {
  const manifestState = useAsyncData<SnapshotManifest>(() => loadManifest(), []);
  const indexState = useAsyncData<DocketIndex>(() => loadDocketIndex(), []);
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
      <section className="hero panel">
        <p className="eyebrow">Docket Stories</p>
        <h1>Choose a docket</h1>
        <p className="lead">
          Start with a docket summary, review the top commenter themes, then inspect the priority change cards and
          evidence.
        </p>
        <p className="meta-line">Snapshot published {formatStamp(manifest.snapshot.published_at)}.</p>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Dockets</span>
            <strong>{manifest.snapshot.docket_count}</strong>
          </div>
          <div className="stat-card">
            <span>Change cards</span>
            <strong>{totalCards}</strong>
          </div>
          <div className="stat-card">
            <span>Comment themes</span>
            <strong>{totalCommentThemes}</strong>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Story Launcher</p>
            <h2>Choose a docket</h2>
          </div>
        </div>
        <div className="docket-grid">
          {docketIndex.dockets.map((docket) => {
            const insightState = insightPreviewStates[docket.docket_id] || { status: "loading" };
            const insightReport = insightState.status === "ready" ? insightState.data : null;
            const topFinding = insightReport?.top_findings.find((finding) => finding.card_ids.length > 0);
            const storyTitle = docketStoryTitle(docket.docket_id, docket.display_title);
            return (
              <Link
                key={docket.docket_id}
                className="docket-card story-card story-card-link"
                to={`/dockets/${docket.docket_id}`}
                aria-label={`Open ${storyTitle}`}
              >
                <div className="docket-card-header">
                  <div>
                    <p className="eyebrow">{docket.docket_id}</p>
                    <h3>{storyTitle}</h3>
                  </div>
                  <span className={`status-chip ${docket.insight_available ? "available" : "not_available"}`}>
                    {docket.insight_available ? "insights available" : "insights unavailable"}
                  </span>
                </div>

                {insightState.status === "loading" ? (
                  <p className="meta-line">Loading insight preview...</p>
                ) : insightReport ? (
                  <>
                    <p className="story-summary">{insightReport.executive_summary}</p>
                    {topFinding ? (
                      <div className="story-teaser">
                        <p className="eyebrow">Top commenter theme</p>
                        <h4>{topFinding.title}</h4>
                        <p>{topFinding.summary}</p>
                      </div>
                    ) : null}
                    <div className="story-teaser">
                      <p className="eyebrow">Where final text appears aligned</p>
                      <p>{insightReport.rule_story.where_final_text_aligned}</p>
                    </div>
                  </>
                ) : (
                  <p className="meta-line">No insight preview published for this docket yet.</p>
                )}

                <div className="story-meta">
                  <span>{docket.total_change_cards} change cards</span>
                  <span>{docket.total_clusters} comment themes</span>
                  <span>{docket.insight_available ? "insights available" : "insights unavailable"}</span>
                </div>
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
  const visibleTopFindings = insightReport
    ? insightReport.top_findings.filter((finding) => finding.card_ids.length > 0).slice(0, 5)
    : [];
  const changeType = searchParams.get("changeType") || "all";
  const signal = searchParams.get("signal") || "all";
  const clusterState = searchParams.get("clusterState") || "all";
  const clusterQuery = (searchParams.get("clusterQuery") || "").trim().toLowerCase();
  const cardSort = normalizeCardSort(searchParams.get("cardSort"));
  const cardMetrics = new Map(report.change_cards.map((card) => [card.card_id, cardDisplayMetrics(card)]));

  const filteredClusters = report.clusters.filter((cluster) => {
    const hasLabel = Boolean(cluster.label);
    const matchesState =
      clusterState === "all" ||
      (clusterState === "labeled" && hasLabel) ||
      (clusterState === "unlabeled" && !hasLabel);
    const haystack = [cluster.label || "", cluster.label_description || "", ...(cluster.top_keywords || [])]
      .join(" ")
      .toLowerCase();
    const matchesQuery = !clusterQuery || haystack.includes(clusterQuery);
    return matchesState && matchesQuery;
  });

  const filteredCards = report.change_cards
    .filter((card) => {
      const signalLevel = card.alignment_signal?.level || "none";
      const relatedClusters = card.related_clusters || [];
      const hasLabeledCluster = relatedClusters.some((cluster) => Boolean(cluster.label));
      const matchesClusterState =
        clusterState === "all" ||
        (clusterState === "labeled" && hasLabeledCluster) ||
        (clusterState === "unlabeled" && !hasLabeledCluster);
      return (
        (changeType === "all" || card.change_type === changeType) &&
        (signal === "all" || signalLevel === signal) &&
        matchesClusterState
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

  const changeTypes = Array.from(new Set(report.change_cards.map((card) => card.change_type).filter(Boolean)));
  const signalLevels = Array.from(
    new Set(report.change_cards.map((card) => card.alignment_signal?.level || "none").filter(Boolean))
  );

  function updateFilter(name: string, value: string) {
    const next = new URLSearchParams(searchParams);
    if (!value || value === "all") {
      next.delete(name);
    } else {
      next.set(name, value);
    }
    setSearchParams(next, { replace: true });
  }

  return (
    <AppChrome>
      <section className="hero panel">
        <p className="eyebrow">Docket</p>
        <h1>{report.docket_id}</h1>
        <p className="lead">Review the docket story, then inspect the priority changes and evidence links.</p>
        <p className="meta-line">Snapshot published {formatStamp(report.generated_at)}.</p>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Comments</span>
            <strong>{report.summary.total_comments}</strong>
          </div>
          <div className="stat-card">
            <span>Unique comments</span>
            <strong>{report.summary.total_canonical_comments}</strong>
          </div>
          <div className="stat-card">
            <span>Comment themes</span>
            <strong>{report.summary.total_clusters}</strong>
          </div>
          <div className="stat-card">
            <span>Comment-linked cards</span>
            <strong>{commentLinkedCardCount}</strong>
          </div>
          <div className="stat-card">
            <span>Total change cards</span>
            <strong>{report.summary.total_change_cards}</strong>
          </div>
        </div>
      </section>

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
      ) : null}

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Filters</p>
            <h2>Review priority changes</h2>
          </div>
        </div>
        <div className="filters">
          <label>
            Change type
            <select value={changeType} onChange={(event) => updateFilter("changeType", event.target.value)}>
              <option value="all">All</option>
              {changeTypes.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Signal
            <select value={signal} onChange={(event) => updateFilter("signal", event.target.value)}>
              <option value="all">All</option>
              {signalLevels.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Sort cards
            <select value={cardSort} onChange={(event) => updateFilter("cardSort", event.target.value)}>
              <option value="priority">Priority, then size</option>
              <option value="size">Largest change, then priority</option>
            </select>
          </label>
          <label>
            Comment theme state
            <select value={clusterState} onChange={(event) => updateFilter("clusterState", event.target.value)}>
              <option value="all">All</option>
              <option value="labeled">Labeled only</option>
              <option value="unlabeled">Unlabeled only</option>
            </select>
          </label>
          <label className="wide-filter">
            Comment theme search
            <input
              value={searchParams.get("clusterQuery") || ""}
              onChange={(event) => updateFilter("clusterQuery", event.target.value)}
              placeholder="Search labels, descriptions, or keywords"
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Priority Changes</p>
            <h2>{primaryCards.length} priority change{primaryCards.length === 1 ? "" : "s"} shown</h2>
            <p className="meta-line">
              Comment-linked regulatory changes appear first. Large no-comment changes and docket-process cards remain
              available below.
            </p>
          </div>
        </div>
        <div className="card-list">
          {primaryCards.map((card) => (
            <ChangeCardRow
              key={card.card_id}
              docketId={report.docket_id}
              card={card}
              metrics={cardMetrics.get(card.card_id)!}
            />
          ))}
          {filteredCards.length === 0 ? <p>No priority changes match the current filters.</p> : null}
          {filteredCards.length > 0 && primaryCards.length === 0 ? (
            <p>Only lower-signal or docket-process cards match the current filters.</p>
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
              {foldedCards.map((card) => (
                <ChangeCardRow
                  key={card.card_id}
                  docketId={report.docket_id}
                  card={card}
                  metrics={cardMetrics.get(card.card_id)!}
                />
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Comment Themes</p>
            <h2>{filteredClusters.length} comment themes</h2>
          </div>
        </div>
        <div className="cluster-list">
          {filteredClusters.map((cluster) => (
            <article key={cluster.cluster_id} className="cluster-card">
              <div className="cluster-header">
                <h3>{cluster.label || "Unlabeled comment theme"}</h3>
                <span className={`status-chip ${cluster.label ? "available" : "not_available"}`}>
                  {cluster.label ? "labeled" : "unlabeled"}
                </span>
              </div>
              <p>{cluster.label_description || "No local label description yet."}</p>
              <p className="meta-line">
                {cluster.canonical_count} unique arguments, {cluster.total_raw_comments} total submissions
              </p>
              <div className="keyword-row">
                {cluster.top_keywords.map((keyword) => (
                  <span key={keyword} className="keyword-pill">
                    {keyword}
                  </span>
                ))}
              </div>
            </article>
          ))}
          {filteredClusters.length === 0 ? <p>No comment themes match the current filters.</p> : null}
        </div>
      </section>

      <details className={`panel eval-banner ${evalReport.status}`}>
        <summary>Snapshot quality details</summary>
        <div className="quality-details">
          <h2>{evalReport.status === "available" ? "Blind/seed evaluation available" : "Evaluation not yet annotated"}</h2>
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
      </details>
    </AppChrome>
  );
}

function ChangeCardRow({
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
          <span className={`status-chip ${priorityChipClass(metrics)}`}>
            {metrics.priorityLabel}
          </span>
          <span className={`status-chip ${sizeChipClass(metrics)}`}>
            {metrics.sizeLabel}
          </span>
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

function FindingEvidenceLine({ finding }: { finding: InsightFinding }) {
  const line = findingEvidenceLine(finding);
  return line ? <p className="meta-line">{line}</p> : null;
}

function getCardInsightContext(
  insightReport: InsightReport | null,
  cardId: string
): CardInsightContext {
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

  // Fall back to reverse card references when a priority card is absent or points at findings not in this snapshot.
  return {
    priorityCard,
    linkedFindings: insightReport.top_findings.filter((finding) => finding.card_ids.includes(cardId)),
    hasStalePriorityFindings: Boolean(priorityCard?.finding_ids.length),
  };
}

function CardInsightPanel({
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
            <span className="status-chip">{priorityCard.change_type || "unknown"}</span>
          </div>
        ) : null}
      </div>

      {priorityCard ? (
        <p className="meta-line">Priority card section: {priorityCard.section_title || "Untitled section"}</p>
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

function preambleLinkKey(link: PreambleLink, index: number): string {
  const parts = [
    link.preamble_section_id,
    link.preamble_heading,
    link.link_type,
    link.relationship_label,
    typeof link.link_score === "number" ? String(link.link_score) : undefined,
  ].filter((part): part is string => Boolean(part));

  return parts.length > 0 ? parts.join("|") : `link-${index}`;
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
  const { priorityCard, linkedFindings, hasStalePriorityFindings } = getCardInsightContext(insightReport, cardId);
  const findingClusterIds = new Set(linkedFindings.flatMap((finding) => finding.cluster_ids));
  const detailMetrics = cardDisplayMetrics(card);
  const preambleLinks = card.preamble_links || [];

  return (
    <AppChrome>
      <section className="panel">
        <Link className="back-link" to={`/dockets/${docketId}`}>
          Back to {docketId}
        </Link>
        <p className="eyebrow">{card.card_id}</p>
        <h1>{card.final_heading || card.proposed_heading || "Untitled section"}</h1>
        <div className="chip-row">
          <span className={`status-chip ${priorityChipClass(detailMetrics)}`}>
            {detailMetrics.priorityLabel}
          </span>
          <span className={`status-chip ${sizeChipClass(detailMetrics)}`}>
            {detailMetrics.sizeLabel}
          </span>
          <span className="status-chip available">{card.change_type || "unknown"}</span>
          <span className={`status-chip ${detailMetrics.linkedComments > 0 ? "available" : "not_available"}`}>
            {detailMetrics.linkedComments > 0
              ? `${detailMetrics.linkedComments} linked comments`
              : "No linked comments"}
          </span>
        </div>
      </section>

      {insightState.status === "loading" ? (
        <InsightLoadingPanel title="Loading Card Insight" />
      ) : (
        <CardInsightPanel
          insightReport={insightReport}
          priorityCard={priorityCard}
          linkedFindings={linkedFindings}
          hasStalePriorityFindings={hasStalePriorityFindings}
        />
      )}

      <section className="panel detail-grid">
        <div>
          <p className="eyebrow">Proposed text</p>
          <ChangeSnippet card={card} side="proposed" />
        </div>
        <div>
          <p className="eyebrow">Final text</p>
          <ChangeSnippet card={card} side="final" />
        </div>
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
          {(card.related_clusters || []).length === 0 ? (
            <p>No related comment themes recorded for this card.</p>
          ) : null}
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
                  {link.link_type || "unknown"} | score{" "}
                  {typeof link.link_score === "number" ? link.link_score : "n/a"}
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
