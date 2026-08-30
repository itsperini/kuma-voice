import type { Metadata } from "next";
import { StudioAuthForm } from "../../../components/studio-auth-form";

export const metadata: Metadata = {
  title: "Create your Studio account",
  robots: { index: false, follow: false },
};

export default function StudioSignupPage() {
  return <StudioAuthForm mode="signup" />;
}
