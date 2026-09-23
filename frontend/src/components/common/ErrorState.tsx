import React from 'react';
import { AlertTriangle, RefreshCw, WifiOff, Lock, ServerCrash } from 'lucide-react';
import { ApiClientError } from '@/api/client';

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

function resolveErrorDisplay(error: unknown): {
  icon: React.ReactNode;
  title: string;
  message: string;
} {
  if (error instanceof ApiClientError) {
    if (error.status === 401) {
      return {
        icon: <Lock size={24} />,
        title: 'Session Expired',
        message: 'Please log in again to continue.',
      };
    }
    if (error.status === 403) {
      return {
        icon: <Lock size={24} />,
        title: 'Access Denied',
        message: error.message,
      };
    }
    if (error.status === 0 || error.status >= 500) {
      return {
        icon: <ServerCrash size={24} />,
        title: 'Server Error',
        message: error.message || 'The server encountered an error. Please try again.',
      };
    }
    return {
      icon: <AlertTriangle size={24} />,
      title: 'Request Failed',
      message: error.message,
    };
  }

  if (error instanceof TypeError && error.message.includes('fetch')) {
    return {
      icon: <WifiOff size={24} />,
      title: 'Cannot Reach Server',
      message: 'Make sure the backend is running on http://localhost:8000.',
    };
  }

  return {
    icon: <AlertTriangle size={24} />,
    title: 'Unexpected Error',
    message: error instanceof Error ? error.message : 'An unexpected error occurred.',
  };
}

export function ErrorState({ error, onRetry, title }: ErrorStateProps) {
  const display = resolveErrorDisplay(error);

  return (
    <div className="empty-state" role="alert">
      <div
        className="empty-state-icon"
        style={{ background: 'var(--color-error-bg)', color: 'var(--color-error)' }}
      >
        {display.icon}
      </div>
      <div className="empty-state-title">{title ?? display.title}</div>
      <p className="empty-state-desc">{display.message}</p>
      {onRetry && (
        <button className="btn btn-secondary btn-sm" onClick={onRetry}>
          <RefreshCw size={14} />
          Try Again
        </button>
      )}
    </div>
  );
}

interface InlineErrorProps {
  error: unknown;
}

export function InlineError({ error }: InlineErrorProps) {
  const display = resolveErrorDisplay(error);
  return (
    <div className="alert alert-error" role="alert">
      <AlertTriangle size={16} style={{ flexShrink: 0, marginTop: 1 }} />
      <span>{display.message}</span>
    </div>
  );
}
