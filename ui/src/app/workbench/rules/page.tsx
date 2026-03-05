import { DemoRulesWorkspace } from "@/components/demo-rules-workspace";

export default function WorkbenchRulesPage() {
  return (
    <section className="space-y-3">
      <div className="px-1">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#8ec5ff]">Rules Page</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">Manual rule editor</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--pz-muted)]">
          Edit rule payloads directly and inspect what will be saved by the backend.
        </p>
      </div>
      <DemoRulesWorkspace />
    </section>
  );
}
