"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import {
  addCRMColumn,
  deleteCRMColumn,
  deleteERPSchemaColumn,
  getSchemaStore,
  getSchemaStoreStatus,
  renameCRMColumn,
  upsertERPSchemaColumn,
} from "@/lib/api";
import { ERPSchemaColumn, SchemaStore, SchemaStoreStatus } from "@/lib/types";

const emptySchemaStore: SchemaStore = {
  erp_schema: {},
  post_transformation_actions: {},
  metadata: {
    crm_columns: [],
    erp_system: "Odoo",
    version: "1.0.0",
    last_updated: "",
  },
};

const emptySchemaStatus: SchemaStoreStatus = {
  erp_columns_count: 0,
  crm_columns_count: 0,
  has_erp_columns: false,
  has_crm_columns: false,
  can_use_chat: false,
};

function parseDefaultValue(text: string): unknown {
  const trimmed = text.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

export default function SchemaPage() {
  const [schemaStore, setSchemaStore] = useState<SchemaStore>(emptySchemaStore);
  const [schemaStatus, setSchemaStatus] = useState<SchemaStoreStatus>(emptySchemaStatus);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [erpOriginalName, setErpOriginalName] = useState<string | null>(null);
  const [erpName, setErpName] = useState("");
  const [erpDataType, setErpDataType] = useState("string");
  const [erpRequired, setErpRequired] = useState("false");
  const [erpDescription, setErpDescription] = useState("");
  const [erpDefaultValue, setErpDefaultValue] = useState("");
  const [erpRulesText, setErpRulesText] = useState("{}");

  const [crmColumnName, setCrmColumnName] = useState("");
  const [crmEditingOriginal, setCrmEditingOriginal] = useState<string | null>(null);
  const [crmEditingValue, setCrmEditingValue] = useState("");

  const refreshSchema = useCallback(async () => {
    const [store, statusPayload] = await Promise.all([getSchemaStore(), getSchemaStoreStatus()]);
    setSchemaStore(store);
    setSchemaStatus(statusPayload);
  }, []);

  useEffect(() => {
    async function load() {
      try {
        await refreshSchema();
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load schema setup");
      }
    }

    void load();
  }, [refreshSchema]);

  function resetErpForm() {
    setErpOriginalName(null);
    setErpName("");
    setErpDataType("string");
    setErpRequired("false");
    setErpDescription("");
    setErpDefaultValue("");
    setErpRulesText("{}");
  }

  function startEditErp(name: string, column: ERPSchemaColumn) {
    setErpOriginalName(name);
    setErpName(name);
    setErpDataType(column.data_type || "string");
    setErpRequired(column.required ? "true" : "false");
    setErpDescription(column.description || "");
    setErpDefaultValue(
      column.default_value === null || typeof column.default_value === "undefined"
        ? ""
        : JSON.stringify(column.default_value),
    );
    setErpRulesText(JSON.stringify(column.rules || {}, null, 2));
  }

  async function handleSaveErpColumn() {
    const trimmedName = erpName.trim();
    if (!trimmedName) {
      setError("ERP column name is required.");
      return;
    }

    let parsedRules: Record<string, unknown> = {};
    try {
      const payload = erpRulesText.trim() ? JSON.parse(erpRulesText) : {};
      if (!payload || Array.isArray(payload) || typeof payload !== "object") {
        throw new Error("Rules must be a JSON object");
      }
      parsedRules = payload as Record<string, unknown>;
    } catch {
      setError("ERP rules must be a valid JSON object.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      const payload: ERPSchemaColumn = {
        default_value: parseDefaultValue(erpDefaultValue),
        data_type: erpDataType.trim() || "string",
        required: erpRequired === "true",
        description: erpDescription.trim(),
        rules: parsedRules,
      };

      await upsertERPSchemaColumn(trimmedName, payload);
      if (erpOriginalName && erpOriginalName !== trimmedName) {
        await deleteERPSchemaColumn(erpOriginalName);
      }

      await refreshSchema();
      resetErpForm();
      setStatus(`ERP column '${trimmedName}' saved`);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "Failed to save ERP column");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteErpColumn(name: string) {
    setBusy(true);
    setError(null);

    try {
      await deleteERPSchemaColumn(name);
      await refreshSchema();

      if (erpOriginalName === name) {
        resetErpForm();
      }

      setStatus(`ERP column '${name}' deleted`);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete ERP column");
    } finally {
      setBusy(false);
    }
  }

  async function handleAddCrmColumn() {
    const name = crmColumnName.trim();
    if (!name) {
      setError("CRM column name is required.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await addCRMColumn(name);
      await refreshSchema();
      setCrmColumnName("");
      setStatus(`CRM column '${name}' added`);
    } catch (addError) {
      setError(addError instanceof Error ? addError.message : "Failed to add CRM column");
    } finally {
      setBusy(false);
    }
  }

  async function handleRenameCrmColumn() {
    if (!crmEditingOriginal) return;

    const newName = crmEditingValue.trim();
    if (!newName) {
      setError("CRM column name is required.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      await renameCRMColumn(crmEditingOriginal, newName);
      await refreshSchema();
      setStatus(`CRM column '${crmEditingOriginal}' renamed to '${newName}'`);
      setCrmEditingOriginal(null);
      setCrmEditingValue("");
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "Failed to rename CRM column");
    } finally {
      setBusy(false);
    }
  }

  async function handleDeleteCrmColumn(name: string) {
    setBusy(true);
    setError(null);

    try {
      await deleteCRMColumn(name);
      await refreshSchema();
      setStatus(`CRM column '${name}' deleted`);
      if (crmEditingOriginal === name) {
        setCrmEditingOriginal(null);
        setCrmEditingValue("");
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to delete CRM column");
    } finally {
      setBusy(false);
    }
  }

  const erpEntries = Object.entries(schemaStore.erp_schema || {});
  const crmColumns = schemaStore.metadata?.crm_columns || [];

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <div className="mx-auto max-w-6xl space-y-5">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Schema Setup</h1>
          <p className="text-sm text-slate-600">
            Configure ERP and CRM columns here. You must add at least one of each before accessing Rules chat.
          </p>
          <p className="text-sm text-slate-700">
            ERP columns: {schemaStatus.erp_columns_count} | CRM columns: {schemaStatus.crm_columns_count} | Access: {" "}
            <span className={schemaStatus.can_use_chat ? "font-semibold text-emerald-700" : "font-semibold text-amber-700"}>
              {schemaStatus.can_use_chat ? "Ready" : "Locked"}
            </span>
          </p>
          {status && <p className="text-sm font-semibold text-emerald-700">{status}</p>}
          {error && <p className="text-sm font-semibold text-red-700">{error}</p>}
          <div className="pt-1">
            {schemaStatus.can_use_chat ? (
              <Link
                href="/rules"
                className="inline-block rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800">
                Go to Rules
              </Link>
            ) : (
              <button
                type="button"
                disabled
                className="inline-block cursor-not-allowed rounded-md bg-slate-300 px-4 py-2 text-sm font-medium text-slate-600">
                Go to Rules
              </button>
            )}
          </div>
        </header>

        <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
          <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">ERP Columns ({erpEntries.length})</h2>
            <div className="max-h-80 space-y-2 overflow-auto rounded-lg border border-slate-200 p-3">
              {erpEntries.map(([name, column]) => (
                <div key={name} className="rounded-md border border-slate-200 p-2 text-sm">
                  <p className="font-semibold text-slate-900">{name}</p>
                  <p className="text-slate-600">type: {column.data_type || "string"}</p>
                  <p className="text-slate-600">required: {column.required ? "Yes" : "No"}</p>
                  <p className="text-slate-600">description: {column.description || "-"}</p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      onClick={() => startEditErp(name, column)}
                      className="rounded-md bg-cyan-700 px-2 py-1 text-xs font-medium text-white">
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleDeleteErpColumn(name)}
                      disabled={busy}
                      className="rounded-md bg-red-700 px-2 py-1 text-xs font-medium text-white disabled:opacity-60">
                      Delete
                    </button>
                  </div>
                </div>
              ))}
              {!erpEntries.length && <p className="text-sm text-slate-500">No ERP columns added yet.</p>}
            </div>

            <div className="space-y-2 rounded-lg border border-slate-200 p-3">
              <h3 className="text-sm font-semibold text-slate-900">
                {erpOriginalName ? `Edit ERP Column: ${erpOriginalName}` : "Add ERP Column"}
              </h3>
              <input
                value={erpName}
                onChange={(event) => setErpName(event.target.value)}
                placeholder="Column name (e.g. invoice_date)"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={erpDataType}
                onChange={(event) => setErpDataType(event.target.value)}
                placeholder="Data type (string, date, number...)"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <div>
                <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500">Required Field</label>
                <select
                  value={erpRequired}
                  onChange={(event) => setErpRequired(event.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm">
                  <option value="false">Not required (default)</option>
                  <option value="true">Required</option>
                </select>
              </div>
              <input
                value={erpDescription}
                onChange={(event) => setErpDescription(event.target.value)}
                placeholder="Description"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <input
                value={erpDefaultValue}
                onChange={(event) => setErpDefaultValue(event.target.value)}
                placeholder="Default value (plain text or JSON literal)"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <textarea
                value={erpRulesText}
                onChange={(event) => setErpRulesText(event.target.value)}
                placeholder='Rules JSON object, e.g. {"UK":"10%"}'
                className="min-h-[120px] w-full rounded-md border border-slate-300 px-3 py-2 text-xs"
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => void handleSaveErpColumn()}
                  disabled={busy}
                  className="rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">
                  {erpOriginalName ? "Update ERP Column" : "Add ERP Column"}
                </button>
                <button
                  type="button"
                  onClick={resetErpForm}
                  className="rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700">
                  Reset
                </button>
              </div>
            </div>
          </section>

          <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-base font-semibold text-slate-900">CRM Columns ({crmColumns.length})</h2>

            <div className="flex gap-2">
              <input
                value={crmColumnName}
                onChange={(event) => setCrmColumnName(event.target.value)}
                placeholder="Add CRM column name"
                className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => void handleAddCrmColumn()}
                disabled={busy}
                className="rounded-md bg-emerald-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">
                Add
              </button>
            </div>

            <div className="max-h-[70vh] space-y-2 overflow-auto rounded-lg border border-slate-200 p-3">
              {crmColumns.map((name) => (
                <div key={name} className="rounded-md border border-slate-200 p-2">
                  {crmEditingOriginal === name ? (
                    <div className="flex gap-2">
                      <input
                        value={crmEditingValue}
                        onChange={(event) => setCrmEditingValue(event.target.value)}
                        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
                      />
                      <button
                        type="button"
                        onClick={() => void handleRenameCrmColumn()}
                        disabled={busy}
                        className="rounded-md bg-cyan-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">
                        Save
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setCrmEditingOriginal(null);
                          setCrmEditingValue("");
                        }}
                        className="rounded-md bg-slate-100 px-3 py-2 text-sm font-medium text-slate-700">
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm text-slate-900">{name}</p>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setCrmEditingOriginal(name);
                            setCrmEditingValue(name);
                          }}
                          className="rounded-md bg-cyan-700 px-2 py-1 text-xs font-medium text-white">
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleDeleteCrmColumn(name)}
                          disabled={busy}
                          className="rounded-md bg-red-700 px-2 py-1 text-xs font-medium text-white disabled:opacity-60">
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))}
              {!crmColumns.length && <p className="text-sm text-slate-500">No CRM columns added yet.</p>}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
