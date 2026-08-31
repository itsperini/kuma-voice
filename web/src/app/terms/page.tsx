import type { Metadata } from "next";
import { LegalPage } from "../../components/legal-page";

export const metadata: Metadata = {
  title: "Terms & conditions",
  description: "Beta terms for Kuma Voice and Kuma Studio.",
};

const sections = [
  {
    title: "1. The beta service",
    paragraphs: [
      "Kuma Voice is an early-stage Apple Watch assistant and Studio experience. Features, limits, connectors, and availability may change while the product is in beta.",
      "The beta is provided for evaluation and may be interrupted, reset, or discontinued. Do not rely on Kuma for emergencies, safety-critical decisions, or any task where a delayed or incorrect response could cause harm.",
    ],
  },
  {
    title: "2. Your account and Watch",
    paragraphs: [
      "You are responsible for keeping your Studio account and paired devices secure. Only pair a Watch you control, and remove access if a device or credential may be compromised.",
      "You must provide accurate account information and use Kuma in compliance with applicable laws and the terms of any connected service.",
    ],
  },
  {
    title: "3. Agents, connectors, and third parties",
    paragraphs: [
      "Kuma may send requests to model providers and services you choose to connect. Those services operate under their own terms and privacy practices, and their responses may be incomplete or incorrect.",
      "You remain responsible for reviewing consequential actions before approving them and for the permissions granted to connectors or MCP servers.",
    ],
  },
  {
    title: "4. Acceptable use",
    paragraphs: [
      "Do not use Kuma to violate rights, access systems without permission, distribute malware, harass people, or automate illegal activity. We may limit access that threatens users, infrastructure, or the service.",
    ],
  },
  {
    title: "5. Ownership and feedback",
    paragraphs: [
      "You keep ownership of the content you provide. Kuma Voice, its product design, and service software remain owned by their respective rights holders. If you share feedback, you allow us to use it to improve the product without an obligation to compensate you.",
    ],
  },
  {
    title: "6. Changes and contact",
    paragraphs: [
      "These beta terms may change as the product and commercial offering develop. Material updates will be reflected on this page. Questions can be sent through the official @kumavoice account on X until a dedicated support channel is available.",
    ],
  },
];

export default function TermsPage() {
  return (
    <LegalPage
      eyebrow="Beta agreement"
      title="Terms & conditions"
      intro="The short version: use Kuma thoughtfully, keep control of what you connect, and expect the product to evolve while it is in beta."
      sections={sections}
    />
  );
}
