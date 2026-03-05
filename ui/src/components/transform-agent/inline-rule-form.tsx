import { DROPDOWN_OPTIONS, FIELDS } from "./constants";
import { ArrowRightIcon, LockIcon } from "./icons";
import { RuleDropdown } from "./rule-dropdown";
import type { FormValues } from "./types";

type Props = {
  mode: "add" | "edit";
  formData: FormValues;
  submitted: boolean;
  onChange: (next: FormValues) => void;
};

export function InlineRuleForm({ mode, formData, submitted, onChange }: Props) {
  const bodyFields = FIELDS.filter((field) => field.key !== "customer_name");

  const update = (key: string, value: string) => {
    onChange({ ...formData, [key]: value });
  };

  const updateCrmCustomerName = (value: string) => {
    const shouldSyncErp =
      !formData.erp_customer_name || formData.erp_customer_name === formData.customer_name;

    onChange({
      ...formData,
      customer_name: value,
      erp_customer_name: shouldSyncErp ? value : formData.erp_customer_name,
    });
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-slate-700 bg-slate-900/80">
      <div className="grid grid-cols-[1fr_32px_1fr] gap-3 px-4 pt-4 text-[11px] font-bold tracking-[0.1em]">
        <div className="flex items-center gap-2 text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          CRM SOURCE
        </div>
        <div />
        <div className="flex items-center gap-2 text-sky-300">
          <span className="h-1.5 w-1.5 rounded-full bg-sky-300" />
          ERP TARGET
        </div>
      </div>

      <div className="grid grid-cols-[1fr_32px_1fr] items-end gap-3 px-4 pb-4 pt-3">
        <label className="space-y-1">
          <span className="font-mono text-[11px] text-emerald-400">Customer Name</span>
          <input
            value={formData.customer_name}
            onChange={(event) => updateCrmCustomerName(event.target.value)}
            disabled={submitted || mode === "edit"}
            placeholder="CRM customer name..."
            className="w-full rounded-lg border border-emerald-700 bg-emerald-950/40 px-3 py-2 text-sm text-emerald-300 outline-none transition focus:border-emerald-500 disabled:opacity-60"
          />
        </label>
        <div className="mb-2 flex justify-center text-slate-400">
          <ArrowRightIcon />
        </div>
        <label className="space-y-1">
          <span className="font-mono text-[11px] text-sky-300">Customer Name</span>
          <input
            value={formData.erp_customer_name}
            onChange={(event) => update("erp_customer_name", event.target.value)}
            disabled={submitted}
            placeholder="ERP customer name..."
            className="w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-slate-200 outline-none transition focus:border-sky-500 disabled:opacity-60"
          />
        </label>
      </div>

      <div className="mx-4 border-t border-slate-700 py-3 text-center font-mono text-[11px] tracking-[0.1em] text-slate-400">
        ERP FIELD MAPPING
      </div>

      <div className="grid grid-cols-1 gap-3 px-4 pb-4 md:grid-cols-2">
        {bodyFields.map((field) => (
          <div key={field.key} className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[11px] text-slate-300">{field.label}</span>
              {field.systemGenerated ? (
                <span className="inline-flex items-center gap-1 rounded border border-slate-600 bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                  <LockIcon />
                  {field.note}
                </span>
              ) : null}
            </div>

            {field.systemGenerated ? (
              <div className="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-slate-300">
                <span>{(formData as Record<string, string>)[field.key] || "-"}</span>
                <LockIcon />
              </div>
            ) : field.type === "dropdown" ? (
              <RuleDropdown
                value={(formData as Record<string, string>)[field.key] || ""}
                options={DROPDOWN_OPTIONS[field.key as keyof typeof DROPDOWN_OPTIONS] ?? []}
                onChange={(value) => update(field.key, value)}
              />
            ) : (
              <input
                value={(formData as Record<string, string>)[field.key] || ""}
                onChange={(event) => update(field.key, event.target.value)}
                disabled={submitted}
                className="w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none transition focus:border-sky-500"
              />
            )}
          </div>
        ))}
      </div>

      {!submitted ? (
        <div className="border-t border-slate-700 bg-slate-950/60 px-4 py-2.5 text-xs text-slate-300">
          Fill in the fields, then press <span className="font-semibold text-sky-300">Send</span> to save.
        </div>
      ) : null}
    </div>
  );
}
