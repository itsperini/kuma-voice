import type { Metadata } from "next";
import { StudioOnboarding } from "../../components/studio-onboarding";

export const metadata: Metadata = {
  title: "Studio",
  description: "Pair your Apple Watch and configure Kuma Voice.",
  robots: { index: false, follow: false },
};

export default function StudioPage() {
  return <StudioOnboarding />;
}
