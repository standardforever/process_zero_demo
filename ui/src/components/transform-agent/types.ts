export type RuleAction = "created" | "updated" | "deleted";

export type RuleRecord = {
  erp_customer_name?: string;
  taxes?: string;
  terms_and_conditions?: string;
  payment_method?: string;
  sales_person?: string;
  payment_terms?: string;
  payment_reference?: string;
  customer_reference?: string;
  invoice_date?: string;
  invoice_reference?: string;
};

export type RulesStore = Record<string, RuleRecord>;

export type FormValues = {
  customer_name: string;
} & Required<RuleRecord>;

export type ChatMode =
  | null
  | "submit_add"
  | "submit_edit"
  | "submit_add_email"
  | "submit_update_email"
  | "await_edit_name"
  | "await_delete_name"
  | "confirm_delete"
  | "confirm_delete_email"
  | "await_get_name";

export type Intent =
  | { type: "ADD_RULE" }
  | { type: "LIST_RULES" }
  | { type: "ADD_EMAIL" }
  | { type: "UPDATE_EMAIL" }
  | { type: "DELETE_EMAIL" }
  | { type: "HELP" }
  | { type: "EDIT_RULE"; name: string | null }
  | { type: "DELETE_RULE"; name: string | null }
  | { type: "GET_RULE"; name: string | null }
  | { type: "YES" }
  | { type: "NO" }
  | { type: "CHAT"; text: string };

export type MenuItemId = "list" | "add" | "edit" | "delete" | "get";

export type AgentMessage =
  | { id: string; role: "agent"; kind: "stream"; text: string; time: string }
  | { id: string; role: "agent"; kind: "inline_form"; formSubmitted: boolean; time: string }
  | { id: string; role: "agent"; kind: "inline_email_form"; formSubmitted: boolean; time: string }
  | { id: string; role: "agent"; kind: "rules_list"; time: string }
  | { id: string; role: "agent"; kind: "rule_summary"; data: { name: string; rule: RuleRecord; action: RuleAction }; time: string }
  | { id: string; role: "agent"; kind: "rule_detail"; data: { name: string; rule: RuleRecord }; time: string }
  | { id: string; role: "agent"; kind: "confirm_delete"; data: { name: string }; time: string };

export type AgentPayload =
  | { kind: "stream"; text: string }
  | { kind: "inline_form"; formSubmitted: boolean }
  | { kind: "inline_email_form"; formSubmitted: boolean }
  | { kind: "rules_list" }
  | { kind: "rule_summary"; data: { name: string; rule: RuleRecord; action: RuleAction } }
  | { kind: "rule_detail"; data: { name: string; rule: RuleRecord } }
  | { kind: "confirm_delete"; data: { name: string } };

export type UserMessage = { id: string; role: "user"; text: string; time: string };

export type ChatMessage = AgentMessage | UserMessage;
