import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ConnectButton from './ConnectButton';

describe('ConnectButton Component', () => {
  it('renders correctly and buttons are clickable', () => {
    const onDemo = vi.fn();
    const onGmail = vi.fn();
    const onImap = vi.fn();
    
    render(<ConnectButton onDemo={onDemo} onGmail={onGmail} onImap={onImap} loading={false} />);
    
    const gmailBtn = screen.getByText('Connect Gmail Account');
    const imapBtn = screen.getByText(/Connect via IMAP/i);
    const demoBtn = screen.getByText(/Load Sandbox Data/i);
    
    expect(gmailBtn).toBeInTheDocument();
    expect(imapBtn).toBeInTheDocument();
    expect(demoBtn).toBeInTheDocument();
    
    fireEvent.click(imapBtn);
    expect(onImap).toHaveBeenCalledTimes(1);
    
    fireEvent.click(demoBtn);
    expect(onDemo).toHaveBeenCalledTimes(1);
  });

  it('shows loading state when loading is true', () => {
    const onDemo = vi.fn();
    const onGmail = vi.fn();
    const onImap = vi.fn();
    
    render(<ConnectButton onDemo={onDemo} onGmail={onGmail} onImap={onImap} loading={true} />);
    
    const loadingText = screen.getByText(/Loading secure environment\.\.\./i);
    expect(loadingText).toBeInTheDocument();
    
    expect(screen.queryByText('Connect Gmail Account')).not.toBeInTheDocument();
    expect(screen.queryByText('Connect Corporate IMAP')).not.toBeInTheDocument();
    expect(screen.queryByText(/Load Sandbox Data/i)).not.toBeInTheDocument();
  });
});
