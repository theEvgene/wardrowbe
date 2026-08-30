import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { OutfitPreviewDialog } from '@/components/outfit-preview-dialog'
import { Outfit } from '@/lib/hooks/use-outfits'

vi.mock('@/lib/hooks/use-family', () => ({
  useFamily: () => ({ data: null }),
}))

vi.mock('@/lib/hooks/use-items', () => ({
  useRotateImage: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('@/components/outfit-refinement-panel', () => ({
  OutfitRefinementPanel: ({ onVersionChange }: { onVersionChange: (outfit: Outfit) => void }) => (
    <button
      type="button"
      onClick={() => onVersionChange({ ...outfit, id: 'short-version', items: [outfit.items[0]] })}
    >
      Select shorter version
    </button>
  ),
}))

const outfit: Outfit = {
  id: 'outfit-1',
  occasion: 'casual',
  scheduled_for: null,
  status: 'pending',
  source: 'on_demand',
  name: null,
  replaces_outfit_id: null,
  cloned_from_outfit_id: null,
  reasoning: null,
  style_notes: null,
  season: null,
  formality: null,
  palette: null,
  notes: null,
  highlights: null,
  weather: null,
  feedback: null,
  family_ratings: null,
  family_rating_average: null,
  family_rating_count: null,
  created_at: '2026-08-26T10:00:00Z',
  items: [
    {
      id: 'shirt', type: 'shirt', subtype: null, name: 'Shirt', primary_color: 'white',
      colors: ['white'], image_path: 'shirt.jpg', thumbnail_path: null,
      image_url: '/shirt.jpg', layer_type: 'top', position: 0,
    },
    {
      id: 'pants', type: 'pants', subtype: null, name: 'Pants', primary_color: 'navy',
      colors: ['navy'], image_path: 'pants.jpg', thumbnail_path: null,
      image_url: '/pants.jpg', layer_type: 'bottom', position: 1,
    },
  ],
}

describe('OutfitPreviewDialog', () => {
  it('opens on the whole outfit and keeps item inspection as a secondary view', () => {
    render(<OutfitPreviewDialog outfit={outfit} open onClose={vi.fn()} />)

    expect(screen.getByTestId('outfit-composite')).toBeInTheDocument()
    expect(screen.getByTestId('outfit-item-shirt')).toBeInTheDocument()
    expect(screen.getByTestId('outfit-item-pants')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'itemView' }))

    expect(screen.queryByTestId('outfit-composite')).not.toBeInTheDocument()
    expect(screen.getByAltText('Shirt')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'rotateLeft' })).toBeInTheDocument()
  })

  it('clamps item inspection when a selected version has fewer items', () => {
    render(<OutfitPreviewDialog outfit={outfit} open onClose={vi.fn()} />)

    fireEvent.click(screen.getByRole('button', { name: 'itemView' }))
    fireEvent.click(screen.getByRole('button', { name: 'P' }))
    expect(screen.getByAltText('Pants')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Select shorter version' }))

    expect(screen.getByAltText('Shirt')).toBeInTheDocument()
    expect(screen.getByText('1 / 1')).toBeInTheDocument()
  })
})
