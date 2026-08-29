import { describe, expect, it } from 'vitest';

import { buildStyleBatchRequest } from '@/lib/style-outfits';

describe('buildStyleBatchRequest', () => {
  it('sends the selected detected style and default batch size', () => {
    expect(buildStyleBatchRequest(' Smart-Casual ', 3, 'Office')).toEqual({
      target_style: 'smart-casual',
      count: 3,
      occasion: 'office',
    });
  });

  it.each([0, 21])('rejects an out-of-range count: %s', (count) => {
    expect(() => buildStyleBatchRequest('casual', count, 'casual')).toThrow(RangeError);
  });
});
