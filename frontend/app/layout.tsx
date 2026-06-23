import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HRMS AI — Test Harness",
  description: "Dev-only UI for exercising the HRMS AI endpoints.",
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
