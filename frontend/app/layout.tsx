import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Instrument_Serif } from "next/font/google";
import type { ReactNode } from "react";

import { SkipLink } from "@/components/layout/skip-link";
import { HTML_LANG } from "@/lib/i18n";
import { getServerLocale, serverTranslate } from "@/lib/i18n/server";
import { getServerDateFormat } from "@/lib/preferences/server";
import { getSiteUrl } from "@/lib/site/config";
import { getServerTheme } from "@/lib/theme/server";

import { Providers } from "./providers";

import "@/styles/globals.css";

const instrumentSerif = Instrument_Serif({
  weight: "400",
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-instrument-serif",
  display: "swap",
  preload: true,
});

const geistSans = Geist({
  subsets: ["latin"],
  variable: "--font-geist-sans",
  display: "swap",
  preload: true,
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
  preload: true,
});

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F5F3EE" },
    { media: "(prefers-color-scheme: dark)", color: "#0C1214" },
  ],
};

export async function generateMetadata(): Promise<Metadata> {
  const locale = await getServerLocale();
  const title = serverTranslate(locale, "meta.title");
  const description = serverTranslate(locale, "meta.description");

  return {
    metadataBase: new URL(getSiteUrl()),
    title,
    description,
    applicationName: "SentinelPay",
    manifest: "/manifest.webmanifest",
    icons: {
      icon: [
        { url: "/icon.svg", type: "image/svg+xml" },
        { url: "/icon.png", type: "image/png", sizes: "512x512" },
        { url: "/favicon.ico", type: "image/x-icon", sizes: "16x16 32x32 48x48" },
      ],
      apple: [{ url: "/apple-icon.png", type: "image/png", sizes: "180x180" }],
    },
    openGraph: {
      type: "website",
      siteName: "SentinelPay",
      title,
      description,
      images: [
        {
          url: "/opengraph-image",
          width: 1200,
          height: 630,
          alt: "SentinelPay",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: ["/opengraph-image"],
    },
  };
}

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const locale = await getServerLocale();
  const theme = await getServerTheme();
  const dateFormat = await getServerDateFormat();

  return (
    <html
      lang={HTML_LANG[locale]}
      data-theme={theme}
      data-scroll-behavior="smooth"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${instrumentSerif.variable}`}
    >
      <body className="min-h-dvh bg-background text-foreground antialiased">
        <Providers initialLocale={locale} initialTheme={theme} initialDateFormat={dateFormat}>
          <SkipLink />
          {children}
        </Providers>
      </body>
    </html>
  );
}
