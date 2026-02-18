"use client";

import { CRMRecord, ERPInvoice } from "@/lib/types";

type TransformPreviewProps = {
  original: CRMRecord | null;
  transformed: ERPInvoice | null;
};

function row(label: string, originalValue: string, transformedValue: string) {
  const changed = originalValue !== transformedValue;
  return (
    <div key={label} className={`grid grid-cols-3 gap-3 rounded-lg p-2 text-sm ${changed ? "bg-cyan-50" : ""}`}>
      <div className="font-medium text-slate-700">{label}</div>
      <div className="text-slate-600">{originalValue || "-"}</div>
      <div className="text-slate-900">{transformedValue || "-"}</div>
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
      <div className="grid grid-cols-3 gap-3 border-b border-slate-100 pb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">
        <div>Field</div>
        <div>CRM</div>
        <div>ERP</div>
      </div>

      <div className="space-y-1">
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
        <div className="grid grid-cols-3 gap-2">
          <span>Subtotal: {transformed.subtotal.toFixed(2)}</span>
          <span>Tax: {transformed.tax_amount.toFixed(2)}</span>
          <span>Total: {transformed.total.toFixed(2)}</span>
        </div>
      </div>

      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-slate-700">Line Items</h4>
        {transformed.line_items.map((item) => (
          <div key={`${item.product_code}-${item.description}`} className="rounded-lg border border-slate-200 p-3 text-sm">
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
