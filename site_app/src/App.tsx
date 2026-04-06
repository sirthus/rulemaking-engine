import { useEffect, useState, type ReactNode } from "react";
import {
  Link,
  Navigate,
  Route,
  Routes,
  useParams,
  useSearchParams,
} from "react-router-dom";
import type { ChangeCard, DocketIndex, EvalReport, Report, SnapshotManifest } from "./models";
import { loadDocketIndex, loadEvalReport, loadManifest, loadReport, summarizeMetricBlock } from "./snapshot";

type LoadState<T> =
  | { status: "loading" }
  | { status: "error"; error: string }
  | { status: "ready"; data: T };

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

function AppChrome({ children }: { children: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Local Batch Snapshot</p>
          <Link className="brand" to="/">
            Rulemaking Engine
          </Link>
        </div>
        <p className="topbar-note">Read-only React site powered by published JSON snapshots.</p>
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

function HomePage() {
  const manifestState = useAsyncData<SnapshotManifest>(() => loadManifest(), []);
  const indexState = useAsyncData<DocketIndex>(() => loadDocketIndex(), []);

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
  const totalClusters = docketIndex.dockets.reduce((sum, docket) => sum + docket.total_clusters, 0);

  return (
    <AppChrome>
      <section className="hero panel">
        <p className="eyebrow">Published Snapshot</p>
        <h1>Traceable rule changes, local-only LLM batches, and a read-only review surface.</h1>
        <p className="lead">
          This site reads only from <code>site_data/current/</code>. No browser actions invoke a model.
        </p>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Release</span>
            <strong>{manifest.snapshot.release_id}</strong>
          </div>
          <div className="stat-card">
            <span>Published</span>
            <strong>{formatStamp(manifest.snapshot.published_at)}</strong>
          </div>
          <div className="stat-card">
            <span>Dockets</span>
            <strong>{manifest.snapshot.docket_count}</strong>
          </div>
          <div className="stat-card">
            <span>Change cards</span>
            <strong>{totalCards}</strong>
          </div>
          <div className="stat-card">
            <span>Clusters</span>
            <strong>{totalClusters}</strong>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Dockets</p>
            <h2>Published starter set</h2>
          </div>
        </div>
        <div className="docket-grid">
          {docketIndex.dockets.map((docket) => (
            <article key={docket.docket_id} className="docket-card">
              <div className="docket-card-header">
                <p className="eyebrow">{docket.docket_id}</p>
                <h3>{docket.display_title}</h3>
              </div>
              <p className={`status-chip ${docket.evaluation_status}`}>
                Evaluation: {docket.evaluation_status === "available" ? "available" : "not yet annotated"}
              </p>
              <dl className="inline-stats">
                <div>
                  <dt>Cards</dt>
                  <dd>{docket.total_change_cards}</dd>
                </div>
                <div>
                  <dt>Clusters</dt>
                  <dd>{docket.total_clusters}</dd>
                </div>
                <div>
                  <dt>Labeled</dt>
                  <dd>{docket.labeled_clusters}</dd>
                </div>
              </dl>
              <p className="meta-line">
                Labeling model: <strong>{docket.labeling.model || "n/a"}</strong>
              </p>
              <p className="meta-line">Published {formatStamp(docket.latest_publish_at)}</p>
              <Link className="action-link" to={`/dockets/${docket.docket_id}`}>
                Open docket
              </Link>
            </article>
          ))}
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
  const [searchParams, setSearchParams] = useSearchParams();

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
  const changeType = searchParams.get("changeType") || "all";
  const signal = searchParams.get("signal") || "all";
  const reviewStatus = searchParams.get("reviewStatus") || "all";
  const clusterState = searchParams.get("clusterState") || "all";
  const clusterQuery = (searchParams.get("clusterQuery") || "").trim().toLowerCase();

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

  const filteredCards = report.change_cards.filter((card) => {
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
      (reviewStatus === "all" || (card.review_status || "pending") === reviewStatus) &&
      matchesClusterState
    );
  });

  const changeTypes = Array.from(new Set(report.change_cards.map((card) => card.change_type).filter(Boolean)));
  const signalLevels = Array.from(
    new Set(report.change_cards.map((card) => card.alignment_signal?.level || "none").filter(Boolean))
  );
  const reviewStatuses = Array.from(
    new Set(report.change_cards.map((card) => card.review_status || "pending").filter(Boolean))
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
        <p className="eyebrow">{report.docket_id}</p>
        <h1>{report.docket_id}</h1>
        <p className="lead">Published {formatStamp(report.generated_at)} from the local artifact pipeline.</p>
        <div className="stat-grid">
          <div className="stat-card">
            <span>Comments</span>
            <strong>{report.summary.total_comments}</strong>
          </div>
          <div className="stat-card">
            <span>Canonical</span>
            <strong>{report.summary.total_canonical_comments}</strong>
          </div>
          <div className="stat-card">
            <span>Clusters</span>
            <strong>{report.summary.total_clusters}</strong>
          </div>
          <div className="stat-card">
            <span>Change cards</span>
            <strong>{report.summary.total_change_cards}</strong>
          </div>
          <div className="stat-card">
            <span>Label model</span>
            <strong>{report.summary.labeling?.model || "n/a"}</strong>
          </div>
        </div>
      </section>

      <section className={`panel eval-banner ${evalReport.status}`}>
        <div>
          <p className="eyebrow">Evaluation</p>
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
        </div>
        {evalReport.status === "available" ? (
          <ul className="metric-list">
            {summarizeMetricBlock(evalReport.alignment_metrics).slice(0, 3).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
        ) : null}
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Filters</p>
            <h2>Read-only review surface</h2>
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
            Review status
            <select value={reviewStatus} onChange={(event) => updateFilter("reviewStatus", event.target.value)}>
              <option value="all">All</option>
              {reviewStatuses.map((value) => (
                <option key={value} value={value}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Cluster state
            <select value={clusterState} onChange={(event) => updateFilter("clusterState", event.target.value)}>
              <option value="all">All</option>
              <option value="labeled">Labeled only</option>
              <option value="unlabeled">Unlabeled only</option>
            </select>
          </label>
          <label className="wide-filter">
            Cluster search
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
            <p className="eyebrow">Clusters</p>
            <h2>{filteredClusters.length} theme clusters</h2>
          </div>
        </div>
        <div className="cluster-list">
          {filteredClusters.map((cluster) => (
            <article key={cluster.cluster_id} className="cluster-card">
              <div className="cluster-header">
                <h3>{cluster.label || "Unlabeled cluster"}</h3>
                <span className={`status-chip ${cluster.label ? "available" : "not_available"}`}>
                  {cluster.label ? "labeled" : "unlabeled"}
                </span>
              </div>
              <p>{cluster.label_description || "No local label description yet."}</p>
              <p className="meta-line">
                {cluster.canonical_count} canonical arguments, {cluster.total_raw_comments} total submissions
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
          {filteredClusters.length === 0 ? <p>No clusters match the current filters.</p> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Change Cards</p>
            <h2>{filteredCards.length} cards in view</h2>
          </div>
        </div>
        <div className="card-list">
          {filteredCards.map((card) => (
            <ChangeCardRow key={card.card_id} docketId={report.docket_id} card={card} />
          ))}
          {filteredCards.length === 0 ? <p>No change cards match the current filters.</p> : null}
        </div>
      </section>
    </AppChrome>
  );
}

function ChangeCardRow({ docketId, card }: { docketId: string; card: ChangeCard }) {
  return (
    <article className="change-card">
      <div className="change-card-header">
        <div>
          <p className="eyebrow">{card.card_id}</p>
          <h3>{card.final_heading || card.proposed_heading || "Untitled section"}</h3>
        </div>
        <div className="chip-row">
          <span className="status-chip available">{card.change_type || "unknown"}</span>
          <span className="status-chip">{card.alignment_signal?.level || "none"}</span>
          <span className="status-chip">{card.review_status || "pending"}</span>
        </div>
      </div>
      <p className="meta-line">{card.alignment_signal?.evidence_note || "No evidence note available."}</p>
      <div className="card-grid">
        <div>
          <h4>Proposed</h4>
          <p>{card.proposed_text_snippet || "n/a"}</p>
        </div>
        <div>
          <h4>Final</h4>
          <p>{card.final_text_snippet || "n/a"}</p>
        </div>
      </div>
      <p className="meta-line">
        Related clusters: {(card.related_clusters || []).length} | Preamble links: {(card.preamble_links || []).length}
      </p>
      <Link className="action-link" to={`/dockets/${docketId}/cards/${card.card_id}`}>
        Open card detail
      </Link>
    </article>
  );
}

function CardDetailPage() {
  const params = useParams<{ docketId: string; cardId: string }>();
  const docketId = params.docketId ?? "";
  const cardId = params.cardId ?? "";
  const reportState = useAsyncData<Report>(() => loadReport(docketId), [docketId]);

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

  return (
    <AppChrome>
      <section className="panel">
        <Link className="back-link" to={`/dockets/${docketId}`}>
          Back to {docketId}
        </Link>
        <p className="eyebrow">{card.card_id}</p>
        <h1>{card.final_heading || card.proposed_heading || "Untitled section"}</h1>
        <div className="chip-row">
          <span className="status-chip available">{card.change_type || "unknown"}</span>
          <span className="status-chip">{card.alignment_signal?.level || "none"}</span>
          <span className="status-chip">{card.review_status || "pending"}</span>
        </div>
      </section>

      <section className="panel detail-grid">
        <div>
          <p className="eyebrow">Proposed text</p>
          <p>{card.proposed_text_snippet || "n/a"}</p>
        </div>
        <div>
          <p className="eyebrow">Final text</p>
          <p>{card.final_text_snippet || "n/a"}</p>
        </div>
      </section>

      <section className="panel">
        <p className="eyebrow">Evidence note</p>
        <p>{card.alignment_signal?.evidence_note || "No evidence note available."}</p>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Related clusters</p>
            <h2>{(card.related_clusters || []).length} linked clusters</h2>
          </div>
        </div>
        <div className="cluster-list">
          {(card.related_clusters || []).map((cluster) => (
            <article key={cluster.cluster_id} className="cluster-card">
              <h3>{cluster.label || cluster.cluster_id}</h3>
              <p>{cluster.label_description || "No label description available."}</p>
              <p className="meta-line">Comments linked: {cluster.comment_count || 0}</p>
            </article>
          ))}
          {(card.related_clusters || []).length === 0 ? <p>No related clusters recorded for this card.</p> : null}
        </div>
      </section>

      <section className="panel">
        <div className="section-header">
          <div>
            <p className="eyebrow">Preamble links</p>
            <h2>{(card.preamble_links || []).length} linked sections</h2>
          </div>
        </div>
        <div className="cluster-list">
          {(card.preamble_links || []).map((link, index) => (
            <article key={`${link.preamble_section_id || "link"}-${index}`} className="cluster-card">
              <h3>{link.preamble_heading || link.preamble_section_id || "Preamble section"}</h3>
              <p>{link.relationship_label || "No relationship label recorded."}</p>
              <p className="meta-line">
                {link.link_type || "unknown"} | score {typeof link.link_score === "number" ? link.link_score : "n/a"}
              </p>
            </article>
          ))}
          {(card.preamble_links || []).length === 0 ? <p>No preamble links recorded for this card.</p> : null}
        </div>
      </section>
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
