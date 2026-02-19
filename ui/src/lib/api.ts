import {
  CRMRecord,
  DataStats,
  ERPSchemaColumn,
  PaginatedCRMRecords,
  RulesAICopilotMessage,
  RulesAICopilotResponse,
  RulesAIExplainResponse,
  RulesAIUpdateResponse,
  SchemaStore,
  SchemaStoreStatus,
  TransformBatchResponse,
  TransformOutput,
  TransformPreviewResponse,
  TransformRules,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") || "/transformer/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail || detail;
    } catch {
      // no-op
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function getCRMData(params: {
  page?: number;
  limit?: number;
  search?: string;
}): Promise<PaginatedCRMRecords> {
  const query = new URLSearchParams();

  if (params.page) query.set("page", String(params.page));
  if (params.limit) query.set("limit", String(params.limit));
  if (params.search) query.set("search", params.search);

  const search = query.toString();
  return request<PaginatedCRMRecords>(`/data${search ? `?${search}` : ""}`);
}

export async function getCustomers(): Promise<string[]> {
  const response = await request<{ customers: string[] }>("/data/customers");
  return response.customers;
}

export function getDataStats(): Promise<DataStats> {
  return request<DataStats>("/data/stats");
}

export function getRules(): Promise<TransformRules> {
  return request<TransformRules>("/rules");
}

export function updateRules(payload: TransformRules): Promise<TransformRules> {
  return request<TransformRules>("/rules", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export async function getRuleType<T>(ruleType: string): Promise<T> {
  const response = await request<{ type: string; data: T }>(`/rules/${ruleType}`);
  return response.data;
}

export async function updateRuleType<T>(ruleType: string, payload: T): Promise<T> {
  const response = await request<{ type: string; data: T }>(`/rules/${ruleType}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return response.data;
}

export function previewTransformByRef(salesRequestRef: string): Promise<TransformPreviewResponse> {
  return request<TransformPreviewResponse>("/transform/preview", {
    method: "POST",
    body: JSON.stringify({ sales_request_ref: salesRequestRef }),
  });
}

export function previewTransformByRecord(record: CRMRecord): Promise<TransformPreviewResponse> {
  return request<TransformPreviewResponse>("/transform/preview", {
    method: "POST",
    body: JSON.stringify({ record }),
  });
}

export function batchTransform(salesRequestRefs: string[]): Promise<TransformBatchResponse> {
  return request<TransformBatchResponse>("/transform/batch", {
    method: "POST",
    body: JSON.stringify({ sales_request_refs: salesRequestRefs }),
  });
}

export function getTransformOutput(): Promise<TransformOutput> {
  return request<TransformOutput>("/transform/output");
}

export function previewRulesAIUpdate(instruction: string): Promise<RulesAIUpdateResponse> {
  return request<RulesAIUpdateResponse>("/rules/ai/update", {
    method: "POST",
    body: JSON.stringify({ instruction, apply: false }),
  });
}

export function applyRulesAIUpdate(instruction: string): Promise<RulesAIUpdateResponse> {
  return request<RulesAIUpdateResponse>("/rules/ai/update", {
    method: "POST",
    body: JSON.stringify({ instruction, apply: true }),
  });
}

export function explainRulesForSituation(situation: string): Promise<RulesAIExplainResponse> {
  return request<RulesAIExplainResponse>("/rules/ai/explain", {
    method: "POST",
    body: JSON.stringify({ situation }),
  });
}

export function askRulesCopilot(
  messages: RulesAICopilotMessage[],
  apply = false,
): Promise<RulesAICopilotResponse> {
  return request<RulesAICopilotResponse>("/rules/ai/copilot", {
    method: "POST",
    body: JSON.stringify({ messages, apply }),
  });
}

export function getSchemaStore(): Promise<SchemaStore> {
  return request<SchemaStore>("/schema-store");
}

export function getSchemaStoreStatus(): Promise<SchemaStoreStatus> {
  return request<SchemaStoreStatus>("/schema-store/status");
}

export function updateSchemaStore(payload: SchemaStore): Promise<SchemaStore> {
  return request<SchemaStore>("/schema-store", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function upsertERPSchemaColumn(columnName: string, payload: ERPSchemaColumn): Promise<SchemaStore> {
  return request<SchemaStore>(`/schema-store/erp/${encodeURIComponent(columnName)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function deleteERPSchemaColumn(columnName: string): Promise<SchemaStore> {
  return request<SchemaStore>(`/schema-store/erp/${encodeURIComponent(columnName)}`, {
    method: "DELETE",
  });
}

export function addCRMColumn(columnName: string): Promise<SchemaStore> {
  return request<SchemaStore>("/schema-store/crm", {
    method: "POST",
    body: JSON.stringify({ column_name: columnName }),
  });
}

export function renameCRMColumn(columnName: string, newName: string): Promise<SchemaStore> {
  return request<SchemaStore>(`/schema-store/crm/${encodeURIComponent(columnName)}`, {
    method: "PUT",
    body: JSON.stringify({ new_name: newName }),
  });
}

export function deleteCRMColumn(columnName: string): Promise<SchemaStore> {
  return request<SchemaStore>(`/schema-store/crm/${encodeURIComponent(columnName)}`, {
    method: "DELETE",
  });
}

export function addNotificationEmail(email: string): Promise<SchemaStore> {
  return request<SchemaStore>("/schema-store/notifications/email", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function renameNotificationEmail(email: string, newEmail: string): Promise<SchemaStore> {
  return request<SchemaStore>(`/schema-store/notifications/email/${encodeURIComponent(email)}`, {
    method: "PUT",
    body: JSON.stringify({ new_email: newEmail }),
  });
}

export function deleteNotificationEmail(email: string): Promise<SchemaStore> {
  return request<SchemaStore>(`/schema-store/notifications/email/${encodeURIComponent(email)}`, {
    method: "DELETE",
  });
}

export async function streamTransformerChat(message: string): Promise<Response> {
  const response = await fetch(`${API_BASE_URL}/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail || detail;
    } catch {
      // no-op
    }
    throw new Error(detail);
  }

  return response;
}
