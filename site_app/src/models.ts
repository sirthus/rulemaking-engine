export type EvalStatus = "available" | "not_available";

export interface SnapshotInfo {
  release_id: string;
  published_at: string;
  docket_count: number;
}

export interface LabelingSummary {
  model?: string;
  prompt_version?: string;
  labeled_at?: string;
  no_think?: boolean;
  total_input_tokens?: number;
  total_output_tokens?: number;
}

export interface DocketIndexEntry {
  docket_id: string;
  display_title: string;
  report_path: string;
  eval_report_path: string;
  latest_publish_at: string;
  generated_at?: string;
  evaluated_at?: string;
  evaluation_status: EvalStatus | string;
  evaluation_available: boolean;
  total_clusters: number;
  total_change_cards: number;
  labeled_clusters: number;
  change_type_counts: Record<string, number>;
  alignment_signal_counts: Record<string, number>;
  review_status_counts: Record<string, number>;
  labeling: LabelingSummary;
}

export interface SnapshotManifest {
  schema_version: "v1";
  snapshot: SnapshotInfo;
  release_id: string;
  published_at: string;
  docket_count: number;
  dockets: DocketIndexEntry[];
}

export interface DocketIndex {
  schema_version: "v1";
  snapshot: SnapshotInfo;
  release_id: string;
  published_at: string;
  dockets: DocketIndexEntry[];
}

export interface ClusterSummary {
  cluster_id: string;
  label?: string | null;
  label_description?: string | null;
  canonical_count: number;
  total_raw_comments: number;
  top_keywords: string[];
  commenter_type_distribution: Record<string, number>;
}

export interface RelatedClusterSummary {
  cluster_id: string;
  label?: string | null;
  label_description?: string | null;
  comment_count?: number;
}

export interface PreambleLink {
  preamble_section_id?: string;
  preamble_heading?: string;
  link_type?: string;
  link_score?: number;
  relationship_label?: string;
}

export interface AlignmentSignal {
  level?: string;
  score?: number;
  evidence_note?: string;
  features?: Record<string, unknown>;
}

export interface ChangeCard {
  card_id: string;
  change_type?: string;
  match_type?: string;
  proposed_section_id?: string;
  final_section_id?: string;
  proposed_heading?: string;
  final_heading?: string;
  proposed_text_snippet?: string;
  final_text_snippet?: string;
  alignment_signal?: AlignmentSignal;
  related_clusters?: RelatedClusterSummary[];
  preamble_links?: PreambleLink[];
  review_status?: string;
}

export interface ReportSummary {
  total_comments: number;
  total_canonical_comments: number;
  total_clusters: number;
  labeled_clusters: number;
  total_change_cards: number;
  change_type_counts: Record<string, number>;
  alignment_signal_counts: Record<string, number>;
  review_status_counts: Record<string, number>;
  alignment_stats?: Record<string, number>;
  comment_attribution_stats?: Record<string, unknown>;
  labeling?: LabelingSummary;
  notes?: string[];
}

export interface Report {
  schema_version: "v1";
  docket_id: string;
  generated_at: string;
  generator: string;
  summary: ReportSummary;
  clusters: ClusterSummary[];
  change_cards: ChangeCard[];
}

export interface GoldSetProvenance {
  annotator?: string;
  annotated_at?: string;
  annotation_method?: string;
  blinded?: boolean;
  notes?: string;
}

export interface EvalReport {
  schema_version: "v1";
  docket_id: string;
  evaluated_at: string;
  generator: string;
  status: EvalStatus | string;
  reason?: string;
  gold_set_annotator?: string;
  gold_set_provenance?: GoldSetProvenance;
  alignment_metrics?: Record<string, unknown>;
  cluster_relevance_metrics?: Record<string, unknown>;
}
