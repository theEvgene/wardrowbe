import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';

import { chromium } from '@playwright/test';

const baseUrl = (process.env.WARDROWBE_BASE_URL || 'http://localhost:3000').replace(/\/$/, '');
const fixturePath = fileURLToPath(
  new URL('../../backend/tests/fixtures/garment_extraction/worn-person.jpg', import.meta.url),
);
const pantsFixturePath = fileURLToPath(
  new URL('../../backend/tests/fixtures/garment_extraction/mannequin.jpg', import.meta.url),
);
const shoesFixturePath = fileURLToPath(
  new URL('../../backend/tests/fixtures/garment_extraction/hanger.jpg', import.meta.url),
);

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const pageErrors = [];
let accessToken;
const itemIds = [];
let pairingId;
let metricsBefore;

page.on('pageerror', (error) => pageErrors.push(error.message));

async function api(path, { method = 'GET', json } = {}) {
  return page.evaluate(
    async ({ path, method, json, accessToken }) => {
      const response = await fetch(`/api/v1${path}`, {
        method,
        credentials: 'include',
        headers: {
          Authorization: `Bearer ${accessToken}`,
          ...(json === undefined ? {} : { 'Content-Type': 'application/json' }),
        },
        body: json === undefined ? undefined : JSON.stringify(json),
      });
      const body = response.status === 204 ? null : await response.json().catch(() => null);
      return { ok: response.ok, status: response.status, body };
    },
    { path, method, json, accessToken },
  );
}

async function uploadItem({ bytes, filename, type, name }) {
  const created = await page.evaluate(
    async ({ bytes, filename, type, name, accessToken }) => {
      const form = new FormData();
      form.append('image', new Blob([new Uint8Array(bytes)], { type: 'image/jpeg' }), filename);
      form.append('type', type);
      form.append('name', name);
      form.append('skip_ai', 'true');
      const response = await fetch('/api/v1/items', {
        method: 'POST',
        credentials: 'include',
        headers: { Authorization: `Bearer ${accessToken}` },
        body: form,
      });
      return { ok: response.ok, status: response.status, body: await response.json().catch(() => null) };
    },
    { bytes: Array.from(bytes), filename, type, name, accessToken },
  );
  assert.equal(created.ok, true, `Upload failed: ${created.status} ${JSON.stringify(created.body)}`);
  itemIds.push(created.body.id);
  return created.body;
}

async function confirmMetadata(item, { type, primaryColor }) {
  const reviewed = await api(`/items/${item.id}`, {
    method: 'PATCH',
    json: {
      type,
      primary_color: primaryColor,
      colors: [primaryColor],
      confirm_fields: ['type', 'primary_color', 'colors'],
    },
  });
  assert.equal(reviewed.ok, true, `Metadata review failed: ${reviewed.status}`);
  assert.equal(reviewed.body.field_metadata?.type?.provenance, 'user_confirmed');
  assert.equal(reviewed.body.field_metadata?.primary_color?.provenance, 'user_confirmed');
  return reviewed.body;
}

async function visuallyDistinctReencode(bytes) {
  return page.evaluate(async (sourceBytes) => {
    const image = await createImageBitmap(
      new Blob([new Uint8Array(sourceBytes)], { type: 'image/jpeg' }),
    );
    const canvas = document.createElement('canvas');
    canvas.width = image.width;
    canvas.height = image.height;
    const context = canvas.getContext('2d');
    context.translate(image.width, 0);
    context.scale(-1, 1);
    context.drawImage(image, 0, 0);
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.91));
    return Array.from(new Uint8Array(await blob.arrayBuffer()));
  }, Array.from(bytes));
}

async function cleanupInterruptedSmokeRun() {
  const pairings = await api('/pairings?page_size=100');
  if (pairings.ok) {
    for (const pairing of pairings.body.pairings || []) {
      if (pairing.reasoning?.startsWith('Full-stack smoke')) {
        await api(`/pairings/${pairing.id}`, { method: 'DELETE' });
      }
    }
  }
  const items = await api('/items?page_size=100&search=Full-stack%20smoke');
  if (items.ok) {
    for (const item of items.body.items || []) {
      if (item.name?.startsWith('Full-stack smoke')) {
        await api(`/items/${item.id}`, { method: 'DELETE' });
      }
    }
  }
}

try {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' });
  await page.locator('#email').fill('full-stack-smoke@wardrowbe.local');
  await page.locator('#name').fill('Full-stack Smoke');
  await Promise.all([
    page.waitForURL(/\/(onboarding|dashboard)/, { timeout: 30_000 }),
    page.locator('form button[type="submit"]').click(),
  ]);

  await page.waitForFunction(async () => {
    const response = await fetch('/api/auth/session');
    const currentSession = await response.json();
    return Boolean(currentSession.accessToken || currentSession.syncError);
  });
  const session = await page.evaluate(async () => {
    const response = await fetch('/api/auth/session');
    return response.json();
  });
  accessToken = session.accessToken;
  assert.ok(
    accessToken,
    `NextAuth login did not receive a backend access token${session.syncError ? `: ${session.syncError}` : ''}`,
  );
  await cleanupInterruptedSmokeRun();

  const initialMetrics = await page.request.get(
    `${baseUrl}/api/v1/health/metrics/garment-extraction`,
  );
  assert.equal(initialMetrics.ok(), true, `Initial metrics endpoint failed: ${initialMetrics.status()}`);
  metricsBefore = await initialMetrics.json();
  assert.equal(metricsBefore.scope, 'shared_redis');
  assert.equal(metricsBefore.available, true);

  const onboarding = await api('/users/me/onboarding/complete', { method: 'POST' });
  assert.equal(onboarding.ok, true, `Onboarding failed: ${onboarding.status}`);

  const image = await readFile(fixturePath);
  let source = await uploadItem({
    bytes: image,
    filename: 'smoke-worn-person.jpg',
    type: 'shirt',
    name: 'Full-stack smoke garment',
  });
  source = await confirmMetadata(source, { type: 'shirt', primaryColor: 'blue' });

  await page.goto(`${baseUrl}/dashboard/wardrobe?item=${source.id}`, { waitUntil: 'networkidle' });
  await page.getByRole('dialog').getByText('Full-stack smoke garment', { exact: true }).waitFor();

  const extraction = await api(`/items/${source.id}/remove-background`, {
    method: 'POST',
    json: { mode: 'garment', bg_color: '#FFFFFF' },
  });
  assert.equal(
    extraction.ok,
    true,
    `Garment extraction failed: ${extraction.status} ${JSON.stringify(extraction.body)}`,
  );
  assert.equal(extraction.body.background_removal?.outcome, 'accepted');
  assert.equal(extraction.body.background_removal?.garment_category, 'upper');
  assert.ok(
    extraction.body.background_removal?.transparent_path,
    'Accepted extraction did not persist a transparent cutout path',
  );
  assert.ok(extraction.body.image_url, 'Accepted extraction did not expose the processed image URL');

  const duplicate = await uploadItem({
    bytes: await visuallyDistinctReencode(image),
    filename: 'smoke-worn-person-variant.jpg',
    type: 'shirt',
    name: 'Full-stack smoke same garment',
  });
  await confirmMetadata(duplicate, { type: 'shirt', primaryColor: 'blue' });

  const duplicateDeadline = Date.now() + 180_000;
  let duplicateMatch;
  do {
    const pending = await api('/duplicate-matches');
    assert.equal(pending.ok, true, `Duplicate review lookup failed: ${pending.status}`);
    duplicateMatch = pending.body.find(
      (candidate) =>
        [candidate.item_low_id, candidate.item_high_id].includes(source.id) &&
        [candidate.item_low_id, candidate.item_high_id].includes(duplicate.id),
    );
    if (!duplicateMatch) await page.waitForTimeout(2_000);
  } while (!duplicateMatch && Date.now() < duplicateDeadline);
  assert.ok(duplicateMatch, 'Real DINO worker did not create the expected duplicate review');

  const duplicateDecision = await api(`/duplicate-matches/${duplicateMatch.id}/decision`, {
    method: 'POST',
    json: { decision: 'keep_separate' },
  });
  assert.equal(duplicateDecision.ok, true, `Duplicate decision failed: ${duplicateDecision.status}`);
  assert.equal(duplicateDecision.body.status, 'kept_separate');

  let pants = await uploadItem({
    bytes: await readFile(pantsFixturePath),
    filename: 'smoke-pants.jpg',
    type: 'pants',
    name: 'Full-stack smoke pants',
  });
  pants = await confirmMetadata(pants, { type: 'pants', primaryColor: 'beige' });
  let shoes = await uploadItem({
    bytes: await readFile(shoesFixturePath),
    filename: 'smoke-shoes.jpg',
    type: 'shoes',
    name: 'Full-stack smoke shoes',
  });
  shoes = await confirmMetadata(shoes, { type: 'shoes', primaryColor: 'white' });

  const pairing = await api(`/pairings/item/${source.id}`, {
    method: 'POST',
    json: {
      items: [pants.id, shoes.id],
      reasoning: 'Full-stack smoke composite pairing',
      style_notes: 'Verified through the external-authoring seam',
    },
  });
  assert.equal(pairing.ok, true, `Pairing creation failed: ${pairing.status}`);
  pairingId = pairing.body.id;
  const sourcePreview = pairing.body.items.find((item) => item.id === source.id);
  assert.ok(sourcePreview?.transparent_url, 'Pairing did not expose the source garment cutout');

  await page.goto(`${baseUrl}/dashboard/pairings`, { waitUntil: 'networkidle' });
  await page.getByText('Full-stack smoke composite pairing', { exact: true }).waitFor();
  await page
    .getByRole('button')
    .filter({ has: page.getByRole('img', { name: 'Full-stack smoke pants' }) })
    .click();
  await page.getByTestId('outfit-composite').waitFor();
  assert.equal(
    await page.getByTestId(`outfit-item-${source.id}`).getAttribute('data-image-kind'),
    'cutout',
  );
  assert.equal(
    await page.getByTestId(`outfit-item-${pants.id}`).getAttribute('data-image-kind'),
    'photo',
  );
  assert.equal(
    await page.getByTestId(`outfit-item-${shoes.id}`).getAttribute('data-image-kind'),
    'photo',
  );

  const processedImage = await page.request.get(`${baseUrl}${extraction.body.image_url}`);
  assert.equal(
    processedImage.ok(),
    true,
    `Processed garment image is not readable: ${processedImage.status()}`,
  );

  const metrics = await page.request.get(
    `${baseUrl}/api/v1/health/metrics/garment-extraction`,
  );
  assert.equal(metrics.ok(), true, `Metrics endpoint failed: ${metrics.status()}`);
  const snapshot = await metrics.json();
  assert.equal(
    snapshot.total_requests,
    metricsBefore.total_requests + 1,
    'Extraction did not add exactly one shared metric sample',
  );
  assert.equal(
    snapshot.outcomes?.accepted,
    metricsBefore.outcomes?.accepted + 1,
    'Accepted extraction was not reflected in shared metrics',
  );

  assert.deepEqual(pageErrors, [], `Browser errors: ${pageErrors.join('; ')}`);
  console.log(
    JSON.stringify({
      status: 'passed',
      frontend: baseUrl,
      backend: 'healthy',
      garment_model: extraction.body.background_removal?.model,
      garment_category: extraction.body.background_removal?.garment_category,
      mask_area_ratio: extraction.body.background_removal?.metrics?.mask_area_ratio,
      metrics_scope: snapshot.scope,
      duplicate_model: duplicateMatch.evidence?.visual?.model,
      duplicate_decision: duplicateDecision.body.status,
      composite_items: pairing.body.items.length,
    }),
  );
} finally {
  if (accessToken && pairingId) {
    const deletedPairing = await api(`/pairings/${pairingId}`, { method: 'DELETE' }).catch(() => null);
    if (!deletedPairing?.ok) {
      console.error(`Smoke cleanup failed for pairing ${pairingId}`);
    }
  }
  if (accessToken) {
    for (const itemId of itemIds.reverse()) {
      const deleted = await api(`/items/${itemId}`, { method: 'DELETE' }).catch(() => null);
      if (!deleted?.ok) {
        console.error(`Smoke cleanup failed for item ${itemId}`);
      }
    }
  }
  await browser.close();
}
