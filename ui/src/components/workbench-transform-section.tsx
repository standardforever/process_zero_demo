"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";

import { DataTable, type Column } from "@/components/data-table";
import { TransformPreview } from "@/components/transform-preview";
import {
  batchTransform,
  getCRMData,
  getTransformOutput,
  previewTransformByRecord,
  previewTransformByRef,
} from "@/lib/api";
import { CRMRecord, ERPInvoice, PaginatedCRMRecords, TransformOutput } from "@/lib/types";

const emptyPage: PaginatedCRMRecords = {
  items: [],
  total: 0,
  page: 1,
  limit: 10,
  total_pages: 1,
};

const emptyOutput: TransformOutput = {
  count: 0,
  invoices: [],
};

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function WorkbenchTransformSectionContent() {
  const searchParams = useSearchParams();
  const initialRef = searchParams.get("ref") || "";

  const [records, setRecords] = useState<PaginatedCRMRecords>(emptyPage);
  const [search, setSearch] = useState(initialRef);
  const [page, setPage] = useState(1);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(initialRef ? new Set([initialRef]) : new Set());
  const [selectedRecord, setSelectedRecord] = useState<CRMRecord | null>(null);
  const [previewInvoice, setPreviewInvoice] = useState<ERPInvoice | null>(null);
  const [savedOutput, setSavedOutput] = useState<TransformOutput>(emptyOutput);
  const [loadingRecords, setLoadingRecords] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [batchLoading, setBatchLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadRecords() {
      setLoadingRecords(true);

      try {
        const response = await getCRMData({ page, limit: 10, search: search.trim() || undefined });
        if (cancelled) return;
        setRecords(response);
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : "Failed to load CRM records");
        }
      } finally {
        if (!cancelled) {
          setLoadingRecords(false);
        }
      }
    }

    void loadRecords();
    return () => {
      cancelled = true;
    };
  }, [page, search]);

  useEffect(() => {
    let cancelled = false;

    async function loadSavedOutput() {
      try {
        const response = await getTransformOutput();
        if (!cancelled) {
          setSavedOutput(response);
        }
      } catch {
        if (!cancelled) {
          setSavedOutput(emptyOutput);
        }
      }
    }

    void loadSavedOutput();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!initialRef || loadingRecords || selectedRecord) return;
    const match = records.items.find((item) => item.sales_request_ref === initialRef);
    if (!match) return;
    void handlePreviewRecord(match);
  }, [initialRef, loadingRecords, records.items, selectedRecord]);

  const columns = useMemo<Column<CRMRecord>[]>(
    () => [
      { key: "sales_request_ref", label: "Sales Ref", sortable: true },
      { key: "customer_company", label: "Customer", sortable: true },
      { key: "customer_contact", label: "Contact", sortable: true },
      { key: "sales_person", label: "Sales Person", sortable: true },
      { key: "status", label: "Status", sortable: true },
      { key: "date_raised", label: "Date Raised", sortable: true },
    ],
    [],
  );

  async function handlePreviewRecord(record: CRMRecord) {
    setPreviewLoading(true);
    setError(null);
    setStatus(null);

    try {
      const response = await previewTransformByRecord(record);
      setSelectedRecord(response.original);
      setPreviewInvoice(response.transformed);
      setSelectedIds(new Set([record.sales_request_ref]));
      setStatus(`Preview loaded for ${record.sales_request_ref}`);
    } catch (previewError) {
      setError(previewError instanceof Error ? previewError.message : "Failed to preview transformation");
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleRunBatch(useAllRecords: boolean) {
    setBatchLoading(true);
    setError(null);
    setStatus(null);

    try {
      const refs = useAllRecords ? [] : Array.from(selectedIds);
      const response = await batchTransform(refs);
      setSavedOutput({ count: response.count, invoices: response.invoices });

      const previewRef = useAllRecords
        ? response.invoices[0]?.sales_request_ref
        : refs[0] || response.invoices[0]?.sales_request_ref;

      if (previewRef) {
        try {
          const preview = await previewTransformByRef(previewRef);
          setSelectedRecord(preview.original);
          setPreviewInvoice(preview.transformed);
        } catch {
          // Keep batch output even if preview refresh fails.
        }
      }

      setStatus(
        useAllRecords
          ? `Transformed ${response.count} record(s) from the full dataset${previewRef ? ` and loaded preview for ${previewRef}` : ""}`
          : `Transformed ${response.count} selected record(s)${previewRef ? ` and loaded preview for ${previewRef}` : ""}`,
      );
    } catch (batchError) {
      setError(batchError instanceof Error ? batchError.message : "Failed to run batch transformation");
    } finally {
      setBatchLoading(false);
    }
  }

  function toggleRow(id: string) {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }

  function toggleAll(ids: string[]) {
    setSelectedIds((current) => {
      const allSelected = ids.length > 0 && ids.every((id) => current.has(id));
      return allSelected ? new Set<string>() : new Set(ids);
    });
  }

  return (
    <div className="space-y-6">
      {status && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {status}
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="space-y-6">
        <div className="rounded-[28px] border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">CRM Records</h2>
              <p className="text-sm text-slate-600">
                Click a row to load preview. Use checkboxes to prepare a batch transform.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void handleRunBatch(false)}
                disabled={batchLoading || selectedIds.size === 0}
                className="rounded-xl bg-cyan-700 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-cyan-600 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {batchLoading ? "Running..." : `Transform Selected (${selectedIds.size})`}
              </button>
              <button
                type="button"
                onClick={() => void handleRunBatch(true)}
                disabled={batchLoading}
                className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {batchLoading ? "Running..." : "Transform All"}
              </button>
            </div>
          </div>

          {loadingRecords ? (
            <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-6 text-sm text-slate-600">
              Loading CRM records...
            </div>
          ) : (
            <DataTable
              data={records.items}
              columns={columns}
              pagination={{
                page: records.page,
                total_pages: records.total_pages,
                total: records.total,
                limit: records.limit,
              }}
              onPageChange={setPage}
              search={search}
              onSearchChange={(value) => {
                setPage(1);
                setSearch(value);
              }}
              rowIdKey="sales_request_ref"
              selectedRowIds={selectedIds}
              onToggleRow={toggleRow}
              onToggleAll={toggleAll}
              onRowClick={(row) => {
                void handlePreviewRecord(row as CRMRecord);
              }}
            />
          )}
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Selection Summary</h2>
              <p className="text-sm text-slate-600">Current transform selection state.</p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Selected Records</div>
              <div className="mt-2 text-2xl font-bold text-slate-900">{selectedIds.size}</div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Preview Record</div>
              <div className="mt-2 text-sm font-semibold text-slate-900">
                {selectedRecord?.sales_request_ref || "-"}
              </div>
            </div>
            <div className="rounded-xl bg-slate-50 p-4">
              <div className="text-xs font-semibold uppercase tracking-wide text-slate-500">Saved Output Count</div>
              <div className="mt-2 text-2xl font-bold text-slate-900">{savedOutput.count}</div>
            </div>
          </div>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Transformation Preview</h2>
              <p className="text-sm text-slate-600">
                CRM to ERP mapping preview based on the currently declared rules.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  if (!selectedRecord || !previewInvoice) return;
                  downloadJson(`${selectedRecord.sales_request_ref}-preview.json`, {
                    original: selectedRecord,
                    transformed: previewInvoice,
                  });
                }}
                disabled={!selectedRecord || !previewInvoice}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Export Preview JSON
              </button>
            </div>
          </div>

          <div className="mb-4">
            <p className="text-sm text-slate-600">
              {previewLoading
                ? "Generating preview..."
                : selectedRecord
                  ? `Showing ${selectedRecord.sales_request_ref}`
                  : "Select a CRM row to inspect the ERP mapping."}
            </p>
          </div>
          <TransformPreview original={selectedRecord} transformed={previewInvoice} />
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Preview JSON</h2>
                <p className="text-sm text-slate-600">Raw JSON for the current preview selection.</p>
              </div>
            </div>
            <pre className="max-h-[420px] overflow-auto rounded-2xl bg-slate-900 p-4 text-xs text-slate-100">
              {selectedRecord && previewInvoice
                ? JSON.stringify({ original: selectedRecord, transformed: previewInvoice }, null, 2)
                : "Select a CRM record to inspect preview JSON."}
            </pre>
          </div>

          <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Latest Batch Output JSON</h2>
                <p className="text-sm text-slate-600">Saved invoices from the latest batch transform run.</p>
              </div>
              <button
                type="button"
                onClick={() => {
                  downloadJson("transform-output.json", savedOutput);
                }}
                disabled={savedOutput.invoices.length === 0}
                className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Export Output JSON
              </button>
            </div>
            <pre className="max-h-[420px] overflow-auto rounded-2xl bg-slate-900 p-4 text-xs text-slate-100">
              {JSON.stringify(savedOutput, null, 2)}
            </pre>
          </div>
        </div>

        <div className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Latest Batch Output</h2>
              <p className="text-sm text-slate-600">{savedOutput.count} invoice(s) saved in the latest run.</p>
            </div>
            <button
              type="button"
              onClick={async () => {
                try {
                  const response = await getTransformOutput();
                  setSavedOutput(response);
                } catch {
                  setSavedOutput(emptyOutput);
                }
              }}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
            >
              Refresh Output
            </button>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {savedOutput.invoices.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-sm text-slate-500">
                No transformed invoices saved yet.
              </div>
            ) : (
              savedOutput.invoices.map((invoice) => (
                <div key={invoice.sales_request_ref} className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                  <div className="text-sm font-semibold text-slate-900">{invoice.sales_request_ref}</div>
                  <div className="mt-1 text-sm text-slate-600">
                    {invoice.customer_name} · {invoice.total.toFixed(2)} · {invoice.payment_method}
                  </div>
                  <div className="mt-2 text-xs text-slate-500">
                    {invoice.line_items.length} line item(s) · Delivery {invoice.delivery_date}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </section>
    </div>
  );
}

export function WorkbenchTransformSection() {
  return (
    <Suspense
      fallback={
        <div className="rounded-[28px] border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm">
          Loading transform workspace...
        </div>
      }
    >
      <WorkbenchTransformSectionContent />
    </Suspense>
  );
}
