import { describe, expect, it } from 'vitest';

import { homeStatsPath } from './api';

describe('api helpers', () => {
  it('builds home-stats path without tenant when unset', () => {
    expect(homeStatsPath(null)).toBe('/v1.0/m8flow/home-stats');
    expect(homeStatsPath(undefined)).toBe('/v1.0/m8flow/home-stats');
  });

  it('appends tenantId when set', () => {
    expect(homeStatsPath('t2')).toBe('/v1.0/m8flow/home-stats?tenantId=t2');
  });
});

describe('homeRecentInstancesPath', () => {
  it('builds path with optional tenantId', async () => {
    const { homeRecentInstancesPath } = await import('./api');
    expect(homeRecentInstancesPath(null)).toBe('/v1.0/m8flow/home-recent-instances');
    expect(homeRecentInstancesPath('t2')).toBe(
      '/v1.0/m8flow/home-recent-instances?tenantId=t2',
    );
  });
});

describe('processModelsPath', () => {
  it('builds path with tenant and optional group', async () => {
    const { processModelsPath } = await import('./api');
    expect(processModelsPath(null)).toBe('/v1.0/m8flow/process-models');
    expect(processModelsPath('t1')).toBe(
      '/v1.0/m8flow/process-models?tenantId=t1',
    );
    expect(processModelsPath('t1', 'finance')).toBe(
      '/v1.0/m8flow/process-models?tenantId=t1&group=finance',
    );
  });
});

describe('processGroupsPath', () => {
  it('builds path with optional tenantId', async () => {
    const { processGroupsPath } = await import('./api');
    expect(processGroupsPath(null)).toBe('/v1.0/m8flow/process-groups');
    expect(processGroupsPath('t1')).toBe('/v1.0/m8flow/process-groups?tenantId=t1');
  });
});

describe('processModelDetailPath', () => {
  it('keeps colon separators and optional tenantId', async () => {
    const { processModelDetailPath } = await import('./api');
    expect(processModelDetailPath('finance:invoice-approval')).toBe(
      '/v1.0/m8flow/process-models/finance:invoice-approval',
    );
    expect(processModelDetailPath('finance:invoice-approval', 't1')).toBe(
      '/v1.0/m8flow/process-models/finance:invoice-approval?tenantId=t1',
    );
  });
});