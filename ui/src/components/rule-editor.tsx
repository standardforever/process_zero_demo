"use client";

import { useEffect, useMemo, useState } from "react";

type RuleEditorProps = {
  ruleType: string;
  ruleData: unknown;
  onSave: (nextRuleData: unknown) => Promise<void>;
};

type MappingRow = {
  key: string;
  value: string;
};

function asMappingRows(value: unknown): MappingRow[] {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value as Record<string, string>).map(([key, target]) => ({
    key,
    value: String(target),
  }));
}

function asConditional(value: unknown): { defaultValue: string; rows: MappingRow[] } {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { defaultValue: "", rows: [] };
  }

  const typed = value as { _default?: string | number; conditions?: Record<string, string | number> };
  return {
    defaultValue: String(typed._default ?? ""),
    rows: Object.entries(typed.conditions || {}).map(([key, raw]) => ({
      key,
      value: String(raw),
    })),
  };
}

export function RuleEditor({ ruleType, ruleData, onSave }: RuleEditorProps) {
  const [rows, setRows] = useState<MappingRow[]>([]);
  const [defaultValue, setDefaultValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isMappingRule = ruleType === "customerNameMapping";
  const isConfigRule = ruleType === "customerReference" || ruleType === "paymentReference";
  const isNumericConditional = ruleType === "deliveryDays";

  const initialState = useMemo(() => {
    if (isMappingRule || isConfigRule) {
      return { rows: asMappingRows(ruleData), defaultValue: "" };
    }
    return asConditional(ruleData);
  }, [isConfigRule, isMappingRule, ruleData]);

  useEffect(() => {
    setRows(initialState.rows);
    setDefaultValue(initialState.defaultValue);
    setError(null);
  }, [initialState]);

  function updateRow(index: number, next: Partial<MappingRow>) {
    setRows((current) => {
      const copy = [...current];
      copy[index] = { ...copy[index], ...next };
      return copy;
    });
  }

  function removeRow(index: number) {
    setRows((current) => current.filter((_, idx) => idx !== index));
  }

  function addRow() {
    setRows((current) => [...current, { key: "", value: "" }]);
  }

  async function save() {
    setSaving(true);
    setError(null);

    try {
      const duplicateKeys = new Set<string>();
      const builtRows = rows.reduce<Record<string, string | number>>((acc, row) => {
        const key = row.key.trim();
        const value = row.value.trim();

        if (!key || !value) return acc;
        if (acc[key] !== undefined) duplicateKeys.add(key);

        acc[key] = isNumericConditional ? Number(value) : value;
        return acc;
      }, {});

      if (duplicateKeys.size > 0) {
        throw new Error(`Duplicate keys: ${Array.from(duplicateKeys).join(", ")}`);
      }

      if (isMappingRule) {
        await onSave(builtRows);
      } else if (isConfigRule) {
        const numericConfigKeys = new Set([
          "customerNamePrefixLength",
          "invoiceIdPadLength",
        ]);
        const booleanConfigKeys = new Set([
          "includeYear",
          "useInvoiceTotalWithoutDecimals",
        ]);

        const payload = Object.entries(builtRows).reduce<Record<string, string | number | boolean>>(
          (acc, [key, value]) => {
            if (numericConfigKeys.has(key)) {
              acc[key] = Number(value);
              return acc;
            }
            if (booleanConfigKeys.has(key)) {
              acc[key] = String(value).toLowerCase() === "true";
              return acc;
            }

            acc[key] = String(value);
            return acc;
          },
          {},
        );

        await onSave(payload);
      } else {
        const payload = {
          _default: isNumericConditional ? Number(defaultValue || 0) : defaultValue,
          conditions: builtRows,
        };
        await onSave(payload);
      }
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save rule");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      {!isMappingRule && !isConfigRule && (
        <div className="space-y-2">
          <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">Default Value</label>
          <input
            type={isNumericConditional ? "number" : "text"}
            value={defaultValue}
            onChange={(event) => setDefaultValue(event.target.value)}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          />
        </div>
      )}

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-700">Conditions</h3>
          <button
            type="button"
            onClick={addRow}
            className="rounded-lg border border-slate-300 px-3 py-1 text-xs font-medium"
          >
            Add Row
          </button>
        </div>

        <div className="space-y-2">
          {rows.map((row, index) => (
            <div key={`${row.key}-${index}`} className="grid grid-cols-[1fr_1fr_auto] gap-2">
              <input
                type="text"
                value={row.key}
                onChange={(event) => updateRow(index, { key: event.target.value })}
                placeholder={isMappingRule ? "CRM value" : isConfigRule ? "Config key" : "Customer name"}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                type={isNumericConditional ? "number" : "text"}
                value={row.value}
                onChange={(event) => updateRow(index, { value: event.target.value })}
                placeholder={isMappingRule ? "ERP value" : isConfigRule ? "Config value" : "Condition value"}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => removeRow(index)}
                className="rounded-lg border border-rose-200 px-3 py-2 text-xs font-semibold text-rose-600"
              >
                Remove
              </button>
            </div>
          ))}
          {rows.length === 0 && (
            <p className="rounded-lg border border-dashed border-slate-300 p-3 text-sm text-slate-500">
              No rows configured.
            </p>
          )}
        </div>
      </div>

      {error && <p className="text-sm text-rose-600">{error}</p>}

      <button
        type="button"
        onClick={() => {
          void save();
        }}
        disabled={saving}
        className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
      >
        {saving ? "Saving..." : `Save ${ruleType}`}
      </button>
    </div>
  );
}
