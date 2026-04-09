export function ErrorView({ title, message }: { title: string; message: string }) {
  return (
    <section className="panel error-panel">
      <p className="eyebrow">Snapshot Error</p>
      <h1>{title}</h1>
      <p>{message}</p>
    </section>
  );
}
