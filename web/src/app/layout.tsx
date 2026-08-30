import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://kumavoice.com"),
  title: {
    default: "Kuma Voice — Your agents, on your wrist",
    template: "%s — Kuma Voice",
  },
  description:
    "A watch-only voice and notification endpoint for your AI agents. Speak, receive results, and approve actions from Apple Watch.",
  icons: {
    icon: "/kumavoice-icon.png",
    apple: "/kumavoice-icon.png",
  },
  openGraph: {
    type: "website",
    url: "https://kumavoice.com",
    siteName: "Kuma Voice",
    title: "Kuma Voice — Your agents, on your wrist",
    description:
      "Speak to your agents, receive results, and approve actions from Apple Watch.",
    images: [
      {
        url: "/og.png",
        width: 1774,
        height: 887,
        alt: "Kuma Voice running on two Apple Watches",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    creator: "@kumavoice",
    title: "Kuma Voice — Your agents, on your wrist",
    description:
      "Speak to your agents, receive results, and approve actions from Apple Watch.",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
