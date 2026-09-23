import React from 'react';
import { Loader2 } from 'lucide-react';

interface SpinnerProps {
  size?: number;
  className?: string;
}

export function Spinner({ size = 20, className = '' }: SpinnerProps) {
  return (
    <Loader2
      size={size}
      className={`spinner ${className}`}
      aria-label="Loading"
    />
  );
}

export function FullPageSpinner() {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 16,
        color: 'var(--color-text-muted)',
      }}
    >
      <Spinner size={32} />
      <span style={{ fontSize: '0.875rem' }}>Loading…</span>
    </div>
  );
}

export function LoadingDots() {
  return (
    <span
      className="dot-pulse"
      style={{ display: 'inline-flex', gap: 4, color: 'var(--color-brand-400)' }}
      aria-label="Generating response"
    >
      <span />
      <span />
      <span />
    </span>
  );
}
