import type { Metadata } from "next";
import { StudioSettings } from "../../../components/studio-settings";

export const metadata: Metadata = {
  title: "Settings",
  description: "Manage your Kuma Studio account, MCP servers, and paired Apple Watches.",
};

export default function StudioSettingsPage() {
  return <StudioSettings />;
}
