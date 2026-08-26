import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { OutfitCompositePreview } from '@/components/outfit-composite-preview'
import { OutfitItem } from '@/lib/hooks/use-outfits'

const items: OutfitItem[] = [
  {
    id: 'coat', type: 'coat', subtype: null, name: 'Coat', primary_color: 'black',
    colors: ['black'], image_path: 'coat.jpg', thumbnail_path: null,
    image_url: '/coat.jpg', transparent_url: '/coat-cutout.png', layer_type: 'outer', position: 0,
  },
  {
    id: 'shirt', type: 'shirt', subtype: null, name: 'Shirt', primary_color: 'white',
    colors: ['white'], image_path: 'shirt.jpg', thumbnail_path: null,
    image_url: '/shirt.jpg', layer_type: 'top', position: 1,
  },
  {
    id: 'pants', type: 'pants', subtype: null, name: 'Pants', primary_color: 'navy',
    colors: ['navy'], image_path: 'pants.jpg', thumbnail_path: null,
    image_url: '/pants.jpg', layer_type: 'bottom', position: 2,
  },
  {
    id: 'shoes', type: 'sneakers', subtype: null, name: 'Shoes', primary_color: 'white',
    colors: ['white'], image_path: 'shoes.jpg', thumbnail_path: null,
    image_url: '/shoes.jpg', layer_type: 'shoes', position: 3,
  },
  {
    id: 'belt', type: 'belt', subtype: null, name: 'Belt', primary_color: 'brown',
    colors: ['brown'], image_path: '', thumbnail_path: null,
    layer_type: 'accessory', position: 4,
  },
]

describe('OutfitCompositePreview visual structure', () => {
  it('renders every item in a deterministic body slot with cutout and missing-image fallbacks', () => {
    const { container } = render(<OutfitCompositePreview items={items} />)

    expect(screen.getByTestId('outfit-composite')).toBeInTheDocument()
    expect(screen.getByTestId('outfit-item-coat')).toHaveAttribute('data-slot', 'outerwear')
    expect(screen.getByTestId('outfit-item-shirt')).toHaveAttribute('data-slot', 'top')
    expect(screen.getByTestId('outfit-item-pants')).toHaveAttribute('data-slot', 'bottom')
    expect(screen.getByTestId('outfit-item-shoes')).toHaveAttribute('data-slot', 'shoes')
    expect(screen.getByTestId('outfit-item-belt')).toHaveAttribute('data-slot', 'accessory')
    expect(screen.getByAltText('Coat')).toHaveAttribute('src', expect.stringContaining('coat-cutout.png'))
    expect(screen.getByText('Belt')).toBeInTheDocument()
    expect(container.firstChild).toMatchSnapshot()
  })

  it('keeps a full-body garment, shoes, and accessories in stable separate slots', () => {
    const fullBodyItems: OutfitItem[] = [
      {
        id: 'dress', type: 'dress', subtype: null, name: 'Dress', primary_color: 'red',
        colors: ['red'], image_path: 'dress.jpg', thumbnail_path: null,
        transparent_url: '/dress-cutout.png', layer_type: null, position: 0,
      },
      {
        id: 'heels', type: 'shoes', subtype: null, name: 'Heels', primary_color: 'black',
        colors: ['black'], image_path: 'heels.jpg', thumbnail_path: null,
        image_url: '/heels.jpg', layer_type: null, position: 1,
      },
      {
        id: 'bag', type: 'bag', subtype: null, name: 'Bag', primary_color: 'black',
        colors: ['black'], image_path: 'bag.jpg', thumbnail_path: null,
        image_url: '/bag.jpg', layer_type: null, position: 2,
      },
    ]

    const { container } = render(<OutfitCompositePreview items={fullBodyItems} />)

    expect(screen.getByTestId('outfit-item-dress')).toHaveAttribute('data-slot', 'full')
    expect(screen.getByTestId('outfit-item-heels')).toHaveAttribute('data-slot', 'shoes')
    expect(screen.getByTestId('outfit-item-bag')).toHaveAttribute('data-slot', 'accessory')
    expect(container.firstChild).toMatchSnapshot()
  })
})
