'use client';

import { useEffect, useRef, useState } from 'react';
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
  refined_from_outfit_id?: string | null;
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
  const historyRef = useRef<T[]>([outfit]);
  const [selectedVersion, setSelectedVersion] = useState<T>(outfit);
  const [instruction, setInstruction] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setSelectedVersion(outfit);
    if (session?.accessToken) {
      setAccessToken(session.accessToken as string);
    }
    if (historyRef.current.length > 1 && historyRef.current.some((version) => version.id === outfit.id)) {
      return () => {
        active = false;
      };
    }
    historyRef.current = [outfit];
    setHistory([outfit]);
    setError(null);
    if (!outfit.refined_from_outfit_id) {
      return () => {
        active = false;
      };
    }
    api
      .get<{ outfits: T[] }>(`/outfits/${outfit.id}/refinement-history`)
      .then((result) => {
        if (active) {
          historyRef.current = result.outfits;
          setHistory(result.outfits);
        }
      })
      .catch(() => {
        if (active) {
          historyRef.current = [outfit];
          setHistory([outfit]);
        }
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
      const refined = await api.post<T>(`/outfits/${selectedVersion.id}/refine`, {
        instruction: normalized,
      });
      const selectedIndex = historyRef.current.findIndex(
        (version) => version.id === selectedVersion.id,
      );
      const lineage = selectedIndex >= 0
        ? historyRef.current.slice(0, selectedIndex + 1)
        : [selectedVersion];
      const nextHistory = [...lineage, refined];
      historyRef.current = nextHistory;
      setHistory(nextHistory);
      setSelectedVersion(refined);
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
            const versionNumber = refinement?.turn ?? index;
            const isActive = selectedVersion.id === version.id;
            return (
              <button
                key={version.id}
                type="button"
                aria-label={t('selectVersion', { number: versionNumber })}
                aria-current={isActive ? 'true' : undefined}
                onClick={() => {
                  setSelectedVersion(version);
                  onVersionChange(version);
                }}
                className={`w-full rounded-lg border px-3 py-2 text-left text-sm transition-colors ${
                  isActive ? 'border-primary bg-primary/5 ring-1 ring-primary' : 'bg-muted/30 hover:bg-muted/60'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">
                    {refinement ? t('version', { number: versionNumber }) : t('original')}
                  </span>
                  {isActive && <span className="text-xs text-primary">{t('activeVersion')}</span>}
                </div>
                {refinement && (
                  <div className="mt-2 space-y-2" data-testid="refinement-turn">
                    <div className="ml-6 rounded-lg bg-primary px-3 py-2 text-sm text-primary-foreground">
                      <span className="sr-only">{t('you')}: </span>
                      {refinement.instruction}
                    </div>
                    <div className="mr-6 rounded-lg border bg-background px-3 py-2 text-sm">
                      <span className="sr-only">{t('stylist')}: </span>
                      {version.reasoning || version.style_notes || t('updated')}
                    </div>
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <div className="space-y-2">
          <Label htmlFor={`refinement-${selectedVersion.id}`}>{t('instruction')}</Label>
          <Textarea
            id={`refinement-${selectedVersion.id}`}
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
