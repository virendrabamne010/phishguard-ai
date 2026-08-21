import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import RiskScoreBadge from './RiskScoreBadge';

describe('RiskScoreBadge Component', () => {
  it('renders green for low risk (0-30)', () => {
    render(<RiskScoreBadge score={15} label="legitimate" />);
    const badge = screen.getByText('15%').parentElement;
    expect(badge.className).toContain('emerald-500');
    expect(screen.getByText('legitimate')).toBeInTheDocument();
  });

  it('renders amber for medium risk (31-70)', () => {
    render(<RiskScoreBadge score={50} label="suspicious" />);
    const badge = screen.getByText('50%').parentElement;
    expect(badge.className).toContain('amber-500');
    expect(screen.getByText('suspicious')).toBeInTheDocument();
  });

  it('renders red for high risk (71-100)', () => {
    render(<RiskScoreBadge score={90} label="phishing" />);
    const badge = screen.getByText('90%').parentElement;
    expect(badge.className).toContain('red-500');
    expect(screen.getByText('phishing')).toBeInTheDocument();
  });
});
