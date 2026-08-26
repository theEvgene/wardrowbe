'use client';

import { useQuery } from '@tanstack/react-query';
import { useSession } from 'next-auth/react';
import { api, ApiError, setAccessToken } from '@/lib/api';

function useSetTokenIfAvailable() {
  const { data: session } = useSession();
  if (session?.accessToken) {
    setAccessToken(session.accessToken as string);
  }
}

export interface Weather {
  temperature: number;
  feels_like: number;
  humidity: number;
  precipitation_chance: number;
  precipitation_mm: number;
  wind_speed: number;
  condition: string;
  condition_code: number;
  is_day: boolean;
  uv_index: number;
  timestamp: string;
}

export function useWeather() {
  const { status } = useSession();
  useSetTokenIfAvailable();

  return useQuery({
    queryKey: ['weather'],
    queryFn: async (): Promise<Weather | null> => {
      try {
        return await api.get<Weather>('/weather/current');
      } catch (error) {
        if (error instanceof ApiError && error.status === 400) return null;
        throw error;
      }
    },
    enabled: status !== 'loading',
    staleTime: 1000 * 60 * 15, // 15 minutes - weather doesn't change that fast
    retry: false, // Don't retry if location not set
  });
}
