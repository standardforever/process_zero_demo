"use client";

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { streamTransformerChatWithMessages } from "@/lib/api";
import { notifyRulesUpdated } from "@/lib/rules-sync";

const CHAT_STORAGE_KEY = "transformer_rules_chat_messages";
const MAX_STORED_MESSAGES = 200;

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type StreamEvent =
  | { type: "start" }
  | { type: "chunk"; content: string }
  | { type: "done"; result?: unknown }
  | { type: "error"; error?: string };

export function RulesChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const canSend = useMemo(() => !busy && input.trim().length > 0, [busy, input]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      const raw = window.localStorage.getItem(CHAT_STORAGE_KEY);
      if (!raw) return;

      const parsed = JSON.parse(raw) as unknown;
      if (!Array.isArray(parsed)) return;

      const restored = parsed.filter(isChatMessage).slice(-MAX_STORED_MESSAGES);
      if (restored.length > 0) {
        setMessages(restored);
      }
    } catch {
      window.localStorage.removeItem(CHAT_STORAGE_KEY);
    }
  }, []);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    try {
      if (messages.length === 0) {
        window.localStorage.removeItem(CHAT_STORAGE_KEY);
        return;
      }

      window.localStorage.setItem(
        CHAT_STORAGE_KEY,
        JSON.stringify(messages.slice(-MAX_STORED_MESSAGES)),
      );
    } catch {
      // Ignore storage quota and serialization failures.
    }
  }, [messages]);

  async function handleSend() {
    const prompt = input.trim();
    if (!prompt) return;

    setBusy(true);
    setError(null);

    let assistantIndex = -1;
    const requestMessages = messages
      .map((item) => ({ role: item.role, content: item.content }))
      .concat({ role: "user", content: prompt });

    setMessages((current) => {
      assistantIndex = current.length + 1;
      return [...current, { role: "user", content: prompt }, { role: "assistant", content: "" }];
    });
    setInput("");

    try {
      const response = await streamTransformerChatWithMessages(requestMessages, prompt);
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("Streaming response not available");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const rawEvent of events) {
          const dataLine = rawEvent
            .split("\n")
            .map((line) => line.trim())
            .find((line) => line.startsWith("data:"));

          if (!dataLine) continue;
          const payloadText = dataLine.slice(5).trim();
          if (!payloadText) continue;

          let event: StreamEvent;
          try {
            event = JSON.parse(payloadText) as StreamEvent;
          } catch {
            continue;
          }

          if (event.type === "chunk") {
            const chunk = event.content || "";
            setMessages((current) => {
              const next = [...current];
              if (assistantIndex < 0 || !next[assistantIndex]) return current;
              next[assistantIndex] = {
                ...next[assistantIndex],
                content: next[assistantIndex].content + chunk,
              };
              return next;
            });
          } else if (event.type === "done") {
            if (didApplyRuleChanges(event.result)) {
              notifyRulesUpdated();
            }
          } else if (event.type === "error") {
            throw new Error(event.error || "Chat request failed");
          }
        }
      }
    } catch (streamError) {
      const message = streamError instanceof Error ? streamError.message : "Failed to stream chat response";
      setError(message);
      setMessages((current) => {
        const next = [...current];
        if (assistantIndex >= 0 && next[assistantIndex] && !next[assistantIndex].content) {
          next[assistantIndex] = {
            ...next[assistantIndex],
            content: `Error: ${message}`,
          };
        }
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      if (!canSend) return;
      void handleSend();
    }
  }

  function handleClearHistory() {
    setMessages([]);
    setError(null);
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(CHAT_STORAGE_KEY);
    }
  }

  return (
    <section className="rounded-[28px] border border-slate-200 bg-white p-5 shadow-sm">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-900">Chat Page</h2>
          <p className="mt-1 text-sm text-slate-600">
            Ask AI to create, update, explain, or delete rules. This is separate from the manual Rules Page editor.
          </p>
        </div>
        <button
          type="button"
          onClick={handleClearHistory}
          disabled={busy || messages.length === 0}
          className="shrink-0 rounded-full border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 transition hover:border-slate-400 hover:text-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Clear Chat History
        </button>
      </div>

      <div
        ref={scrollRef}
        className="mb-4 max-h-[60vh] overflow-y-auto rounded-2xl border border-slate-200 bg-slate-50 p-4"
      >
        <div className="space-y-3">
          {messages.length === 0 && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-4 text-sm text-slate-500">
              Try:
              <br />
              <span className="font-medium">Set payment terms for Sony Entertainment to 15 Days</span>
            </div>
          )}

          {messages.map((message, index) => {
            const isUser = message.role === "user";
            return (
              <div key={`${message.role}-${index}`} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                    isUser
                      ? "rounded-br-md bg-cyan-700 text-white"
                      : "rounded-bl-md border border-slate-200 bg-white text-slate-900"
                  }`}
                >
                  <div
                    className={`mb-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                      isUser ? "text-cyan-100" : "text-slate-500"
                    }`}
                  >
                    {isUser ? "You" : "Assistant"}
                  </div>
                  <div className="whitespace-pre-wrap break-words">
                    {message.content || (!isUser && busy ? "..." : "")}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-3 py-2 shadow-sm">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Ask about rules, or tell AI what to create or update..."
            disabled={busy}
            className="h-11 w-full rounded-full border-0 bg-transparent px-3 text-sm text-slate-800 outline-none focus:ring-0"
          />
          <button
            type="button"
            onClick={() => {
              void handleSend();
            }}
            disabled={!canSend}
            aria-label="Send message"
            className="inline-flex h-11 w-11 items-center justify-center rounded-full bg-cyan-800 text-white shadow-sm disabled:opacity-60"
          >
            <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
              <path d="M3.4 20.4L21 12 3.4 3.6 3.3 10l12.6 2-12.6 2z" />
            </svg>
          </button>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-slate-500">AI changes go through the backend rule engine.</div>
          <div className="flex items-center gap-3">
            {error && <p className="text-sm font-medium text-red-700">{error}</p>}
            {busy && <p className="text-sm font-medium text-slate-500">Streaming...</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function isChatMessage(value: unknown): value is ChatMessage {
  if (!value || typeof value !== "object") return false;

  const candidate = value as { role?: unknown; content?: unknown };
  return (
    (candidate.role === "user" || candidate.role === "assistant") &&
    typeof candidate.content === "string"
  );
}

function didApplyRuleChanges(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;

  const candidate = value as { payload?: unknown };
  if (!candidate.payload || typeof candidate.payload !== "object") return false;

  const payload = candidate.payload as { applied?: unknown };
  return payload.applied === true;
}
