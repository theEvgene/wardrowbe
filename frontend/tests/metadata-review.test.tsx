import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { MetadataReview } from '@/components/metadata-review'
import { Item } from '@/lib/types'

const item = {
  id: 'item-1',
  type: 'shirt',
  subtype: 'oxford',
  primary_color: 'navy',
  colors: ['navy'],
  material: undefined,
  pattern: 'solid',
  season: ['spring'],
  formality: 'smart-casual',
  style: ['classic'],
  tags: {},
  field_metadata: {
    type: { confidence: 0.42, provenance: 'auto' },
    primary_color: { confidence: 0.95, provenance: 'user_confirmed' },
  },
} as Item

describe('MetadataReview', () => {
  it('highlights uncertain and missing fields and submits corrections as confirmed', () => {
    const onSubmit = vi.fn()
    render(<MetadataReview item={item} onSubmit={onSubmit} />)

    expect(screen.getByTestId('metadata-field-type')).toHaveAttribute(
      'data-review-status',
      'uncertain',
    )
    expect(screen.getByTestId('metadata-field-material')).toHaveAttribute(
      'data-review-status',
      'missing',
    )
    expect(screen.getByTestId('metadata-field-primary_color')).toHaveAttribute(
      'data-review-status',
      'confirmed',
    )

    fireEvent.change(screen.getByLabelText('review.fields.material'), {
      target: { value: 'cotton' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'review.confirmAll' }))

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'shirt',
        primary_color: 'navy',
        confirm_fields: [
          'type',
          'subtype',
          'colors',
          'primary_color',
          'material',
          'pattern',
          'season',
          'formality',
          'style',
        ],
        tags: expect.objectContaining({ material: 'cotton' }),
      }),
    )
  })
})
