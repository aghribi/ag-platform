import type { Metadata } from "next";
import { Plus_Jakarta_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeScript } from "./components/ThemeScript";
import { ThemeProvider } from "./components/ThemeProvider";
import ServiceBanner from "./components/ServiceBanner";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-sans",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  display: "swap",
  variable: "--jb-mono",
});

export const metadata: Metadata = {
  title: "ag-tools",
  description: "PII Vault, Eval, Guardrails, and Document Understanding for AI pipelines.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${plusJakartaSans.variable} ${jetbrainsMono.variable}`}>
      <head>
        <ThemeScript />
      </head>
      <body className="bg-canvas text-ink antialiased min-h-screen" style={{ fontFamily: "var(--font-sans), -apple-system, sans-serif" }}>
        <ServiceBanner />
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
