"use client";

import { CRMRecord, ERPInvoice } from "@/lib/types";

type TransformPreviewProps = {
  original: CRMRecord | null;
  transformed: ERPInvoice | null;
};

function valueCell(label: string, value: string, tone: "crm" | "erp") {
  return (
    <div className="rounded-xl bg-white/80 px-3 py-2 md:bg-transparent md:px-0 md:py-0">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-400 md:hidden">
        {label}
      </div>
      <div
        className={`break-words text-sm ${
          tone === "erp" ? "font-semibold text-slate-900" : "text-slate-600"
        }`}
      >
        {value || "-"}
      </div>
    </div>
  );
}

function row(label: string, originalValue: string, transformedValue: string) {
  const changed = originalValue !== transformedValue;
  return (
    <div
      key={label}
      className={`rounded-2xl border px-3 py-3 md:grid md:grid-cols-[minmax(120px,0.8fr)_1fr_1fr] md:items-start md:gap-4 md:border-transparent md:px-3 md:py-2 ${
        changed ? "border-cyan-200 bg-cyan-50/80" : "border-slate-200 bg-slate-50/70"
      }`}
    >
      <div className="mb-3 text-sm font-semibold text-slate-800 md:mb-0">{label}</div>
      <div className="grid gap-2 md:contents">
        {valueCell("CRM", originalValue, "crm")}
        {valueCell("ERP", transformedValue, "erp")}
      </div>
    </div>
  );
}

export function TransformPreview({ original, transformed }: TransformPreviewProps) {
  if (!original || !transformed) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-5 text-sm text-slate-500">
        Select a record to preview transformation.
      </div>
    );
  }

  return (
    <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5">
      <div className="hidden grid-cols-[minmax(120px,0.8fr)_1fr_1fr] gap-4 border-b border-slate-100 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500 md:grid">
        <div>Field</div>
        <div>CRM</div>
        <div>ERP</div>
      </div>

      <div className="space-y-2">
        {row("Sales Ref", original.sales_request_ref, transformed.sales_request_ref)}
        {row("Date", original.date_raised, transformed.invoice_date)}
        {row("Customer", original.customer_company, transformed.customer_name)}
        {row("Contact", original.customer_contact, transformed.customer_contact)}
        {row("Tax", "-", transformed.tax_rate)}
        {row("Terms", "-", transformed.payment_terms)}
        {row("Method", "-", transformed.payment_method)}
        {row("Delivery Date", "-", transformed.delivery_date)}
        {row("Customer Ref", "-", transformed.customer_reference)}
        {row("Payment Ref", "-", transformed.payment_reference)}
      </div>

      <div className="rounded-xl bg-slate-50 p-3 text-sm text-slate-700">
        <div className="grid gap-2 sm:grid-cols-3">
          <span>Subtotal: {transformed.subtotal.toFixed(2)}</span>
          <span>Tax: {transformed.tax_amount.toFixed(2)}</span>
          <span>Total: {transformed.total.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">Line Items</h4>
        {transformed.line_items.map((item) => (
          <div
            key={`${item.product_code}-${item.description}`}
            className="rounded-lg border border-slate-200 p-3 text-sm"
          >
            <div className="font-medium text-slate-800">
              {item.product_code} - {item.description}
            </div>
            <div className="text-slate-600">
              Qty {item.quantity} x {item.unit_price.toFixed(2)} = {item.line_total.toFixed(2)}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
