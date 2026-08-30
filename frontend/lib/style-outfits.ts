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

const TIME_OF_DAY_MESSAGE_KEYS: Record<string, string> = {
  morning: 'context.times.morning',
  afternoon: 'context.times.afternoon',
  evening: 'context.times.evening',
  night: 'context.times.night',
  'full day': 'context.times.fullDay',
};

export function getTimeOfDayMessageKey(value: string): string | null {
  return TIME_OF_DAY_MESSAGE_KEYS[value] ?? null;
}

function formatDateInTimezone(value: Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(value);
  const part = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((candidate) => candidate.type === type)?.value ?? '';
  return `${part('year')}-${part('month')}-${part('day')}`;
}

function addCalendarDays(date: string, days: number): string {
  const [year, month, day] = date.split('-').map(Number);
  const shifted = new Date(Date.UTC(year, month - 1, day + days));
  return shifted.toISOString().slice(0, 10);
}

export function getStyleDateBounds(
  now = new Date(),
  timezone = 'UTC',
): { min: string; max: string } {
  const min = formatDateInTimezone(now, timezone);
  return { min, max: addCalendarDays(min, 15) };
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
