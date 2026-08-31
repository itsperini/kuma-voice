import type { Metadata } from "next";
import { LegalPage } from "../../components/legal-page";

export const metadata: Metadata = {
  title: "Privacy policy",
  description: "How Kuma Voice handles account, Watch, voice, and connector data.",
};

const sections = [
  {
    title: "1. Information Kuma handles",
    paragraphs: [
      "Studio stores the account details, onboarding preferences, paired-device metadata, and connector settings needed to provide the service. Provider credentials are designed to be encrypted before storage and are never placed in the Watch app bundle.",
      "When you speak to Kuma, audio and request context are sent through the backend to the model or connector needed to answer. The exact data handled depends on the services you choose to connect.",
    ],
  },
  {
    title: "2. How information is used",
    paragraphs: [
      "Information is used to authenticate you, pair your Watch, personalize replies, run the actions you request, protect the service, and understand which product experiences are useful.",
      "Kuma does not use Watch microphone access for passive listening. A voice turn starts from an explicit interaction on your Watch.",
    ],
  },
  {
    title: "3. Providers and connectors",
    paragraphs: [
      "Requests may be shared with model providers, search services, and connectors such as calendars or knowledge tools when necessary to complete an action you requested. Their own privacy terms apply to the information they receive.",
      "Permissions should be limited to the data Kuma needs. Connector access is designed to be reversible from Studio.",
    ],
  },
  {
    title: "4. Retention and control",
    paragraphs: [
      "Kuma is being designed around short-lived conversations and explicit memory rather than a permanent voice archive. Account, preference, pairing, and connector data may remain while your account is active or as needed to operate and secure the service.",
      "Self-hosted deployments are controlled by their operator. Hosted-account controls for reviewing and deleting data will continue to expand during beta.",
    ],
  },
  {
    title: "5. Cookies and local storage",
    paragraphs: [
      "The website currently uses essential browser storage for product functions such as remembering your cookie preference. If analytics are added later, the choice shown in the cookie banner will be respected on that browser.",
    ],
  },
  {
    title: "6. Updates and contact",
    paragraphs: [
      "This policy will evolve as hosted features, subscriptions, and connectors launch. Material changes will be reflected on this page. Privacy questions can be sent through the official @kumavoice account on X until a dedicated support channel is available.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <LegalPage
      eyebrow="Privacy, in plain language"
      title="Privacy policy"
      intro="Kuma should know enough to help without quietly turning every conversation into a permanent archive."
      sections={sections}
    />
  );
}
