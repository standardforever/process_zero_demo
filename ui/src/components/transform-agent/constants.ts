import type { MenuItemId } from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "/transformer");

export const DROPDOWN_OPTIONS = {
  taxes: ["0%", "5%", "10%", "15%", "20%", "VAT Standard (20%)", "VAT Reduced (5%)", "Exempt"],
  terms_and_conditions: ["Standard T&C v1", "Standard T&C v2", "Enterprise Agreement", "Custom Contract", "NDA Required"],
  payment_method: ["Bank Transfer", "Credit Card", "Debit Card", "PayPal", "Stripe", "Cash", "Cheque", "Direct Debit"],
  sales_person: ["Alice Johnson", "Bob Martinez", "Carol White", "David Chen", "Emma Davis", "Frank Wilson"],
  payment_terms: ["Due on Receipt", "Net 7", "Net 15", "Net 30", "Net 45", "Net 60", "Net 90"],
} as const;

export type FieldConfig = {
  key: string;
  label: string;
  type: "text" | "dropdown";
  systemGenerated: boolean;
  note?: string;
};

export const FIELDS: FieldConfig[] = [
  { key: "customer_name", label: "Customer Name", type: "text", systemGenerated: false },
  { key: "taxes", label: "Taxes", type: "dropdown", systemGenerated: false },
  { key: "terms_and_conditions", label: "Terms & Conditions", type: "dropdown", systemGenerated: false },
  { key: "payment_method", label: "Payment Method", type: "dropdown", systemGenerated: false },
  { key: "sales_person", label: "Sales Person", type: "dropdown", systemGenerated: false },
  { key: "payment_terms", label: "Payment Terms", type: "dropdown", systemGenerated: false },
  { key: "payment_reference", label: "Payment Reference", type: "text", systemGenerated: true, note: "System Generated" },
  { key: "customer_reference", label: "Customer Reference", type: "text", systemGenerated: true, note: "System Generated" },
  { key: "invoice_date", label: "Invoice Date", type: "text", systemGenerated: true, note: "System Generated" },
  { key: "invoice_reference", label: "Invoice Reference", type: "text", systemGenerated: true, note: "Sales Ref" },
];

export const MENU_ITEMS: Array<{ id: MenuItemId; label: string; icon: string }> = [
  { id: "list", label: "List all rules", icon: "📋" },
  { id: "add", label: "Add new rule", icon: "➕" },
  { id: "edit", label: "Edit a rule", icon: "✏️" },
  { id: "delete", label: "Delete a rule", icon: "🗑️" },
  { id: "get", label: "Get a rule", icon: "🔍" },
];

export const WELCOME_MESSAGE = `Hello! I'm **TransformAgent** - your CRM to ERP mapping assistant.

I manage transformation rules so invoices, payments, and customer records map correctly.

Commands:

**add rule** - create a new mapping
**list rules** - show all active mappings
**edit rule <name>** - modify a customer rule
**delete rule <name>** - remove a rule
**get rule <name>** - inspect one rule
**add email** - add notification email
**update email** - update notification email
**delete email** - delete notification email
**cancel** - exit current form or pending action
**help** - show command summary`;
