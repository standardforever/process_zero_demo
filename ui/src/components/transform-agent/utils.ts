import { DROPDOWN_OPTIONS, FIELDS } from "./constants";
import type { FormValues, Intent, RulesStore } from "./types";

export const SUPPORTED_COMMANDS = [
  "add rule",
  "list rules",
  "edit rule <name>",
  "delete rule <name>",
  "get rule <name>",
  "cancel",
  "help",
] as const;

export function makeId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function currentTime(): string {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function generateSystemValue(key: string): string {
  const now = new Date();
  switch (key) {
    case "payment_reference":
      return `PAY-${Date.now().toString(36).toUpperCase()}`;
    case "customer_reference":
      return `CUS-${Math.random().toString(36).slice(2, 7).toUpperCase()}`;
    case "invoice_date":
      return now.toISOString().split("T")[0] ?? "";
    case "invoice_reference":
      return `SALES-REF-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
    default:
      return "";
  }
}

export function makeDefaults(seed: Partial<FormValues> = {}): FormValues {
  const output: Record<string, string> = {};
  const seedMap = seed as Record<string, string | undefined>;

  for (const field of FIELDS) {
    const seededValue = seedMap[field.key];
    if (seededValue) {
      output[field.key] = seededValue;
      continue;
    }

    if (field.systemGenerated) {
      output[field.key] = generateSystemValue(field.key);
      continue;
    }

    if (field.type === "dropdown") {
      const first = DROPDOWN_OPTIONS[field.key as keyof typeof DROPDOWN_OPTIONS]?.[0] ?? "";
      output[field.key] = first;
      continue;
    }

    output[field.key] = "";
  }

  // ERP customer name defaults to CRM customer name, but remains editable.
  output.erp_customer_name = seedMap.erp_customer_name ?? seedMap.customer_name ?? "";

  return output as FormValues;
}

export function parseIntent(raw: string): Intent {
  const text = raw.trim();
  const lower = text.toLowerCase().replace(/\s+/g, " ");

  if (lower === "add rule") return { type: "ADD_RULE" };
  if (lower === "list rules") return { type: "LIST_RULES" };
  if (lower === "help") return { type: "HELP" };

  if (lower === "edit rule") return { type: "EDIT_RULE", name: null };
  if (lower.startsWith("edit rule ")) return { type: "EDIT_RULE", name: text.slice(10).trim() || null };

  if (lower === "delete rule") return { type: "DELETE_RULE", name: null };
  if (lower.startsWith("delete rule ")) return { type: "DELETE_RULE", name: text.slice(12).trim() || null };

  if (lower === "get rule") return { type: "GET_RULE", name: null };
  if (lower.startsWith("get rule ")) return { type: "GET_RULE", name: text.slice(9).trim() || null };

  if (lower === "yes") return { type: "YES" };
  if (lower === "no" || lower === "cancel") return { type: "NO" };

  return { type: "CHAT", text };
}

export function suggestCommands(raw: string): string[] {
  const lower = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!lower) return ["help"];

  const suggestions = new Set<string>();

  if (lower.startsWith("list")) suggestions.add("list rules");
  if (lower.startsWith("add")) suggestions.add("add rule");
  if (lower.startsWith("edit")) suggestions.add("edit rule <name>");
  if (lower.startsWith("delete")) suggestions.add("delete rule <name>");
  if (lower.startsWith("get")) suggestions.add("get rule <name>");
  if (lower === "list rule") suggestions.add("list rules");
  if (lower.includes("cancel")) suggestions.add("cancel");
  if (lower.includes("help")) suggestions.add("help");

  if (suggestions.size === 0) {
    suggestions.add("help");
    suggestions.add("list rules");
  }

  return Array.from(suggestions).slice(0, 3);
}

export function findRuleName(input: string | null, rules: RulesStore): string | null {
  if (!input) return null;

  const normalize = (value: string) => value.trim().toLowerCase().replace(/\s+/g, " ");
  const query = normalize(input);
  if (!query) return null;

  // Prevent command-like inputs from fuzzy-matching arbitrary rule names.
  const blocked = new Set([
    "add rule",
    "list rule",
    "list rules",
    "edit rule",
    "edit rules",
    "delete rule",
    "delete rules",
    "get rule",
    "get rules",
    "rule",
    "rules",
    "cancel",
    "help",
    "yes",
    "no",
  ]);
  if (blocked.has(query)) return null;

  const names = Object.keys(rules);
  const exact = names.find((name) => normalize(name) === query);
  if (exact) return exact;

  // Keep fuzzy support for convenience, but only for meaningful queries.
  if (query.length < 3) return null;

  const prefixMatch = names.find((name) => normalize(name).startsWith(query));
  if (prefixMatch) return prefixMatch;

  return names.find((name) => normalize(name).includes(query)) ?? null;
}
