import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { DuplicateMatchReview } from '@/components/duplicate-match-review'
import { DuplicateMatch } from '@/lib/types'

const match: DuplicateMatch = {
  id: 'match-1',
  item_low_id: 'item-1',
  item_high_id: 'item-2',
  status: 'pending',
  canonical_item_id: null,
  cosine_score: 0.8946,
  matcher_revision: 'test-v1',
  evidence: {},
  created_at: '2026-08-26T10:00:00Z',
  updated_at: '2026-08-26T10:00:00Z',
  item_low: {
    id: 'item-1',
    type: 'shorts',
    name: 'Front view',
    image_path: 'test/front.jpg',
    image_url: '/front.jpg',
    created_at: '2026-08-25T10:00:00Z',
  },
  item_high: {
    id: 'item-2',
    type: 'shorts',
    name: 'Back view',
    image_path: 'test/back.jpg',
    image_url: '/back.jpg',
    created_at: '2026-08-26T10:00:00Z',
  },
}

describe('DuplicateMatchReview', () => {
  it('offers only merge and keep-separate decisions and merges into the selected item', () => {
    const onDecision = vi.fn()
    render(<DuplicateMatchReview match={match} total={1} onDecision={onDecision} />)

    expect(screen.getByAltText('Front view')).toBeInTheDocument()
    expect(screen.getByAltText('Back view')).toBeInTheDocument()
    expect(screen.queryByText(/dismiss/i)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Back view/i }))
    fireEvent.click(screen.getByRole('button', { name: 'duplicateReview.merge' }))
    expect(onDecision).toHaveBeenCalledWith('merge', 'item-2')

    fireEvent.click(screen.getByRole('button', { name: 'duplicateReview.keepSeparate' }))
    expect(onDecision).toHaveBeenCalledWith('keep_separate')
  })
})
