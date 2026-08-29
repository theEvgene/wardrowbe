import type { StyleBatchRequest } from '@/lib/types';

export interface StyleBatchContextInput {
  scheduledFor: string;
  timeOfDay?: 'morning' | 'afternoon' | 'evening' | 'night' | 'full day' | null;
  activity?: string | null;
  requiredItemIds?: string[];
  excludedItemIds?: string[];
  avoidedColors?: string[];
  note?: string | null;
}

function formatLocalDate(value: Date): string {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, '0');
  const day = String(value.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

export function getStyleDateBounds(now = new Date()): { min: string; max: string } {
  const max = new Date(now);
  max.setDate(max.getDate() + 15);
  return { min: formatLocalDate(now), max: formatLocalDate(max) };
}

export function buildStyleBatchRequest(
  targetStyle: string,
  count: number,
  occasion: string,
  context?: StyleBatchContextInput,
): StyleBatchRequest {
  const normalizedCount = Math.trunc(count);
  if (normalizedCount < 1 || normalizedCount > 20) {
    throw new RangeError('Outfit count must be between 1 and 20');
  }
  const request: StyleBatchRequest = {
    target_style: targetStyle.trim().toLowerCase(),
    count: normalizedCount,
    occasion: occasion.trim().toLowerCase(),
  };
  if (!context) return request;

  const requiredItemIds = Array.from(new Set(context.requiredItemIds ?? []));
  const excludedItemIds = Array.from(new Set(context.excludedItemIds ?? []));
  if (requiredItemIds.some((itemId) => excludedItemIds.includes(itemId))) {
    throw new RangeError('An item cannot be both required and excluded');
  }
  const avoidedColors = Array.from(
    new Set(
      (context.avoidedColors ?? [])
        .map((color) => color.trim().toLowerCase())
        .filter(Boolean),
    ),
  );

  return {
    ...request,
    scheduled_for: context.scheduledFor,
    time_of_day: context.timeOfDay ?? null,
    activity: context.activity?.trim() || null,
    constraints: {
      required_item_ids: requiredItemIds,
      excluded_item_ids: excludedItemIds,
      avoided_colors: avoidedColors,
      note: context.note?.trim() || null,
    },
  };
}
