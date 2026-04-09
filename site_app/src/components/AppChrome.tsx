import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AppChrome({ children, topbarEnd }: { children: ReactNode; topbarEnd?: ReactNode }) {
  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <Link className="brand" to="/">
            Rulemaking Engine
          </Link>
        </div>
        {topbarEnd ? <div className="topbar-meta">{topbarEnd}</div> : null}
      </header>
      <main>{children}</main>
    </div>
  );
}
