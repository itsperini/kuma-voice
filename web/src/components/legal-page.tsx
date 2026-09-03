import Link from "next/link";
import { Brand } from "./brand";

type LegalSection = {
  id: string;
  title: string;
  paragraphs?: string[];
  items?: string[];
  subsections?: Array<{
    title: string;
    paragraphs?: string[];
    items?: string[];
  }>;
};

type LegalPageProps = {
  eyebrow?: string;
  title: string;
  intro: string;
  sections: LegalSection[];
  effectiveDate?: string;
};

function LegalParagraph({ text }: { text: string }) {
  const contactEmail = "privacy@kumavoice.com";
  const parts = text.split(contactEmail);

  return (
    <p>
      {parts.map((part, index) => (
        <span key={`${part}-${index}`}>
          {index > 0 ? <a href={`mailto:${contactEmail}`}>{contactEmail}</a> : null}
          {part}
        </span>
      ))}
    </p>
  );
}

function LegalCopy({
  paragraphs,
  items,
}: Pick<LegalSection, "paragraphs" | "items">) {
  return (
    <>
      {paragraphs?.map((paragraph) => <LegalParagraph key={paragraph} text={paragraph} />)}
      {items?.length ? (
        <ul>
          {items.map((item) => <li key={item}>{item}</li>)}
        </ul>
      ) : null}
    </>
  );
}

export function LegalPage({
  eyebrow,
  title,
  intro,
  sections,
  effectiveDate = "August 31, 2026",
}: LegalPageProps) {
  return (
    <div className="legal-page">
      <header className="legal-header">
        <Brand short />
        <Link href="/">Back to Kuma <span aria-hidden="true">↗</span></Link>
      </header>

      <main className="legal-main">
        <section className="legal-hero">
          {eyebrow ? <p className="section-kicker">{eyebrow}</p> : null}
          <h1>{title}</h1>
          <p>{intro}</p>
          <small>Effective and last updated {effectiveDate}</small>
        </section>

        <nav className="legal-toc" aria-label="On this page">
          <p>On this page</p>
          <ol>
            {sections.map((section) => (
              <li key={section.id}>
                <a href={`#${section.id}`}>{section.title}</a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="legal-content">
          {sections.map((section) => (
            <section id={section.id} key={section.id}>
              <h2>{section.title}</h2>
              <div className="legal-section-copy">
                <LegalCopy paragraphs={section.paragraphs} items={section.items} />
                {section.subsections?.map((subsection) => (
                  <div className="legal-subsection" key={subsection.title}>
                    <h3>{subsection.title}</h3>
                    <LegalCopy paragraphs={subsection.paragraphs} items={subsection.items} />
                  </div>
                ))}
              </div>
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
