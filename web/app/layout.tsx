import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Pixi — Voice Agent Reliability",
    template: "%s · Pixi",
  },
  description:
    "Reproduce voice-agent failures and verify candidate changes against saved regression evidence.",
  applicationName: "Pixi",
};

export const viewport: Viewport = {
  themeColor: "#0c1118",
  colorScheme: "dark",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
