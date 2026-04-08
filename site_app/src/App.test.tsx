import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
          insight_report_path: "dockets/EPA-HQ-OAR-2020-0430/insight_report.json",
          insight_available: true,
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
    snapshotMocks.loadInsightReport.mockResolvedValue({
      schema_version: "v1",
      docket_id: "EPA-HQ-OAR-2020-0430",
      generated_at: "2026-04-07T12:00:00+00:00",
      generator: "generate_insights.py",
      executive_summary: "Home executive summary.",
      top_findings: [
        {
          finding_id: "finding-001",
          title: "Home Top Theme",
          summary: "Home top finding summary.",
          why_it_matters: "Home top finding matters.",
          evidence_note: "Home evidence note.",
          card_ids: ["card-1"],
          cluster_ids: ["cluster-1"],
        },
      ],
      rule_story: {
        what_changed: "Home change story.",
        what_commenters_emphasized: "Home commenter theme.",
        where_final_text_aligned: "Home alignment headline.",
        caveats: "Alignment signals indicate co-occurrence, not causation.",
      },
      priority_cards: [],
      provenance: {
        source_report: "outputs/EPA-HQ-OAR-2020-0430/report.json",
        source_eval_report: null,
        eval_available: false,
        report_schema_version: "v1",
        card_count: 1,
        cluster_count: 1,
        finding_count: 1,
      },
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Choose a docket", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText(/Start with a docket summary/i)).toBeInTheDocument();
    expect(await screen.findByText("Home executive summary.")).toBeInTheDocument();
    expect(await screen.findByText("Home Top Theme")).toBeInTheDocument();
    expect(await screen.findByText("Top commenter theme")).toBeInTheDocument();
    expect(await screen.findByText("Home alignment headline.")).toBeInTheDocument();
    expect(await screen.findByText("Where final text appears aligned")).toBeInTheDocument();
    expect(await screen.findByText("12 comment themes")).toBeInTheDocument();
    expect(await screen.findByText("Primary Copper Smelting NESHAP Reviews")).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: /Open Primary Copper Smelting NESHAP Reviews/i })
    ).toHaveAttribute("href", "/dockets/EPA-HQ-OAR-2020-0430");
    expect(screen.queryByText(/Open docket story/i)).toBeNull();
    expect(screen.queryByText("Local Batch Snapshot")).toBeNull();
    expect(screen.queryByText(/Read-only React site powered/i)).toBeNull();
    expect(screen.queryByText(/^Release$/i)).toBeNull();
  });

  it("renders the landing page when an insight preview is unavailable", async () => {
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
          insight_report_path: null,
          insight_available: false,
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
    snapshotMocks.loadInsightReport.mockResolvedValue(null);

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("No insight preview published for this docket yet.")).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: /Open Primary Copper Smelting NESHAP Reviews/i })
    ).toHaveAttribute("href", "/dockets/EPA-HQ-OAR-2020-0430");
    expect(screen.queryByText(/Open docket story/i)).toBeNull();
  });

  it("renders the landing page while an insight preview is loading", async () => {
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
          insight_report_path: "dockets/EPA-HQ-OAR-2020-0430/insight_report.json",
          insight_available: true,
          latest_publish_at: "2026-04-06T12:00:00+00:00",
          evaluation_status: "available",
          evaluation_available: true,
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
    snapshotMocks.loadInsightReport.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Choose a docket", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("Loading insight preview...")).toBeInTheDocument();
    expect(
      await screen.findByRole("link", { name: /Open Primary Copper Smelting NESHAP Reviews/i })
    ).toHaveAttribute("href", "/dockets/EPA-HQ-OAR-2020-0430");
    expect(screen.queryByText(/Open docket story/i)).toBeNull();
  });

  it("renders the docket page with unavailable evaluation messaging", async () => {
    const user = userEvent.setup();
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
        total_change_cards: 5,
        change_type_counts: { modified: 1 },
        alignment_signal_counts: { high: 1, low: 1 },
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
          proposed_text_snippet: "Old text stays",
          final_text_snippet: "New text stays",
          alignment_signal: {
            level: "high",
            score: 1,
            evidence_note: "One comment linked.",
            features: { comment_count: 2 },
          },
          related_clusters: [{ cluster_id: "cluster-1", label: "Example cluster", comment_count: 2 }],
          preamble_links: [],
          review_status: "pending",
        },
        {
          card_id: "card-4",
          change_type: "modified",
          final_heading: "Large linked heading",
          proposed_text_snippet: "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
          final_text_snippet: "nu xi omicron pi rho sigma tau upsilon phi chi psi omega",
          alignment_signal: {
            level: "low",
            score: 2,
            evidence_note: "Two comments linked to a larger regulatory text change.",
            features: { comment_count: 2 },
          },
          related_clusters: [{ cluster_id: "cluster-1", label: "Example cluster", comment_count: 2 }],
          preamble_links: [],
          review_status: "pending",
        },
        {
          card_id: "card-3",
          change_type: "modified",
          final_heading: "Large no comment heading",
          proposed_text_snippet: "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu",
          final_text_snippet: "nu xi omicron pi rho sigma tau upsilon phi chi psi omega",
          alignment_signal: {
            level: "none",
            score: 0,
            evidence_note: "No comment evidence on a larger text change.",
            features: { comment_count: 0 },
          },
          related_clusters: [],
          preamble_links: [],
          review_status: "pending",
        },
        {
          card_id: "card-process",
          change_type: "removed",
          proposed_heading: "A. Written Comments",
          proposed_text_snippet:
            "Submit your comments at regulations.gov and review participation in virtual public hearing materials before the public hearing.",
          final_text_snippet: "",
          alignment_signal: {
            level: "high",
            score: 1000,
            evidence_note: "41 comments attributed to a procedural comment section.",
            features: { comment_count: 41 },
          },
          related_clusters: [{ cluster_id: "cluster-1", label: "Example cluster", comment_count: 41 }],
          preamble_links: [],
          review_status: "pending",
        },
        {
          card_id: "card-2",
          change_type: "modified",
          final_heading: "No comment heading",
          proposed_text_snippet: "No comment old text",
          final_text_snippet: "No comment new text",
          alignment_signal: {
            level: "high",
            score: 100,
            evidence_note: "No comment evidence.",
            features: { comment_count: 0 },
          },
          related_clusters: [],
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
          evidence_card_id: "card-1",
          evidence_section_title: "Example heading",
          evidence_card_score: 2,
          evidence_cluster_comment_count: 2,
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

    const { container } = render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Snapshot quality details/i)).toBeInTheDocument();
    expect(container.textContent).toContain("Evaluation not yet annotated");
    expect(await screen.findByText("Test executive summary.")).toBeInTheDocument();
    expect(await screen.findByText("Air Quality Standards")).toBeInTheDocument();
    expect(await screen.findByText("1 change card")).toBeInTheDocument();
    expect(await screen.findByText("1 associated card showed high comment alignment.")).toBeInTheDocument();
    expect(await screen.findByText("Top linked change: Example heading; 2 theme comments linked")).toBeInTheDocument();
    expect(screen.queryByText("score 2")).toBeNull();
    expect(screen.queryByText("Attachment-Only File Submissions")).toBeNull();
    expect(screen.getByText("What Changed")).toBeInTheDocument();
    expect(await screen.findByText("Unique comments")).toBeInTheDocument();
    expect(screen.queryByText("Canonical")).toBeNull();
    expect(screen.queryByText("Label model")).toBeNull();
    expect(await screen.findByRole("heading", { name: /Review priority changes/i, level: 2 })).toBeInTheDocument();
    expect(screen.queryByLabelText("Review status")).toBeNull();
    const priorityHeading = await screen.findByRole("heading", { name: /2 priority changes shown/i, level: 2 });
    const themeHeading = await screen.findByRole("heading", { name: /1 comment themes/i, level: 2 });
    expect(Boolean(priorityHeading.compareDocumentPosition(themeHeading) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    const commentLinkedCard = await screen.findByRole("heading", { name: "Example heading", level: 3 });
    const largeLinkedCard = await screen.findByRole("heading", { name: "Large linked heading", level: 3 });
    expect(Boolean(commentLinkedCard.compareDocumentPosition(largeLinkedCard) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(
      true
    );
    expect(screen.queryByRole("heading", { name: "Large no comment heading", level: 3 })).toBeNull();
    expect(screen.queryByRole("heading", { name: "No comment heading", level: 3 })).toBeNull();
    expect(screen.queryByRole("heading", { name: "A. Written Comments", level: 3 })).toBeNull();
    const foldButton = await screen.findByRole("button", { name: "Show 3 lower-signal and docket-process cards" });
    expect(Boolean(largeLinkedCard.compareDocumentPosition(foldButton) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    await user.selectOptions(await screen.findByLabelText("Sort cards"), "size");
    const sizeSortedLargeCard = await screen.findByRole("heading", { name: "Large linked heading", level: 3 });
    const sizeSortedCommentCard = await screen.findByRole("heading", { name: "Example heading", level: 3 });
    expect(
      Boolean(sizeSortedLargeCard.compareDocumentPosition(sizeSortedCommentCard) & Node.DOCUMENT_POSITION_FOLLOWING)
    ).toBe(true);
    const sizeSortedFoldButton = await screen.findByRole("button", {
      name: "Show 3 lower-signal and docket-process cards",
    });
    expect(
      Boolean(sizeSortedCommentCard.compareDocumentPosition(sizeSortedFoldButton) & Node.DOCUMENT_POSITION_FOLLOWING)
    ).toBe(true);
    await user.click(sizeSortedFoldButton);
    expect(await screen.findByText("Lower-signal and docket-process cards")).toBeInTheDocument();
    const foldedHeading = await screen.findByRole("heading", { name: "3 cards available", level: 3 });
    const hideFoldButton = await screen.findByRole("button", { name: "Hide lower-signal and docket-process cards" });
    expect(Boolean(hideFoldButton.compareDocumentPosition(foldedHeading) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(
      true
    );
    expect(await screen.findByRole("heading", { name: "Large no comment heading", level: 3 })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "No comment heading", level: 3 })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "A. Written Comments", level: 3 })).toBeInTheDocument();
    expect(await screen.findByText("Docket process")).toHaveClass("chip-priority-process");
    const rowChipTexts = Array.from(container.querySelectorAll(".change-card .status-chip")).map((node) =>
      node.textContent?.trim().toLowerCase()
    );
    expect(rowChipTexts).not.toContain("high");
    expect(rowChipTexts).not.toContain("pending");
    expect((await screen.findAllByText("2 linked comments")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("No linked comments")).length).toBeGreaterThan(0);
    expect(await screen.findByText("High priority")).toHaveClass("chip-priority-high");
    expect(await screen.findByText("Medium priority")).toHaveClass("chip-priority-medium");
    expect((await screen.findAllByText("Large change"))[0]).toHaveClass("chip-size-large");
    expect((await screen.findAllByText("Moderate change"))[0]).toHaveClass("chip-size-moderate");
    expect((await screen.findAllByText("Minor change"))[0]).toHaveClass("chip-size-minor");
    expect(screen.queryByText("Preamble links: 0")).toBeNull();
    expect(await screen.findByText(/Example cluster/i)).toBeInTheDocument();
    expect(Array.from(container.querySelectorAll("del.diff-removed")).some((node) => node.textContent === "Old ")).toBe(
      true
    );
    expect(Array.from(container.querySelectorAll("ins.diff-added")).some((node) => node.textContent === "New ")).toBe(
      true
    );
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
    expect(screen.queryByText(/Loading insight report/i)).toBeNull();
    expect(screen.queryByText("Insight Report")).toBeNull();
  });

  it("renders a docket insight loading placeholder while insight report is pending", async () => {
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
    snapshotMocks.loadInsightReport.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "EPA-HQ-OAR-2020-0430", level: 1 })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Loading Docket Analysis" })).toBeInTheDocument();
    expect(await screen.findByText(/Loading insight report/i)).toBeInTheDocument();
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
      status: "available",
      gold_set_provenance: {
        annotation_method: "llm_blind",
        annotator: "test-annotator",
        annotated_at: "2026-04-06T11:00:00+00:00",
      },
      alignment_metrics: { total_gold_alignments: 25 },
    });

    const { container } = render(
      <MemoryRouter
        initialEntries={[
          "/dockets/EPA-HQ-OAR-2020-0430?changeType=modified&signal=high&clusterState=labeled&clusterQuery=health",
        ]}
      >
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Health heading/i)).toBeInTheDocument();
    expect(screen.queryByText(/Cost heading/i)).not.toBeInTheDocument();
    expect(await screen.findByText(/Health impacts/i)).toBeInTheDocument();
    expect(await screen.findByText("Snapshot quality details")).toBeInTheDocument();
    expect(container.textContent).toContain("total_gold_alignments: 25");
  });

  it("renders a deep-linked card detail page", async () => {
    const user = userEvent.setup();
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
          proposed_text_snippet: "",
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
          evidence_card_id: "card-99",
          evidence_section_title: "After",
          evidence_card_score: 88,
          evidence_cluster_comment_count: 2,
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

    const { container } = render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-99"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: /Why This Card Matters/i })).toBeInTheDocument();
    expect(await screen.findByText("Card priority 88")).toBeInTheDocument();
    expect((await screen.findAllByText("Comment signal: medium")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Primary Health Finding")).toBeInTheDocument();
    expect(await screen.findByText("Top linked change: After; 2 theme comments linked")).toBeInTheDocument();
    expect(await screen.findByText("1 more linked finding not shown.")).toBeInTheDocument();
    expect(screen.queryByText("Sixth Hidden Finding")).toBeNull();
    await user.click(await screen.findByRole("button", { name: "Show all 6 linked findings" }));
    expect(await screen.findByText("Sixth Hidden Finding")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Show first 5 findings" }));
    expect(screen.queryByText("Sixth Hidden Finding")).toBeNull();
    expect(await screen.findByText("No proposed text in this card")).toBeInTheDocument();
    expect(container.querySelector("ins.diff-added")?.textContent).toContain("After ");
    expect(await screen.findByText(/Evidence note/i)).toBeInTheDocument();
    const detailChipTexts = Array.from(container.querySelectorAll(".status-chip")).map((node) =>
      node.textContent?.trim().toLowerCase()
    );
    expect(detailChipTexts).not.toContain("medium");
    expect(detailChipTexts).not.toContain("pending");
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
          change_type: "removed",
          proposed_heading: "Existing section",
          proposed_text_snippet: "Existing text",
          final_text_snippet: "",
          alignment_signal: { level: "low", evidence_note: "Older snapshot evidence." },
          related_clusters: [{ cluster_id: "cluster-10", label: "Cost impacts", comment_count: 1 }],
          preamble_links: [{ preamble_heading: "Preamble cost response", link_type: "citation", link_score: 1 }],
          review_status: "pending",
        },
      ],
    });
    snapshotMocks.loadInsightReport.mockResolvedValue(null);

    const { container } = render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-100"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Evidence note/i)).toBeInTheDocument();
    expect(await screen.findByText("Older snapshot evidence.")).toBeInTheDocument();
    expect(await screen.findByText(/Cost impacts/i)).toBeInTheDocument();
    expect(await screen.findByText(/Preamble cost response/i)).toBeInTheDocument();
    expect(await screen.findByText("No final text in this card")).toBeInTheDocument();
    expect(container.querySelector("del.diff-removed")?.textContent).toContain("Existing ");
    expect(screen.queryByText(/Loading insight report/i)).toBeNull();
    expect(screen.queryByText(/Why This Card Matters/i)).toBeNull();
  });

  it("renders a card insight loading placeholder while insight report is pending", async () => {
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
          card_id: "card-101",
          change_type: "modified",
          proposed_heading: "Before",
          final_heading: "After",
          proposed_text_snippet: "Before text",
          final_text_snippet: "After text",
          alignment_signal: { level: "low", evidence_note: "Pending insight evidence." },
          related_clusters: [],
          preamble_links: [],
          review_status: "pending",
        },
      ],
    });
    snapshotMocks.loadInsightReport.mockReturnValue(new Promise(() => {}));

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-101"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "After", level: 1 })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "Loading Card Insight" })).toBeInTheDocument();
    expect(await screen.findByText(/Loading insight report/i)).toBeInTheDocument();
    expect(screen.queryByText("Preamble links")).toBeNull();
  });

  it("renders stale priority-card messaging when referenced findings are missing", async () => {
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
          card_id: "card-102",
          change_type: "modified",
          proposed_heading: "Before",
          final_heading: "After",
          proposed_text_snippet: "Before text",
          final_text_snippet: "After text",
          alignment_signal: { level: "high", evidence_note: "Stale insight evidence." },
          related_clusters: [],
          preamble_links: [],
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
      top_findings: [],
      rule_story: {
        what_changed: "1 section modified.",
        what_commenters_emphasized: "Commenters emphasized health impacts.",
        where_final_text_aligned: "1 change card showed high comment alignment.",
        caveats: "Alignment signals indicate co-occurrence, not causation.",
      },
      priority_cards: [
        {
          card_id: "card-102",
          section_title: "After",
          change_type: "modified",
          score: 77,
          alignment_level: "high",
          finding_ids: ["missing-finding"],
        },
      ],
      provenance: {
        source_report: "outputs/EPA-HQ-OAR-2020-0430/report.json",
        source_eval_report: null,
        eval_available: false,
        report_schema_version: "v1",
        card_count: 1,
        cluster_count: 1,
        finding_count: 0,
      },
    });

    render(
      <MemoryRouter initialEntries={["/dockets/EPA-HQ-OAR-2020-0430/cards/card-102"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByText("Card priority 77")).toBeInTheDocument();
    expect(
      await screen.findByText("Card priority is available, but referenced findings are not in this snapshot.")
    ).toBeInTheDocument();
    expect(screen.queryByText("No insight finding linked for this card.")).toBeNull();
  });
});
