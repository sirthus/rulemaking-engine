import { Link } from "react-router-dom";
import { AppChrome } from "../components/AppChrome";

export default function NotFoundPage() {
  return (
    <AppChrome>
      <section className="panel hero">
        <p className="eyebrow">404</p>
        <h1>Page not found</h1>
        <p className="lead">This route is not part of the published snapshot.</p>
        <Link className="action-link" to="/">
          Return home
        </Link>
      </section>
    </AppChrome>
  );
}
