import { expect, Page, test } from '@playwright/test';

import type { Outfit } from '../lib/types';

const now = '2026-08-26T10:00:00Z';
const image = (name: string) => `/e2e-${name}.svg`;

function item(id: string, type: string, name: string, color: string) {
  return {
    id,
    user_id: 'user-e2e',
    type,
    name,
    favorite: false,
    image_path: image(id),
    thumbnail_path: image(id),
    image_url: image(id),
    thumbnail_url: image(id),
    tags: { colors: [color], style: ['casual'], season: [] },
    colors: [color],
    primary_color: color,
    style: ['casual'],
    season: [],
    status: 'ready',
    ai_processed: true,
    ai_confidence: 0.96,
    field_metadata: {
      type: { provenance: 'user_confirmed' },
      primary_color: { provenance: 'user_confirmed' },
    },
    tagging_status: 'tagged',
    tagged_by: 'manual',
    wear_count: 0,
    suggestion_count: 0,
    acceptance_count: 0,
    wears_since_wash: 0,
    needs_wash: false,
    effective_wash_interval: 3,
    additional_images: [],
    is_archived: false,
    created_at: now,
    updated_at: now,
  };
}

const source = item('item-source', 'shirt', 'Blue shirt', 'blue');
const duplicate = item('item-duplicate', 'shirt', 'Same blue shirt', 'blue');
const pants = item('item-pants', 'pants', 'Beige pants', 'beige');
const shoes = item('item-shoes', 'shoes', 'White shoes', 'white');
const secondShirt = item('item-second-shirt', 'shirt', 'Green shirt', 'green');
const uploaded = item('item-uploaded', 'shirt', 'Uploaded smoke shirt', 'blue');

const pairing = {
  id: 'pairing-1',
  occasion: 'casual',
  scheduled_for: null,
  status: 'pending',
  source: 'pairing',
  reasoning: 'Blue shirt with beige pants and white shoes',
  style_notes: 'Keep the shirt untucked',
  highlights: ['White shoes finish the outfit'],
  items: [
    {
      id: source.id,
      type: source.type,
      name: source.name,
      primary_color: source.primary_color,
      colors: source.colors,
      image_path: source.image_path,
      image_url: source.image_url,
      thumbnail_url: source.thumbnail_url,
      transparent_url: image('source-cutout'),
      layer_type: 'top',
      position: 0,
    },
    {
      id: pants.id,
      type: pants.type,
      name: pants.name,
      primary_color: pants.primary_color,
      colors: pants.colors,
      image_path: pants.image_path,
      image_url: pants.image_url,
      thumbnail_url: pants.thumbnail_url,
      layer_type: 'bottom',
      position: 1,
    },
    {
      id: shoes.id,
      type: shoes.type,
      name: shoes.name,
      primary_color: shoes.primary_color,
      colors: shoes.colors,
      image_path: shoes.image_path,
      image_url: shoes.image_url,
      thumbnail_url: shoes.thumbnail_url,
      layer_type: 'shoes',
      position: 2,
    },
  ],
  source_item: {
    id: source.id,
    type: source.type,
    name: source.name,
    primary_color: source.primary_color,
    image_path: source.image_path,
    image_url: source.image_url,
    thumbnail_url: source.thumbnail_url,
  },
  family_ratings: [],
  family_rating_average: null,
  family_rating_count: 0,
  created_at: now,
};

const secondStyleOutfit = {
  ...pairing,
  id: 'style-outfit-2',
  source: 'on_demand',
  target_style: 'casual',
  source_item: null,
  reasoning: null,
  style_notes: null,
  highlights: [],
  items: [
    {
      ...pairing.items[0],
      id: secondShirt.id,
      name: secondShirt.name,
      image_path: secondShirt.image_path,
      image_url: secondShirt.image_url,
      thumbnail_url: secondShirt.thumbnail_url,
      transparent_url: image('second-shirt-cutout'),
    },
    pairing.items[1],
    pairing.items[2],
  ],
};

const firstStyleOutfit = {
  ...pairing,
  id: 'style-outfit-1',
  source: 'on_demand',
  target_style: 'casual',
  source_item: null,
  reasoning: null,
  style_notes: null,
  highlights: [],
};

async function installApiContract(page: Page) {
  const unexpectedRequests: string[] = [];
  const pageErrors: string[] = [];
  page.on('pageerror', (error) => pageErrors.push(error.message));
  let duplicateMatches = [
    {
      id: 'match-1',
      item_low_id: source.id,
      item_high_id: duplicate.id,
      status: 'pending',
      canonical_item_id: null,
      cosine_score: 0.98,
      matcher_revision: 'e2e-v1',
      evidence: {},
      created_at: now,
      updated_at: now,
      item_low: source,
      item_high: duplicate,
    },
  ];
  let wardrobeItems = [source, duplicate, secondShirt, pants, shoes];
  let onboardingCompleted = false;
  let generatedOutfits: Outfit[] = [];
  const refinementHistory = new Map<string, Outfit[]>();

  await page.route('**/api/auth/session', (route) =>
    route.fulfill({
      json: {
        user: { id: 'user-e2e', name: 'E2E User', email: 'e2e@wardrowbe.test' },
        accessToken: 'e2e-token',
        onboardingCompleted,
        expires: '2099-01-01T00:00:00.000Z',
      },
    }),
  );

  await page.route('**/e2e-*.svg*', (route) => {
    const label = new URL(route.request().url()).pathname.replace('/e2e-', '').replace('.svg', '');
    return route.fulfill({
      contentType: 'image/svg+xml',
      body: `<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200"><rect width="200" height="200" fill="#dbeafe"/><text x="100" y="105" text-anchor="middle" font-size="18">${label}</text></svg>`,
    });
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname.replace('/api/v1', '');
    const method = request.method();

    if (path === '/users/me') {
      return route.fulfill({ json: {
        id: 'user-e2e', email: 'e2e@wardrowbe.test', display_name: 'E2E User',
        timezone: 'UTC', locale: 'en', role: 'user', onboarding_completed: onboardingCompleted,
      } });
    }
    if (path === '/users/me/onboarding/complete' && method === 'POST') {
      onboardingCompleted = true;
      return route.fulfill({ json: { onboarding_completed: true } });
    }
    if (path === '/items/tagging-progress') {
      return route.fulfill({ json: { processing: 0, queued: 0, analyzing: 0, failed: 0, completed: 4, total: 4 } });
    }
    if (path === '/items/types') {
      return route.fulfill({ json: [
        { type: 'shirt', count: 3 }, { type: 'pants', count: 1 }, { type: 'shoes', count: 1 },
      ] });
    }
    if (path === '/items' && method === 'GET') {
      return route.fulfill({ json: { items: wardrobeItems, total: wardrobeItems.length, page: 1, page_size: 20, has_more: false } });
    }
    if (path === '/items' && method === 'POST') {
      const multipart = request.postData() ?? '';
      expect(multipart).toContain('name="auto_extract"');
      expect(multipart).toContain('true');
      expect(multipart).toContain('e2e-upload.jpg');
      wardrobeItems = [uploaded, ...wardrobeItems];
      return route.fulfill({ status: 201, json: uploaded });
    }
    if (path === `/items/${source.id}` && method === 'GET') {
      return route.fulfill({ json: source });
    }
    if (path === `/items/${source.id}/wash-history` || path === `/items/${source.id}/history`) {
      return route.fulfill({ json: [] });
    }
    if (path === `/items/${source.id}/wear-stats`) {
      return route.fulfill({ json: {
        total_wears: 0, days_since_last_worn: null, average_wears_per_month: 0,
        wear_by_month: {}, wear_by_day_of_week: {}, most_common_occasion: null,
      } });
    }
    if (path === '/duplicate-matches' && method === 'GET') {
      return route.fulfill({ json: duplicateMatches });
    }
    if (path === '/duplicate-matches/match-1/decision' && method === 'POST') {
      expect(request.postDataJSON()).toEqual({ decision: 'merge', canonical_item_id: source.id });
      duplicateMatches = [];
      return route.fulfill({ json: { id: 'match-1', status: 'merged' } });
    }
    if (path === '/health/features') {
      return route.fulfill({ json: { background_removal: true } });
    }
    if (path === '/styles/detected' && method === 'GET') {
      return route.fulfill({ json: { styles: [{ style: 'casual', item_count: 4 }] } });
    }
    if (path === '/users/me/preferences' && method === 'GET') {
      return route.fulfill({ json: { default_occasion: null, temperature_unit: 'celsius' } });
    }
    if (path === '/weather/current' && method === 'GET') {
      return route.fulfill({ json: {
        temperature: 20, feels_like: 20, humidity: 50, precipitation_chance: 0,
        wind_speed: 2, condition: 'clear', condition_code: 0, is_day: true,
      } });
    }
    if (path === '/outfits' && method === 'GET') {
      return route.fulfill({ json: { outfits: [], total: 0, page: 1, page_size: 20, has_more: false } });
    }
    if (path === '/notifications/schedules' && method === 'GET') {
      return route.fulfill({ json: [] });
    }
    if (path === '/notifications/settings' && method === 'GET') {
      return route.fulfill({ json: {} });
    }
    if (path === '/analytics' && method === 'GET') {
      return route.fulfill({ json: {} });
    }
    if (path === '/outfits/generate-by-style' && method === 'POST') {
      const payload = request.postDataJSON();
      expect(payload).toEqual({
        target_style: 'casual',
        count: 2,
        occasion: 'casual',
        scheduled_for: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
        time_of_day: 'evening',
        activity: 'Dinner and a walk',
        constraints: {
          required_item_ids: [shoes.id],
          excluded_item_ids: [duplicate.id],
          avoided_colors: ['orange', 'lime'],
          note: 'Keep it rain friendly',
        },
      });
      const context = {
        time_of_day: payload.time_of_day,
        activity: payload.activity,
        constraints: payload.constraints,
      };
      const weather = {
        temperature: 18,
        feels_like: 17,
        humidity: 60,
        precipitation_chance: 20,
        condition: 'partly cloudy',
      };
      generatedOutfits = [firstStyleOutfit, secondStyleOutfit].map(
        (outfit) => ({
          ...outfit,
          source: 'on_demand',
          status: 'pending',
          scheduled_for: payload.scheduled_for,
          generation_context: context,
          weather,
        }),
      );
      for (const outfit of generatedOutfits) refinementHistory.set(outfit.id, [outfit]);
      return route.fulfill({
        json: {
          outfits: generatedOutfits,
        },
      });
    }
    const historyMatch = path.match(/^\/outfits\/([^/]+)\/refinement-history$/);
    if (historyMatch && method === 'GET') {
      return route.fulfill({ json: { outfits: refinementHistory.get(historyMatch[1]) ?? [] } });
    }
    const refineMatch = path.match(/^\/outfits\/([^/]+)\/refine$/);
    if (refineMatch && method === 'POST') {
      const parentId = refineMatch[1];
      const lineage = refinementHistory.get(parentId);
      expect(lineage, `missing lineage for ${parentId}`).toBeDefined();
      const parent = lineage![lineage!.length - 1];
      const turn = (parent.generation_context?.refinement?.turn ?? 0) + 1;
      const instruction = turn === 1 ? 'Make it more relaxed' : 'Make it weatherproof';
      expect(request.postDataJSON()).toEqual({ instruction });
      const rootId = parent.generation_context?.refinement?.root_outfit_id ?? parent.id;
      const refined = {
        ...parent,
        id: `${rootId}-refined-${turn}`,
        replaces_outfit_id: null,
        refined_from_outfit_id: parent.id,
        reasoning: turn === 1
          ? 'Swapped the shirt for a more relaxed version.'
          : 'Made the outfit more weatherproof.',
        items: turn === 1
          ? secondStyleOutfit.items
          : [
              {
                ...secondStyleOutfit.items[0],
                id: uploaded.id,
                name: uploaded.name,
                image_path: uploaded.image_path,
                image_url: uploaded.image_url,
                thumbnail_url: uploaded.thumbnail_url,
                transparent_url: image('uploaded-cutout'),
              },
              ...secondStyleOutfit.items.slice(1),
            ],
        generation_context: {
          ...parent.generation_context,
          refinement: {
            instruction,
            turn,
            root_outfit_id: rootId,
            parent_outfit_id: parent.id,
          },
        },
      };
      const nextLineage = [...lineage!, refined];
      refinementHistory.set(refined.id, nextLineage);
      generatedOutfits = generatedOutfits.map((outfit) => {
        const outfitRoot = outfit.generation_context?.refinement?.root_outfit_id ?? outfit.id;
        return outfitRoot === rootId ? refined : outfit;
      });
      return route.fulfill({ status: 201, json: refined });
    }
    if (path === `/items/${source.id}/remove-background` && method === 'POST') {
      expect(request.postDataJSON()).toMatchObject({ mode: 'garment' });
      return route.fulfill({ json: {
        ...source,
        original_image_path: source.image_path,
        background_removal: {
          outcome: 'accepted', mode: 'garment', transparent_path: 'item-source.png', metrics: { foreground_ratio: 0.4 },
        },
      } });
    }
    if (path === `/pairings/generate/${source.id}` && method === 'POST') {
      return route.fulfill({ json: { generated: 1, pairings: [pairing] } });
    }
    if (path === '/pairings' && method === 'GET') {
      const pairings = generatedOutfits.length > 0 ? [generatedOutfits[0]] : [pairing];
      return route.fulfill({ json: { pairings, total: pairings.length, page: 1, page_size: 20, has_more: false } });
    }
    if (path === '/families/me' && method === 'GET') {
      return route.fulfill({ status: 404, json: { detail: 'Not in a family' } });
    }

    unexpectedRequests.push(`${method} ${path}`);
    return route.fulfill({ status: 501, json: { detail: `Unexpected E2E request: ${method} ${path}` } });
  });

  return () => {
    expect(unexpectedRequests).toEqual([]);
    expect(pageErrors).toEqual([]);
  };
}

test('user reaches a cutout-based composite outfit through the browser happy path', async ({ page }) => {
  const assertCleanBrowserContract = await installApiContract(page);

  await page.goto('/onboarding');
  await page.getByRole('button', { name: 'Get Started' }).click();
  for (let step = 0; step < 4; step += 1) {
    await page.getByRole('button', { name: 'Skip for now' }).click();
  }
  await page.getByRole('button', { name: 'Go to Dashboard' }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.goto('/dashboard/wardrobe');
  await expect(page.getByRole('heading', { name: 'My Wardrobe' })).toBeVisible();

  await page.getByRole('button', { name: 'Add Item' }).click();
  const addDialog = page.getByRole('dialog', { name: 'Add Items' });
  await addDialog.locator('input[type="file"]').first().setInputFiles({
    name: 'e2e-upload.jpg',
    mimeType: 'image/jpeg',
    buffer: Buffer.from('deterministic-e2e-image'),
  });
  await addDialog.getByLabel('Name (optional)').fill(uploaded.name);
  await expect(
    addDialog.getByRole('checkbox', {
      name: 'Automatically isolate the garment after AI analysis',
    }),
  ).toBeChecked();
  await addDialog.getByRole('button', { name: 'Add Item' }).click();
  await expect(addDialog).toBeHidden();
  await expect(page.getByText(uploaded.name, { exact: true })).toBeVisible();

  await expect(page.getByRole('heading', { name: 'Possible duplicate' })).toBeVisible();

  await page.getByRole('button', { name: 'Merge' }).click();
  await expect(page.getByRole('heading', { name: 'Possible duplicate' })).toBeHidden();

  await page.goto(`/dashboard/wardrobe?item=${source.id}`);
  await expect(page.getByRole('dialog').getByText(source.name)).toBeVisible();
  await page.getByTitle('Extract garment').click();
  await expect(page.getByText('Garment extracted')).toBeVisible();

  await page.getByTitle('Find matching outfits').click();
  await page.getByRole('button', { name: 'Generate Outfits' }).click();
  await expect(page.getByRole('dialog').getByText('1 outfit created!')).toBeVisible();
  await page.getByRole('button', { name: 'View Pairings' }).click();

  await expect(page).toHaveURL(/\/dashboard\/pairings/);
  await expect(page.getByText(pairing.reasoning)).toBeVisible();
  await page.getByRole('button').filter({ has: page.getByRole('img', { name: pants.name }) }).click();

  const composite = page.getByTestId('outfit-composite');
  await expect(composite).toBeVisible();
  await expect(page.getByTestId(`outfit-item-${source.id}`)).toHaveAttribute('data-image-kind', 'cutout');
  await expect(page.getByTestId(`outfit-item-${pants.id}`)).toHaveAttribute('data-image-kind', 'photo');
  await expect(page.getByTestId(`outfit-item-${shoes.id}`)).toHaveAttribute('data-image-kind', 'photo');

  await page.goto('/dashboard/suggest');
  await page.locator('button[aria-pressed]').filter({ hasText: 'casual' }).click();
  await page.getByLabel('Number of outfits').fill('2');
  const dateInput = page.getByLabel('Date');
  await expect(dateInput).toHaveAttribute('min', /^\d{4}-\d{2}-\d{2}$/);
  await expect(dateInput).toHaveAttribute('max', /^\d{4}-\d{2}-\d{2}$/);
  await page.getByLabel('Time of day').selectOption('evening');
  await page.getByLabel('Activity').fill('Dinner and a walk');
  await page.getByText('Require items (0)').click();
  await page.getByRole('button').filter({ has: page.getByRole('img', { name: shoes.name }) }).last().click();
  await page.getByText('Exclude items (0)').click();
  await page.getByRole('button').filter({ has: page.getByRole('img', { name: duplicate.name }) }).last().click();
  await page.getByLabel('Avoided colors').fill(' Orange, orange, LIME ');
  await page.getByLabel('Additional constraints').fill('Keep it rain friendly');
  await page.locator('button[data-selected]').filter({ hasText: 'Casual' }).click();
  await page.getByRole('button', { name: 'Get Suggestion' }).click();

  await expect(page.getByTestId('outfit-composite')).toHaveCount(2);
  await expect(page.getByTestId('generation-context-summary').first()).toContainText('Dinner and a walk');
  await expect(page.getByTestId('generation-context-summary').first()).toContainText('orange, lime');
  await expect(page.getByTestId('generation-context-summary').first()).toContainText('1 required, 1 excluded');
  await expect(page.getByTestId('outfit-refinement-panel')).toHaveCount(2);
  const stylist = page.getByTestId('outfit-refinement-panel').first();
  await stylist.getByLabel('Tell the stylist what to change').fill('Make it more relaxed');
  await stylist.getByRole('button', { name: 'Refine outfit' }).click();
  await expect(page.getByTestId('outfit-refinement-panel').first()).toContainText(
    'Make it more relaxed',
  );
  await expect(page.getByTestId('outfit-refinement-panel').first()).toContainText(
    'Swapped the shirt for a more relaxed version.',
  );
  await expect(page.getByTestId(`outfit-item-${secondShirt.id}`).first()).toBeVisible();

  await stylist.getByLabel('Tell the stylist what to change').fill('Make it weatherproof');
  await stylist.getByRole('button', { name: 'Refine outfit' }).click();
  await expect(stylist).toContainText('Make it weatherproof');
  await expect(stylist.getByRole('button', { name: 'Open version 2' })).toHaveAttribute(
    'aria-current',
    'true',
  );
  await expect(page.getByTestId(`outfit-item-${uploaded.id}`).first()).toBeVisible();

  await page.goto('/dashboard/pairings');
  await page.reload();
  await expect(page.getByText('Made the outfit more weatherproof.')).toBeVisible();
  await page.getByRole('button').filter({ has: page.getByRole('img', { name: uploaded.name }) }).click();
  const reopenedStylist = page.getByTestId('outfit-refinement-panel');
  await expect(reopenedStylist).toContainText('Make it more relaxed');
  await expect(reopenedStylist).toContainText('Make it weatherproof');
  await expect(reopenedStylist.getByRole('button', { name: 'Open version 2' })).toHaveAttribute(
    'aria-current',
    'true',
  );
  await expect(page.getByTestId(`outfit-item-${uploaded.id}`)).toBeVisible();
  assertCleanBrowserContract();
});
