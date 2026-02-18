"use client";

import Link from "next/link";

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,#dbeafe_0%,#f8fafc_45%,#ffffff_100%)] px-6 py-8">
      <div className="mx-auto max-w-4xl space-y-6">
        <header className="space-y-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-700">CRM to ERP Transformer</p>
          <h1 className="text-3xl font-bold text-slate-900">Demo Mode</h1>
          <p className="text-sm text-slate-600">
            Rules + AI assistant only. Data and Transform sections are commented out for this demo.
          </p>
        </header>

        {/* Demo mode: dashboard stats and activity widgets are commented out. */}
        {/* Previous dashboard cards and activity section intentionally hidden. */}

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Setup Flow</h2>
          <p className="mt-1 text-sm text-slate-600">
            Configure ERP/CRM columns first, then use AI chat on Rules page.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              href="/schema"
              className="inline-block rounded-xl bg-cyan-700 px-4 py-3 text-sm font-semibold text-white shadow hover:bg-cyan-600">
              Open Schema Setup
            </Link>
            <Link
              href="/rules"
              className="inline-block rounded-xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white shadow hover:bg-slate-800">
              Open Rules Page
            </Link>
          </div>
        </section>
      </div>
    </div>
  );
}
