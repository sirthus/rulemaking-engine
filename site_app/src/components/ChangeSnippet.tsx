import type { ReactNode } from "react";
import type { ChangeCard } from "../models";

export interface DiffPiece {
  text: string;
  kind: "unchanged" | "added" | "removed";
}

export function tokenizeSnippet(text: string): string[] {
  return text.match(/\S+\s*/g) || [];
}

export function diffSnippets(proposed: string, final: string): { proposed: DiffPiece[]; final: DiffPiece[] } {
  const proposedTokens = tokenizeSnippet(proposed);
  const finalTokens = tokenizeSnippet(final);
  const table = Array.from({ length: proposedTokens.length + 1 }, () =>
    Array.from({ length: finalTokens.length + 1 }, () => 0)
  );

  for (let i = proposedTokens.length - 1; i >= 0; i -= 1) {
    for (let j = finalTokens.length - 1; j >= 0; j -= 1) {
      table[i][j] =
        proposedTokens[i].trim() === finalTokens[j].trim()
          ? table[i + 1][j + 1] + 1
          : Math.max(table[i + 1][j], table[i][j + 1]);
    }
  }

  const proposedPieces: DiffPiece[] = [];
  const finalPieces: DiffPiece[] = [];
  let i = 0;
  let j = 0;

  while (i < proposedTokens.length && j < finalTokens.length) {
    if (proposedTokens[i].trim() === finalTokens[j].trim()) {
      proposedPieces.push({ text: proposedTokens[i], kind: "unchanged" });
      finalPieces.push({ text: finalTokens[j], kind: "unchanged" });
      i += 1;
      j += 1;
    } else if (table[i + 1][j] >= table[i][j + 1]) {
      proposedPieces.push({ text: proposedTokens[i], kind: "removed" });
      i += 1;
    } else {
      finalPieces.push({ text: finalTokens[j], kind: "added" });
      j += 1;
    }
  }

  while (i < proposedTokens.length) {
    proposedPieces.push({ text: proposedTokens[i], kind: "removed" });
    i += 1;
  }
  while (j < finalTokens.length) {
    finalPieces.push({ text: finalTokens[j], kind: "added" });
    j += 1;
  }

  return { proposed: proposedPieces, final: finalPieces };
}

export function renderDiffPieces(pieces: DiffPiece[]): ReactNode {
  return pieces.map((piece, index) => {
    if (piece.kind === "added") {
      return (
        <ins key={`${piece.kind}-${index}`} className="diff-added">
          {piece.text}
        </ins>
      );
    }
    if (piece.kind === "removed") {
      return (
        <del key={`${piece.kind}-${index}`} className="diff-removed">
          {piece.text}
        </del>
      );
    }
    return <span key={`${piece.kind}-${index}`}>{piece.text}</span>;
  });
}

export function ChangeSnippet({
  card,
  side,
  preview = false,
}: {
  card: ChangeCard;
  side: "proposed" | "final";
  preview?: boolean;
}) {
  const proposed = card.proposed_text_snippet || "";
  const final = card.final_text_snippet || "";
  const changeType = (card.change_type || "").toLowerCase();
  const className = `diff-text${preview ? " snippet-preview" : ""}`;

  if (changeType === "added" && side === "proposed" && !proposed.trim()) {
    return <p className="meta-line">No proposed text in this card</p>;
  }
  if (changeType === "removed" && side === "final" && !final.trim()) {
    return <p className="meta-line">No final text in this card</p>;
  }
  if (side === "proposed" && !proposed.trim()) {
    return <p className="meta-line">n/a</p>;
  }
  if (side === "final" && !final.trim()) {
    return <p className="meta-line">n/a</p>;
  }

  if (changeType === "added" && side === "final") {
    const addedPieces: DiffPiece[] = tokenizeSnippet(final).map((text) => ({ text, kind: "added" }));
    return <p className={className}>{renderDiffPieces(addedPieces)}</p>;
  }
  if (changeType === "removed" && side === "proposed") {
    const removedPieces: DiffPiece[] = tokenizeSnippet(proposed).map((text) => ({ text, kind: "removed" }));
    return <p className={className}>{renderDiffPieces(removedPieces)}</p>;
  }

  const diff = diffSnippets(proposed, final);
  return <p className={className}>{renderDiffPieces(side === "proposed" ? diff.proposed : diff.final)}</p>;
}
