"use client";

export const RULES_SYNC_EVENT = "transformer-rules-updated";
export const RULES_SYNC_STORAGE_KEY = "transformer_rules_last_updated";

export function notifyRulesUpdated(): void {
  if (typeof window === "undefined") return;

  const timestamp = String(Date.now());

  try {
    window.localStorage.setItem(RULES_SYNC_STORAGE_KEY, timestamp);
  } catch {
    // Ignore storage write failures.
  }

  window.dispatchEvent(
    new CustomEvent(RULES_SYNC_EVENT, {
      detail: { updatedAt: timestamp },
    }),
  );
}
