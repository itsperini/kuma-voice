import type { Metadata } from "next";
import { LegalPage } from "../../components/legal-page";

export const metadata: Metadata = {
  title: "Terms & conditions",
  description: "Terms for the Kuma Voice app, Kuma Studio, hosted APIs, AI, and connected tools.",
};

const sections = [
  {
    id: "agreement",
    title: "1. Agreement and scope",
    paragraphs: [
      "These Terms & Conditions (“Terms”) are an agreement between you and Kuma Voice governing your use of the Kuma Voice Apple Watch app, kumavoice.com, Kuma Studio, Kuma-hosted APIs, and related beta, support, and paid services (together, the “Service”). By creating an account, pairing a Watch, or using the Service, you agree to these Terms and the Privacy Policy.",
      "Kuma Voice is currently an independent project and is not operated through a separately incorporated company. In these Terms, “Kuma Voice,” “we,” “us,” and “our” mean the operator of the Service under the Kuma Voice name. Software released under a separate open-source licence remains governed by that licence; these Terms govern the hosted Service and your product account.",
    ],
  },
  {
    id: "eligibility",
    title: "2. Eligibility",
    paragraphs: [
      "You must be at least 18 years old and legally able to enter into these Terms. If you use Kuma Voice for an organisation, you confirm that you have authority to bind it, and “you” includes that organisation. You may not use the Service if law prohibits you from receiving it.",
    ],
  },
  {
    id: "service",
    title: "3. What Kuma Voice provides",
    paragraphs: [
      "Kuma Voice provides a voice interface on Apple Watch that can communicate with configured AI providers, remember selected context, and use tools, connectors, or MCP servers. Kuma Studio can be used to manage an account, pair devices, configure providers and integrations, and control available product settings.",
      "Features, models, connectors, quotas, supported regions, and platform requirements may change. Some features may be experimental, invite-only, self-hosted, or supplied by third parties. We may impose reasonable technical and usage limits to protect availability, safety, and cost.",
    ],
  },
  {
    id: "account-security",
    title: "4. Your account and Watch",
    items: [
      "Provide accurate information and keep it reasonably current.",
      "Protect your password, provider credentials, paired devices, recovery methods, and any access token issued to you.",
      "Pair only a Watch you own or are authorised to control, and promptly unpair a lost, sold, or compromised device.",
      "Tell Kuma Voice promptly if you suspect unauthorised use. You are responsible for activity under your account until access is secured, except to the extent caused by Kuma Voice’s breach of these Terms or applicable law.",
      "Do not share an individual account in a way that defeats security, plan limits, or device controls.",
    ],
  },
  {
    id: "licence",
    title: "5. Licence to use the Service",
    paragraphs: [
      "Subject to these Terms, Kuma Voice grants you a limited, personal, revocable, non-exclusive, non-transferable licence to access and use the Service for its intended purpose. This licence does not transfer ownership of Kuma Voice software, branding, models, designs, or documentation. Rights granted by a separate open-source licence are not restricted by this section.",
    ],
  },
  {
    id: "voice-and-consent",
    title: "6. Voice use and recording consent",
    paragraphs: [
      "Kuma Voice activates a voice turn when you deliberately start one through the Watch interaction. Microphones, transcription, and connected tools can capture personal or confidential information about you and other people.",
      "You are responsible for complying with recording, wiretapping, privacy, confidentiality, workplace, and data-protection laws. Before recording, transcribing, summarising, or sharing a conversation, provide any required notice and obtain any required consent from everyone involved. Do not use Kuma Voice for covert surveillance or where recording is prohibited.",
    ],
  },
  {
    id: "ai-output",
    title: "7. AI output and important limitations",
    paragraphs: [
      "AI responses, transcripts, summaries, memories, search results, and tool selections can be incomplete, outdated, offensive, or wrong. Kuma may misunderstand speech, attribute a statement incorrectly, invent information, or take an unintended action. Output is generated probabilistically and similar input may produce different results.",
      "Review important output and confirm consequential actions before relying on them. Kuma Voice is not an emergency service and is not a substitute for qualified medical, legal, financial, safety, or other professional advice. Do not rely on the Service as the sole basis for high-impact decisions about a person or where an error or delay could cause injury, loss, or legal harm.",
    ],
  },
  {
    id: "agent-actions",
    title: "8. Agent actions and approvals",
    paragraphs: [
      "If you authorise Kuma to use a connector or MCP tool, it may read external information or create, change, send, purchase, publish, or delete something in another service. You choose the permissions and remain responsible for instructions, approvals, and results produced through your account.",
      "Use the narrowest permissions practical and keep confirmation enabled for consequential actions. Kuma Voice may block, pause, or require confirmation for an action, but safety checks cannot identify every risk. A connector’s record of an action may be authoritative even if Kuma’s interface shows a different status.",
    ],
  },
  {
    id: "providers-and-connectors",
    title: "9. Providers, connectors, and MCP servers",
    paragraphs: [
      "The Service may send relevant audio, prompts, context, and data to the model provider, connector, search service, remote server, or MCP server you select. Those services are independent and governed by their own terms, privacy policies, limits, availability, and fees.",
      "If you bring your own API key or server, you are responsible for the provider account, billing, data controls, model choice, server security, and compliance. Kuma Voice is not responsible for charges, outages, output, data loss, or actions caused by an independently operated service, except where applicable law requires otherwise. Disconnecting a service stops future access by Kuma but may not erase data already held by that service.",
    ],
  },
  {
    id: "your-content",
    title: "10. Your content",
    paragraphs: [
      "You retain ownership of content you submit to the Service and of any rights you may have in output, subject to applicable law and third-party rights. You confirm that you have the rights and permissions needed to provide that content and direct Kuma Voice to process it.",
      "You grant Kuma Voice a worldwide, non-exclusive, royalty-free licence to host, copy, transmit, format, transform, and otherwise process your content only as needed to provide, secure, maintain, and troubleshoot the Service; complete actions you request; and comply with law. This licence lasts only while needed for those purposes and the retention periods in the Privacy Policy. Kuma Voice does not use your conversation content to train its own general-purpose AI model unless you separately and explicitly opt in.",
    ],
  },
  {
    id: "acceptable-use",
    title: "11. Acceptable use",
    paragraphs: [
      "You may not use the Service, or help another person use it, to:",
    ],
    items: [
      "Break the law, violate sanctions, or infringe privacy, publicity, confidentiality, intellectual-property, or other rights.",
      "Record people without legally required notice or consent; stalk, harass, threaten, exploit, or impersonate someone; or facilitate abuse of children or vulnerable people.",
      "Access an account, device, model, connector, or system without permission; bypass safeguards or rate limits; probe the Service except through an authorised security programme; or distribute malware.",
      "Generate or distribute spam, fraud, phishing, deceptive impersonation, unlawful surveillance, or instructions primarily intended to cause harm.",
      "Use AI output as the sole basis for prohibited or unlawful high-impact decisions about employment, housing, credit, insurance, healthcare, education, or legal access.",
      "Reverse engineer or copy protected parts of the hosted Service, except where law or a separate open-source licence expressly allows it.",
      "Resell access, conceal abusive usage, or consume resources in a way that materially disrupts the Service or other users.",
    ],
  },
  {
    id: "privacy",
    title: "12. Privacy",
    paragraphs: [
      "The Privacy Policy explains how Kuma Voice handles account, device, voice, conversation, memory, and connector data. By using the Service, you acknowledge that this processing is necessary to provide the features you choose. Where consent is required, Kuma Voice will request it separately.",
    ],
  },
  {
    id: "payments",
    title: "13. Plans, payments, and subscriptions",
    paragraphs: [
      "Some features may later require a paid plan, credits, or a third-party provider account. Before purchase, Kuma Voice will show the price, billing period, included usage, taxes where known, and material limits. Except where law requires otherwise, charges for consumed credits or a completed billing period are non-refundable.",
      "If you subscribe through Apple or another app store, that store processes payment, renewal, cancellation, and eligible refunds under its terms. Subscriptions may renew automatically until cancelled through the store’s controls. Deleting your Kuma account does not automatically cancel an external subscription, so cancel it separately before deletion. If billing is handled directly by Kuma Voice in the future, the checkout terms presented at purchase will also apply.",
    ],
  },
  {
    id: "ownership",
    title: "14. Kuma Voice property and feedback",
    paragraphs: [
      "Kuma Voice and its licensors retain all rights in the hosted Service, product design, software, documentation, branding, and other materials, excluding your content and separately licensed code. “Kuma,” “Kuma Voice,” the cat mark, and related visual identity may not be used in a way that suggests endorsement without permission.",
      "If you provide suggestions or feedback, you grant Kuma Voice a perpetual, worldwide, irrevocable, royalty-free right to use it without restriction or compensation. This does not transfer ownership of your other content.",
    ],
  },
  {
    id: "availability",
    title: "15. Beta, changes, and availability",
    paragraphs: [
      "Kuma Voice is an early-stage service. Beta features may contain defects, lose data, reset, change materially, or be discontinued. We do not promise uninterrupted or error-free availability, a particular model or connector, permanent storage, or compatibility with every Watch, provider, or region.",
      "We may change, limit, suspend, or discontinue a feature or the Service. Where reasonably possible, we will give advance notice of a material discontinuation and a practical opportunity to export stored data. Immediate changes may be necessary for security, legal compliance, third-party changes, or service stability.",
    ],
  },
  {
    id: "suspension",
    title: "16. Suspension and termination",
    paragraphs: [
      "You may stop using the Service at any time and may delete your account through Studio where available. Account deletion is governed by the Privacy Policy and does not automatically cancel an app-store subscription or remove data from an independent provider or self-hosted server.",
      "Kuma Voice may restrict or suspend access if reasonably necessary to protect users or infrastructure, investigate abuse, comply with law, prevent unexpected provider cost, or address a material breach of these Terms. We may terminate an account for a serious or repeated breach. Where appropriate, we will give notice and an opportunity to appeal at privacy@kumavoice.com.",
      "Sections that by their nature should survive termination—including ownership, payment obligations already incurred, disclaimers, liability limits, dispute terms, and general provisions—continue to apply.",
    ],
  },
  {
    id: "disclaimers",
    title: "17. Disclaimers",
    paragraphs: [
      "To the maximum extent permitted by law, the Service is provided “as is” and “as available.” Kuma Voice disclaims implied warranties of merchantability, fitness for a particular purpose, non-infringement, accuracy, availability, and quiet enjoyment. We do not warrant that AI output, transcription, memory, connectors, or agent actions will be correct, safe, complete, or suitable for your purpose.",
      "Nothing in these Terms excludes a warranty, remedy, or consumer right that cannot lawfully be excluded. If you are a consumer, mandatory protections in your country continue to apply.",
    ],
  },
  {
    id: "liability",
    title: "18. Limitation of liability",
    paragraphs: [
      "To the maximum extent permitted by law, Kuma Voice is not liable for indirect, incidental, special, consequential, exemplary, or punitive damages, or for lost profits, revenue, business, goodwill, data, or anticipated savings, arising from the Service, AI output, a connector, an MCP server, or a third-party provider.",
      "To the maximum extent permitted by law, Kuma Voice’s total aggregate liability arising out of the Service or these Terms will not exceed the greater of €100 or the amount you paid directly to Kuma Voice for the Service during the 12 months before the event giving rise to the claim.",
      "These limits do not apply to liability that cannot legally be limited, including liability for fraud, wilful misconduct, gross negligence, death or personal injury caused by negligence, or mandatory data-protection and consumer rights. Some jurisdictions do not allow certain exclusions, so parts of this section may not apply to you.",
    ],
  },
  {
    id: "claims",
    title: "19. Responsibility for third-party claims",
    paragraphs: [
      "You are responsible for losses and claims caused by your unlawful content, unlawful recording, unauthorised connector use, or material breach of these Terms. If you use the Service on behalf of a business, that business will defend and indemnify Kuma Voice against third-party claims arising from those acts, to the extent permitted by law. This section does not reduce the statutory rights of consumers.",
    ],
  },
  {
    id: "apple",
    title: "20. Apple App Store terms",
    paragraphs: [
      "If you download Kuma Voice through Apple’s App Store, Apple’s Usage Rules and the applicable Apple standard end-user licence also apply. These Terms are between you and Kuma Voice, not Apple. Kuma Voice, not Apple, is responsible for the app, its content, maintenance and support, product claims, privacy claims, and the investigation and resolution of third-party intellectual-property claims relating to the app.",
      "Your app licence is non-transferable and limited to Apple-branded products you own or control as permitted by Apple’s Usage Rules, including permitted Family Sharing. Apple has no obligation to provide maintenance or support. If the app fails to conform to an applicable warranty, you may notify Apple and Apple may refund the app purchase price; to the maximum extent permitted by law, Apple has no other warranty obligation.",
      "You must comply with applicable third-party terms and represent that you are not located in a US-embargoed or US-designated terrorist-supporting country and are not on a US prohibited or restricted-party list. Apple and its subsidiaries are third-party beneficiaries of this section and may enforce it against you.",
    ],
  },
  {
    id: "law-and-disputes",
    title: "21. Governing law and disputes",
    paragraphs: [
      "These Terms are governed by the laws of Italy, without regard to conflict-of-law rules. If you are a consumer, you keep the benefit of mandatory protections and courts available under the laws of your country of residence. Before starting a formal claim, please email privacy@kumavoice.com with a description of the issue so both sides can try to resolve it informally. Nothing here prevents either side from seeking urgent protective relief or using a consumer dispute process available by law.",
    ],
  },
  {
    id: "changes",
    title: "22. Changes to these Terms",
    paragraphs: [
      "We may update these Terms as the Service or law changes. The effective date at the top will change. For material changes, we will provide reasonable notice through the Service, by email, or by another appropriate method. If a change materially reduces your rights, it will apply prospectively after the required notice period. Continuing to use the Service after the effective date means you accept the revised Terms; if you do not agree, stop using the Service and delete your account.",
    ],
  },
  {
    id: "general",
    title: "23. General terms",
    paragraphs: [
      "These Terms, the Privacy Policy, purchase terms presented at checkout, and any feature-specific terms form the entire agreement about the Service. If a provision is unenforceable, it will be limited to the minimum extent necessary and the rest will remain effective. A failure to enforce a provision is not a waiver. You may not assign these Terms without consent; Kuma Voice may assign them in connection with a reorganisation or transfer of the project, subject to applicable notice and privacy requirements. Headings are for convenience only.",
    ],
  },
  {
    id: "contact",
    title: "24. Contact",
    paragraphs: [
      "Questions, complaints, support requests, and legal notices may be sent to Kuma Voice at privacy@kumavoice.com. Do not send passwords, API keys, connector tokens, or other secrets by email.",
    ],
  },
];

export default function TermsPage() {
  return (
    <LegalPage
      title="Terms & conditions"
      intro="Kuma is a voice interface for AI and connected tools. These terms set the boundaries: what the service provides, what you control, where AI can fail, and how accounts, actions, and third parties are handled."
      sections={sections}
    />
  );
}
