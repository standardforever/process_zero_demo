import { API_BASE } from "./constants";
import type { RuleRecord, RulesStore } from "./types";

const AGENT_RULES_KEY = "transformAgentRules";

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
  ping: async (): Promise<boolean> => {
    try {
      const response = await fetch(`${API_BASE}/api/`, { signal: AbortSignal.timeout(3000) });
      return response.ok;
    } catch {
      return false;
    }
  },
};
