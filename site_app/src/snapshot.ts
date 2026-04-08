import type { DocketIndex, DocketIndexEntry, EvalReport, InsightReport, Report, SnapshotManifest } from "./models";

const SNAPSHOT_BASE = (import.meta.env.VITE_SNAPSHOT_BASE as string | undefined) || "/site_data/current";

function assertSchemaVersion(resource: string, payload: unknown): asserts payload is { schema_version: "v1" } {
  if (!payload || typeof payload !== "object" || (payload as { schema_version?: string }).schema_version !== "v1") {
    throw new Error(`${resource} uses an unsupported snapshot schema.`);
  }
}

async function fetchJson<T>(resourcePath: string, resourceName: string): Promise<T> {
  const response = await fetch(`${SNAPSHOT_BASE}/${resourcePath}`);
  if (!response.ok) {
    throw new Error(`Failed to load ${resourceName}: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as unknown;
  assertSchemaVersion(resourceName, payload);
  return payload as T;
}

function normalizeIndexEntry(
  rawEntry: Record<string, unknown>,
  fallbackPublishedAt: string,
): DocketIndexEntry {
  const evaluationStatus = typeof rawEntry.evaluation_status === "string" ? rawEntry.evaluation_status : "not_available";
  const rawLabeling = rawEntry.labeling && typeof rawEntry.labeling === "object" ? rawEntry.labeling : {};
  const insightAvailable = typeof rawEntry.insight_available === "boolean" ? rawEntry.insight_available : false;
  const insightReportPath = typeof rawEntry.insight_report_path === "string" ? rawEntry.insight_report_path : null;

  return {
    docket_id: typeof rawEntry.docket_id === "string" ? rawEntry.docket_id : "unknown-docket",
    display_title:
      typeof rawEntry.display_title === "string"
        ? rawEntry.display_title
        : typeof rawEntry.docket_id === "string"
          ? rawEntry.docket_id
          : "unknown-docket",
    report_path: typeof rawEntry.report_path === "string" ? rawEntry.report_path : "",
    eval_report_path: typeof rawEntry.eval_report_path === "string" ? rawEntry.eval_report_path : "",
    insight_report_path: insightReportPath,
    insight_available: insightAvailable,
    insight_generated_at: typeof rawEntry.insight_generated_at === "string" ? rawEntry.insight_generated_at : null,
    latest_publish_at:
      typeof rawEntry.latest_publish_at === "string" ? rawEntry.latest_publish_at : fallbackPublishedAt,
    generated_at: typeof rawEntry.generated_at === "string" ? rawEntry.generated_at : undefined,
    evaluated_at: typeof rawEntry.evaluated_at === "string" ? rawEntry.evaluated_at : undefined,
    evaluation_status: evaluationStatus,
    evaluation_available:
      typeof rawEntry.evaluation_available === "boolean"
        ? rawEntry.evaluation_available
        : evaluationStatus === "available",
    total_clusters: typeof rawEntry.total_clusters === "number" ? rawEntry.total_clusters : 0,
    total_change_cards: typeof rawEntry.total_change_cards === "number" ? rawEntry.total_change_cards : 0,
    labeled_clusters: typeof rawEntry.labeled_clusters === "number" ? rawEntry.labeled_clusters : 0,
    change_type_counts:
      rawEntry.change_type_counts && typeof rawEntry.change_type_counts === "object"
        ? (rawEntry.change_type_counts as Record<string, number>)
        : {},
    alignment_signal_counts:
      rawEntry.alignment_signal_counts && typeof rawEntry.alignment_signal_counts === "object"
        ? (rawEntry.alignment_signal_counts as Record<string, number>)
        : {},
    review_status_counts:
      rawEntry.review_status_counts && typeof rawEntry.review_status_counts === "object"
        ? (rawEntry.review_status_counts as Record<string, number>)
        : {},
    labeling: {
      model: typeof rawLabeling.model === "string" ? rawLabeling.model : undefined,
      prompt_version: typeof rawLabeling.prompt_version === "string" ? rawLabeling.prompt_version : undefined,
      labeled_at: typeof rawLabeling.labeled_at === "string" ? rawLabeling.labeled_at : undefined,
      no_think: typeof rawLabeling.no_think === "boolean" ? rawLabeling.no_think : undefined,
      total_input_tokens: typeof rawLabeling.total_input_tokens === "number" ? rawLabeling.total_input_tokens : undefined,
      total_output_tokens:
        typeof rawLabeling.total_output_tokens === "number" ? rawLabeling.total_output_tokens : undefined,
    },
  };
}

function normalizeManifest(rawManifest: Record<string, unknown>): SnapshotManifest {
  const rawDockets = Array.isArray(rawManifest.dockets) ? rawManifest.dockets : [];
  const publishedAt = typeof rawManifest.published_at === "string" ? rawManifest.published_at : "";
  const releaseId = typeof rawManifest.release_id === "string" ? rawManifest.release_id : "unknown-release";

  return {
    schema_version: "v1",
    snapshot:
      rawManifest.snapshot && typeof rawManifest.snapshot === "object"
        ? {
            release_id:
              typeof (rawManifest.snapshot as Record<string, unknown>).release_id === "string"
                ? ((rawManifest.snapshot as Record<string, unknown>).release_id as string)
                : releaseId,
            published_at:
              typeof (rawManifest.snapshot as Record<string, unknown>).published_at === "string"
                ? ((rawManifest.snapshot as Record<string, unknown>).published_at as string)
                : publishedAt,
            docket_count:
              typeof (rawManifest.snapshot as Record<string, unknown>).docket_count === "number"
                ? ((rawManifest.snapshot as Record<string, unknown>).docket_count as number)
                : rawDockets.length,
          }
        : {
            release_id: releaseId,
            published_at: publishedAt,
            docket_count:
              typeof rawManifest.docket_count === "number" ? (rawManifest.docket_count as number) : rawDockets.length,
          },
    release_id: releaseId,
    published_at: publishedAt,
    docket_count:
      typeof rawManifest.docket_count === "number" ? (rawManifest.docket_count as number) : rawDockets.length,
    dockets: rawDockets
      .filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object")
      .map((entry) => normalizeIndexEntry(entry, publishedAt)),
  };
}

function normalizeDocketIndex(rawIndex: Record<string, unknown>): DocketIndex {
  const rawDockets = Array.isArray(rawIndex.dockets) ? rawIndex.dockets : [];
  const publishedAt = typeof rawIndex.published_at === "string" ? rawIndex.published_at : "";
  const releaseId = typeof rawIndex.release_id === "string" ? rawIndex.release_id : "unknown-release";

  return {
    schema_version: "v1",
    snapshot:
      rawIndex.snapshot && typeof rawIndex.snapshot === "object"
        ? {
            release_id:
              typeof (rawIndex.snapshot as Record<string, unknown>).release_id === "string"
                ? ((rawIndex.snapshot as Record<string, unknown>).release_id as string)
                : releaseId,
            published_at:
              typeof (rawIndex.snapshot as Record<string, unknown>).published_at === "string"
                ? ((rawIndex.snapshot as Record<string, unknown>).published_at as string)
                : publishedAt,
            docket_count:
              typeof (rawIndex.snapshot as Record<string, unknown>).docket_count === "number"
                ? ((rawIndex.snapshot as Record<string, unknown>).docket_count as number)
                : rawDockets.length,
          }
        : {
            release_id: releaseId,
            published_at: publishedAt,
            docket_count: rawDockets.length,
          },
    release_id: releaseId,
    published_at: publishedAt,
    dockets: rawDockets
      .filter((entry): entry is Record<string, unknown> => Boolean(entry) && typeof entry === "object")
      .map((entry) => normalizeIndexEntry(entry, publishedAt)),
  };
}

export async function loadManifest(): Promise<SnapshotManifest> {
  const payload = await fetchJson<Record<string, unknown>>("manifest.json", "manifest.json");
  return normalizeManifest(payload);
}

export async function loadDocketIndex(): Promise<DocketIndex> {
  const payload = await fetchJson<Record<string, unknown>>("dockets/index.json", "dockets/index.json");
  return normalizeDocketIndex(payload);
}

export async function loadReport(docketId: string): Promise<Report> {
  return fetchJson<Report>(`dockets/${docketId}/report.json`, `report.json for ${docketId}`);
}

export async function loadEvalReport(docketId: string): Promise<EvalReport> {
  return fetchJson<EvalReport>(`dockets/${docketId}/eval_report.json`, `eval_report.json for ${docketId}`);
}

export async function loadInsightReport(docketId: string): Promise<InsightReport | null> {
  try {
    return await fetchJson<InsightReport>(
      `dockets/${docketId}/insight_report.json`,
      `insight_report.json for ${docketId}`
    );
  } catch {
    return null;
  }
}

export function summarizeMetricBlock(metricBlock: Record<string, unknown> | undefined): string[] {
  if (!metricBlock) {
    return [];
  }
  return Object.entries(metricBlock).map(([key, value]) => `${key}: ${JSON.stringify(value)}`);
}

export { SNAPSHOT_BASE, assertSchemaVersion };
