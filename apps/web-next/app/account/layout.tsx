import Link from "next/link";

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <main className="shell shell--narrow">
      <div className="section">
        <div className="section__header">
          <div>
            <p className="eyebrow">Account</p>
            <h2>Orders and saved quotes</h2>
          </div>
        </div>
        <div className="account-nav">
          <Link className="nav-pill" href="/account/orders">
            My orders
          </Link>
          <Link className="nav-pill" href="/account/saved-quotes">
            Saved quotes
          </Link>
        </div>
      </div>
      <div className="section">{children}</div>
    </main>
  );
}
