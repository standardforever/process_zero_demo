export type CRMRecord = {
  sales_request_ref: string;
  crm_source_system_id?: string | null;
  date_raised: string;
  sales_person: string;
  status: string;
  customer_company: string;
  customer_contact: string;
  trading_address: string;
  delivery_address: string;
  sales_discount_percent: string;
  product_1?: string | null;
  product_1_quantity?: string | null;
  product_1_price_per_unit?: string | null;
  product_2?: string | null;
  product_2_quantity?: string | null;
  product_2_price_per_unit?: string | null;
  product_3?: string | null;
  product_3_quantity?: string | null;
  product_3_price_per_unit?: string | null;
};

export type PaginatedCRMRecords = {
  items: CRMRecord[];
  total: number;
  page: number;
  limit: number;
  total_pages: number;
};

export type DataStats = {
  total_records: number;
  active_records: number;
  customer_count: number;
  latest_sales_request_ref: string | null;
};

export type ConditionalStringRule = {
  _default: string;
  conditions: Record<string, string>;
};

export type ConditionalIntRule = {
  _default: number;
  conditions: Record<string, number>;
};

export type CustomerReferenceRule = {
  customerNamePrefixLength: number;
  includeYear: boolean;
  invoiceIdSource: string;
  invoiceIdPrefix: string;
  invoiceIdPadLength: number;
};

export type PaymentReferenceRule = {
  customerNamePrefixLength: number;
  crmSourceIdField: string;
  fallbackSourceIdField: string;
  useInvoiceTotalWithoutDecimals: boolean;
};

export type TransformRules = {
  version: string;
  lastUpdated: string;
  customerNameMapping: Record<string, string>;
  customerCountry: ConditionalStringRule;
  salesTaxRate: ConditionalStringRule;
  termsAndConditions: ConditionalStringRule;
  paymentTerms: ConditionalStringRule;
  paymentMethod: ConditionalStringRule;
  deliveryDays: ConditionalIntRule;
  customerReference: CustomerReferenceRule;
  paymentReference: PaymentReferenceRule;
  [ruleName: string]: unknown;
};

export type LineItem = {
  product_code: string;
  description: string;
  quantity: number;
  unit_price: number;
  line_total: number;
};

export type ERPInvoice = {
  sales_request_ref: string;
  invoice_date: string;
  sales_person: string;
  customer_contact: string;
  trading_address: string;
  delivery_address: string;
  discount_percent: number;
  customer_name: string;
  country: string;
  tax_rate: string;
  terms_and_conditions: string;
  payment_terms: string;
  payment_method: string;
  delivery_date: string;
  customer_reference: string;
  payment_reference: string;
  line_items: LineItem[];
  subtotal: number;
  tax_amount: number;
  total: number;
};

export type TransformPreviewResponse = {
  original: CRMRecord;
  transformed: ERPInvoice;
};

export type TransformBatchResponse = {
  count: number;
  missing_sales_request_refs: string[];
  invoices: ERPInvoice[];
};

export type TransformOutput = {
  count: number;
  invoices: ERPInvoice[];
};

export type RulesAIChange = {
  path: string;
  before: unknown;
  after: unknown;
};

export type RulesAIUpdateResponse = {
  applied: boolean;
  summary: string;
  changes: RulesAIChange[];
  updated_rules: TransformRules;
};

export type RulesAIApplicableRule = {
  rule_type: string;
  match_type: string;
  matched_key: string | null;
  resolved_value: unknown;
  reason: string;
};

export type RulesAIExplainResponse = {
  summary: string;
  applicable_rules: RulesAIApplicableRule[];
  used_ai: boolean;
};

export type RulesAICopilotMessage = {
  role: "user" | "assistant";
  content: string;
};

export type RulesAICopilotResponse = {
  mode: "answer" | "clarify" | "proposal";
  reply: string;
  questions: string[];
  changes: RulesAIChange[];
  updated_rules: TransformRules | null;
  applied: boolean;
  used_ai: boolean;
  state_persisted: boolean;
};

export type ERPSchemaColumn = {
  default_value: unknown;
  data_type: string;
  description: string;
  required: boolean;
  rules: Record<string, unknown>;
};

export type SchemaStoreAction = {
  enabled: boolean;
  action: string;
  [key: string]: unknown;
};

export type SchemaStore = {
  erp_schema: Record<string, ERPSchemaColumn>;
  post_transformation_actions: Record<string, SchemaStoreAction>;
  metadata: {
    crm_columns: string[];
    notification_emails: string[];
    erp_system: string;
    version: string;
    last_updated: string;
  };
};

export type SchemaStoreStatus = {
  erp_columns_count: number;
  crm_columns_count: number;
  notification_emails_count: number;
  has_erp_columns: boolean;
  has_crm_columns: boolean;
  has_notification_emails: boolean;
  can_use_chat: boolean;
};
