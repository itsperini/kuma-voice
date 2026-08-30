import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Private beta",
  description: "Kuma Voice private beta access.",
  robots: { index: false, follow: false },
};

export default function DashboardRedirect() {
  redirect("/studio");
}
