import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const snapshotMocks = vi.hoisted(() => ({
  loadManifest: vi.fn(),
  loadDocketIndex: vi.fn(),
  loadReport: vi.fn(),
  loadEvalReport: vi.fn(),
  loadInsightReport: vi.fn(),
}));

vi.mock("./snapshot", () => ({
  SNAPSHOT_BASE: "/site_data/current",
  loadManifest: snapshotMocks.loadManifest,
  loadDocketIndex: snapshotMocks.loadDocketIndex,
  loadReport: snapshotMocks.loadReport,
  loadEvalReport: snapshotMocks.loadEvalReport,
  loadInsightReport: snapshotMocks.loadInsightReport,
  summarizeMetricBlock: (metricBlock: Record<string, unknown> | undefined) =>
    metricBlock ? Object.keys(metricBlock).map((key) => `${key}: ${JSON.stringify(metricBlock[key])}`) : [],
}));

describe("App routes", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    snapshotMocks.loadManifest.mockReset();
    snapshotMocks.loadDocketIndex.mockReset();
    snapshotMocks.loadReport.mockReset();
    snapshotMocks.loadEvalReport.mockReset();
    snapshotMocks.loadInsightReport.mockReset();
    snapshotMocks.loadInsightReport.mockResolvedValue(null);
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
    snapshotMocks.loadInsightReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-07T12:00:00+00:00",
      generator: "generate_insights.py",
      executive_summary: "Test executive summary.",
      top_findings: [
        {
          finding_id: "finding-001",
          title: "Air Quality Standards",
          summary: "Commenters emphasized air quality standards.",
          why_it_matters: "1 associated card showed high comment alignment.",
          evidence_note: "One comment linked.",
          card_ids: ["card-1"],
          cluster_ids: ["cluster-1"],
        },
        {
          finding_id: "finding-002",
          title: "Attachment-Only File Submissions",
          summary: "Attachment-only filings had no linked regulatory changes.",
          why_it_matters: "No associated change cards showed elevated comment alignment.",
          evidence_note: "",
          card_ids: [],
          cluster_ids: ["cluster-2"],
        },
      ],
      rule_story: {
        what_changed: "1 section(s) modified across 1 change cards.",
        what_commenters_emphasized: "Commenters most frequently raised: Air Quality Standards (2 comments).",
        where_final_text_aligned: "1 change card(s) showed high comment alignment.",
        caveats: "Alignment signals indicate co-occurrence, not causation.",
      },
      priority_cards: [
        {
          card_id: "card-1",
          section_title: "Example heading",
          change_type: "modified",
          score: 2,
          alignment_level: "low",
          finding_ids: ["finding-001"],
        },
      ],
      provenance: {
        source_report: "outputs/EPA-HQ-OAR-2020-0430/report.json",
        source_eval_report: "outputs/EPA-HQ-OAR-2020-0430/eval_report.json",
        eval_available: false,
        report_schema_version: "v1",
        card_count: 1,
        cluster_count: 1,
        finding_count: 1,
      },
    });

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Evaluation not yet annotated/i)).toBeInTheDocument();
    expect(await screen.findByText("Test executive summary.")).toBeInTheDocument();
    expect(await screen.findByText("Air Quality Standards")).toBeInTheDocument();
    expect(await screen.findByText("1 change card")).toBeInTheDocument();
    expect(await screen.findByText("1 associated card showed high comment alignment.")).toBeInTheDocument();
    expect(screen.queryByText("Attachment-Only File Submissions")).toBeNull();
    expect(screen.getByText("What Changed")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /Read-only review surface/i, level: 2 })).toBeInTheDocument();
    expect(await screen.findByText(/Example cluster/i)).toBeInTheDocument();
  });

  it("renders docket page without insight panel when loadInsightReport returns null", async () => {
    snapshotMocks.loadReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-06T12:00:00+00:00",
      generator: "generate_outputs.py",
      summary: {
        total_comments: 22,
        total_canonical_comments: 14,
        total_clusters: 0,
        labeled_clusters: 0,
        total_change_cards: 0,
        change_type_counts: {},
        alignment_signal_counts: {},
        review_status_counts: {},
        labeling: { model: "qwen3:14b" },
      },
      clusters: [],
      change_cards: [],
    });
    snapshotMocks.loadEvalReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      evaluated_at: "2026-04-06T12:00:00+00:00",
      generator: "evaluate_pipeline.py",
      status: "not_available",
      reason: "no_gold_set",
    });
    snapshotMocks.loadInsightReport.mockResolvedValue(null);

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "EPA-HQ-OAR-2020-0430", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("Insight Report")).toBeNull();
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
    snapshotMocks.loadInsightReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-07T12:00:00+00:00",
      generator: "generate_insights.py",
      executive_summary: "Card detail insights.",
      top_findings: [
        {
          finding_id: "finding-001",
          title: "Primary Health Finding",
          summary: "Health-related comments aligned with the card.",
          why_it_matters: "This card is linked to health comments.",
          evidence_note: "Top linked change card: After (card-99); 2 comments from this theme linked to the card.",
          card_ids: ["card-99"],
          cluster_ids: ["cluster-7"],
        },
        {
          finding_id: "finding-002",
          title: "Second Finding",
          summary: "Second finding summary.",
          why_it_matters: "Second finding context.",
          evidence_note: "Second cluster-specific evidence.",
          card_ids: ["card-99"],
          cluster_ids: ["cluster-8"],
        },
        {
          finding_id: "finding-003",
          title: "Third Finding",
          summary: "Third finding summary.",
          why_it_matters: "Third finding context.",
          evidence_note: "Third cluster-specific evidence.",
          card_ids: ["card-99"],
          cluster_ids: ["cluster-9"],
        },
        {
          finding_id: "finding-004",
          title: "Fourth Finding",
          summary: "Fourth finding summary.",
          why_it_matters: "Fourth finding context.",
          evidence_note: "Fourth cluster-specific evidence.",
          card_ids: ["card-99"],
          cluster_ids: ["cluster-10"],
        },
        {
          finding_id: "finding-005",
          title: "Fifth Finding",
          summary: "Fifth finding summary.",
          why_it_matters: "Fifth finding context.",
          evidence_note: "Fifth cluster-specific evidence.",
          card_ids: ["card-99"],
          cluster_ids: ["cluster-11"],
        },
        {
          finding_id: "finding-006",
          title: "Sixth Hidden Finding",
          summary: "Sixth finding summary.",
          why_it_matters: "Sixth finding context.",
          evidence_note: "Sixth cluster-specific evidence.",
          card_ids: ["card-99"],
          cluster_ids: ["cluster-12"],
        },
      ],
      rule_story: {
        what_changed: "1 section added.",
        what_commenters_emphasized: "Commenters emphasized health impacts.",
        where_final_text_aligned: "1 change card showed medium comment alignment.",
        caveats: "Alignment signals indicate co-occurrence, not causation.",
      },
      priority_cards: [
        {
          card_id: "card-99",
          section_title: "After",
          change_type: "added",
          score: 88,
          alignment_level: "medium",
          finding_ids: [
            "finding-001",
            "finding-002",
            "finding-003",
            "finding-004",
            "finding-005",
            "finding-006",
          ],
        },
      ],
      provenance: {
        source_report: "outputs/EPA-HQ-OAR-2020-0430/report.json",
        source_eval_report: null,
        eval_available: false,
        report_schema_version: "v1",
        card_count: 1,
        cluster_count: 1,
        finding_count: 6,
      },
    });

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-99"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /Why This Card Matters/i })).toBeInTheDocument();
    expect(await screen.findByText("score 88")).toBeInTheDocument();
    expect(await screen.findByText("Primary Health Finding")).toBeInTheDocument();
    expect(await screen.findByText(/2 comments from this theme linked to the card/i)).toBeInTheDocument();
    expect(await screen.findByText("1 more linked finding not shown.")).toBeInTheDocument();
    expect(screen.queryByText("Sixth Hidden Finding")).toBeNull();
    expect(await screen.findByText(/Evidence note/i)).toBeInTheDocument();
    expect((await screen.findAllByText(/Health impacts/i)).length).toBeGreaterThan(0);
    expect(await screen.findByText("linked finding")).toBeInTheDocument();
    expect(await screen.findByText(/Response to comments/i)).toBeInTheDocument();
  });

  it("renders a deep-linked card detail page without an insight report", async () => {
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
          card_id: "card-100",
          change_type: "modified",
          proposed_heading: "Existing section",
          final_heading: "Updated section",
          proposed_text_snippet: "Existing text",
          final_text_snippet: "Updated text",
          alignment_signal: { level: "low", evidence_note: "Older snapshot evidence." },
          related_clusters: [{ cluster_id: "cluster-10", label: "Cost impacts", comment_count: 1 }],
          preamble_links: [{ preamble_heading: "Preamble cost response", link_type: "citation", link_score: 1 }],
          review_status: "pending",
        },
      ],
    });
    snapshotMocks.loadInsightReport.mockResolvedValue(null);

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-100"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Evidence note/i)).toBeInTheDocument();
    expect(await screen.findByText("Older snapshot evidence.")).toBeInTheDocument();
    expect(await screen.findByText(/Cost impacts/i)).toBeInTheDocument();
    expect(await screen.findByText(/Preamble cost response/i)).toBeInTheDocument();
    expect(screen.queryByText(/Why This Card Matters/i)).toBeNull();
  });
});
