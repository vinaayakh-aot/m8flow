import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import type { ProcessModelDetail } from '@/lib/api';
import {
  fileKind,
  formatBytes,
  formatDuration,
  ProcessModelOverview,
} from './ProcessModelOverview';

const DETAIL: ProcessModelDetail = {
  id: 'finance/invoice-approval',
  display_name: 'Invoice Approval',
  description: 'Two-step',
  group_id: 'finance',
  group_display_name: 'Finance',
  last_run_in_seconds: 1_700_000_000,
  running_now: 1,
  runs_30d: 12,
  recent_instances: [
    {
      id: 1042,
      started_by: 'editor',
      start_in_seconds: 1_700_000_000,
      duration_seconds: 102,
      status: 'complete',
    },
  ],
  files: [
    {
      name: 'invoice-approval.bpmn',
      size_bytes: 24576,
      updated_at_in_seconds: 1_700_000_000,
      primary: true,
    },
    {
      name: 'invoice-form-schema.json',
      size_bytes: 3000,
      updated_at_in_seconds: 1_700_000_000,
      primary: false,
    },
  ],
};

function renderOverview(detail: ProcessModelDetail = DETAIL) {
  return render(
    <MemoryRouter>
      <ProcessModelOverview detail={detail} />
    </MemoryRouter>,
  );
}

describe('formatDuration / formatBytes / fileKind', () => {
  it('formats duration and bytes', () => {
    expect(formatDuration(null)).toBe('—');
    expect(formatDuration(12)).toBe('12s');
    expect(formatDuration(102)).toBe('1m 42s');
    expect(formatBytes(500)).toBe('500 B');
    expect(formatBytes(24576)).toBe('24 KB');
  });

  it('maps file extensions', () => {
    expect(fileKind('a.bpmn')).toEqual({ ext: 'BPMN', label: 'BPMN' });
    expect(fileKind('form-schema.json')).toEqual({ ext: 'JSON', label: 'Form schema' });
    expect(fileKind('form-uischema.json')).toEqual({ ext: 'JSON', label: 'UI schema' });
    expect(fileKind('notes.md')).toEqual({ ext: 'MD', label: 'Markdown' });
  });
});

describe('ProcessModelOverview', () => {
  it('renders live identity, stats, instances, and files', () => {
    renderOverview();

    expect(screen.getByRole('heading', { name: 'Invoice Approval' })).toBeInTheDocument();
    expect(screen.getByText('Two-step')).toBeInTheDocument();
    expect(screen.getByText('finance/invoice-approval')).toBeInTheDocument();
    expect(screen.getByText('Running now')).toBeInTheDocument();
    expect(screen.getByText('Runs 30d')).toBeInTheDocument();
    expect(screen.getByText('View all 12')).toBeInTheDocument();
    expect(screen.getByText('1042')).toBeInTheDocument();
    expect(screen.getByText('editor')).toBeInTheDocument();
    expect(screen.getByText('invoice-approval.bpmn')).toBeInTheDocument();
    expect(screen.getByText('Primary')).toBeInTheDocument();
    const groupLinks = screen.getAllByRole('link', { name: /Finance/ });
    expect(groupLinks).toHaveLength(2);
    for (const link of groupLinks) {
      expect(link).toHaveAttribute('href', '/processes?group=finance');
    }
  });

  it('omits unpublished facts and shows placeholder stats', () => {
    renderOverview();

    expect(screen.queryByText('Published')).not.toBeInTheDocument();
    expect(screen.queryByText('Owner')).not.toBeInTheDocument();
    expect(screen.queryByText('Trigger')).not.toBeInTheDocument();
    expect(screen.queryByText('Success rate')).not.toBeInTheDocument();
    expect(screen.getByText('Median time')).toBeInTheDocument();
    expect(screen.getByText('Errors 30d')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(2);
  });

  it('keeps header and file-creation controls from navigating', () => {
    renderOverview();

    expect(screen.getByRole('button', { name: 'Start process' })).toBeDisabled();
    expect(screen.getByRole('link', { name: /Open in modeler/ })).toHaveAttribute(
      'href',
      '/processes/finance:invoice-approval/modeler/invoice-approval.bpmn',
    );
    expect(screen.getByRole('button', { name: 'Save as template' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'More actions' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Add file' })).toBeDisabled();
  });

  it('wires the recent-instances "View all" link and each row id to Process Instances (ticket 04 capstone)', () => {
    renderOverview();

    expect(screen.getByRole('link', { name: /View all/ })).toHaveAttribute(
      'href',
      '/process-instances?search=Invoice%20Approval',
    );
    expect(screen.getByRole('link', { name: '1042' })).toHaveAttribute(
      'href',
      '/process-instances/1042',
    );
  });

  it('wires each file row to its own modeler link and download', () => {
    renderOverview();

    const editLinks = screen.getAllByTitle('Edit file');
    expect(editLinks).toHaveLength(DETAIL.files.length);
    expect(editLinks[0]).toHaveAttribute(
      'href',
      '/processes/finance:invoice-approval/modeler/invoice-approval.bpmn',
    );
    expect(editLinks[1]).toHaveAttribute(
      'href',
      '/processes/finance:invoice-approval/modeler/invoice-form-schema.json',
    );

    const downloadButtons = screen.getAllByTitle('Download file');
    expect(downloadButtons).toHaveLength(DETAIL.files.length);
    for (const button of downloadButtons) {
      expect(button).not.toBeDisabled();
    }
  });

  it('shows empty copy when there are no instances or files', () => {
    renderOverview({
      ...DETAIL,
      recent_instances: [],
      files: [],
    });

    expect(screen.getByText('No instances yet.')).toBeInTheDocument();
    expect(screen.getByText('No files yet.')).toBeInTheDocument();
    expect(screen.getByText('Files (0)')).toBeInTheDocument();
  });

  it('keeps Open in modeler disabled when there is no primary file', () => {
    renderOverview({ ...DETAIL, files: [{ ...DETAIL.files[1], primary: false }] });

    expect(screen.getByRole('button', { name: /Open in modeler/ })).toBeDisabled();
    expect(screen.queryByRole('link', { name: /Open in modeler/ })).not.toBeInTheDocument();
  });
});
