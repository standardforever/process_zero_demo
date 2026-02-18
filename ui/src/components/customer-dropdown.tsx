"use client";

import { useEffect, useMemo, useState } from "react";

import { getCustomers, getRules } from "@/lib/api";

type CustomerDropdownProps = {
  value: string;
  onChange: (value: string) => void;
  label?: string;
};

export function CustomerDropdown({ value, onChange, label = "Customer" }: CustomerDropdownProps) {
  const [query, setQuery] = useState("");
  const [customers, setCustomers] = useState<string[]>([]);
  const [mappedNames, setMappedNames] = useState<Record<string, string>>({});

  useEffect(() => {
    async function load() {
      try {
        const [crmCustomers, rules] = await Promise.all([getCustomers(), getRules()]);
        setCustomers(crmCustomers);
        setMappedNames(rules.customerNameMapping || {});
      } catch {
        setCustomers([]);
        setMappedNames({});
      }
    }

    void load();
  }, []);

  const filtered = useMemo(() => {
    const lowered = query.toLowerCase().trim();
    if (!lowered) return customers;
    return customers.filter((customer) => customer.toLowerCase().includes(lowered));
  }, [customers, query]);

  return (
    <div className="space-y-2">
      <label className="block text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</label>
      <input
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search customers"
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      />
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
      >
        <option value="">Select customer</option>
        {filtered.map((customer) => {
          const mapped = mappedNames[customer];
          const text = mapped && mapped !== customer ? `${customer} -> ${mapped}` : customer;
          return (
            <option key={customer} value={customer}>
              {text}
            </option>
          );
        })}
      </select>
    </div>
  );
}
