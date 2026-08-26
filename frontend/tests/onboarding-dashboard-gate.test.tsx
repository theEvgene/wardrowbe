import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, waitFor } from '@testing-library/react'
import { useSession } from 'next-auth/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import DashboardLayout from '@/app/dashboard/layout'
import { useFamily } from '@/lib/hooks/use-family'
import { useWeather } from '@/lib/hooks/use-weather'

const push = vi.fn()
const replace = vi.fn()
const useAuth = vi.fn()

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push, replace }),
  usePathname: () => '/dashboard',
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock('@/lib/hooks/use-auth', () => ({ useAuth: () => useAuth() }))

function DashboardQueries() {
  useFamily()
  useWeather()
  return <div>dashboard children</div>
}

function renderLayout() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardLayout>
        <DashboardQueries />
      </DashboardLayout>
    </QueryClientProvider>,
  )
}

describe('dashboard onboarding gate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSession).mockReturnValue({
      data: { accessToken: 'token' },
      status: 'authenticated',
      update: vi.fn(),
    } as never)
  })

  it('redirects an incomplete user before dashboard queries can run', async () => {
    useAuth.mockReturnValue({
      user: { id: 'user-1', onboarding_completed: false },
      isAuthenticated: true,
      isLoading: false,
      error: null,
    })

    renderLayout()

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/onboarding'))
    expect(global.fetch).not.toHaveBeenCalled()
  })
})
