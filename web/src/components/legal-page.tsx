import Link from "next/link";
import { Brand } from "./brand";

type LegalSection = {
  title: string;
  paragraphs: string[];
};

type LegalPageProps = {
  eyebrow: string;
  title: string;
  intro: string;
  sections: LegalSection[];
};

export function LegalPage({ eyebrow, title, intro, sections }: LegalPageProps) {
  return (
    <div className="legal-page">
      <header className="legal-header">
        <Brand short />
        <Link href="/">Back to Kuma <span aria-hidden="true">↗</span></Link>
      </header>

      <main className="legal-main">
        <section className="legal-hero">
          <p className="section-kicker">{eyebrow}</p>
          <h1>{title}</h1>
          <p>{intro}</p>
          <small>Last updated August 31, 2026</small>
        </section>

        <div className="legal-content">
          {sections.map((section) => (
            <section key={section.title}>
              <h2>{section.title}</h2>
              {section.paragraphs.map((paragraph) => (
                <p key={paragraph}>{paragraph}</p>
              ))}
            </section>
          ))}
        </div>
      </main>

      <footer className="legal-footer">
        <span>Kuma Voice beta</span>
        <nav aria-label="Legal navigation">
          <Link href="/terms">Terms &amp; conditions</Link>
          <Link href="/privacy">Privacy policy</Link>
        </nav>
      </footer>
    </div>
  );
}
