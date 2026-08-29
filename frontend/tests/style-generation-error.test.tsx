import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { StyleGenerationError } from '@/components/style-generation-error';

describe('StyleGenerationError', () => {
  it('shows an actionable error and retries without rendering stale outfits', () => {
    const onRetry = vi.fn();
    render(
      <StyleGenerationError
        message="Could not assemble 3 valid outfits. Try again."
        retryLabel="Retry generation"
        retrying={false}
        onRetry={onRetry}
      />,
    );

    expect(screen.getByText(/could not assemble 3 valid outfits/i)).toBeVisible();
    expect(screen.queryByTestId('outfit-composite')).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /retry generation/i }));
    expect(onRetry).toHaveBeenCalledOnce();
  });
});
