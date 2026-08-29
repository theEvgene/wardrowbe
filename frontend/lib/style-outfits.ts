import type { StyleBatchRequest } from '@/lib/types';

export function buildStyleBatchRequest(
  targetStyle: string,
  count: number,
  occasion: string,
): StyleBatchRequest {
  const normalizedCount = Math.trunc(count);
  if (normalizedCount < 1 || normalizedCount > 20) {
    throw new RangeError('Outfit count must be between 1 and 20');
  }
  return {
    target_style: targetStyle.trim().toLowerCase(),
    count: normalizedCount,
    occasion: occasion.trim().toLowerCase(),
  };
}
