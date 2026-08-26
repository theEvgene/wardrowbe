import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import { useSession } from 'next-auth/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useFamily } from '@/lib/hooks/use-family'
import { useWeather } from '@/lib/hooks/use-weather'

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('expected empty dashboard data', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSession).mockReturnValue({
      data: { accessToken: 'token' },
      status: 'authenticated',
      update: vi.fn(),
    } as never)
  })

  it('represents a missing family as a successful empty state', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 404,
      json: async () => ({ detail: 'You are not in a family' }),
    } as Response)

    const { result } = renderHook(() => useFamily(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeNull()
  })

  it('represents a missing location as a successful empty weather state', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'Location not set' }),
    } as Response)

    const { result } = renderHook(() => useWeather(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toBeNull()
  })

  it('keeps genuine weather failures actionable', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: false,
      status: 503,
      json: async () => ({ detail: 'Weather provider unavailable' }),
    } as Response)

    const { result } = renderHook(() => useWeather(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error).toMatchObject({
      status: 503,
      message: 'Weather provider unavailable',
    })
  })
})
