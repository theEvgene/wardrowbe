'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import { Check, GitMerge, Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  useDecideDuplicateMatch,
  useDuplicateMatches,
} from '@/lib/hooks/use-duplicate-matches';
import { DuplicateMatch, DuplicateMatchItem } from '@/lib/types';
import { cn } from '@/lib/utils';

function defaultCanonical(match: DuplicateMatch) {
  return match.item_low.created_at <= match.item_high.created_at
    ? match.item_low.id
    : match.item_high.id;
}

export function DuplicateMatchReview({
  match,
  total,
  onDecision,
  isPending = false,
}: {
  match: DuplicateMatch;
  total: number;
  onDecision: (
    decision: 'merge' | 'keep_separate',
    canonicalItemId?: string
  ) => void | Promise<void>;
  isPending?: boolean;
}) {
  const t = useTranslations('wardrobe');
  const [canonicalItemId, setCanonicalItemId] = useState(() => defaultCanonical(match));

  useEffect(() => setCanonicalItemId(defaultCanonical(match)), [match]);

  const itemChoice = (item: DuplicateMatchItem) => {
    const selected = canonicalItemId === item.id;
    const label = item.name || item.type;
    return (
      <button
        type="button"
        aria-label={label}
        aria-pressed={selected}
        onClick={() => setCanonicalItemId(item.id)}
        disabled={isPending}
        className={cn(
          'relative overflow-hidden rounded-lg border-2 text-left transition-colors',
          selected ? 'border-primary' : 'border-transparent hover:border-muted-foreground/40'
        )}
      >
        <div className="relative aspect-square bg-muted">
          <Image src={item.image_url} alt={label} fill className="object-cover" />
        </div>
        <div className="flex items-center justify-between gap-2 p-3">
          <div className="min-w-0">
            <p className="truncate font-medium">{label}</p>
            <p className="text-xs capitalize text-muted-foreground">{item.type}</p>
          </div>
          {selected && (
            <Badge className="shrink-0 gap-1">
              <Check className="h-3 w-3" />
              {t('duplicateReview.primary')}
            </Badge>
          )}
        </div>
      </button>
    );
  };

  return (
    <Card className="border-primary/40">
      <CardHeader className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <GitMerge className="h-5 w-5" />
            {t('duplicateReview.title')}
          </CardTitle>
          <Badge variant="secondary">{t('duplicateReview.remaining', { count: total })}</Badge>
        </div>
        <p className="text-sm text-muted-foreground">
          {t('duplicateReview.description')}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3">
          {itemChoice(match.item_low)}
          {itemChoice(match.item_high)}
        </div>
        {match.cosine_score !== null && (
          <p className="text-xs text-muted-foreground">
            {t('duplicateReview.similarity', {
              percent: Math.round(match.cosine_score * 100),
            })}
          </p>
        )}
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <Button
            variant="outline"
            disabled={isPending}
            onClick={() => onDecision('keep_separate')}
          >
            {t('duplicateReview.keepSeparate')}
          </Button>
          <Button
            disabled={isPending}
            onClick={() => onDecision('merge', canonicalItemId)}
          >
            {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {t('duplicateReview.merge')}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function DuplicateMatchReviewQueue() {
  const t = useTranslations('wardrobe');
  const matches = useDuplicateMatches();
  const decision = useDecideDuplicateMatch();
  const match = matches.data?.[0];

  if (!match) return null;

  return (
    <DuplicateMatchReview
      match={match}
      total={matches.data?.length || 1}
      isPending={decision.isPending}
      onDecision={async (choice, canonicalItemId) => {
        try {
          await decision.mutateAsync({
            candidateId: match.id,
            decision: choice,
            canonicalItemId,
          });
          toast.success(
            choice === 'merge'
              ? t('duplicateReview.merged')
              : t('duplicateReview.keptSeparate')
          );
        } catch {
          toast.error(t('duplicateReview.error'));
        }
      }}
    />
  );
}
