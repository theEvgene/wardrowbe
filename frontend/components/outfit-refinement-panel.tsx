'use client';

import { useEffect, useState } from 'react';
import { useSession } from 'next-auth/react';
import { useTranslations } from 'next-intl';
import { Loader2, MessageCircle, Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { api, setAccessToken } from '@/lib/api';

interface RefinementMetadata {
  instruction: string;
  turn: number;
  root_outfit_id: string;
  parent_outfit_id: string;
}

export interface RefinableOutfit {
  id: string;
  replaces_outfit_id?: string | null;
  reasoning?: string | null;
  style_notes?: string | null;
  generation_context?: {
    refinement?: RefinementMetadata;
  } | null;
}

interface OutfitRefinementPanelProps<T extends RefinableOutfit> {
  outfit: T;
  onVersionChange: (outfit: T) => void;
  disabled?: boolean;
}

export function OutfitRefinementPanel<T extends RefinableOutfit>({
  outfit,
  onVersionChange,
  disabled = false,
}: OutfitRefinementPanelProps<T>) {
  const t = useTranslations('suggest.refinement');
  const { data: session } = useSession();
  const [history, setHistory] = useState<T[]>([outfit]);
  const [instruction, setInstruction] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (session?.accessToken) {
      setAccessToken(session.accessToken as string);
    }
    setHistory([outfit]);
    setError(null);
    if (!outfit.replaces_outfit_id) {
      return () => {
        active = false;
      };
    }
    api
      .get<{ outfits: T[] }>(`/outfits/${outfit.id}/refinement-history`)
      .then((result) => {
        if (active) setHistory(result.outfits);
      })
      .catch(() => {
        if (active) setHistory([outfit]);
      });
    return () => {
      active = false;
    };
  }, [outfit, session?.accessToken]);

  const handleSubmit = async () => {
    const normalized = instruction.trim();
    if (!normalized || isSubmitting || disabled) return;
    if (session?.accessToken) {
      setAccessToken(session.accessToken as string);
    }
    setIsSubmitting(true);
    setError(null);
    try {
      const refined = await api.post<T>(`/outfits/${outfit.id}/refine`, {
        instruction: normalized,
      });
      setHistory((current) => [...current, refined]);
      setInstruction('');
      onVersionChange(refined);
    } catch {
      setError(t('error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Card data-testid="outfit-refinement-panel">
      <CardContent className="p-4 space-y-4">
        <div className="flex items-start gap-3">
          <div className="rounded-full bg-primary/10 p-2 text-primary">
            <MessageCircle className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-semibold">{t('title')}</h3>
            <p className="text-sm text-muted-foreground">{t('description')}</p>
          </div>
        </div>

        <div className="space-y-3" aria-live="polite">
          {history.map((version, index) => {
            const refinement = version.generation_context?.refinement;
            if (!refinement) {
              return (
                <div key={version.id} className="rounded-lg border bg-muted/30 px-3 py-2 text-sm">
                  <span className="font-medium">{t('original')}</span>
                </div>
              );
            }
            return (
              <div key={version.id} className="space-y-2" data-testid="refinement-turn">
                <p className="text-xs font-medium text-muted-foreground">
                  {t('version', { number: refinement.turn || index })}
                </p>
                <div className="ml-6 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
                  <span className="sr-only">{t('you')}: </span>
                  {refinement.instruction}
                </div>
                <div className="mr-6 rounded-lg border bg-background px-3 py-2 text-sm">
                  <span className="sr-only">{t('stylist')}: </span>
                  {version.reasoning || version.style_notes || t('updated')}
                </div>
              </div>
            );
          })}
        </div>

        <div className="space-y-2">
          <Label htmlFor={`refinement-${outfit.id}`}>{t('instruction')}</Label>
          <Textarea
            id={`refinement-${outfit.id}`}
            value={instruction}
            maxLength={1000}
            disabled={disabled || isSubmitting}
            onChange={(event) => setInstruction(event.target.value)}
            placeholder={t('placeholder')}
          />
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          <Button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || isSubmitting || !instruction.trim()}
            className="w-full gap-2"
          >
            {isSubmitting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                {t('submitting')}
              </>
            ) : (
              <>
                <Send className="h-4 w-4" />
                {t('submit')}
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
