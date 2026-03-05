import { RulesChatPanel } from "@/components/rules-chat-panel";

export default function WorkbenchChatPage() {
  return (
    <section className="space-y-3">
      <div className="px-1">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[#8ec5ff]">Chat Page</p>
        <h2 className="mt-2 text-2xl font-semibold text-white">AI-assisted rule editing</h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--pz-muted)]">
          Use natural language to create, update, explain, and delete rules.
        </p>
      </div>
      <RulesChatPanel />
    </section>
  );
}
