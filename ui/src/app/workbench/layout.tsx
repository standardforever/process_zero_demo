import Link from "next/link";

const workbenchLinks = [
  { href: "/workbench/rules", label: "Rules Page" },
  { href: "/workbench/transform", label: "Transform Page" },
  { href: "/workbench/chat", label: "Chat Page" },
];

export default function WorkbenchLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(37,99,235,0.18),transparent_24%),radial-gradient(circle_at_85%_18%,rgba(124,58,237,0.2),transparent_28%),linear-gradient(180deg,#03040a_0%,#050814_52%,#03040a_100%)] px-5 py-6 sm:px-6 sm:py-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="overflow-hidden rounded-[34px] border border-white/10 bg-[linear-gradient(135deg,rgba(10,16,32,0.96),rgba(16,25,51,0.92))] shadow-[0_28px_90px_rgba(2,6,23,0.45)]">
          <div className="flex flex-col gap-5 border-b border-white/10 px-6 py-6 sm:px-8 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-[#8ec5ff]">
                Process Zero Workbench
              </p>
              <div className="space-y-2">
                <h1 className="max-w-3xl text-3xl font-semibold tracking-tight text-white sm:text-4xl">
                  Transformation Layer Pages
                </h1>
                <p className="max-w-3xl text-sm leading-6 text-[var(--pz-muted)]">
                  Separate routes for manual rules, transform preview, and AI chat.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-2 lg:max-w-[480px] lg:justify-end">
              {workbenchLinks.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/6 px-4 py-2 text-sm font-medium text-[#d9e4f8] transition hover:border-[#8ec5ff]/45 hover:bg-white/12 hover:text-white"
                >
                  <span>{link.label}</span>
                  <span className="text-xs text-[#8ec5ff]">{"->"}</span>
                </Link>
              ))}
            </div>
          </div>
        </section>

        {children}
      </div>
    </div>
  );
}
