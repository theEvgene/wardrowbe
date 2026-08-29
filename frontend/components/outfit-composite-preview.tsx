'use client';

import Image from 'next/image';
import Link from 'next/link';
import { ImageOff } from 'lucide-react';

import { cn } from '@/lib/utils';

interface CompositeOutfitItem {
  id: string;
  type: string;
  name?: string | null;
  image_url?: string | null;
  thumbnail_url?: string | null;
  transparent_url?: string | null;
  layer_type?: string | null;
  position: number;
}

type BodySlot = 'outerwear' | 'full' | 'top' | 'bottom' | 'shoes' | 'accessory';

const SLOT_ORDER: BodySlot[] = ['outerwear', 'full', 'top', 'bottom', 'shoes', 'accessory'];

const TYPE_SLOTS: Record<string, BodySlot> = {
  coat: 'outerwear',
  jacket: 'outerwear',
  blazer: 'outerwear',
  cardigan: 'outerwear',
  vest: 'outerwear',
  dress: 'full',
  jumpsuit: 'full',
  suit: 'full',
  shirt: 'top',
  't-shirt': 'top',
  blouse: 'top',
  polo: 'top',
  'tank-top': 'top',
  top: 'top',
  sweater: 'top',
  hoodie: 'top',
  pants: 'bottom',
  jeans: 'bottom',
  shorts: 'bottom',
  skirt: 'bottom',
  shoes: 'shoes',
  sneakers: 'shoes',
  boots: 'shoes',
  sandals: 'shoes',
  socks: 'shoes',
  hat: 'accessory',
  scarf: 'accessory',
  belt: 'accessory',
  bag: 'accessory',
  tie: 'accessory',
  accessories: 'accessory',
};

const LAYER_SLOTS: Record<string, BodySlot> = {
  outer: 'outerwear',
  outerwear: 'outerwear',
  full: 'full',
  'full-body': 'full',
  top: 'top',
  upper: 'top',
  bottom: 'bottom',
  lower: 'bottom',
  shoes: 'shoes',
  footwear: 'shoes',
  accessory: 'accessory',
};

const SLOT_CLASSES: Record<BodySlot, string> = {
  outerwear: 'col-start-1 row-start-1 row-span-3 z-30',
  full: 'col-start-2 row-start-1 row-span-4 z-10',
  top: 'col-start-2 row-start-1 row-span-2 z-20',
  bottom: 'col-start-2 row-start-3 row-span-2 z-20',
  shoes: 'col-start-2 row-start-5 row-span-2 z-30',
  accessory: 'col-start-3 row-start-2 row-span-3 z-40',
};

export function getOutfitBodySlot(item: CompositeOutfitItem): BodySlot {
  const layer = item.layer_type?.toLowerCase();
  if (layer && LAYER_SLOTS[layer]) return LAYER_SLOTS[layer];
  return TYPE_SLOTS[item.type.toLowerCase()] || 'accessory';
}

interface OutfitCompositePreviewProps {
  items: CompositeOutfitItem[];
  className?: string;
}

export function OutfitCompositePreview({ items, className }: OutfitCompositePreviewProps) {
  const groups = new Map<BodySlot, CompositeOutfitItem[]>();
  for (const item of [...items].sort((a, b) => a.position - b.position || a.id.localeCompare(b.id))) {
    const slot = getOutfitBodySlot(item);
    groups.set(slot, [...(groups.get(slot) || []), item]);
  }

  return (
    <div
      data-testid="outfit-composite"
      className={cn(
        'relative grid aspect-[4/5] w-full grid-cols-[minmax(64px,0.8fr)_minmax(0,2fr)_minmax(64px,0.8fr)] grid-rows-6 gap-2 overflow-hidden rounded-xl bg-gradient-to-b from-muted/40 to-muted p-3 sm:gap-3 sm:p-4',
        className,
      )}
    >
      <div className="pointer-events-none absolute inset-x-[28%] bottom-[7%] top-[5%] rounded-[45%] border border-dashed border-muted-foreground/15" />
      {SLOT_ORDER.map((slot) => {
        const slotItems = groups.get(slot);
        if (!slotItems?.length) return null;
        return (
          <div
            key={slot}
            className={cn('flex min-h-0 min-w-0 items-center justify-center gap-1', SLOT_CLASSES[slot])}
          >
            {slotItems.map((item) => {
              const source = item.transparent_url || item.image_url || item.thumbnail_url;
              const isCutout = Boolean(item.transparent_url);
              return (
                <Link
                  key={item.id}
                  href={`/dashboard/wardrobe?item=${item.id}`}
                  data-testid={`outfit-item-${item.id}`}
                  data-slot={slot}
                  data-image-kind={isCutout ? 'cutout' : source ? 'photo' : 'missing'}
                  className={cn(
                    'group relative h-full min-h-0 min-w-0 flex-1 overflow-hidden',
                    isCutout
                      ? 'drop-shadow-md'
                      : 'rounded-lg border border-border/70 bg-background/90 shadow-sm',
                  )}
                >
                  {source ? (
                    <Image
                      src={source}
                      alt={item.name || item.type}
                      fill
                      className={cn(
                        'object-contain transition-transform group-hover:scale-[1.03]',
                        !isCutout && 'p-1',
                      )}
                      sizes="(max-width: 640px) 45vw, 240px"
                    />
                  ) : (
                    <span className="flex h-full min-h-12 flex-col items-center justify-center gap-1 p-1 text-center text-[10px] text-muted-foreground sm:text-xs">
                      <ImageOff className="h-4 w-4" />
                      {item.name || item.type}
                    </span>
                  )}
                </Link>
              );
            })}
          </div>
        );
      })}
    </div>
  );
}
