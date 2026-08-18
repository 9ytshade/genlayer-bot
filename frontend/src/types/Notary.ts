export type NotaryVerdict = 'PENDING' | 'CONFIRMED' | 'REFUTED' | 'INCONCLUSIVE';

export type NotarySourceStatus = 'USABLE' | 'UNAVAILABLE' | 'STALE' | 'CONFLICTING';

export interface NotarySpec {
  claim_id: string;
  statement: string;
  source_urls: string[];
  rubric: string;
  freshness_rule: string;
  product_status: 'prototype' | string;
}
export interface NotaryBlueprintArtifact {
  code: string;
  contract_name: string;
  contract_type: 'ai_notary' | string;
  file_name: string;
  explanation: string;
  notary_spec: NotarySpec;
  constructor_args: unknown[];
  constructor_kwargs: Record<string, unknown>;
  validation: {
    valid: boolean;
    message: string;
    errors: string[];
    warnings: string[];
    contract_names: string[];
  };
  evidence_policy: string;
  equivalence_rule: string;
  authorization: string;
  source_hash: string;
  source_origin: 'notary';
  py_genlayer_dependency: string;
  genlayer_sdk_version: string;
  generator_version: string;
  validator_version: string;
  compiler_version: string;
  artifact_version: number;
}

export interface NotaryRecord {
  claim_id: string;
  claimant: string;
  statement: string;
  source_urls: string[];
  rubric: string;
  freshness_rule: string;
  verdict: NotaryVerdict;
  source_statuses: NotarySourceStatus[];
  material_facts: string[];
  rationale: string;
  failure_reason: string;
  evaluated: boolean;
}

export interface NotaryRegistrySummary {
  id: number;
  network: string;
  contractAddress: string | null;
  deployTxHash: string | null;
  consensusTxId: string | null;
  status: string;
  sourceHash: string;
  claims: Array<{
    claimId: string;
    status: string;
    verdict: NotaryVerdict;
    claimant: string;
  }>;
}
