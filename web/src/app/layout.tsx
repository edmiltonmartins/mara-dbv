// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import { SwRegister } from "@/components/SwRegister";
import "@/styles/globals.css";

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-plex-sans",
  display: "swap",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Mara — IA dos Desbravadores · Infinito Soft",
  description:
    "Instrutora virtual oficial para consulta de manuais DSA (RUD, Classes, Sistema de Unidades), simulados interativos e biblioteca offline para acampamento.",
  manifest: "/manifest.webmanifest",
  icons: {
    icon: "/icons/icon-192.png",
    apple: "/icons/icon-192.png",
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "default",
    title: "Mara DBV",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#010440",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className={`${plexSans.variable} ${plexMono.variable}`}>
      <body>
        <SwRegister />
        {children}
      </body>
    </html>
  );
}
