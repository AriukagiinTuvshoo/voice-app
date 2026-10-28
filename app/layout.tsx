import type { Metadata, Viewport } from "next";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "VOICE — Speak. Clean. Write.",
  description: "Монгол болон бусад хэлний яриаг бодит цагт текст болгох, зөв бичих дүрэм шалгах систем.",
  applicationName: "VOICE",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "VOICE",
  },
  icons: {
    icon: "/icon.svg",
    apple: "/icon.svg",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  viewportFit: "cover",
  themeColor: "#07090e",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="mn" suppressHydrationWarning>
      <head>
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="mobile-web-app-capable" content="yes" />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
