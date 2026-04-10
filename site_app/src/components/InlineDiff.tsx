import { useEffect, useMemo, useState } from "react";
import type { ChangeCard } from "../models";
import { type DiffPiece, diffSnippets, tokenizeSnippet } from "./ChangeSnippet";
import type { CardDisplayMetrics } from "./ChangeCardRow";

export type DiffMode = "inline" | "side_by_side" | "changes_only";

const DIFF_MODES: Array<{ id: DiffMode; label: string }> = [
  { id: "inline", label: "Inline" },
  { id: "side_by_side", label: "Side-by-side" },
  { id: "changes_only", label: "Changes only" },
];

export function normalizeDiffMode(value: string | null | undefined): DiffMode {
  if (value === "side_by_side" || value === "side-by-side") {
    return "side_by_side";
  }
  if (value === "changes_only" || value === "changes-only") {
    return "changes_only";
  }
  return "inline";
}

export function diffModeToSearchParam(mode: DiffMode): string | null {
  if (mode === "side_by_side") {
    return "side-by-side";
  }
  if (mode === "changes_only") {
    return "changes-only";
  }
  return null;
}

export function mergeToInlineStream(proposed: DiffPiece[], final: DiffPiece[]): DiffPiece[] {
  const merged: DiffPiece[] = [];
  let proposedIndex = 0;
  let finalIndex = 0;

  while (proposedIndex < proposed.length || finalIndex < final.length) {
    const proposedPiece = proposed[proposedIndex];
    const finalPiece = final[finalIndex];

    if (proposedPiece && finalPiece && proposedPiece.kind === "unchanged" && finalPiece.kind === "unchanged") {
      merged.push({ text: proposedPiece.text, kind: "unchanged" });
      proposedIndex += 1;
      finalIndex += 1;
    } else if (proposedPiece && proposedPiece.kind === "removed") {
      merged.push(proposedPiece);
      proposedIndex += 1;
    } else if (finalPiece && finalPiece.kind === "added") {
      merged.push(finalPiece);
      finalIndex += 1;
    } else {
      if (proposedPiece) {
        merged.push(proposedPiece);
        proposedIndex += 1;
      }
      if (finalPiece) {
        merged.push(finalPiece);
        finalIndex += 1;
      }
    }
  }

  return merged;
}

function mergeAdjacentPieces(pieces: DiffPiece[]): DiffPiece[] {
  const merged: DiffPiece[] = [];

  for (const piece of pieces) {
    const last = merged[merged.length - 1];
    if (last && last.kind === piece.kind) {
      last.text += piece.text;
      continue;
    }
    merged.push({ ...piece });
  }

  return merged;
}

export function cardChangeSynopsis(card: ChangeCard, metrics: CardDisplayMetrics): string {
  const type = card.change_type || "modified";
  const size = metrics.sizeLabel.toLowerCase();
  const signal = card.alignment_signal?.level;
  const parts: string[] = [];

  if (type === "added") {
    parts.push("Provision added");
  } else if (type === "removed") {
    parts.push("Provision removed");
  } else {
    parts.push("Text modified");
  }

  if (size === "large change") {
    parts.push("major revision");
  }
  if (signal === "high" || signal === "medium") {
    parts.push(`${signal} comment signal`);
  }

  return parts.join(" · ");
}

export function DiffSynopsis({ card, metrics }: { card: ChangeCard; metrics: CardDisplayMetrics }) {
  return <p className="diff-synopsis">{cardChangeSynopsis(card, metrics)}</p>;
}

function renderPiece(piece: DiffPiece, key: string) {
  if (piece.kind === "added") {
    return (
      <ins key={key} className="diff-added">
        {piece.text}
      </ins>
    );
  }
  if (piece.kind === "removed") {
    return (
      <del key={key} className="diff-removed">
        {piece.text}
      </del>
    );
  }
  return <span key={key}>{piece.text}</span>;
}

interface ParagraphPiece {
  key: string;
  piece: DiffPiece;
}

function splitPiecesIntoParagraphs(pieces: DiffPiece[]): ParagraphPiece[][] {
  const paragraphs: ParagraphPiece[][] = [[]];

  for (let pieceIndex = 0; pieceIndex < pieces.length; pieceIndex += 1) {
    const piece = pieces[pieceIndex];
    const segments = piece.text.split(/(\n{2,})/);

    for (let segmentIndex = 0; segmentIndex < segments.length; segmentIndex += 1) {
      const segment = segments[segmentIndex];
      if (!segment) {
        continue;
      }

      if (segmentIndex % 2 === 1) {
        if (paragraphs[paragraphs.length - 1].length > 0) {
          paragraphs.push([]);
        }
        continue;
      }

      paragraphs[paragraphs.length - 1].push({
        key: `${pieceIndex}-${segmentIndex}`,
        piece: { ...piece, text: segment },
      });
    }
  }

  return paragraphs.filter((paragraph) => paragraph.length > 0);
}

function renderParagraphs(paragraphs: ParagraphPiece[][], keyPrefix: string) {
  return paragraphs.map((paragraph, paragraphIndex) => (
    <span key={`${keyPrefix}-paragraph-${paragraphIndex}`} className="diff-paragraph">
      {paragraph.map((entry, entryIndex) => renderPiece(entry.piece, `${keyPrefix}-${entry.key}-${entryIndex}`))}
    </span>
  ));
}

function renderInlineParagraphs(
  pieces: DiffPiece[],
  expandedRuns: Record<number, boolean>,
  onExpand: (runIndex: number) => void
) {
  const paragraphs = splitPiecesIntoParagraphs(pieces);
  let runIndex = 0;

  return paragraphs.map((paragraph, paragraphIndex) => {
    const nodes: JSX.Element[] = [];

    for (const entry of paragraph) {
      if (entry.piece.kind === "unchanged") {
        nodes.push(...renderCollapsedContext(entry.piece, runIndex, expandedRuns, onExpand));
      } else {
        nodes.push(renderPiece(entry.piece, `inline-${entry.key}-${runIndex}`));
      }
      runIndex += 1;
    }

    return (
      <span key={`inline-paragraph-${paragraphIndex}`} className="diff-paragraph">
        {nodes}
      </span>
    );
  });
}

function buildDiffSets(card: ChangeCard) {
  const proposed = card.proposed_text_snippet || "";
  const final = card.final_text_snippet || "";
  const changeType = (card.change_type || "").toLowerCase();

  if (changeType === "added") {
    const addedPieces = mergeAdjacentPieces(tokenizeSnippet(final).map((text) => ({ text, kind: "added" as const })));
    return {
      inlinePieces: addedPieces,
      removedPieces: [] as DiffPiece[],
      addedPieces,
      removedGroups: [] as DiffPiece[],
      addedGroups: addedPieces,
    };
  }

  if (changeType === "removed") {
    const removedPieces = mergeAdjacentPieces(
      tokenizeSnippet(proposed).map((text) => ({ text, kind: "removed" as const }))
    );
    return {
      inlinePieces: removedPieces,
      removedPieces,
      addedPieces: [] as DiffPiece[],
      removedGroups: removedPieces,
      addedGroups: [] as DiffPiece[],
    };
  }

  const diff = diffSnippets(proposed, final);
  const removedPieces = mergeAdjacentPieces(diff.proposed);
  const addedPieces = mergeAdjacentPieces(diff.final);
  const inlinePieces = mergeAdjacentPieces(mergeToInlineStream(diff.proposed, diff.final));

  return {
    inlinePieces,
    removedPieces,
    addedPieces,
    removedGroups: removedPieces.filter((piece) => piece.kind === "removed"),
    addedGroups: addedPieces.filter((piece) => piece.kind === "added"),
  };
}

function renderCollapsedContext(
  piece: DiffPiece,
  runIndex: number,
  expandedRuns: Record<number, boolean>,
  onExpand: (runIndex: number) => void
) {
  const tokens = tokenizeSnippet(piece.text);

  if (tokens.length <= 24 || expandedRuns[runIndex]) {
    return [<span key={`context-${runIndex}`}>{piece.text}</span>];
  }

  return [
    <span key={`context-start-${runIndex}`}>{tokens.slice(0, 8).join("")}</span>,
    <button
      key={`context-toggle-${runIndex}`}
      type="button"
      className="diff-collapse-btn"
      onClick={() => onExpand(runIndex)}
    >
      ...show {tokens.length - 16} words
    </button>,
    <span key={`context-end-${runIndex}`}>{tokens.slice(-8).join("")}</span>,
  ];
}

function ChangeGroupSection({
  title,
  pieces,
  emptyCopy,
}: {
  title: string;
  pieces: DiffPiece[];
  emptyCopy?: string;
}) {
  if (!pieces.length && !emptyCopy) {
    return null;
  }

  return (
    <section className="diff-group-section">
      <p className="diff-section-label">{title}</p>
      {pieces.length ? (
        <div className="diff-change-list">
          {pieces.map((piece, index) => (
            <div key={`${title}-${index}`} className={`diff-change-item diff-change-item-${piece.kind}`}>
              {renderParagraphs(splitPiecesIntoParagraphs([piece]), `${title}-${piece.kind}-${index}`)}
            </div>
          ))}
        </div>
      ) : (
        <p className="meta-line">{emptyCopy}</p>
      )}
    </section>
  );
}

function DiffColumn({
  title,
  pieces,
  emptyCopy,
}: {
  title: string;
  pieces: DiffPiece[];
  emptyCopy: string;
}) {
  return (
    <section className="diff-column">
      <p className="diff-section-label">{title}</p>
      <div className="diff-column-body">
        {pieces.length ? (
          <div className="diff-column-text">{renderParagraphs(splitPiecesIntoParagraphs(pieces), title)}</div>
        ) : (
          <p className="meta-line">{emptyCopy}</p>
        )}
      </div>
    </section>
  );
}

export function InlineDiff({
  card,
  synopsis,
  initialMode,
  onModeChange,
}: {
  card: ChangeCard;
  synopsis?: string;
  initialMode?: string | null;
  onModeChange?: (mode: DiffMode) => void;
}) {
  const normalizedInitialMode = normalizeDiffMode(initialMode);
  const [mode, setMode] = useState<DiffMode>(normalizedInitialMode);
  const [expandedRuns, setExpandedRuns] = useState<Record<number, boolean>>({});
  const { inlinePieces, removedPieces, addedPieces, removedGroups, addedGroups } = useMemo(
    () => buildDiffSets(card),
    [card.change_type, card.final_text_snippet, card.proposed_text_snippet]
  );
  const hasInlineContext = useMemo(() => inlinePieces.some((piece) => piece.kind === "unchanged"), [inlinePieces]);

  useEffect(() => {
    setMode(normalizedInitialMode);
  }, [normalizedInitialMode]);

  useEffect(() => {
    setExpandedRuns({});
  }, [card.card_id, mode]);

  const handleModeChange = (nextMode: DiffMode) => {
    setMode(nextMode);
    onModeChange?.(nextMode);
  };

  return (
    <div className="diff-viewer">
      <div className="diff-header">
        {synopsis ? <p className="diff-synopsis">{synopsis}</p> : null}
        <div className="diff-mode-bar" role="group" aria-label="Diff view">
          {DIFF_MODES.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`diff-mode-btn${mode === option.id ? " active" : ""}`}
              onClick={() => handleModeChange(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {mode === "inline" ? (
        <section className="diff-context-panel">
          <p className="diff-section-label">{hasInlineContext ? "Inline diff" : "Changes"}</p>
          <div className="diff-inline">
            {renderInlineParagraphs(inlinePieces, expandedRuns, (runIndex) =>
              setExpandedRuns((current) => ({ ...current, [runIndex]: true }))
            )}
          </div>
        </section>
      ) : null}

      {mode === "side_by_side" ? (
        <div className="diff-side-by-side">
          <DiffColumn title="Removed" pieces={removedPieces} emptyCopy="No removed text in this card." />
          <DiffColumn title="Added" pieces={addedPieces} emptyCopy="No added text in this card." />
        </div>
      ) : null}

      {mode === "changes_only" ? (
        <div className="diff-summary-grid diff-summary-grid-changes-only">
          <ChangeGroupSection title="Removed" pieces={removedGroups} emptyCopy="No removed phrases." />
          <ChangeGroupSection title="Added" pieces={addedGroups} emptyCopy="No added phrases." />
        </div>
      ) : null}
    </div>
  );
}
