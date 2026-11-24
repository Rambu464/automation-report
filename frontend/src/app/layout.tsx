import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Newstent — Analyst Workflow Automation Tool",
  description: "Local Web UI for Newstensity Media Monitoring Cleaning, 3-Pass AI, Interactive QC, & Triple Deliverables.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="id">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
