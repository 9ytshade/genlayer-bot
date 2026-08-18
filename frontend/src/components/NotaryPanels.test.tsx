import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import NotaryBlueprintPanel from './NotaryBlueprintPanel';
import NotaryRecordPanel from './NotaryRecordPanel';
import type { NotaryBlueprintArtifact, NotaryRecord, NotaryVerdict } from '@/types/Notary';

const artifact: NotaryBlueprintArtifact = {
  code: 'class PublicEvidenceNotary:\n    pass',
  contract_name: 'PublicEvidenceNotary',
  contract_type: 'ai_notary',
  file_name: 'public_evidence_notary.py',
  explanation: 'Canonical public-evidence registry.',
  notary_spec: {
    claim_id: 'notary-wallet-claim',
    statement: 'GenLayer publishes documentation for Intelligent Contracts',
    source_urls: ['https://docs.genlayer.com/', 'https://genlayer.com/'],
    rubric: 'Confirm the statement from public evidence.',
    freshness_rule: 'Evidence must be current within 30 days.',
    product_status: 'prototype',
  },
  constructor_args: [],
  constructor_kwargs: {},
  validation: { valid: true, message: 'valid', errors: [], warnings: [], contract_names: ['PublicEvidenceNotary'] },
  evidence_policy: 'Only public HTTPS sources may be used.',
  equivalence_rule: 'Validators must agree on verdict and material facts.',
  authorization: 'The connected claimant wallet owns the claim.',
  source_hash: '0xsourcehash',
  source_origin: 'notary',
  py_genlayer_dependency: 'genlayer-py==0.3.0',
  genlayer_sdk_version: '1.1.8',
  generator_version: 'notary-generator-v1',
  validator_version: 'notary-validator-v1',
  compiler_version: 'genvm-v1',
  artifact_version: 1,
};

const baseRecord: NotaryRecord = {
  claim_id: artifact.notary_spec.claim_id,
  claimant: '0xClaimant',
  statement: artifact.notary_spec.statement,
  source_urls: artifact.notary_spec.source_urls,
  rubric: artifact.notary_spec.rubric,
  freshness_rule: artifact.notary_spec.freshness_rule,
  verdict: 'PENDING',
  source_statuses: ['USABLE'],
  material_facts: ['The documentation page describes Intelligent Contracts.'],
  rationale: '',
  failure_reason: '',
  evaluated: false,
};

describe('NotaryBlueprintPanel', () => {
  it('renders reviewed evidence and routes deploy, submit, and refresh states', () => {
    const onDeploy = vi.fn();
    const onSubmit = vi.fn();
    const onRefresh = vi.fn();
    const view = render(
      <NotaryBlueprintPanel
        artifact={artifact}
        status="awaiting_confirmation"
        onDeploy={onDeploy}
        onSubmit={onSubmit}
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByText(artifact.notary_spec.claim_id)).toBeTruthy();
    expect(screen.getByText(artifact.notary_spec.freshness_rule)).toBeTruthy();
    const source = screen.getByRole('link', { name: /docs.genlayer.com/i });
    expect(source.getAttribute('href')).toBe('https://docs.genlayer.com/');
    expect(source.getAttribute('target')).toBe('_blank');
    fireEvent.click(screen.getByRole('button', { name: /deploy registry/i }));
    expect(onDeploy).toHaveBeenCalledTimes(1);

    view.rerender(
      <NotaryBlueprintPanel
        artifact={artifact}
        contractAddress="0xRegistry"
        operation="deploy_registry"
        status="success"
        onDeploy={onDeploy}
        onSubmit={onSubmit}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /submit claim/i }));
    expect(onSubmit).toHaveBeenCalledTimes(1);

    view.rerender(
      <NotaryBlueprintPanel
        artifact={artifact}
        contractAddress="0xRegistry"
        operation="submit_claim"
        status="success"
        onDeploy={onDeploy}
        onSubmit={onSubmit}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /refresh claim/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('shows the correct busy and finalized states', () => {
    const callbacks = { onDeploy: vi.fn(), onSubmit: vi.fn(), onRefresh: vi.fn() };
    const view = render(
      <NotaryBlueprintPanel artifact={artifact} operation="evaluate_claim" status="executing" {...callbacks} />,
    );
    expect(screen.getByText(/evaluating evidence/i)).toBeTruthy();

    view.rerender(
      <NotaryBlueprintPanel
        artifact={artifact}
        contractAddress="0xRegistry"
        operation="submit_claim"
        status="success"
        record={{ ...baseRecord, evaluated: true, verdict: 'CONFIRMED' }}
        {...callbacks}
      />,
    );
    expect(screen.getByText(/record finalized/i)).toBeTruthy();
    expect(screen.queryByRole('button', { name: /refresh claim/i })).toBeNull();
  });
});

describe('NotaryRecordPanel', () => {
  it.each<[NotaryVerdict, string]>([
    ['PENDING', 'Pending evaluation'],
    ['CONFIRMED', 'Confirmed'],
    ['REFUTED', 'Refuted'],
    ['INCONCLUSIVE', 'Inconclusive'],
  ])('renders the %s verdict', (verdict, label) => {
    render(
      <NotaryRecordPanel
        record={{ ...baseRecord, verdict, evaluated: verdict !== 'PENDING' }}
        onEvaluate={vi.fn()}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText(label)).toBeTruthy();
  });

  it('renders source fallbacks, material facts, rationale, and actions', () => {
    const onEvaluate = vi.fn();
    const onRefresh = vi.fn();
    render(
      <NotaryRecordPanel
        record={{ ...baseRecord, rationale: 'The usable source supports the statement.' }}
        onEvaluate={onEvaluate}
        onRefresh={onRefresh}
      />,
    );

    expect(screen.getByText('USABLE')).toBeTruthy();
    expect(screen.getByText('UNAVAILABLE')).toBeTruthy();
    expect(screen.getByText(baseRecord.material_facts[0])).toBeTruthy();
    expect(screen.getByText('The usable source supports the statement.')).toBeTruthy();
    expect(screen.getByText('None')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /evaluate evidence/i }));
    fireEvent.click(screen.getByRole('button', { name: /refresh record/i }));
    expect(onEvaluate).toHaveBeenCalledTimes(1);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it('disables pending actions while a transaction is busy', () => {
    render(
      <NotaryRecordPanel record={baseRecord} isBusy onEvaluate={vi.fn()} onRefresh={vi.fn()} />,
    );
    expect((screen.getByRole('button', { name: /evaluate evidence/i }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: /refresh record/i }) as HTMLButtonElement).disabled).toBe(true);
  });
});
