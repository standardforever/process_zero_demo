"use client";

import { useMemo, useState } from "react";

type SortDirection = "asc" | "desc";

type Column<T> = {
  key: keyof T;
  label: string;
  sortable?: boolean;
  render?: (row: T) => React.ReactNode;
};

type Pagination = {
  page: number;
  total_pages: number;
  total: number;
  limit: number;
};

type DataTableProps<T extends Record<string, unknown>> = {
  data: T[];
  columns: Column<T>[];
  pagination: Pagination;
  onPageChange: (page: number) => void;
  search: string;
  onSearchChange: (value: string) => void;
  rowIdKey: keyof T;
  selectedRowIds?: Set<string>;
  onToggleRow?: (id: string) => void;
  onToggleAll?: (ids: string[]) => void;
  onRowClick?: (row: T) => void;
};

function sortValue(value: unknown): string | number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return value.toLowerCase();
  if (value == null) return "";
  return String(value).toLowerCase();
}

export function DataTable<T extends Record<string, unknown>>({
  data,
  columns,
  pagination,
  onPageChange,
  search,
  onSearchChange,
  rowIdKey,
  selectedRowIds,
  onToggleRow,
  onToggleAll,
  onRowClick,
}: DataTableProps<T>) {
  const [sortKey, setSortKey] = useState<keyof T | null>(null);
  const [sortDirection, setSortDirection] = useState<SortDirection>("asc");

  const sortedData = useMemo(() => {
    if (!sortKey) return data;

    return [...data].sort((left, right) => {
      const leftValue = sortValue(left[sortKey]);
      const rightValue = sortValue(right[sortKey]);

      if (leftValue < rightValue) return sortDirection === "asc" ? -1 : 1;
      if (leftValue > rightValue) return sortDirection === "asc" ? 1 : -1;
      return 0;
    });
  }, [data, sortDirection, sortKey]);

  const pageStart = pagination.total === 0 ? 0 : (pagination.page - 1) * pagination.limit + 1;
  const pageEnd = Math.min(pagination.page * pagination.limit, pagination.total);

  function toggleSort(key: keyof T) {
    if (sortKey === key) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortKey(key);
    setSortDirection("asc");
  }

  const ids = data.map((row) => String(row[rowIdKey] ?? ""));
  const allSelected = ids.length > 0 && ids.every((id) => selectedRowIds?.has(id));

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <input
          type="text"
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Search by customer or sales ref"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-cyan-600 sm:max-w-md"
        />
        <div className="text-xs text-slate-500">
          Showing {pageStart}-{pageEnd} of {pagination.total}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[920px] table-auto border-collapse">
          <thead>
            <tr className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
              {onToggleRow && (
                <th className="px-3 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={() => onToggleAll?.(ids)}
                    aria-label="Select all"
                  />
                </th>
              )}
              {columns.map((column) => (
                <th key={String(column.key)} className="px-3 py-3">
                  {column.sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(column.key)}
                      className="inline-flex items-center gap-1 font-semibold text-slate-600"
                    >
                      {column.label}
                      {sortKey === column.key ? (sortDirection === "asc" ? "▲" : "▼") : ""}
                    </button>
                  ) : (
                    <span>{column.label}</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {sortedData.map((row) => {
              const rowId = String(row[rowIdKey] ?? "");
              return (
                <tr
                  key={rowId}
                  onClick={() => onRowClick?.(row)}
                  className="cursor-pointer border-t border-slate-100 text-sm text-slate-800 hover:bg-cyan-50/50"
                >
                  {onToggleRow && (
                    <td
                      className="px-3 py-3"
                      onClick={(event) => {
                        event.stopPropagation();
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={selectedRowIds?.has(rowId) ?? false}
                        onChange={() => onToggleRow(rowId)}
                        aria-label={`Select ${rowId}`}
                      />
                    </td>
                  )}
                  {columns.map((column) => (
                    <td key={String(column.key)} className="px-3 py-3 align-top">
                      {column.render ? column.render(row) : String(row[column.key] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-4 flex items-center justify-between">
        <button
          type="button"
          disabled={pagination.page <= 1}
          onClick={() => onPageChange(pagination.page - 1)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <div className="text-sm text-slate-600">
          Page {pagination.page} / {pagination.total_pages}
        </div>
        <button
          type="button"
          disabled={pagination.page >= pagination.total_pages}
          onClick={() => onPageChange(pagination.page + 1)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  );
}
