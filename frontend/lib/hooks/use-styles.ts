'use client'

import { useQuery } from '@tanstack/react-query'
import { useSession } from 'next-auth/react'

import { api, setAccessToken } from '@/lib/api'

export interface DetectedStyle {
  style: string
  item_count: number
}

interface DetectedStylesResponse {
  styles: DetectedStyle[]
}

export function useDetectedStyles() {
  const { data: session, status } = useSession()

  return useQuery({
    queryKey: ['styles', 'detected'],
    queryFn: async () => {
      if (session?.accessToken) {
        setAccessToken(session.accessToken as string)
      }
      return api.get<DetectedStylesResponse>('/styles/detected')
    },
    enabled: status !== 'loading',
  })
}
