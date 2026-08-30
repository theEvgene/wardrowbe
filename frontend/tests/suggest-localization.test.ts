import { describe, expect, it } from 'vitest';

import de from '@/messages/de/suggest.json';
import en from '@/messages/en/suggest.json';
import fr from '@/messages/fr/suggest.json';
import itMessages from '@/messages/it/suggest.json';
import ja from '@/messages/ja/suggest.json';
import ko from '@/messages/ko/suggest.json';
import zhCN from '@/messages/zh-CN/suggest.json';
import zhTW from '@/messages/zh-TW/suggest.json';

function leaves(value: unknown): string[] {
  if (typeof value === 'string') return [value];
  if (!value || typeof value !== 'object') return [];
  return Object.values(value).flatMap(leaves);
}

describe('suggest context and refinement localization', () => {
  const locales = { de, fr, it: itMessages, ja, ko, 'zh-CN': zhCN, 'zh-TW': zhTW };
  const englishContext = new Set(leaves(en.context));

  it.each(Object.entries(locales))('%s translates every context string', (_locale, messages) => {
    for (const value of leaves(messages.context)) {
      expect(englishContext.has(value), `untranslated context value: ${value}`).toBe(false);
    }
  });

  it.each(Object.entries(locales))('%s translates version navigation', (_locale, messages) => {
    expect(messages.refinement.activeVersion).toBeTruthy();
    expect(messages.refinement.activeVersion).not.toBe(en.refinement.activeVersion);
    expect(messages.refinement.selectVersion).toContain('{number}');
    expect(messages.refinement.selectVersion).not.toBe(en.refinement.selectVersion);
  });
});
