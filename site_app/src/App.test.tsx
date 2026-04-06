import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const snapshotMocks = vi.hoisted(() => ({
  loadManifest: vi.fn(),
  loadDocketIndex: vi.fn(),
  loadReport: vi.fn(),
  loadEvalReport: vi.fn(),
}));

vi.mock("./snapshot", () => ({
  SNAPSHOT_BASE: "/site_data/current",
  loadManifest: snapshotMocks.loadManifest,
  loadDocketIndex: snapshotMocks.loadDocketIndex,
  loadReport: snapshotMocks.loadReport,
  loadEvalReport: snapshotMocks.loadEvalReport,
  summarizeMetricBlock: (metricBlock: Record<string, unknown> | undefined) =>
    metricBlock ? Object.keys(metricBlock).map((key) => `${key}: ${JSON.stringify(metricBlock[key])}`) : [],
}));

describe("App routes", () => {
  beforeEach(() => {
    snapshotMocks.loadManifest.mockReset();
    snapshotMocks.loadDocketIndex.mockReset();
    snapshotMocks.loadReport.mockReset();
    snapshotMocks.loadEvalReport.mockReset();
  });

  it("renders the landing page", async () => {
    snapshotMocks.loadManifest.mockResolvedValue({
      schema_version: "v1",
      snapshot: {
        release_id: "20260406T120000Z",
        published_at: "2026-04-06T12:00:00+00:00",
        docket_count: 1,
      },
      release_id: "20260406T120000Z",
      published_at: "2026-04-06T12:00:00+00:00",
      docket_count: 1,
      dockets: [],
    });
    snapshotMocks.loadDocketIndex.mockResolvedValue({
      schema_version: "v1",
      snapshot: {
        release_id: "20260406T120000Z",
        published_at: "2026-04-06T12:00:00+00:00",
        docket_count: 1,
      },
      release_id: "20260406T120000Z",
      published_at: "2026-04-06T12:00:00+00:00",
      dockets: [
        {
          docket_id: "EPA-HQ-OAR-2020-0430",
          display_title: "EPA-HQ-OAR-2020-0430",
          report_path: "dockets/EPA-HQ-OAR-2020-0430/report.json",
          eval_report_path: "dockets/EPA-HQ-OAR-2020-0430/eval_report.json",
          latest_publish_at: "2026-04-06T12:00:00+00:00",
          evaluation_status: "not_available",
          evaluation_available: false,
          total_clusters: 12,
          total_change_cards: 146,
          labeled_clusters: 12,
          change_type_counts: {},
          alignment_signal_counts: {},
          review_status_counts: {},
          labeling: { model: "qwen3:14b" },
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Published starter set/i)).toBeInTheDocument();
    expect(await screen.findByText(/Open docket/i)).toBeInTheDocument();
  });

  it("renders the docket page with unavailable evaluation messaging", async () => {
    snapshotMocks.loadReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-06T12:00:00+00:00",
      generator: "generate_outputs.py",
      summary: {
        total_comments: 22,
        total_canonical_comments: 14,
        total_clusters: 2,
        labeled_clusters: 2,
        total_change_cards: 1,
        change_type_counts: { modified: 1 },
        alignment_signal_counts: { low: 1 },
        review_status_counts: { pending: 1 },
        labeling: { model: "qwen3:14b" },
      },
      clusters: [
        {
          cluster_id: "cluster-1",
          label: "Example cluster",
          label_description: "Example description.",
          canonical_count: 2,
          total_raw_comments: 3,
          top_keywords: ["ozone"],
          commenter_type_distribution: { individual: 2 },
        },
      ],
      change_cards: [
        {
          card_id: "card-1",
          change_type: "modified",
          final_heading: "Example heading",
          proposed_text_snippet: "Old text",
          final_text_snippet: "New text",
          alignment_signal: { level: "low", evidence_note: "One comment linked." },
          related_clusters: [{ cluster_id: "cluster-1", label: "Example cluster", comment_count: 1 }],
          preamble_links: [],
          review_status: "pending",
        },
      ],
    });
    snapshotMocks.loadEvalReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      evaluated_at: "2026-04-06T12:00:00+00:00",
      generator: "evaluate_pipeline.py",
      status: "not_available",
      reason: "no_gold_set",
    });

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Evaluation not yet annotated/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /Read-only review surface/i, level: 2 })).toBeInTheDocument();
    expect(await screen.findByText(/Example cluster/i)).toBeInTheDocument();
  });

  it("applies docket filters from the URL", async () => {
    snapshotMocks.loadReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-06T12:00:00+00:00",
      generator: "generate_outputs.py",
      summary: {
        total_comments: 22,
        total_canonical_comments: 14,
        total_clusters: 2,
        labeled_clusters: 1,
        total_change_cards: 2,
        change_type_counts: { modified: 1, added: 1 },
        alignment_signal_counts: { high: 1, low: 1 },
        review_status_counts: { pending: 1, confirmed: 1 },
      },
      clusters: [
        {
          cluster_id: "cluster-1",
          label: "Health impacts",
          label_description: "Health concerns",
          canonical_count: 2,
          total_raw_comments: 2,
          top_keywords: ["health"],
          commenter_type_distribution: { individual: 2 },
        },
        {
          cluster_id: "cluster-2",
          label: null,
          label_description: null,
          canonical_count: 1,
          total_raw_comments: 1,
          top_keywords: ["cost"],
          commenter_type_distribution: { business: 1 },
        },
      ],
      change_cards: [
        {
          card_id: "card-1",
          change_type: "modified",
          final_heading: "Health heading",
          proposed_text_snippet: "Old text",
          final_text_snippet: "New text",
          alignment_signal: { level: "high", evidence_note: "Visible card" },
          related_clusters: [{ cluster_id: "cluster-1", label: "Health impacts", comment_count: 1 }],
          preamble_links: [],
          review_status: "confirmed",
        },
        {
          card_id: "card-2",
          change_type: "added",
          final_heading: "Cost heading",
          proposed_text_snippet: "Old cost text",
          final_text_snippet: "New cost text",
          alignment_signal: { level: "low", evidence_note: "Filtered out" },
          related_clusters: [{ cluster_id: "cluster-2", label: null, comment_count: 1 }],
          preamble_links: [],
          review_status: "pending",
        },
      ],
    });
    snapshotMocks.loadEvalReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      evaluated_at: "2026-04-06T12:00:00+00:00",
      generator: "evaluate_pipeline.py",
      status: "not_available",
      reason: "no_gold_set",
    });

    render(
      <MemoryRouter
        initialEntries={[
          "/dockets/EPA-HQ-OAR-2020-0430?changeType=modified&signal=high&reviewStatus=confirmed&clusterState=labeled&clusterQuery=health",
        ]}
      >
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Health heading/i)).toBeInTheDocument();
    expect(screen.queryByText(/Cost heading/i)).not.toBeInTheDocument();
    expect(await screen.findByText(/Health impacts/i)).toBeInTheDocument();
  });

  it("renders a deep-linked card detail page", async () => {
    snapshotMocks.loadReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-06T12:00:00+00:00",
      generator: "generate_outputs.py",
      summary: {
        total_comments: 22,
        total_canonical_comments: 14,
        total_clusters: 1,
        labeled_clusters: 1,
        total_change_cards: 1,
        change_type_counts: {},
        alignment_signal_counts: {},
        review_status_counts: {},
      },
      clusters: [],
      change_cards: [
        {
          card_id: "card-99",
          change_type: "added",
          proposed_heading: "Before",
          final_heading: "After",
          proposed_text_snippet: "Before text",
          final_text_snippet: "After text",
          alignment_signal: { level: "medium", evidence_note: "Two comments and one preamble link." },
          related_clusters: [{ cluster_id: "cluster-7", label: "Health impacts", comment_count: 2 }],
          preamble_links: [{ preamble_heading: "Response to comments", link_type: "citation", link_score: 1 }],
          review_status: "pending",
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-99"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Evidence note/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/Health impacts/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText(/Response to comments/i)).toBeInTheDocument();
  });
});
