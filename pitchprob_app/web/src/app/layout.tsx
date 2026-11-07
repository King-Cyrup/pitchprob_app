import type { Metadata } from "next";
import "@fontsource-variable/manrope";
import "./globals.css";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "PitchProb — Match forecasts",
  description: "Statistical football forecasts, with an honest record of results.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
