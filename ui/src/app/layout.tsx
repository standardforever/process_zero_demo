import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";

import RulesNavLink from "@/components/rules-nav-link";

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
      <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
        <div className="min-h-screen">
          <nav className="sticky top-0 z-30 border-b border-slate-200 bg-white/90 backdrop-blur">
            <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
              <Link href="/" className="text-sm font-bold uppercase tracking-[0.2em] text-cyan-700">
                Transformer
              </Link>
              <div className="flex items-center gap-3 text-sm font-medium text-slate-600">
                <Link href="/schema" className="rounded-md px-3 py-1 hover:bg-slate-100">
                  Schema
                </Link>
                <RulesNavLink />
                {/* Demo mode: hide Data and Transform navigation. */}
                {/* <Link href="/data" className="rounded-md px-3 py-1 hover:bg-slate-100">Data</Link> */}
                {/* <Link href="/transform" className="rounded-md px-3 py-1 hover:bg-slate-100">Transform</Link> */}
              </div>
            </div>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
