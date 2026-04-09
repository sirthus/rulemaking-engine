import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  assertSchemaVersion,
  clearSnapshotCache,
  loadDocketIndex,
  loadInsightReport,
  loadManifest,
  loadReleaseSummary,
} from "./snapshot";

describe("snapshot schema guard", () => {
  beforeEach(() => {
    clearSnapshotCache();
    vi.restoreAllMocks();
  });

  it("accepts v1 payloads", () => {
    expect(() => assertSchemaVersion("manifest.json", { schema_version: "v1" })).not.toThrow();
  });

  it("rejects unsupported schema versions", () => {
    expect(() => assertSchemaVersion("manifest.json", { schema_version: "v2" })).toThrow(
      /unsupported snapshot schema/
    );
  });

  it("normalizes legacy manifest and docket index payloads", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          schema_version: "v1",
          release_id: "legacy-release",
          published_at: "2026-04-06T00:35:04+00:00",
          docket_count: 1,
          dockets: [
            {
              docket_id: "EPA-HQ-OAR-2020-0430",
              report_path: "dockets/EPA-HQ-OAR-2020-0430/report.json",
              eval_report_path: "dockets/EPA-HQ-OAR-2020-0430/eval_report.json",
              insight_report_path: "dockets/EPA-HQ-OAR-2020-0430/insight_report.json",
              insight_available: true,
              insight_generated_at: "2026-04-07T12:00:00+00:00",
              evaluation_status: "not_available",
              total_clusters: 12,
              total_change_cards: 146,
              labeled_clusters: 12,
            },
            {
              docket_id: "EPA-HQ-OAR-2018-0225",
              report_path: "dockets/EPA-HQ-OAR-2018-0225/report.json",
              eval_report_path: "dockets/EPA-HQ-OAR-2018-0225/eval_report.json",
              evaluation_status: "available",
              total_clusters: 2,
              total_change_cards: 3,
              labeled_clusters: 2,
            },
          ],
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          schema_version: "v1",
          release_id: "legacy-release",
          published_at: "2026-04-06T00:35:04+00:00",
          dockets: [
            {
              docket_id: "EPA-HQ-OAR-2020-0430",
              report_path: "dockets/EPA-HQ-OAR-2020-0430/report.json",
              eval_report_path: "dockets/EPA-HQ-OAR-2020-0430/eval_report.json",
              insight_report_path: "dockets/EPA-HQ-OAR-2020-0430/insight_report.json",
              insight_available: true,
              insight_generated_at: "2026-04-07T12:00:00+00:00",
              evaluation_status: "not_available",
              total_clusters: 12,
              total_change_cards: 146,
              labeled_clusters: 12,
            },
            {
              docket_id: "EPA-HQ-OAR-2018-0225",
              report_path: "dockets/EPA-HQ-OAR-2018-0225/report.json",
              eval_report_path: "dockets/EPA-HQ-OAR-2018-0225/eval_report.json",
              evaluation_status: "available",
              total_clusters: 2,
              total_change_cards: 3,
              labeled_clusters: 2,
            },
          ],
        }),
      } as Response);

    const manifest = await loadManifest();
    const index = await loadDocketIndex();

    expect(manifest.snapshot.release_id).toBe("legacy-release");
    expect(index.snapshot.release_id).toBe("legacy-release");
    expect(index.dockets[0].display_title).toBe("EPA-HQ-OAR-2020-0430");
    expect(index.dockets[0].evaluation_available).toBe(false);
    expect(index.dockets[0].insight_available).toBe(true);
    expect(index.dockets[0].insight_report_path).toBe("dockets/EPA-HQ-OAR-2020-0430/insight_report.json");
    expect(index.dockets[1].insight_available).toBe(false);
    expect(index.dockets[1].insight_report_path).toBeNull();
    expect(index.dockets[0].labeling.model).toBeUndefined();

    fetchMock.mockRestore();
  });

  it("loadInsightReport returns parsed insight report", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        schema_version: "v1",
        docket_id: "EPA-HQ-OAR-2020-0430",
        generated_at: "2026-04-07T12:00:00+00:00",
        generator: "generate_insights.py",
        executive_summary: "Expected insight summary.",
        top_findings: [],
        rule_story: {
          what_changed: "1 section changed.",
          what_commenters_emphasized: "Commenters raised air quality.",
          where_final_text_aligned: "1 card showed high comment alignment.",
          caveats: "Alignment signals indicate co-occurrence, not causation.",
        },
        priority_cards: [],
        provenance: {
          source_report: "outputs/EPA-HQ-OAR-2020-0430/report.json",
          source_eval_report: "outputs/EPA-HQ-OAR-2020-0430/eval_report.json",
          eval_available: true,
          report_schema_version: "v1",
          card_count: 1,
          cluster_count: 1,
          finding_count: 0,
        },
      }),
    } as Response);

    const result = await loadInsightReport("EPA-HQ-OAR-2020-0430");

    expect(result?.executive_summary).toBe("Expected insight summary.");
    fetchMock.mockRestore();
  });

  it("loadInsightReport returns null on fetch failure", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(new Error("404"));

    const result = await loadInsightReport("EPA-HQ-OAR-2020-0430");

    expect(result).toBeNull();
    fetchMock.mockRestore();
  });

  it("loadReleaseSummary returns parsed release summary", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        schema_version: "v1",
        release_id: "20260408T120000Z",
        published_at: "2026-04-08T12:00:00+00:00",
        docket_count: 3,
        docket_ids: ["EPA-HQ-OAR-2018-0225", "EPA-HQ-OAR-2020-0272", "EPA-HQ-OAR-2020-0430"],
        evaluation: { available: 2, not_available: 1 },
        insights: { available: 3, not_available: 0 },
        labeling: {
          models: ["qwen3:14b"],
          total_input_tokens: 1200,
          total_output_tokens: 340,
        },
      }),
    } as Response);

    const summary = await loadReleaseSummary();

    expect(summary.evaluation.available).toBe(2);
    expect(summary.insights.available).toBe(3);
    expect(summary.labeling.models).toEqual(["qwen3:14b"]);
    fetchMock.mockRestore();
  });

  it("caches repeated snapshot fetches by resource path", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({
        schema_version: "v1",
        release_id: "20260408T120000Z",
        published_at: "2026-04-08T12:00:00+00:00",
        docket_count: 3,
        docket_ids: ["EPA-HQ-OAR-2018-0225", "EPA-HQ-OAR-2020-0272", "EPA-HQ-OAR-2020-0430"],
        evaluation: { available: 2, not_available: 1 },
        insights: { available: 3, not_available: 0 },
        labeling: {
          models: ["qwen3:14b"],
          total_input_tokens: 1200,
          total_output_tokens: 340,
        },
      }),
    } as Response);

    await loadReleaseSummary();
    await loadReleaseSummary();

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
