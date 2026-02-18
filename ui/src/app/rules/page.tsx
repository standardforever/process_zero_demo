"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

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

export default function RulesPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSend = useMemo(() => !busy && input.trim().length > 0, [busy, input]);

  async function handleSend() {
    const prompt = input.trim();
    if (!prompt) return;

    setBusy(true);
    setError(null);

    const assistantIndex = messages.length + 1;
    setMessages((current) => [
      ...current,
      { role: "user", content: prompt },
      { role: "assistant", content: "" },
    ]);
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
              if (!next[assistantIndex]) return current;
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
        if (next[assistantIndex] && !next[assistantIndex].content) {
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

  return (
    <div className="min-h-screen bg-slate-50 px-6 py-8">
      <div className="mx-auto max-w-4xl space-y-4">
        <header className="space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Rules Chat</h1>
          <p className="text-sm text-slate-600">
            Chat with AI to create, update, search, and manage transformation rules.
          </p>
          <Link href="/schema" className="inline-block text-sm font-medium text-cyan-700 hover:text-cyan-800">
            Open Schema Setup
          </Link>
        </header>

        <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="mb-4 max-h-[55vh] space-y-3 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
            {messages.length === 0 && (
              <p className="text-sm text-slate-500">
                Start by describing a rule change. Example: Add a sales_tax_rate rule for customer &quot;ACME&quot; set to 10%.
              </p>
            )}
            {messages.map((message, index) => (
              <div
                key={`${message.role}-${index}`}
                className={message.role === "user" ? "text-slate-900" : "text-cyan-900"}>
                <span className="font-semibold">{message.role === "user" ? "You" : "Assistant"}:</span>{" "}
                <span className="whitespace-pre-wrap">{message.content || (busy && message.role === "assistant" ? "..." : "")}</span>
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Describe the rule operation you want..."
              className="min-h-[110px] w-full rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-800 outline-none ring-cyan-600 focus:ring"
              disabled={busy}
            />
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void handleSend()}
                disabled={!canSend}
                className="rounded-md bg-cyan-800 px-4 py-2 text-sm font-medium text-white disabled:opacity-60">
                {busy ? "Streaming..." : "Send"}
              </button>
              {error && <p className="text-sm font-medium text-red-700">{error}</p>}
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
