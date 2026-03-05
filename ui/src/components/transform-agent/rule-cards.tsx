import { EditIcon, TrashIcon } from "./icons";
import { FIELDS } from "./constants";
import type { RuleAction, RuleRecord, RulesStore } from "./types";

const FIELD_LABEL_BY_KEY = new Map(FIELDS.map((field) => [field.key, field.label]));

export function RuleSummaryCard({ name, rule, action }: { name: string; rule: RuleRecord; action: RuleAction }) {
  const palette: Record<RuleAction, string> = {
    created: "text-emerald-300",
    updated: "text-sky-300",
    deleted: "text-rose-300",
  };

  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-slate-700 bg-slate-900/80">
      <div className="border-b border-slate-700 bg-slate-950/60 px-4 py-3">
        <p className={`text-sm font-semibold ${palette[action]}`}>{name}</p>
        <p className="mt-1 font-mono text-[11px] tracking-[0.08em] text-slate-400">RULE {action.toUpperCase()} SUCCESSFULLY</p>
      </div>

      {action !== "deleted" ? (
        <div className="grid grid-cols-1 gap-2 p-4 md:grid-cols-2">
          {FIELDS.filter((field) => field.key !== "customer_name" && !field.systemGenerated).map((field) => (
            <div key={field.key} className="rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2">
              <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-slate-400">{field.label}</p>
              <p className="mt-1 text-sm text-slate-100">{(rule as Record<string, string>)[field.key] || "-"}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function RuleDetailCard({ name, rule }: { name: string; rule: RuleRecord }) {
  return (
    <div className="mt-2 overflow-hidden rounded-xl border border-slate-700 bg-slate-900/80">
      <div className="flex items-center gap-2 border-b border-slate-700 bg-slate-950/60 px-4 py-3">
        <span className="h-2 w-2 rounded-full bg-sky-300" />
        <p className="text-sm font-semibold text-slate-100">{name}</p>
      </div>

      <div className="grid grid-cols-1 gap-2 p-4 md:grid-cols-2">
        {FIELDS.filter((field) => field.key !== "customer_name").map((field) => (
          <div key={field.key} className="rounded-lg border border-slate-700 bg-slate-800/70 px-3 py-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.08em] text-slate-400">{field.label}</p>
            <p className="mt-1 text-sm text-slate-100">{(rule as Record<string, string>)[field.key] || "-"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RulesListCard({
  rules,
  onEdit,
  onDelete,
}: {
  rules: RulesStore;
  onEdit: (name: string) => void;
  onDelete: (name: string) => void;
}) {
  const names = Object.keys(rules);
  if (names.length === 0) return <p className="mt-2 text-sm italic text-slate-400">No rules configured yet.</p>;

  return (
    <div className="mt-2 space-y-2">
      {names.map((name) => (
        <div key={name} className="rounded-xl border border-slate-700 bg-slate-900/80 p-3">
          <div className="mb-2 flex items-start justify-between gap-3">
            <p className="text-sm font-semibold text-slate-100">{name}</p>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => onEdit(name)}
                className="inline-flex items-center gap-1 rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs text-slate-200"
              >
                <EditIcon />
                Edit
              </button>
              <button
                type="button"
                onClick={() => onDelete(name)}
                className="inline-flex items-center gap-1 rounded-md border border-rose-700/60 bg-rose-950/40 px-2.5 py-1 text-xs text-rose-300"
              >
                <TrashIcon />
                Delete
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5">
            {["taxes", "payment_method", "payment_terms", "sales_person"].map((key) => (
              <span key={key} className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 font-mono text-[11px] text-slate-300">
                {FIELD_LABEL_BY_KEY.get(key) ?? key}: <span className="text-sky-300">{(rules[name] as Record<string, string>)[key] || "-"}</span>
              </span>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export function ConfirmDeleteCard({
  name,
  onConfirm,
  onCancel,
}: {
  name: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="mt-2 rounded-xl border border-rose-700/60 bg-rose-950/20 p-4">
      <p className="text-sm font-semibold text-rose-300">Delete rule for &quot;{name}&quot;?</p>
      <p className="mt-2 text-sm text-rose-100/90">
        This permanently removes all mappings for this customer. Type <code className="rounded bg-rose-950/60 px-1.5 py-0.5">yes</code> to confirm, or <code className="rounded bg-slate-800 px-1.5 py-0.5">no</code> to cancel.
      </p>
      <div className="mt-3 flex gap-2">
        <button type="button" onClick={onConfirm} className="rounded-md border border-rose-600 bg-rose-950/60 px-3 py-1.5 text-sm font-medium text-rose-200">
          Yes, Delete
        </button>
        <button type="button" onClick={onCancel} className="rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm font-medium text-slate-200">
          Cancel
        </button>
      </div>
    </div>
  );
}
