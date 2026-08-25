import { describe, expect, it } from 'vitest';

import { decodeProcessModelId, encodeProcessModelId } from './processModelId';

describe('processModelId', () => {
  it('encodes path segments with colon', () => {
    expect(encodeProcessModelId('finance/invoice-approval')).toBe(
      'finance:invoice-approval',
    );
  });

  it('decodes colon back to slash', () => {
    expect(decodeProcessModelId('finance:invoice-approval')).toBe(
      'finance/invoice-approval',
    );
  });
});
