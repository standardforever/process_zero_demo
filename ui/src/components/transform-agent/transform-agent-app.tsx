"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { rulesApi } from "./api";
import { MENU_ITEMS, WELCOME_MESSAGE } from "./constants";
import {
  BotIcon,
  CheckIcon,
  ChevronDownIcon,
  RulesIcon,
  SendIcon,
} from "./icons";
import { InlineRuleForm } from "./inline-rule-form";
import { AgentBubble, UserBubble } from "./message-bubbles";
import {
  ConfirmDeleteCard,
  RuleDetailCard,
  RuleSummaryCard,
  RulesListCard,
} from "./rule-cards";
import type {
  AgentPayload,
  ChatMessage,
  ChatMode,
  FormValues,
  Intent,
  MenuItemId,
  RuleAction,
  RuleRecord,
  RulesStore,
} from "./types";
import {
  currentTime,
  findRuleName,
  makeDefaults,
  makeId,
  parseIntent,
  suggestCommands,
} from "./utils";

function toRuleRecord(form: FormValues): RuleRecord {
  return {
    erp_customer_name: form.erp_customer_name,
    taxes: form.taxes,
    terms_and_conditions: form.terms_and_conditions,
    payment_method: form.payment_method,
    sales_person: form.sales_person,
    payment_terms: form.payment_terms,
    payment_reference: form.payment_reference,
    customer_reference: form.customer_reference,
    invoice_date: form.invoice_date,
    invoice_reference: form.invoice_reference,
  };
}

function isCommandIntent(intent: Intent): boolean {
  return ["ADD_RULE", "LIST_RULES", "EDIT_RULE", "DELETE_RULE", "GET_RULE", "HELP"].includes(intent.type);
}

export function TransformAgentApp() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [rules, setRules] = useState<RulesStore>({});
  const [input, setInput] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [chatMode, setChatMode] = useState<ChatMode>(null);
  const [formData, setFormData] = useState<FormValues | null>(null);
  const [pendingRuleName, setPendingRuleName] = useState<string | null>(null);
  const [apiStatus, setApiStatus] = useState<"connecting" | "online" | "offline">("connecting");
  const [apiLoading, setApiLoading] = useState(false);

  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const rulesRef = useRef<RulesStore>({});

  useEffect(() => {
    rulesRef.current = rules;
  }, [rules]);

  const pushUser = useCallback((text: string) => {
    const next: ChatMessage = { id: makeId(), role: "user", text, time: currentTime() };
    setMessages((prev) => [...prev, next]);
  }, []);

  const pushAgent = useCallback((message: AgentPayload) => {
    const next = {
      ...message,
      id: makeId(),
      role: "agent",
      time: currentTime(),
    } as ChatMessage;
    setMessages((prev) => [...prev, next]);
  }, []);

  const say = useCallback((text: string) => pushAgent({ kind: "stream", text }), [pushAgent]);

  const refreshRules = useCallback(async (): Promise<RulesStore> => {
    try {
      setApiLoading(true);
      const nextRules = await rulesApi.list();
      setRules(nextRules);
      return nextRules;
    } catch (error) {
      const message = error instanceof Error ? error.message : "Could not load rules.";
      say(`⚠️ **API Error:** ${message}`);
      return rulesRef.current;
    } finally {
      setApiLoading(false);
    }
  }, [say]);

  useEffect(() => {
    (async () => {
      const alive = await rulesApi.ping();
      if (!alive) {
        setApiStatus("offline");
        return;
      }
      setApiStatus("online");
      await refreshRules();
    })();
  }, [refreshRules]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const closeOnOutside = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) setMenuOpen(false);
    };
    document.addEventListener("mousedown", closeOnOutside);
    return () => document.removeEventListener("mousedown", closeOnOutside);
  }, []);

  const cancelFormMode = () => {
    setChatMode(null);
    setFormData(null);
    setPendingRuleName(null);
    setMessages((prev) => prev.filter((msg) => !(msg.role === "agent" && msg.kind === "inline_form")));
    say("Okay, cancelled. What do you want to do next?");
  };

  const startEditFlow = (name: string, data: RuleRecord) => {
    say(`Loading the rule for **${name}**. Update fields and click **Send** to save.`);
    setTimeout(() => {
      setFormData(makeDefaults({ ...data, customer_name: name }));
      setPendingRuleName(name);
      setChatMode("submit_edit");
      pushAgent({ kind: "inline_form", formSubmitted: false });
    }, 350);
  };

  const startDeleteFlow = (name: string) => {
    setPendingRuleName(name);
    setChatMode("confirm_delete");
    say(`I found **${name}**. Confirm deletion?`);
    setTimeout(() => pushAgent({ kind: "confirm_delete", data: { name } }), 300);
  };

  const dispatchIntent = async (intent: Intent) => {
    if (intent.type === "ADD_RULE") {
      say("Create a new rule: fill the CRM to ERP mapping below, then click **Send**.");
      setTimeout(() => {
        setFormData(makeDefaults());
        setChatMode("submit_add");
        pushAgent({ kind: "inline_form", formSubmitted: false });
      }, 300);
      return;
    }

    if (intent.type === "LIST_RULES") {
      const nextRules = await refreshRules();
      const count = Object.keys(nextRules).length;
      say(count ? `Found **${count}** active rule${count === 1 ? "" : "s"}:` : "No rules configured yet. Type **add rule** to create one.");
      if (count) setTimeout(() => pushAgent({ kind: "rules_list" }), 300);
      return;
    }

    if (intent.type === "EDIT_RULE") {
      const found = intent.name ? findRuleName(intent.name, rules) : null;
      if (!found) {
        setChatMode("await_edit_name");
        say("Which customer rule should I edit? Type the exact name.");
        return;
      }
      startEditFlow(found, rules[found] ?? {});
      return;
    }

    if (intent.type === "DELETE_RULE") {
      const found = intent.name ? findRuleName(intent.name, rules) : null;
      if (!found) {
        setChatMode("await_delete_name");
        say("Which customer rule should I delete? Type the exact name.");
        return;
      }
      startDeleteFlow(found);
      return;
    }

    if (intent.type === "GET_RULE") {
      const found = intent.name ? findRuleName(intent.name, rules) : null;
      if (!found) {
        setChatMode("await_get_name");
        say("Which customer rule should I show? Type the exact name.");
        return;
      }
      say(`Here is the configuration for **${found}**:`);
      setTimeout(() => pushAgent({ kind: "rule_detail", data: { name: found, rule: rules[found] ?? {} } }), 300);
      return;
    }

    if (intent.type === "HELP") {
      say("Commands: **add rule**, **list rules**, **edit rule <name>**, **delete rule <name>**, **get rule <name>**, **cancel**.");
      return;
    }

    const userText = intent.type === "CHAT" ? intent.text : intent.type === "YES" ? "yes" : "no";
    const suggestions = suggestCommands(userText);
    const suggestionLines = suggestions.map((command, index) => `${index + 1}. **${command}**`).join("\n");
    say(
      "Command not found. Use one of the available commands:\n" +
        "1. **add rule**\n" +
        "2. **list rules**\n" +
        "3. **edit rule <name>**\n" +
        "4. **delete rule <name>**\n" +
        "5. **get rule <name>**\n" +
        "6. **cancel**\n" +
        "7. **help**\n\n" +
        "Suggestions:\n" +
        suggestionLines,
    );
  };

  const submitForm = async () => {
    if (!formData?.customer_name.trim()) {
      say("⚠️ Customer name is required before saving.");
      return;
    }

    const name = formData.customer_name.trim();
    const payload = toRuleRecord(formData);

    try {
      setApiLoading(true);
      if (chatMode === "submit_add") await rulesApi.add(name, payload);
      else await rulesApi.update(pendingRuleName ?? name, payload);

      const nextRules = await rulesApi.list();
      setRules(nextRules);

      setMessages((prev) =>
        prev.map((msg) =>
          msg.role === "agent" && msg.kind === "inline_form" ? { ...msg, formSubmitted: true } : msg,
        ),
      );

      const action: RuleAction = chatMode === "submit_add" ? "created" : "updated";
      setChatMode(null);
      setFormData(null);
      setPendingRuleName(null);

      say(action === "created" ? `Rule for **${name}** created.` : `Rule for **${name}** updated.`);
      setTimeout(() => pushAgent({ kind: "rule_summary", data: { name, rule: payload, action } }), 250);
      setTimeout(() => say(`You now have **${Object.keys(nextRules).length}** active rule${Object.keys(nextRules).length === 1 ? "" : "s"}.`), 500);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Save failed";
      say(`⚠️ **API Error:** ${message}`);
    } finally {
      setApiLoading(false);
    }
  };

  const handleSend = async () => {
    if (chatMode === "submit_add" || chatMode === "submit_edit") {
      const text = input.trim();

      // In form mode:
      // - empty input + Send => submit
      // - typed "cancel"/commands => handle as intent instead of validating form
      if (!text) {
        await submitForm();
        return;
      }

      pushUser(text);
      setInput("");
      if (textareaRef.current) textareaRef.current.style.height = "auto";

      const intent = parseIntent(text);
      if (intent.type === "NO") {
        cancelFormMode();
        return;
      }

      if (isCommandIntent(intent)) {
        setChatMode(null);
        setFormData(null);
        setPendingRuleName(null);
        setMessages((prev) => prev.filter((msg) => !(msg.role === "agent" && msg.kind === "inline_form")));
        await dispatchIntent(intent);
        return;
      }

      say("You are editing a rule form. Click **Send** to save, or type **cancel** to exit form mode.");
      return;
    }

    const text = input.trim();
    if (!text) return;

    pushUser(text);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const intent = parseIntent(text);

    if (chatMode === "await_edit_name") {
      if (isCommandIntent(intent)) {
        setChatMode(null);
        await dispatchIntent(intent);
        return;
      }
      const found = findRuleName(text, rules);
      if (!found) {
        say(`I cannot find **${text}**. Try **list rules** first.`);
        return;
      }
      setChatMode(null);
      startEditFlow(found, rules[found] ?? {});
      return;
    }

    if (chatMode === "await_delete_name") {
      if (isCommandIntent(intent)) {
        setChatMode(null);
        await dispatchIntent(intent);
        return;
      }
      const found = findRuleName(text, rules);
      if (!found) {
        say(`I cannot find **${text}**. Try **list rules** first.`);
        return;
      }
      setChatMode(null);
      startDeleteFlow(found);
      return;
    }

    if (chatMode === "await_get_name") {
      if (isCommandIntent(intent)) {
        setChatMode(null);
        await dispatchIntent(intent);
        return;
      }
      const found = findRuleName(text, rules);
      if (!found) {
        say(`I cannot find **${text}**. Try **list rules** first.`);
        return;
      }
      setChatMode(null);
      say(`Here is the configuration for **${found}**:`);
      setTimeout(() => pushAgent({ kind: "rule_detail", data: { name: found, rule: rules[found] ?? {} } }), 250);
      return;
    }

    if (chatMode === "confirm_delete") {
      if (isCommandIntent(intent)) {
        setChatMode(null);
        setPendingRuleName(null);
        await dispatchIntent(intent);
        return;
      }

      if (intent.type === "YES" && pendingRuleName) {
        try {
          setApiLoading(true);
          await rulesApi.del(pendingRuleName);
          const nextRules = await rulesApi.list();
          setRules(nextRules);
          setChatMode(null);
          setPendingRuleName(null);
          say(`Deleted rule for **${pendingRuleName}**.`);
        } catch (error) {
          const message = error instanceof Error ? error.message : "Delete failed";
          say(`⚠️ **API Error:** ${message}`);
        } finally {
          setApiLoading(false);
        }
      } else {
        setChatMode(null);
        setPendingRuleName(null);
        say("Delete cancelled.");
      }
      return;
    }

    await dispatchIntent(intent);
  };

  const menuMap: Record<MenuItemId, Intent> = useMemo(
    () => ({
      list: { type: "LIST_RULES" },
      add: { type: "ADD_RULE" },
      edit: { type: "EDIT_RULE", name: null },
      delete: { type: "DELETE_RULE", name: null },
      get: { type: "GET_RULE", name: null },
    }),
    [],
  );

  const sendActive = (chatMode === "submit_add" || chatMode === "submit_edit" ? true : !!input.trim()) &&
    apiStatus !== "offline" &&
    !apiLoading;

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-[#03040a] text-slate-100">
      <div className="flex shrink-0 items-center gap-3 border-b border-slate-700 bg-[#101933] px-6 py-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-blue-400/40 bg-gradient-to-br from-blue-600 to-violet-600">
          <BotIcon />
        </div>
        <div>
          <h1 className="text-base font-semibold tracking-wide text-slate-100">TransformAgent</h1>
          <div className="mt-1 flex items-center gap-2 text-xs font-semibold tracking-[0.08em]">
            <span className={`h-1.5 w-1.5 rounded-full ${apiStatus === "online" ? "bg-emerald-400" : apiStatus === "offline" ? "bg-rose-400" : "bg-amber-400"}`} />
            <span className={apiStatus === "online" ? "text-emerald-300" : apiStatus === "offline" ? "text-rose-300" : "text-amber-300"}>
              {apiStatus === "online"
                ? `ONLINE · ${Object.keys(rules).length} RULES ACTIVE${apiLoading ? " · SYNCING" : ""}`
                : apiStatus === "offline"
                  ? "OFFLINE - START FASTAPI"
                  : "CONNECTING"}
            </span>
          </div>
        </div>

        <div className="ml-auto flex items-center gap-3">
          <a
            href="/live/viewer.html"
            target="_blank"
            rel="noreferrer"
            className="rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 font-mono text-xs tracking-[0.06em] text-sky-200"
          >
            LIVE PREVIEW
          </a>
          <span className="font-mono text-xs tracking-[0.08em] text-slate-400">{`CRM -> ERP v1.0`}</span>
        </div>
      </div>

      {apiStatus === "offline" ? (
        <div className="flex shrink-0 items-center gap-3 border-b border-rose-700/60 bg-rose-950/20 px-6 py-2.5 text-sm text-rose-200">
          <span>⚠️</span>
          <span className="font-mono text-xs">Backend is offline</span>
          <button
            type="button"
            className="ml-auto rounded border border-rose-600 px-2.5 py-1 text-xs"
            onClick={async () => {
              setApiStatus("connecting");
              const alive = await rulesApi.ping();
              if (!alive) {
                setApiStatus("offline");
                return;
              }
              setApiStatus("online");
              await refreshRules();
            }}
          >
            Retry
          </button>
        </div>
      ) : null}

      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="mx-auto max-w-4xl">
          <AgentBubble streamText={WELCOME_MESSAGE} time={currentTime()} />

          {messages.map((message) => {
            if (message.role === "user") return <UserBubble key={message.id} text={message.text} time={message.time} />;

            if (message.kind === "stream") return <AgentBubble key={message.id} streamText={message.text} time={message.time} />;

            if (message.kind === "inline_form") {
              return (
                <AgentBubble key={message.id} time={message.time}>
                  {message.formSubmitted ? (
                    <p className="text-sm text-emerald-300">Rule submitted successfully.</p>
                  ) : (
                    <InlineRuleForm
                      mode={chatMode === "submit_edit" ? "edit" : "add"}
                      formData={formData ?? makeDefaults()}
                      submitted={message.formSubmitted}
                      onChange={setFormData}
                    />
                  )}
                </AgentBubble>
              );
            }

            if (message.kind === "rules_list") {
              return (
                <AgentBubble key={message.id} time={message.time}>
                  <RulesListCard
                    rules={rules}
                    onEdit={(name) => startEditFlow(name, rules[name] ?? {})}
                    onDelete={(name) => startDeleteFlow(name)}
                  />
                </AgentBubble>
              );
            }

            if (message.kind === "rule_summary") {
              return (
                <AgentBubble key={message.id} time={message.time}>
                  <RuleSummaryCard name={message.data.name} rule={message.data.rule} action={message.data.action} />
                </AgentBubble>
              );
            }

            if (message.kind === "rule_detail") {
              return (
                <AgentBubble key={message.id} time={message.time}>
                  <RuleDetailCard name={message.data.name} rule={message.data.rule} />
                </AgentBubble>
              );
            }

            return (
              <AgentBubble key={message.id} time={message.time}>
                <ConfirmDeleteCard
                  name={message.data.name}
                  onConfirm={async () => {
                    try {
                      setApiLoading(true);
                      await rulesApi.del(message.data.name);
                      const nextRules = await rulesApi.list();
                      setRules(nextRules);
                      setMessages((prev) => prev.filter((item) => item.id !== message.id));
                      setChatMode(null);
                      setPendingRuleName(null);
                      say(`Deleted rule for **${message.data.name}**.`);
                    } catch (error) {
                      const err = error instanceof Error ? error.message : "Delete failed";
                      say(`⚠️ **API Error:** ${err}`);
                    } finally {
                      setApiLoading(false);
                    }
                  }}
                  onCancel={() => {
                    setMessages((prev) => prev.filter((item) => item.id !== message.id));
                    setChatMode(null);
                    setPendingRuleName(null);
                    say("Delete cancelled.");
                  }}
                />
              </AgentBubble>
            );
          })}

          <div ref={bottomRef} />
        </div>
      </div>

      <div className="shrink-0 px-6 pb-6 pt-3">
        <div className="mx-auto max-w-4xl">
          {(chatMode === "submit_add" || chatMode === "submit_edit") ? (
            <div className="mb-2 flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-900 px-4 py-2 text-xs text-slate-300">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-300" />
              <span className="font-mono tracking-[0.04em]">
                {chatMode === "submit_add" ? "New Rule Form Active" : "Edit Form Active"} - Fill Fields and Click Send
              </span>
              <button type="button" className="ml-auto text-slate-400 hover:text-slate-200" onClick={cancelFormMode}>
                Cancel
              </button>
            </div>
          ) : null}

          <div className="flex items-end gap-2 rounded-2xl border border-blue-500/70 bg-[#121a33] p-2 shadow-[0_12px_42px_rgba(2,6,23,0.55)]">
            <div ref={menuRef} className="relative shrink-0">
              <button
                type="button"
                onClick={() => setMenuOpen((prev) => !prev)}
                className="inline-flex h-11 items-center gap-1.5 rounded-xl border border-blue-500/70 bg-[#1d2f55] px-3.5 text-sm font-semibold text-slate-100 transition hover:bg-[#223a6a]"
              >
                <RulesIcon />
                Rules
                <span className={menuOpen ? "rotate-180" : ""}>
                  <ChevronDownIcon />
                </span>
              </button>

              {menuOpen ? (
                <div className="absolute bottom-[calc(100%+8px)] left-0 z-20 w-48 rounded-xl border border-slate-600 bg-slate-900 p-1.5 shadow-2xl">
                  {MENU_ITEMS.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-slate-200 hover:bg-slate-800"
                      onClick={() => {
                        setMenuOpen(false);
                        void dispatchIntent(menuMap[item.id]);
                      }}
                    >
                      <span>{item.icon}</span>
                      {item.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>

            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={(event) => {
                setInput(event.target.value);
                event.target.style.height = "auto";
                event.target.style.height = `${Math.min(event.target.scrollHeight, 140)}px`;
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void handleSend();
                }
              }}
              placeholder={
                chatMode === "submit_add"
                  ? "Form ready - click Send to save"
                  : chatMode === "submit_edit"
                    ? "Edits ready - click Send to update"
                    : chatMode === "confirm_delete"
                      ? "Type yes to confirm, no to cancel"
                      : chatMode?.startsWith("await")
                        ? "Type a customer name"
                        : "Type command or question"
              }
              className="max-h-36 min-h-[44px] flex-1 resize-none bg-transparent px-2 py-2.5 text-base leading-6 text-slate-100 outline-none placeholder:text-slate-300"
            />

            <button
              type="button"
              onClick={() => {
                void handleSend();
              }}
              disabled={!sendActive}
              className="inline-flex h-11 min-w-[58px] items-center justify-center gap-1 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-3 text-sm font-semibold text-white shadow-[0_10px_28px_rgba(59,130,246,0.35)] transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {apiLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : chatMode === "submit_add" || chatMode === "submit_edit" ? (
                <>
                  <CheckIcon />
                  Save
                </>
              ) : (
                <SendIcon />
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
