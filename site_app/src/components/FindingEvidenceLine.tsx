import type { InsightFinding } from "../models";

export function findingEvidenceLine(finding: InsightFinding): string | null {
  const hasStructuredEvidence =
    Boolean(finding.evidence_section_title) ||
    Boolean(finding.evidence_card_id) ||
    typeof finding.evidence_cluster_comment_count === "number";

  if (hasStructuredEvidence) {
    const linkedChange = finding.evidence_section_title || finding.evidence_card_id || "linked change card";
    const parts = [`Top linked change: ${linkedChange}`];
    if (typeof finding.evidence_cluster_comment_count === "number") {
      const count = finding.evidence_cluster_comment_count;
      parts.push(`${count} theme comment${count === 1 ? "" : "s"} linked`);
    }
    return parts.join("; ");
  }

  return finding.evidence_note || null;
}

export function FindingEvidenceLine({ finding }: { finding: InsightFinding }) {
  const line = findingEvidenceLine(finding);
  return line ? <p className="meta-line">{line}</p> : null;
}
