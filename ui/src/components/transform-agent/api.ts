import { API_BASE } from "./constants";
import type { RuleRecord, RulesStore } from "./types";

const AGENT_RULES_KEY = "transformAgentRules";
const NOTIFICATION_EMAIL_KEY = "notificationEmail";

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const json = (await response.json()) as { detail?: string };
      detail = json.detail ?? detail;
    } catch {
      // keep default detail
    }
    throw new Error(detail);
  }

  if (response.status === 204) return null as T;
  return (await response.json()) as T;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function extractAgentRules(payload: unknown): RulesStore {
  if (!isObject(payload)) return {};
  const section = payload[AGENT_RULES_KEY];
  if (!isObject(section)) return {};
  return section as RulesStore;
}

function extractNotificationEmail(payload: unknown): string | null {
  if (!isObject(payload)) return null;
  const value = payload[NOTIFICATION_EMAIL_KEY];
  if (typeof value !== "string") return null;
  const normalized = value.trim();
  return normalized ? normalized : null;
}

async function loadRawRulesPayload(): Promise<Record<string, unknown>> {
  const payload = await request<unknown>("GET", "/api/rules");
  return isObject(payload) ? payload : {};
}

export const rulesApi = {
  list: async (): Promise<RulesStore> => {
    const raw = await loadRawRulesPayload();
    return extractAgentRules(raw);
  },
  get: async (name: string): Promise<RuleRecord> => {
    const rules = await rulesApi.list();
    const rule = rules[name];
    if (!rule) {
      throw new Error(`Rule for '${name}' not found`);
    }
    return rule;
  },
  add: async (name: string, rule: RuleRecord): Promise<{ customer_name: string; rule: RuleRecord }> => {
    const raw = await loadRawRulesPayload();
    const existing = extractAgentRules(raw);
    if (name in existing) {
      throw new Error(`Rule for '${name}' already exists`);
    }
    raw[AGENT_RULES_KEY] = { ...existing, [name]: rule };
    await request("PUT", "/api/rules", raw);
    return { customer_name: name, rule };
  },
  update: async (name: string, rule: RuleRecord): Promise<{ customer_name: string; rule: RuleRecord }> => {
    const raw = await loadRawRulesPayload();
    const existing = extractAgentRules(raw);
    if (!(name in existing)) {
      throw new Error(`Rule for '${name}' not found`);
    }
    raw[AGENT_RULES_KEY] = { ...existing, [name]: rule };
    await request("PUT", "/api/rules", raw);
    return { customer_name: name, rule };
  },
  del: async (name: string): Promise<{ deleted: string; remaining: number }> => {
    const raw = await loadRawRulesPayload();
    const existing = extractAgentRules(raw);
    if (!(name in existing)) {
      throw new Error(`Rule for '${name}' not found`);
    }
    const nextRules: RulesStore = { ...existing };
    delete nextRules[name];
    raw[AGENT_RULES_KEY] = nextRules;
    await request("PUT", "/api/rules", raw);
    return { deleted: name, remaining: Object.keys(nextRules).length };
  },
  getNotificationEmail: async (): Promise<string | null> => {
    const raw = await loadRawRulesPayload();
    return extractNotificationEmail(raw);
  },
  addNotificationEmail: async (email: string): Promise<string> => {
    const raw = await loadRawRulesPayload();
    const existing = extractNotificationEmail(raw);
    if (existing) {
      throw new Error("Notification email already exists. Use update email.");
    }
    raw[NOTIFICATION_EMAIL_KEY] = email;
    await request("PUT", "/api/rules", raw);
    return email;
  },
  updateNotificationEmail: async (email: string): Promise<string> => {
    const raw = await loadRawRulesPayload();
    const existing = extractNotificationEmail(raw);
    if (!existing) {
      throw new Error("No notification email found. Use add email first.");
    }
    raw[NOTIFICATION_EMAIL_KEY] = email;
    await request("PUT", "/api/rules", raw);
    return email;
  },
  deleteNotificationEmail: async (): Promise<void> => {
    const raw = await loadRawRulesPayload();
    const existing = extractNotificationEmail(raw);
    if (!existing) {
      throw new Error("No notification email found.");
    }
    delete raw[NOTIFICATION_EMAIL_KEY];
    await request("PUT", "/api/rules", raw);
  },
  ping: async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/`, { signal: AbortSignal.timeout(3000) });
      return response.ok;
    } catch {
      return false;
    }
  },
};
