import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useSession } from 'next-auth/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { DetectedStyleSelector } from '@/components/detected-style-selector'

function renderSelector(onSelect = vi.fn()) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  render(
    <QueryClientProvider client={queryClient}>
      <DetectedStyleSelector selected={null} onSelect={onSelect} />
    </QueryClientProvider>,
  )
  return onSelect
}

describe('DetectedStyleSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useSession).mockReturnValue({
      data: { accessToken: 'token' },
      status: 'authenticated',
      update: vi.fn(),
    } as never)
  })

  it('shows a loading state while detected styles are being fetched', () => {
    vi.mocked(global.fetch).mockReturnValueOnce(new Promise(() => {}))

    renderSelector()

    expect(screen.getByLabelText('loading')).toBeVisible()
  })

  it('shows an empty state when the wardrobe has no detected styles', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ styles: [] }),
    } as Response)

    renderSelector()

    await waitFor(() => expect(screen.getByText('empty')).toBeVisible())
  })

  it('renders only API-detected styles and selects one through the public UI', async () => {
    vi.mocked(global.fetch).mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        styles: [
          { style: 'casual', item_count: 1 },
          { style: 'smart-casual', item_count: 2 },
        ],
      }),
    } as Response)
    const onSelect = renderSelector()

    await waitFor(() => expect(screen.getByRole('button', { name: /smart-casual/i })).toBeVisible())
    expect(screen.getByText('casual').closest('button')).toBeVisible()
    expect(screen.queryByText('formal')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /smart-casual/i }))

    expect(onSelect).toHaveBeenCalledWith('smart-casual')
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/styles/detected'),
      expect.objectContaining({ credentials: 'include' }),
    )
  })
})
