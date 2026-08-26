'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';

import { api, setAccessToken } from '@/lib/api';
import { DuplicateMatch } from '@/lib/types';

function useSessionToken() {
  const { data: session, status } = useSession();
  if (session?.accessToken) setAccessToken(session.accessToken as string);
  return status;
}

export function useDuplicateMatches() {
  const status = useSessionToken();
  return useQuery({
    queryKey: ['duplicate-matches'],
    queryFn: () => api.get<DuplicateMatch[]>('/duplicate-matches'),
    enabled: status !== 'loading',
    refetchInterval: 30000,
  });
}

export function useDecideDuplicateMatch() {
  const queryClient = useQueryClient();
  useSessionToken();

  return useMutation({
    mutationFn: ({
      candidateId,
      decision,
      canonicalItemId,
    }: {
      candidateId: string;
      decision: 'merge' | 'keep_separate';
      canonicalItemId?: string;
    }) =>
      api.post(`/duplicate-matches/${candidateId}/decision`, {
        decision,
        canonical_item_id: decision === 'merge' ? canonicalItemId : null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['duplicate-matches'] });
      queryClient.invalidateQueries({ queryKey: ['items'] });
      queryClient.invalidateQueries({ queryKey: ['item'] });
    },
  });
}
