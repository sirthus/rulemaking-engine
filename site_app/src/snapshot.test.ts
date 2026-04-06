import { describe, expect, it, vi } from "vitest";
import { assertSchemaVersion, loadDocketIndex, loadManifest } from "./snapshot";

describe("snapshot schema guard", () => {
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
              evaluation_status: "not_available",
              total_clusters: 12,
              total_change_cards: 146,
              labeled_clusters: 12,
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
              evaluation_status: "not_available",
              total_clusters: 12,
              total_change_cards: 146,
              labeled_clusters: 12,
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
    expect(index.dockets[0].labeling.model).toBeUndefined();

    fetchMock.mockRestore();
  });
});
