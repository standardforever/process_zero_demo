"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { getCustomers, getRules, updateRules } from "@/lib/api";
import { notifyRulesUpdated, RULES_SYNC_EVENT, RULES_SYNC_STORAGE_KEY } from "@/lib/rules-sync";
import { TransformRules } from "@/lib/types";

const CONDITIONAL_RULE_FIELDS = [
  "customerCountry",
  "salesTaxRate",
  "termsAndConditions",
  "paymentTerms",
  "paymentMethod",
  "deliveryDays",
] as const;

type ConditionalRuleField = (typeof CONDITIONAL_RULE_FIELDS)[number];

type CustomerRuleForm = {
  crmCustomerName: string;
  erpCustomerName: string;
  customerCountry: string;
  salesTaxRate: string;
  termsAndConditions: string;
  paymentTerms: string;
  paymentMethod: string;
  deliveryDays: string;
};

type CustomerRuleSummary = CustomerRuleForm & {
  effectiveLookupKey: string;
  backingRules: Record<string, unknown>;
};

function humanizeRuleName(value: string): string {
  return value
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function getMappedCustomerName(rules: TransformRules, customerName: string): string {
  const mapped = rules.customerNameMapping?.[customerName];
  return typeof mapped === "string" && mapped.trim() ? mapped.trim() : customerName;
}

function getConditionalValue(
  rules: TransformRules,
  ruleField: ConditionalRuleField,
  lookupKey: string,
): string {
  const rule = rules[ruleField];
  if (!rule || typeof rule !== "object") return "";

  const typed = rule as { _default?: string | number; conditions?: Record<string, string | number> };
  const value = typed.conditions?.[lookupKey] ?? typed._default ?? "";
  return String(value);
}

function getCustomerRuleForm(rules: TransformRules, customerName: string): CustomerRuleForm {
  const lookupKey = getMappedCustomerName(rules, customerName);
  return {
    crmCustomerName: customerName,
    erpCustomerName: lookupKey,
    customerCountry: getConditionalValue(rules, "customerCountry", lookupKey),
    salesTaxRate: getConditionalValue(rules, "salesTaxRate", lookupKey),
    termsAndConditions: getConditionalValue(rules, "termsAndConditions", lookupKey),
    paymentTerms: getConditionalValue(rules, "paymentTerms", lookupKey),
    paymentMethod: getConditionalValue(rules, "paymentMethod", lookupKey),
    deliveryDays: getConditionalValue(rules, "deliveryDays", lookupKey),
  };
}

function getDefaultValue(rules: TransformRules, ruleField: ConditionalRuleField): string {
  const rule = rules[ruleField] as { _default?: string | number } | undefined;
  return String(rule?._default ?? "");
}

function getFieldOptions(rules: TransformRules, ruleField: ConditionalRuleField): string[] {
  const rule = rules[ruleField];
  if (!rule || typeof rule !== "object") return [];

  const typed = rule as { _default?: string | number; conditions?: Record<string, string | number> };
  const values = new Set<string>();
  if (typed._default !== undefined && typed._default !== null) {
    values.add(String(typed._default));
  }

  Object.values(typed.conditions || {}).forEach((value) => {
    if (value !== undefined && value !== null) {
      values.add(String(value));
    }
  });

  return Array.from(values);
}

function buildSummary(rules: TransformRules, customerName: string): CustomerRuleSummary {
  const form = getCustomerRuleForm(rules, customerName);
  const lookupKey = getMappedCustomerName(rules, customerName);

  return {
    ...form,
    effectiveLookupKey: lookupKey,
    backingRules: {
      customerNameMapping: rules.customerNameMapping?.[customerName] ?? null,
      customerCountry: (rules.customerCountry.conditions || {})[lookupKey] ?? rules.customerCountry._default,
      salesTaxRate: (rules.salesTaxRate.conditions || {})[lookupKey] ?? rules.salesTaxRate._default,
      termsAndConditions:
        (rules.termsAndConditions.conditions || {})[lookupKey] ?? rules.termsAndConditions._default,
      paymentTerms: (rules.paymentTerms.conditions || {})[lookupKey] ?? rules.paymentTerms._default,
      paymentMethod: (rules.paymentMethod.conditions || {})[lookupKey] ?? rules.paymentMethod._default,
      deliveryDays: (rules.deliveryDays.conditions || {})[lookupKey] ?? rules.deliveryDays._default,
    },
  };
}

function cloneRules(rules: TransformRules): TransformRules {
  return JSON.parse(JSON.stringify(rules)) as TransformRules;
}

export function DemoRulesWorkspace() {
  const [rules, setRules] = useState<TransformRules | null>(null);
  const [customers, setCustomers] = useState<string[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState("");
  const [formState, setFormState] = useState<CustomerRuleForm | null>(null);
  const [loadingState, setLoadingState] = useState(true);
  const [savingRule, setSavingRule] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const customerSummary = useMemo(() => {
    if (!rules || !selectedCustomer) return null;
    return buildSummary(rules, selectedCustomer);
  }, [rules, selectedCustomer]);

  const customerCount = customers.length;

  const loadWorkspaceState = useCallback(async (preferredCustomer?: string) => {
    setLoadingState(true);
    setError(null);
    try {
      const [rulesPayload, customerPayload] = await Promise.all([getRules(), getCustomers()]);
      setRules(rulesPayload);
      setCustomers(customerPayload);

      const nextSelectedCustomer =
        (preferredCustomer && customerPayload.includes(preferredCustomer) && preferredCustomer) ||
        (selectedCustomer && customerPayload.includes(selectedCustomer) && selectedCustomer) ||
        customerPayload[0] ||
        "";

      setSelectedCustomer(nextSelectedCustomer);
      setFormState(nextSelectedCustomer ? getCustomerRuleForm(rulesPayload, nextSelectedCustomer) : null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "Failed to load rules workspace");
    } finally {
      setLoadingState(false);
    }
  }, [selectedCustomer]);

  useEffect(() => {
    void loadWorkspaceState();
  }, [loadWorkspaceState]);

  useEffect(() => {
    function refreshRules() {
      void loadWorkspaceState(selectedCustomer || undefined);
    }

    function handleStorage(event: StorageEvent) {
      if (event.key === RULES_SYNC_STORAGE_KEY) {
        refreshRules();
      }
    }

    window.addEventListener(RULES_SYNC_EVENT, refreshRules as EventListener);
    window.addEventListener("focus", refreshRules);
    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener(RULES_SYNC_EVENT, refreshRules as EventListener);
      window.removeEventListener("focus", refreshRules);
      window.removeEventListener("storage", handleStorage);
    };
  }, [loadWorkspaceState, selectedCustomer]);

  useEffect(() => {
    if (!rules || !selectedCustomer) return;
    setFormState(getCustomerRuleForm(rules, selectedCustomer));
  }, [rules, selectedCustomer]);

  function updateField<K extends keyof CustomerRuleForm>(field: K, value: CustomerRuleForm[K]) {
    setFormState((current) => (current ? { ...current, [field]: value } : current));
  }

  async function handleSaveCustomerRules() {
    if (!rules || !formState || !selectedCustomer) return;

    setSavingRule(true);
    setStatus(null);
    setError(null);

    try {
      const nextRules = cloneRules(rules);
      const oldLookupKey = getMappedCustomerName(rules, selectedCustomer);
      const newLookupKey = formState.erpCustomerName.trim() || selectedCustomer;

      if (newLookupKey === selectedCustomer) {
        delete nextRules.customerNameMapping[selectedCustomer];
      } else {
        nextRules.customerNameMapping[selectedCustomer] = newLookupKey;
      }

      for (const field of CONDITIONAL_RULE_FIELDS) {
        const rule = nextRules[field];
        const typedRule = rule as { _default: string | number; conditions: Record<string, string | number> };
        const nextRawValue = formState[field];
        const nextValue = field === "deliveryDays" ? Number(nextRawValue || typedRule._default || 0) : nextRawValue;

        delete typedRule.conditions[oldLookupKey];

        if (String(nextValue) !== String(typedRule._default)) {
          typedRule.conditions[newLookupKey] = nextValue;
        }
      }

      const savedRules = await updateRules(nextRules);
      setRules(savedRules);
      setFormState(getCustomerRuleForm(savedRules, selectedCustomer));
      setStatus(`${selectedCustomer} rules updated successfully`);
      notifyRulesUpdated();
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save customer rules");
    } finally {
      setSavingRule(false);
    }
  }

  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Rules Page</h2>
          <p className="mt-1 text-sm text-slate-600">
            Edit all transformation rules for one customer in a single screen.
          </p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-700">
          <div className="font-semibold text-slate-900">{customerCount}</div>
          <div>available customers</div>
        </div>
      </div>

      <div className="mb-4 rounded-2xl border border-cyan-200 bg-cyan-50 px-4 py-3 text-sm text-cyan-900">
        Live sync enabled. Rule changes applied in <span className="font-semibold">Chat Page</span> appear here
        automatically.
      </div>

      {status && (
        <div className="mb-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {status}
        </div>
      )}
      {error && (
        <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[0.72fr_1fr_0.88fr]">
        <div className="space-y-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
            <div className="mb-3 text-sm font-semibold text-slate-900">Customer</div>
            {loadingState ? (
              <div className="text-sm text-slate-500">Loading customers...</div>
            ) : (
              <div className="space-y-3">
                <select
                  value={selectedCustomer}
                  onChange={(event) => {
                    setSelectedCustomer(event.target.value);
                    setStatus(null);
                  }}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3 py-3 text-sm text-slate-800"
                >
                  {customers.map((customer) => (
                    <option key={customer} value={customer}>
                      {customer}
                    </option>
                  ))}
                </select>
                <div className="rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
                  <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Mapped ERP Name</div>
                  <div className="mt-1 font-semibold text-slate-900">
                    {selectedCustomer && rules ? getMappedCustomerName(rules, selectedCustomer) : "-"}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                {selectedCustomer || "Customer Rules Editor"}
              </h3>
              <p className="text-sm text-slate-600">
                {selectedCustomer
                  ? "Update all customer-specific rules in one save."
                  : "Select a customer to start editing."}
              </p>
            </div>
            {savingRule && <div className="text-sm font-medium text-cyan-700">Saving...</div>}
          </div>

          {selectedCustomer && formState ? (
            <div className="space-y-5 rounded-2xl border border-slate-200 bg-white p-5">
              <div className="grid gap-4 md:grid-cols-2">
                <CustomerField
                  label="CRM Customer Name"
                  value={formState.crmCustomerName}
                  onChange={(value) => updateField("crmCustomerName", value)}
                  disabled
                />
                <CustomerField
                  label="ERP Customer Name"
                  value={formState.erpCustomerName}
                  onChange={(value) => updateField("erpCustomerName", value)}
                />
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <CustomerSelectField
                  label={humanizeRuleName("customerCountry")}
                  value={formState.customerCountry}
                  onChange={(value) => updateField("customerCountry", value)}
                  options={rules ? getFieldOptions(rules, "customerCountry") : []}
                  defaultValue={rules ? getDefaultValue(rules, "customerCountry") : ""}
                />
                <CustomerSelectField
                  label={humanizeRuleName("salesTaxRate")}
                  value={formState.salesTaxRate}
                  onChange={(value) => updateField("salesTaxRate", value)}
                  options={rules ? getFieldOptions(rules, "salesTaxRate") : []}
                  defaultValue={rules ? getDefaultValue(rules, "salesTaxRate") : ""}
                />
                <CustomerSelectField
                  label={humanizeRuleName("paymentTerms")}
                  value={formState.paymentTerms}
                  onChange={(value) => updateField("paymentTerms", value)}
                  options={rules ? getFieldOptions(rules, "paymentTerms") : []}
                  defaultValue={rules ? getDefaultValue(rules, "paymentTerms") : ""}
                />
                <CustomerSelectField
                  label={humanizeRuleName("paymentMethod")}
                  value={formState.paymentMethod}
                  onChange={(value) => updateField("paymentMethod", value)}
                  options={rules ? getFieldOptions(rules, "paymentMethod") : []}
                  defaultValue={rules ? getDefaultValue(rules, "paymentMethod") : ""}
                />
                <CustomerSelectField
                  label={humanizeRuleName("termsAndConditions")}
                  value={formState.termsAndConditions}
                  onChange={(value) => updateField("termsAndConditions", value)}
                  options={rules ? getFieldOptions(rules, "termsAndConditions") : []}
                  defaultValue={rules ? getDefaultValue(rules, "termsAndConditions") : ""}
                />
                <CustomerField
                  label={humanizeRuleName("deliveryDays")}
                  value={formState.deliveryDays}
                  onChange={(value) => updateField("deliveryDays", value)}
                  type="number"
                  hint={rules ? `${getDefaultValue(rules, "deliveryDays")} days` : undefined}
                />
              </div>

              <button
                type="button"
                onClick={() => {
                  void handleSaveCustomerRules();
                }}
                disabled={savingRule}
                className="rounded-lg bg-cyan-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {savingRule ? "Saving..." : `Save ${selectedCustomer} Rules`}
              </button>
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
              Select a customer to start editing.
            </div>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">Customer Rule Summary</h3>
            <p className="text-sm text-slate-600">
              Inspect the effective customer profile and the backing rule entries that drive it.
            </p>
          </div>

          <pre className="max-h-[620px] overflow-auto rounded-2xl bg-slate-900 p-4 text-xs text-slate-100 shadow-sm">
            {customerSummary
              ? JSON.stringify(customerSummary, null, 2)
              : "Select a customer to inspect its effective rule summary."}
          </pre>
        </div>
      </div>
    </section>
  );
}

type CustomerFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: "text" | "number";
  disabled?: boolean;
  hint?: string;
};

function CustomerField({
  label,
  value,
  onChange,
  type = "text",
  disabled = false,
  hint,
}: CustomerFieldProps) {
  return (
    <label className="space-y-2">
      <span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:bg-slate-100 disabled:text-slate-500"
      />
      {hint ? <span className="block text-xs text-slate-500">{hint}</span> : null}
    </label>
  );
}

type CustomerSelectFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  defaultValue: string;
};

function CustomerSelectField({
  label,
  value,
  onChange,
  options,
  defaultValue,
}: CustomerSelectFieldProps) {
  const uniqueOptions = Array.from(new Set([defaultValue, ...options].filter(Boolean)));
  const isCustomValue = !uniqueOptions.includes(value);
  const selectedValue = isCustomValue ? "__custom__" : value;

  return (
    <label className="space-y-2">
      <span className="block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <select
        value={selectedValue}
        onChange={(event) => {
          const nextValue = event.target.value;
          if (nextValue === "__custom__") {
            if (uniqueOptions.includes(value)) {
              onChange("");
            }
            return;
          }
          onChange(nextValue);
        }}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      >
        {uniqueOptions.map((option) => (
          <option key={option} value={option}>
            {option === defaultValue ? `${option} (default)` : option}
          </option>
        ))}
        <option value="__custom__">Custom value...</option>
      </select>
      {isCustomValue ? (
        <input
          type="text"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          placeholder={`Enter custom ${label.toLowerCase()}`}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
      ) : null}
    </label>
  );
}
