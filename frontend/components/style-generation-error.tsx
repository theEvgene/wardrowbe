'use client';

import { AlertCircle, RefreshCw } from 'lucide-react';

import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

interface StyleGenerationErrorProps {
  message: string;
  retryLabel: string;
  retrying: boolean;
  onRetry: () => void;
}

export function StyleGenerationError({
  message,
  retryLabel,
  retrying,
  onRetry,
}: StyleGenerationErrorProps) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription className="flex items-center justify-between gap-3">
        <span>{message}</span>
        <Button type="button" variant="outline" size="sm" disabled={retrying} onClick={onRetry}>
          <RefreshCw className="mr-2 h-3.5 w-3.5" />
          {retryLabel}
        </Button>
      </AlertDescription>
    </Alert>
  );
}
