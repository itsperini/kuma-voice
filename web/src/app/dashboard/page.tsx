import type { Metadata } from "next";
import Link from "next/link";
import { Brand } from "../../components/brand";

export const metadata: Metadata = {
  title: "Private beta",
  description: "Kuma Voice private beta access.",
  robots: { index: false, follow: false },
};

export default function DashboardPlaceholder() {
  return (
    <main className="beta-page">
      <div className="beta-card">
        <Brand className="beta-brand" />
        <p className="section-kicker">Private beta</p>
        <h1>The control plane is next.</h1>
        <p>
          Device pairing, agents, connectors, and memory will live here. The
          first invited accounts will open soon.
        </p>
        <Link className="button button-primary" href="/">
          Back to Kuma Voice
        </Link>
      </div>
    </main>
  );
}
