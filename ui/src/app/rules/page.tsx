"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

import { streamTransformerChat } from "@/lib/api";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type StreamEvent =
  | { type: "start" }
  | { type: "chunk"; content: string }
  | { type: "done"; result?: unknown }
  | { type: "error"; error?: string };

const CHAT_STORAGE_KEY = "transformer_rules_chat_history_v1";
const LINK_PATTERN = /(https?:\/\/[^\s]+|\/transformer\/schema)/g;

function renderMessageWithLinks(content: string): ReactNode {
  const lines = content.split("\n");
  return lines.map((line, lineIndex) => {
    const parts = line.split(LINK_PATTERN);
    return (
      <span key={`line-${lineIndex}`}>
        {parts.map((part, partIndex) => {
          const value = part.trim();
          if (value === "/transformer/schema") {
            return (
              <Link
                key={`part-${lineIndex}-${partIndex}`}
                href="/schema"
                className="font-medium text-cyan-300 underline hover:text-cyan-200">
                Open Schema Setup
              </Link>
            );
          }

          if (value.startsWith("http://") || value.startsWith("https://")) {
            return (
              <a
                key={`part-${lineIndex}-${partIndex}`}
                href={value}
                target="_blank"
                rel="noreferrer"
                className="font-medium text-cyan-300 underline hover:text-cyan-200">
                {value}
              </a>
            );
          }

          return <span key={`part-${lineIndex}-${partIndex}`}>{part}</span>;
        })}
        {lineIndex < lines.length - 1 ? <br /> : null}
      </span>
    );
  });
}

export default function RulesPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const canSend = useMemo(() => !busy && input.trim().length > 0, [busy, input]);

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(CHAT_STORAGE_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as ChatMessage[];
      if (!Array.isArray(parsed)) return;
      const valid = parsed.filter(
        (item) =>
          item &&
          (item.role === "user" || item.role === "assistant") &&
          typeof item.content === "string",
      );
      setMessages(valid.slice(-200));
    } catch {
      // ignore broken local storage payloads
    }
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages.slice(-200)));
    } catch {
      // ignore storage failures
    }
  }, [messages]);

  useEffect(() => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages, busy]);

  async function handleSend() {
    const prompt = input.trim();
    if (!prompt) return;

    setBusy(true);
    setError(null);

    let assistantIndex = -1;
    setMessages((current) => {
      assistantIndex = current.length + 1;
      return [...current, { role: "user", content: prompt }, { role: "assistant", content: "" }];
    });
    setInput("");

    try {
      const response = await streamTransformerChat(prompt);
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
          next[assistantIndex] = { ...next[assistantIndex], content: `Error: ${message}` };
        }
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function handleClearHistory() {
    setMessages([]);
    setError(null);
    try {
      window.localStorage.removeItem(CHAT_STORAGE_KEY);
    } catch {
      // ignore storage failures
    }
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    if (!canSend) return;
    void handleSend();
  }

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <div className="mx-auto max-w-5xl space-y-4">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Rules Chat</h1>
          <p className="text-sm text-slate-600">
            Chat with AI to create, update, search, and manage transformation rules.
          </p>
          <div className="flex items-center gap-4">
            <Link href="/schema" className="text-sm font-medium text-cyan-700 hover:text-cyan-800">
              Open Schema Setup
            </Link>
            <button
              type="button"
              onClick={handleClearHistory}
              className="rounded-md bg-slate-200 px-3 py-1.5 text-xs font-medium text-slate-700 hover:bg-slate-300">
              Clear Chat History
            </button>
          </div>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div
            ref={scrollRef}
            className="mb-4 flex max-h-[58vh] flex-col gap-3 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
            {messages.length === 0 && (
              <div className="rounded-lg border border-dashed border-slate-300 bg-white p-3 text-sm text-slate-500">
                Say hello, ask for help, or start with:
                <br />
                <span className="font-medium">
                  Add a rule in sales_tax_rate: if customer_name equals &quot;ACME&quot;, set value to &quot;10%&quot;
                </span>
              </div>
            )}

            {messages.map((message, index) => {
              const isUser = message.role === "user";
              return (
                <div key={`${message.role}-${index}`} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[78%] rounded-2xl px-4 py-2 text-sm shadow-sm ${
                      isUser
                        ? "rounded-br-md bg-cyan-700 text-white"
                        : "rounded-bl-md border border-slate-200 bg-white text-slate-900"
                    }`}>
                    <p className={`mb-1 text-[11px] font-semibold ${isUser ? "text-cyan-100" : "text-slate-500"}`}>
                      {isUser ? "You" : "Assistant"}
                    </p>
                    <div className="whitespace-pre-wrap break-words">
                      {message.content
                        ? renderMessageWithLinks(message.content)
                        : !isUser && busy
                          ? "..."
                          : ""}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="space-y-2">
            <div className="flex items-center gap-2 rounded-full border border-slate-300 bg-white px-2 py-2 shadow-sm">
              <input
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="Type your message..."
                className="h-10 w-full rounded-full border-0 bg-transparent px-3 text-sm text-slate-800 outline-none focus:ring-0"
                disabled={busy}
              />
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!canSend}
                aria-label={busy ? "Streaming response" : "Send message"}
                className="inline-flex h-10 w-10 items-center justify-center rounded-full bg-cyan-800 text-white disabled:opacity-60">
                <svg viewBox="0 0 24 24" className="h-5 w-5 fill-current" aria-hidden="true">
                  <path d="M3.4 20.4L21 12 3.4 3.6 3.3 10l12.6 2-12.6 2z" />
                </svg>
              </button>
            </div>
            <div className="flex items-center gap-3">
              {busy && <p className="text-xs font-medium text-slate-500">Streaming...</p>}
              {error && <p className="text-sm font-medium text-red-700">{error}</p>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
