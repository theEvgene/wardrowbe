'use client';

import { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2 } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Item, ItemMetadataField, ItemMetadataUpdate } from '@/lib/types';

const REVIEW_FIELDS: ItemMetadataField[] = [
  'type',
  'subtype',
  'colors',
  'primary_color',
  'material',
  'pattern',
  'season',
  'formality',
  'style',
];

const LOW_CONFIDENCE = 0.75;

type FormState = Record<ItemMetadataField, string>;
type ReviewStatus = 'missing' | 'uncertain' | 'confirmed' | 'ready';

function listValue(value: string[] | undefined): string {
  return (value || []).join(', ');
}

function splitList(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

function initialForm(item: Item): FormState {
  return {
    type: item.type || '',
    subtype: item.subtype || '',
    colors: listValue(item.colors || item.tags.colors),
    primary_color: item.primary_color || item.tags.primary_color || '',
    material: item.material || item.tags.material || '',
    pattern: item.pattern || item.tags.pattern || '',
    season: listValue(item.season || item.tags.season),
    formality: item.formality || item.tags.formality || '',
    style: listValue(item.style || item.tags.style),
  };
}

function reviewStatus(item: Item, field: ItemMetadataField, value: string): ReviewStatus {
  const metadata = item.field_metadata?.[field];
  if (metadata?.provenance === 'user_confirmed') return 'confirmed';
  if (!value.trim() || value === 'unknown') return 'missing';
  if (metadata?.provenance === 'auto' && (metadata.confidence ?? 0) < LOW_CONFIDENCE) {
    return 'uncertain';
  }
  return 'ready';
}

interface MetadataReviewProps {
  item: Item;
  onSubmit: (update: ItemMetadataUpdate) => void | Promise<void>;
  isPending?: boolean;
}

export function MetadataReview({ item, onSubmit, isPending = false }: MetadataReviewProps) {
  const t = useTranslations('wardrobe.itemDetail');
  const [form, setForm] = useState<FormState>(() => initialForm(item));

  useEffect(() => {
    setForm(initialForm(item));
  }, [item]);

  const statuses = REVIEW_FIELDS.map((field) => reviewStatus(item, field, form[field]));
  const needsReview = statuses.some((status) => status === 'missing' || status === 'uncertain');

  const submit = () => {
    void onSubmit({
      type: form.type.trim() || 'unknown',
      subtype: form.subtype.trim() || undefined,
      primary_color: form.primary_color.trim() || undefined,
      tags: {
        colors: splitList(form.colors),
        primary_color: form.primary_color.trim() || undefined,
        material: form.material.trim() || undefined,
        pattern: form.pattern.trim() || undefined,
        season: splitList(form.season),
        formality: form.formality.trim() || undefined,
        style: splitList(form.style),
      },
      confirm_fields: REVIEW_FIELDS,
    });
  };

  return (
    <section className="space-y-3 rounded-lg border border-amber-500/30 bg-amber-500/5 p-3">
      <div className="flex items-start gap-2">
        {needsReview ? (
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
        ) : (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
        )}
        <div>
          <p className="text-sm font-medium">{t('review.title')}</p>
          <p className="text-xs text-muted-foreground">
            {t(needsReview ? 'review.description' : 'review.complete')}
          </p>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {REVIEW_FIELDS.map((field) => {
          const status = reviewStatus(item, field, form[field]);
          return (
            <div
              key={field}
              data-testid={`metadata-field-${field}`}
              data-review-status={status}
              className={`space-y-1 rounded-md border p-2 ${
                status === 'missing' || status === 'uncertain'
                  ? 'border-amber-500/60 bg-background'
                  : 'border-border/60'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <Label htmlFor={`metadata-${field}`} className="text-xs">
                  {t(`review.fields.${field}`)}
                </Label>
                {status !== 'ready' && (
                  <span className="text-[10px] text-muted-foreground">
                    {t(`review.status.${status}`)}
                  </span>
                )}
              </div>
              <Input
                id={`metadata-${field}`}
                value={form[field]}
                onChange={(event) =>
                  setForm((current) => ({ ...current, [field]: event.target.value }))
                }
                className="h-8 text-sm"
              />
            </div>
          );
        })}
      </div>

      <Button size="sm" onClick={submit} disabled={isPending}>
        {t('review.confirmAll')}
      </Button>
    </section>
  );
}
