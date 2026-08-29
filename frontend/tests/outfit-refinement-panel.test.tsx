import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { OutfitRefinementPanel } from '@/components/outfit-refinement-panel';
import { api, setAccessToken } from '@/lib/api';

vi.mock('next-auth/react', () => ({
  useSession: () => ({ data: { accessToken: 'test-token' } }),
}));

vi.mock('next-intl', () => ({
  useTranslations: () => (key: string, values?: Record<string, string | number>) => {
    const messages: Record<string, string> = {
      title: 'Refine with your stylist',
      description: 'Ask for a change. Every reply creates a new version.',
      original: 'Original outfit',
      version: `Version ${values?.number}`,
      you: 'You',
      stylist: 'Stylist',
      instruction: 'Tell the stylist what to change',
      placeholder: 'For example: make it more relaxed',
      submit: 'Refine outfit',
      submitting: 'Refining…',
      error: 'Could not refine this outfit. Please try again.',
    };
    return messages[key] || key;
  },
}));

vi.mock('@/lib/api', () => ({
  api: { get: vi.fn(), post: vi.fn() },
  setAccessToken: vi.fn(),
}));

interface TestOutfit {
  id: string;
  replaces_outfit_id: string | null;
  reasoning: string | null;
  generation_context: {
    refinement?: {
      instruction: string;
      turn: number;
      root_outfit_id: string;
      parent_outfit_id: string;
    };
  } | null;
}

const root: TestOutfit = {
  id: 'root',
  replaces_outfit_id: null,
  reasoning: 'Original reasoning',
  generation_context: null,
};

const first: TestOutfit = {
  id: 'first',
  replaces_outfit_id: 'root',
  reasoning: 'Changed the shirt.',
  generation_context: {
    refinement: {
      instruction: 'Use the other shirt',
      turn: 1,
      root_outfit_id: 'root',
      parent_outfit_id: 'root',
    },
  },
};

describe('OutfitRefinementPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.get).mockResolvedValue({ outfits: [root, first] });
  });

  it('loads lineage and refines from the currently selected version', async () => {
    const second: TestOutfit = {
      ...first,
      id: 'second',
      replaces_outfit_id: 'first',
      reasoning: 'Made the styling more relaxed.',
      generation_context: {
        refinement: {
          instruction: 'Make it more relaxed',
          turn: 2,
          root_outfit_id: 'root',
          parent_outfit_id: 'first',
        },
      },
    };
    vi.mocked(api.post).mockResolvedValue(second);
    const onVersionChange = vi.fn();

    render(
      <OutfitRefinementPanel outfit={first} onVersionChange={onVersionChange} />,
    );

    expect(await screen.findByText('Use the other shirt')).toBeInTheDocument();
    expect(screen.getByText('Changed the shirt.')).toBeInTheDocument();
    expect(api.get).toHaveBeenCalledWith('/outfits/first/refinement-history');
    expect(setAccessToken).toHaveBeenCalledWith('test-token');

    fireEvent.change(screen.getByLabelText('Tell the stylist what to change'), {
      target: { value: '  Make it more relaxed  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Refine outfit' }));

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith('/outfits/first/refine', {
        instruction: 'Make it more relaxed',
      });
    });
    expect(onVersionChange).toHaveBeenCalledWith(second);
  });

  it('bounds input and exposes a localized retryable error', async () => {
    vi.mocked(api.get).mockResolvedValue({ outfits: [root] });
    vi.mocked(api.post).mockRejectedValue(new Error('backend unavailable'));

    render(<OutfitRefinementPanel outfit={root} onVersionChange={vi.fn()} />);

    const submit = screen.getByRole('button', { name: 'Refine outfit' });
    expect(submit).toBeDisabled();
    const input = screen.getByLabelText('Tell the stylist what to change');
    expect(input).toHaveAttribute('maxlength', '1000');
    fireEvent.change(input, { target: { value: 'Change the shoes' } });
    fireEvent.click(submit);

    expect(
      await screen.findByText('Could not refine this outfit. Please try again.'),
    ).toBeInTheDocument();
  });
});
