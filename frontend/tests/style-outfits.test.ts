import { describe, expect, it } from 'vitest';

import {
  buildStyleBatchRequest,
  getStyleDateBounds,
  getTimeOfDayMessageKey,
} from '@/lib/style-outfits';

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

  it('sends the complete context contract with normalized colors', () => {
    expect(
      buildStyleBatchRequest('casual', 3, 'casual', {
        scheduledFor: '2026-08-31',
        timeOfDay: 'evening',
        activity: 'Dinner and a walk',
        requiredItemIds: ['required-id'],
        excludedItemIds: ['excluded-id'],
        avoidedColors: [' Orange ', 'orange', 'LIME'],
        note: 'Prefer light layers',
      }),
    ).toEqual({
      target_style: 'casual',
      count: 3,
      occasion: 'casual',
      scheduled_for: '2026-08-31',
      time_of_day: 'evening',
      activity: 'Dinner and a walk',
      constraints: {
        required_item_ids: ['required-id'],
        excluded_item_ids: ['excluded-id'],
        avoided_colors: ['orange', 'lime'],
        note: 'Prefer light layers',
      },
    });
  });

  it('exposes an inclusive today-through-plus-15 date range', () => {
    expect(getStyleDateBounds(new Date('2026-08-30T12:00:00Z'), 'UTC')).toEqual({
      min: '2026-08-30',
      max: '2026-09-14',
    });
  });

  it('uses the saved user timezone at a calendar-day boundary', () => {
    expect(
      getStyleDateBounds(new Date('2026-08-30T01:00:00Z'), 'America/Los_Angeles'),
    ).toEqual({
      min: '2026-08-29',
      max: '2026-09-13',
    });
  });

  it('rejects contradictory item selections before the request is sent', () => {
    expect(() =>
      buildStyleBatchRequest('casual', 3, 'casual', {
        scheduledFor: '2026-08-30',
        requiredItemIds: ['same-id'],
        excludedItemIds: ['same-id'],
      }),
    ).toThrow('required and excluded');
  });

  it('maps persisted time-of-day values to localized message keys', () => {
    expect(getTimeOfDayMessageKey('evening')).toBe('context.times.evening');
    expect(getTimeOfDayMessageKey('full day')).toBe('context.times.fullDay');
  });
});
