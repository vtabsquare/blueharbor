-- Correct Phase 2 document ownership and timing. Run after 05.
BEGIN;
SET search_path TO blueharbor, public;
ALTER TABLE compliance_rule_sets ADD COLUMN IF NOT EXISTS required_stage TEXT NOT NULL DEFAULT 'PRE_LOADING';
ALTER TABLE compliance_rule_sets ADD COLUMN IF NOT EXISTS responsible_party TEXT NOT NULL DEFAULT 'EXPORTER';
ALTER TABLE compliance_rule_sets ADD COLUMN IF NOT EXISTS evidence_type TEXT NOT NULL DEFAULT 'DOCUMENT';
ALTER TABLE compliance_rule_sets ADD COLUMN IF NOT EXISTS original_required INTEGER NOT NULL DEFAULT 0;
ALTER TABLE order_document_requirements ADD COLUMN IF NOT EXISTS required_stage TEXT NOT NULL DEFAULT 'PRE_LOADING';
ALTER TABLE order_document_requirements ADD COLUMN IF NOT EXISTS responsible_party TEXT NOT NULL DEFAULT 'EXPORTER';
ALTER TABLE order_document_requirements ADD COLUMN IF NOT EXISTS official_issuer TEXT NOT NULL DEFAULT '';
ALTER TABLE order_document_requirements ADD COLUMN IF NOT EXISTS evidence_type TEXT NOT NULL DEFAULT 'DOCUMENT';
ALTER TABLE order_document_requirements ADD COLUMN IF NOT EXISTS original_required INTEGER NOT NULL DEFAULT 0;

UPDATE compliance_rule_sets SET required_stage='PRE_CUSTOMS',responsible_party='EXPORTER' WHERE requirement_code IN ('COMMERCIAL_INVOICE','PACKING_LIST');
UPDATE compliance_rule_sets SET required_stage='PRE_LOADING',responsible_party='CUSTOMS_BROKER',issuer='Indian Customs / ICEGATE' WHERE requirement_code='SHIPPING_BILL';
UPDATE compliance_rule_sets SET required_stage='PRE_LOADING',responsible_party='APPROVED_ESTABLISHMENT',original_required=1 WHERE requirement_code='CFE';
UPDATE compliance_rule_sets SET required_stage='PRE_LOADING',responsible_party='COMPETENT_AUTHORITY',original_required=1 WHERE requirement_code='HEALTH_CERTIFICATE';
UPDATE compliance_rule_sets SET required_stage='POST_DEPARTURE',responsible_party='CARRIER',blocking=1 WHERE requirement_code='TRANSPORT_DOCUMENT';
UPDATE compliance_rule_sets SET required_stage='PRE_ARRIVAL',responsible_party='BUYER_IMPORTER',evidence_type='REFERENCE' WHERE buyer_owned=1;

UPDATE order_document_requirements r SET required_stage=x.required_stage,responsible_party=x.responsible_party,official_issuer=x.issuer,evidence_type=x.evidence_type,original_required=x.original_required FROM compliance_rule_sets x WHERE r.source_rule_id=x.id;
COMMIT;
