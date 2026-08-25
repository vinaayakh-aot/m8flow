import { describe, expect, it } from 'vitest';

import {
  processInstanceDetailPath,
  processInstanceOwnersPath,
  processInstancesPath,
} from './processInstancesApi';

describe('processInstancesPath', () => {
  it('builds the bare path with no filters', () => {
    expect(processInstancesPath()).toBe('/v1.0/m8flow/process-instances');
    expect(processInstancesPath({})).toBe('/v1.0/m8flow/process-instances');
  });

  it('appends filters in declaration order', () => {
    expect(
      processInstancesPath({ status: 'error', search: 'invoice', page: 2, perPage: 10, tenantId: 't1' }),
    ).toBe('/v1.0/m8flow/process-instances?status=error&search=invoice&page=2&per_page=10&tenantId=t1');
  });

  it('omits unset filters', () => {
    expect(processInstancesPath({ status: 'running' })).toBe(
      '/v1.0/m8flow/process-instances?status=running',
    );
  });

  it('appends started_by and sort params', () => {
    expect(processInstancesPath({ startedBy: 'amir', sort: 'oldest' })).toBe(
      '/v1.0/m8flow/process-instances?started_by=amir&sort=oldest',
    );
  });
});

describe('processInstanceOwnersPath', () => {
  it('builds the bare owners path with no tenant', () => {
    expect(processInstanceOwnersPath()).toBe('/v1.0/m8flow/process-instances/owners');
  });

  it('appends tenantId when set', () => {
    expect(processInstanceOwnersPath('t1')).toBe(
      '/v1.0/m8flow/process-instances/owners?tenantId=t1',
    );
  });
});

describe('processInstanceDetailPath', () => {
  it('builds the bare path with no tenant', () => {
    expect(processInstanceDetailPath(7)).toBe('/v1.0/m8flow/process-instances/7');
  });

  it('appends tenantId when set', () => {
    expect(processInstanceDetailPath(7, 't1')).toBe('/v1.0/m8flow/process-instances/7?tenantId=t1');
  });
});
