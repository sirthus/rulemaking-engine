import { Link } from "react-router-dom";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export function Breadcrumb({ items }: { items: BreadcrumbItem[] }) {
  return (
    <nav className="breadcrumb" aria-label="Breadcrumb">
      {items.map((item, index) => (
        <span key={`${item.label}-${item.href || "current"}-${index}`}>
          {index > 0 ? (
            <span className="breadcrumb-sep" aria-hidden="true">
              &rsaquo;
            </span>
          ) : null}
          {item.href ? <Link to={item.href}>{item.label}</Link> : <span>{item.label}</span>}
        </span>
      ))}
    </nav>
  );
}
