import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "CRM-to-ERP Transformer",
  description: "Demo app for transforming CRM sales requests into ERP invoices",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`pz-theme ${geistSans.variable} ${geistMono.variable} antialiased`}>
        <div className="min-h-screen">
          {/* Shared layout header is intentionally disabled for this single-page TransformAgent UI. */}
          {children}
        </div>
      </body>
    </html>
  );
}
