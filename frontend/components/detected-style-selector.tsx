'use client'

import { AlertCircle, Sparkles } from 'lucide-react'
import { useTranslations } from 'next-intl'

import { Alert, AlertDescription } from '@/components/ui/alert'
import { Skeleton } from '@/components/ui/skeleton'
import { useDetectedStyles } from '@/lib/hooks/use-styles'
import { cn } from '@/lib/utils'

interface DetectedStyleSelectorProps {
  selected: string | null
  onSelect: (style: string) => void
}

export function DetectedStyleSelector({ selected, onSelect }: DetectedStyleSelectorProps) {
  const t = useTranslations('suggest.detectedStyles')
  const styles = useDetectedStyles()

  if (styles.isLoading) {
    return (
      <div className="space-y-3" aria-label={t('loading')}>
        <Skeleton className="h-5 w-48" />
        <div className="flex gap-2">
          <Skeleton className="h-10 w-24 rounded-full" />
          <Skeleton className="h-10 w-32 rounded-full" />
        </div>
      </div>
    )
  }

  if (styles.isError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription>{t('error')}</AlertDescription>
      </Alert>
    )
  }

  const detected = styles.data?.styles ?? []
  if (detected.length === 0) {
    return (
      <div className="rounded-lg border border-dashed p-4 text-sm text-muted-foreground">
        {t('empty')}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div>
        <h2 className="flex items-center gap-2 font-semibold">
          <Sparkles className="h-4 w-4 text-primary" />
          {t('title')}
        </h2>
        <p className="text-sm text-muted-foreground">{t('description')}</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {detected.map(({ style, item_count: itemCount }) => (
          <button
            key={style}
            type="button"
            aria-pressed={selected === style}
            onClick={() => onSelect(style)}
            className={cn(
              'rounded-full border-2 px-4 py-2 text-left transition-colors',
              selected === style
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-muted bg-background hover:border-primary/50',
            )}
          >
            <span className="font-medium">{style}</span>
            <span className="ml-2 text-xs text-muted-foreground">
              {t('itemCount', { count: itemCount })}
            </span>
          </button>
        ))}
      </div>
    </div>
  )
}
