import { WorkbenchTransformSection } from "@/components/workbench-transform-section";

export default function WorkbenchTransformPage() {
  return (
    <section className="space-y-3">
      <div className="px-1">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#8ec5ff]">Transform Page</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">Manual transform preview</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--pz-muted)]">
          Preview CRM to ERP output and inspect exported JSON from the current rule set.
        </p>
      </div>
      <WorkbenchTransformSection />
    </section>
  );
}
