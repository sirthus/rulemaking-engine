interface FilterBarProps {
  changeType: string;
  signal: string;
  cardSort: string;
  clusterQuery: string;
  changeTypes: string[];
  resultCount: number;
  totalCount: number;
  onFilter: (name: string, value: string) => void;
  onReset: () => void;
}

const SIGNAL_LEVELS = ["all", "high", "medium", "low", "none"] as const;

function signalLabel(level: (typeof SIGNAL_LEVELS)[number]): string {
  if (level === "all") {
    return "All signal";
  }
  return `${level.charAt(0).toUpperCase()}${level.slice(1)}`;
}

export function FilterBar({
  changeType,
  signal,
  cardSort,
  clusterQuery,
  changeTypes,
  resultCount,
  totalCount,
  onFilter,
  onReset,
}: FilterBarProps) {
  return (
    <div className="filter-bar">
      <div className="seg-control" role="group" aria-label="Signal filter">
        {SIGNAL_LEVELS.map((level) => (
          <button
            key={level}
            type="button"
            className={`seg-btn${signal === level ? " active" : ""}`}
            onClick={() => onFilter("signal", level)}
          >
            {signalLabel(level)}
          </button>
        ))}
      </div>

      <div className="filter-field">
        <select
          value={changeType}
          onChange={(event) => onFilter("changeType", event.target.value)}
          aria-label="Change type"
          title="Filter by change type"
        >
          <option value="all">All</option>
          {changeTypes.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </div>

      <div className="filter-field">
        <select
          value={cardSort}
          onChange={(event) => onFilter("cardSort", event.target.value)}
          aria-label="Sort cards"
          title="Sort priority changes"
        >
          <option value="priority">Priority, then size</option>
          <option value="size">Largest change, then priority</option>
        </select>
      </div>

      <div className="filter-field filter-search">
        <input
          value={clusterQuery}
          onChange={(event) => onFilter("clusterQuery", event.target.value)}
          placeholder="Search themes"
          aria-label="Theme search"
          title="Search linked themes"
        />
      </div>

      <div className="filter-bar-tail">
        <div className="filter-bar-result">
          {resultCount} of {totalCount} changes
        </div>

        <button type="button" className="filter-reset-btn" onClick={onReset}>
          Reset
        </button>
      </div>
    </div>
  );
}
