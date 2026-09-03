import type { Metadata } from "next";
import { LegalPage } from "../../components/legal-page";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "How Kuma Voice handles account, Watch, voice, AI, memory, and connector data.",
};

const sections = [
  {
    id: "scope",
    title: "1. Scope and who is responsible",
    paragraphs: [
      "This policy explains how Kuma Voice handles personal data when you use the Kuma Voice Apple Watch app, kumavoice.com, Kuma Studio, Kuma-hosted APIs, and related support or beta services (together, the “Service”). Kuma Voice is currently an independent project and is not operated through a separately incorporated company. In this policy, “Kuma Voice,” “we,” “us,” and “our” mean the operator of the Service under the Kuma Voice name.",
      "For Kuma-hosted accounts, Kuma Voice determines why and how the personal data described here is processed. This policy does not govern a server you self-host, an independently operated MCP server, or another service you connect. The operator of that service is responsible for its own privacy practices.",
    ],
  },
  {
    id: "data-we-collect",
    title: "2. Personal data we collect",
    subsections: [
      {
        title: "Account and profile data",
        paragraphs: [
          "We collect your email address, password hash, account status, onboarding answers, preferences, use cases, and personalization settings. We do not store your plaintext password.",
        ],
      },
      {
        title: "Watch, pairing, and security data",
        paragraphs: [
          "We process pairing codes, device identifiers, device names, token digests, session records, IP addresses, browser or device information, timestamps, and security events needed to pair devices, keep you signed in, and protect the Service.",
        ],
      },
      {
        title: "Voice and conversation data",
        paragraphs: [
          "When you intentionally start a voice turn, we process the audio you submit, transcripts, prompts, conversation context, AI responses, summaries, tool requests, tool results, and feedback. Conversation history may be stored when that feature is enabled. The current beta may also keep some conversation context only in memory, which can disappear when the backend restarts.",
        ],
      },
      {
        title: "Memory and personalization",
        paragraphs: [
          "If memory is enabled, we may store facts, preferences, instructions, summaries, and other details that you ask Kuma to remember or that the product clearly identifies as saved memory. Saved memory is separate from raw voice audio.",
        ],
      },
      {
        title: "Provider, connector, and MCP data",
        paragraphs: [
          "We process the API keys, authorization tokens, selected permission scopes, connector settings, remote server addresses, data returned by connected services, and records of actions you request. Provider credentials stored by Kuma Studio are encrypted at rest and remain server-side; they are not placed in the Watch app bundle.",
        ],
      },
      {
        title: "Website, support, and transaction data",
        paragraphs: [
          "We may collect essential browser storage, cookie choices, diagnostic logs, feature usage, crash information, messages you send to support, survey responses, and feedback. If paid features launch, Apple or a payment provider may send us purchase status, product, price, currency, and transaction identifiers; we do not receive full payment-card details from those providers.",
        ],
      },
    ],
  },
  {
    id: "sources",
    title: "3. Where data comes from",
    paragraphs: [
      "We receive data directly from you, automatically from your Watch, browser, and use of the Service, and from model providers, connectors, MCP servers, app stores, or other services you choose to link. If someone else provides data about you through a conversation or connector, the person using Kuma Voice is responsible for having a lawful basis to provide it.",
    ],
  },
  {
    id: "uses-and-legal-bases",
    title: "4. How and why we use data",
    paragraphs: [
      "Where European or similar data-protection law applies, we rely on performance of our contract with you to provide the Service; your consent for optional features such as microphone access, connectors, or non-essential cookies where consent is required; our legitimate interests in securing, maintaining, and improving Kuma Voice; and compliance with legal obligations. You may withdraw consent at any time, but withdrawal does not make earlier processing unlawful.",
    ],
    items: [
      "Provide the Service: create and secure accounts, pair a Watch, transcribe voice, generate responses, maintain conversation context, personalize Kuma, and perform requested connector or MCP actions.",
      "Operate and improve the product: troubleshoot errors, understand feature reliability, measure aggregate usage, respond to support, and develop new features.",
      "Protect Kuma Voice and others: prevent fraud, abuse, unauthorized access, malware, and violations of the Terms.",
      "Communicate with you: send service notices, security alerts, onboarding messages, and—only where permitted—product updates.",
      "Meet legal obligations: preserve records where required, respond to valid legal requests, and establish or defend legal claims.",
    ],
  },
  {
    id: "ai-and-audio",
    title: "5. Voice and AI processing",
    paragraphs: [
      "Kuma Voice streams audio for speech recognition, response generation, and speech output after you intentionally activate a turn. The current beta does not intentionally write raw voice audio to Kuma’s persistent storage. Audio can exist transiently in device memory, network buffers, backend memory, and the systems of the model or speech provider used for the request. If Kuma Voice later offers saved recordings, we will identify that feature and its retention controls before enabling it.",
      "Prompts, transcripts, context, connector results, and other necessary data may be sent to the AI provider configured for your account. Kuma Voice does not use your conversation content to train its own general-purpose AI model and does not sell it. A third-party model provider may process and retain data under its own terms, API data controls, and your provider account settings. This is especially important when you bring your own API key.",
    ],
  },
  {
    id: "connectors",
    title: "6. Connectors, tools, and MCP servers",
    paragraphs: [
      "When you connect a calendar, knowledge service, messaging service, MCP server, or other tool, Kuma Voice accesses only the permissions you authorize and sends the information needed to complete your request. A connector may return personal data or cause an external action, such as creating an event or sending a message.",
      "You can stop future access by disconnecting the integration in Studio or revoking access with the external provider. Disconnecting does not automatically erase data already sent to or retained by that provider; use its controls or contact it directly for deletion.",
    ],
  },
  {
    id: "sharing",
    title: "7. When we disclose data",
    paragraphs: [
      "We disclose personal data only as needed to provide and protect the Service, complete an action you request, or comply with law. We do not sell personal data, rent contact lists, or share personal data for cross-context behavioural advertising.",
    ],
    items: [
      "Model, speech, and tool providers that process prompts, audio, responses, or tool calls for the configuration you selected.",
      "Infrastructure providers for hosting, databases, encrypted storage, security, monitoring, email, and customer support.",
      "Connectors, MCP servers, and other third parties that you deliberately link or instruct Kuma to contact.",
      "Apple, app stores, or payment providers for distribution, purchases, subscription status, refunds, fraud prevention, and tax records.",
      "Authorities, advisers, or affected parties when reasonably necessary to comply with law, protect rights and safety, investigate abuse, or handle a security incident.",
      "A successor or potential successor in a merger, financing, acquisition, reorganisation, or sale of the project, subject to appropriate confidentiality and notice requirements.",
    ],
    subsections: [
      {
        title: "Service providers",
        paragraphs: [
          "Providers acting on Kuma Voice’s behalf may use data only for contracted services and must protect it consistently with applicable law and their agreements with Kuma Voice. Independent services you choose to connect process data under their own terms and privacy policies.",
        ],
      },
    ],
  },
  {
    id: "international-transfers",
    title: "8. International transfers",
    paragraphs: [
      "Kuma Voice and its providers may process data outside your country, including in countries whose data-protection rules differ from yours. Where required, Kuma Voice will rely on an adequacy decision, approved contractual safeguards such as the European Commission’s Standard Contractual Clauses, or another valid transfer mechanism. You can contact us for information about the safeguards relevant to a hosted deployment.",
    ],
  },
  {
    id: "retention",
    title: "9. How long we keep data",
    paragraphs: [
      "We keep personal data only for the shortest period reasonably needed for the purposes above, using the following retention periods:",
    ],
    items: [
      "Account, profile, device, and configuration data: while your account is active, then removed from active systems within 30 days after a confirmed deletion request unless law requires longer retention.",
      "Pairing codes and sessions: pairing codes normally expire after 10 minutes; Studio sessions normally expire after 30 days; a paired-device record remains until you unpair it or delete the account.",
      "Raw voice audio: not intentionally retained by Kuma Voice after the live turn in the current beta. Transient technical copies are cleared through normal processing and infrastructure rotation.",
      "Conversation history and AI outputs: until you delete the conversation, turn off or clear history, or delete the account. Conversation context kept only in backend memory is removed on deletion or backend restart.",
      "Saved memory and personalization: until you clear the relevant memory, reset personalization, or delete the account.",
      "Provider and connector credentials: until you disconnect the provider or connector or delete the account, after which active copies are deleted promptly.",
      "Security and diagnostic logs: normally up to 90 days, and longer only when needed to investigate an incident, prevent abuse, or comply with law.",
      "Support messages: normally up to 24 months after the issue is resolved, unless a shorter period is requested or a longer period is needed for a dispute.",
      "Backups: deleted data may remain in access-restricted backups for up to 30 additional days before rotation, unless restoration is required for security or disaster recovery. Restored data remains subject to the deletion request.",
      "Purchase, tax, and legal records: for the period required by applicable accounting, tax, consumer, or legal rules.",
    ],
  },
  {
    id: "security",
    title: "10. Security",
    paragraphs: [
      "Kuma Voice uses administrative, technical, and organisational safeguards appropriate to the nature of the data. These include encrypted network connections, password hashing, encryption at rest for stored provider credentials, server-side credential handling, scoped access, and token-based Watch pairing. No internet service can guarantee absolute security.",
      "Protect your Studio password, provider keys, paired Watch, and connected accounts. If you believe your account or data has been compromised, disconnect affected integrations and contact us promptly at privacy@kumavoice.com.",
    ],
  },
  {
    id: "choices-and-rights",
    title: "11. Your choices and privacy rights",
    paragraphs: [
      "Depending on where you live, you may have the right to access, correct, export, or delete personal data; restrict or object to processing; withdraw consent; and receive portable data. You may also complain to your local data-protection authority. These rights can be subject to legal exceptions, including security, the rights of others, legal obligations, and legal claims.",
    ],
    items: [
      "Use Studio to update profile information, review paired devices, disconnect providers, reset personalization, change your password, or delete your account where those controls are available.",
      "Email privacy@kumavoice.com for access, correction, export, objection, restriction, consent withdrawal, or deletion requests not available in Studio.",
      "We may verify your identity before completing a request. We aim to respond within the period required by applicable law and will explain if an exception applies.",
    ],
    subsections: [
      {
        title: "California and similar US state rights",
        paragraphs: [
          "The categories collected, sources, uses, disclosures, and retention periods are described in sections 2–9. Kuma Voice does not sell personal information or share it for cross-context behavioural advertising and therefore does not offer an opt-out for those activities. Where applicable, you may request to know, access, correct, or delete personal information and may use an authorised agent. Kuma Voice will not discriminate against you for exercising a privacy right.",
        ],
      },
    ],
  },
  {
    id: "account-deletion",
    title: "12. Account deletion",
    paragraphs: [
      "Deleting your account is intended to remove the account and personal data associated with it from Kuma Voice’s active systems, including profile data, active sessions, paired devices, saved provider credentials, hosted conversation history, and saved memory. It is not merely deactivation. Data may remain temporarily in backups as described above or be retained when required by law, necessary for fraud or security records, or needed to establish or defend legal claims.",
      "Account deletion does not cancel a subscription managed by Apple or another payment provider, erase data held independently by a connected provider, or delete a self-hosted deployment. Cancel external subscriptions and contact connected providers separately where needed.",
    ],
  },
  {
    id: "cookies",
    title: "13. Cookies and browser storage",
    paragraphs: [
      "Kuma Voice currently uses cookies or similar browser storage that are necessary for authentication, security, preferences, and remembering your cookie choice. Non-essential analytics or marketing technologies will be disabled unless and until the consent shown in the cookie banner permits them where consent is required. You can clear browser storage or change browser settings, although essential features such as sign-in may stop working.",
    ],
  },
  {
    id: "recording-others",
    title: "14. Information about other people",
    paragraphs: [
      "Voice assistants can capture personal data about other people. Before recording, transcribing, summarising, or sharing a conversation, you must give any notice and obtain any consent required by the laws that apply to you and the people involved. Do not use Kuma Voice for covert surveillance or to process information you have no right to provide.",
    ],
  },
  {
    id: "children",
    title: "15. Children",
    paragraphs: [
      "The Service is not directed to anyone under 18 and Kuma Voice does not knowingly collect personal data from children. If you believe a child has provided personal data, contact privacy@kumavoice.com so it can be reviewed and deleted where appropriate.",
    ],
  },
  {
    id: "automated-decisions",
    title: "16. Automated decisions",
    paragraphs: [
      "Kuma Voice uses AI to generate responses and decide which configured tools may help answer a request. Kuma Voice does not currently use solely automated processing to make decisions that produce legal or similarly significant effects about you. Do not use Kuma Voice as the sole decision-maker for employment, credit, housing, insurance, healthcare, legal rights, or other high-impact decisions.",
    ],
  },
  {
    id: "changes",
    title: "17. Changes to this policy",
    paragraphs: [
      "We may update this policy as the Service, providers, or law changes. The effective date at the top will change, and material updates will be presented through the Service, by email, or by another reasonable notice before they take effect when required. Earlier versions may be requested by email.",
    ],
  },
  {
    id: "contact",
    title: "18. Contact",
    paragraphs: [
      "For privacy questions, rights requests, or complaints, contact Kuma Voice at privacy@kumavoice.com. Please do not include passwords, API keys, connector tokens, or sensitive conversation content in your email.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy policy"
      intro="Kuma processes voice, context, memory, and connected-service data to act for you. This policy explains exactly what can be handled, where it can go, how long it stays, and how you can remove it."
      sections={sections}
    />
  );
}
