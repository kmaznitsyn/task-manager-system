export type DocType =
  | 'bill_of_lading'
  | 'manifest'
  | 'proof_of_delivery'
  | 'invoice'
  | 'customs_declaration';

export type DocStatus = 'received' | 'processing' | 'processed' | 'failed';

export const DOC_TYPE_LABELS: Record<DocType, string> = {
  bill_of_lading: 'Bill of Lading',
  manifest: 'Manifest',
  proof_of_delivery: 'Proof of Delivery',
  invoice: 'Invoice',
  customs_declaration: 'Customs Declaration',
};

export interface LogisticsDocument {
  id: string;
  owner_sub: string;
  doc_type: DocType;
  reference_number: string;
  shipment_ref: string | null;
  raw_text: string;
  status: DocStatus;
  extracted: Record<string, string> | null;
  failure_reason: string | null;
  created_at: string;
  processed_at: string | null;
}

export interface DocumentInput {
  doc_type: DocType;
  reference_number: string;
  shipment_ref: string | null;
  raw_text: string;
}
