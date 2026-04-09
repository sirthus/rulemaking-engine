import type { CardSort } from "./components/ChangeCardRow";
import type { ClusterSummary } from "./models";

export const TAB_OVERVIEW = "overview";
export const TAB_CHANGES = "changes";
export const TAB_THEMES = "themes";
export const DEFAULT_TAB = TAB_CHANGES;
export const FILTER_ALL = "all";
export const CLUSTER_STATE_LABELED = "labeled";
export const CLUSTER_STATE_UNLABELED = "unlabeled";

const DOCKET_STORY_TITLES: Record<string, string> = {
  "EPA-HQ-OAR-2018-0225": "Good Neighbor Obligations for the 2008 Ozone NAAQS",
  "EPA-HQ-OAR-2020-0272": "Revised CSAPR Update for the 2008 Ozone NAAQS",
  "EPA-HQ-OAR-2020-0430": "Primary Copper Smelting NESHAP Reviews",
};

export function formatStamp(value?: string): string {
  if (!value) {
    return "n/a";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

export function normalizeCardSort(value: string | null): CardSort {
  return value === "size" ? "size" : "priority";
}

export function docketStoryTitle(docketId: string, fallback?: string): string {
  return DOCKET_STORY_TITLES[docketId] || fallback || docketId;
}

export function clusterSearchText(
  cluster: Pick<ClusterSummary, "label" | "label_description" | "top_keywords">
): string {
  return [cluster.label || "", cluster.label_description || "", ...(cluster.top_keywords || [])].join(" ").toLowerCase();
}

export function docketTabLabel(tab: string): string {
  if (tab === TAB_OVERVIEW) {
    return "Overview";
  }
  if (tab === TAB_THEMES) {
    return "Comment Themes";
  }
  return "Priority Changes";
}
