import { Navigate, useParams, useSearchParams } from "react-router-dom";
import { AppChrome } from "../components/AppChrome";
import { Breadcrumb } from "../components/Breadcrumb";
import {
  cardDisplayMetrics,
  changeTypeLabel,
  priorityChipClass,
  sizeChipClass,
} from "../components/ChangeCardRow";
import { CardInsightPanel, getCardInsightContext, preambleLinkKey } from "../components/CardInsightPanel";
import { ErrorView } from "../components/ErrorView";
import {
  cardChangeSynopsis,
  diffModeToSearchParam,
  normalizeDiffMode,
  type DiffMode,
  InlineDiff,
} from "../components/InlineDiff";
import { InsightLoadingPanel, LoadingView } from "../components/LoadingView";
import { useAsyncData } from "../hooks/useAsyncData";
import type { InsightReport, Report } from "../models";
import { loadInsightReport, loadReport } from "../snapshot";

export default function CardDetailPage() {
  const params = useParams<{ docketId: string; cardId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const docketId = params.docketId ?? "";
  const cardId = params.cardId ?? "";
  const reportState = useAsyncData<Report>(() => loadReport(docketId), [docketId]);
  const insightState = useAsyncData<InsightReport | null>(() => loadInsightReport(docketId), [docketId]);
  const diffMode = normalizeDiffMode(searchParams.get("diffMode"));

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
  const setDiffMode = (value: DiffMode) => {
    const next = new URLSearchParams(searchParams);
    const searchValue = diffModeToSearchParam(value);
    if (!searchValue) {
      next.delete("diffMode");
    } else {
      next.set("diffMode", searchValue);
    }
    setSearchParams(next, { replace: true });
  };

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
            <span className="status-chip chip-comment-count">
              {detailMetrics.linkedComments} comment{detailMetrics.linkedComments === 1 ? "" : "s"}
            </span>
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
        <InlineDiff card={card} synopsis={detailSynopsis} initialMode={diffMode} onModeChange={setDiffMode} />
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
