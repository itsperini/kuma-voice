import type { Metadata } from "next";
import { StudioAuthForm } from "../../../components/studio-auth-form";

export const metadata: Metadata = {
  title: "Sign in to Studio",
  robots: { index: false, follow: false },
};

export default function StudioLoginPage() {
  return <StudioAuthForm mode="signin" />;
}
