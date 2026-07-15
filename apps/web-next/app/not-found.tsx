import Link from "next/link";

export default function NotFound() {
  return (
    <main className="shell shell--narrow">
      <section className="empty-state">
        <strong>Page not found.</strong>
        <p>The requested catalog page is not available.</p>
        <Link href="/">Back to catalog</Link>
      </section>
    </main>
  );
}
