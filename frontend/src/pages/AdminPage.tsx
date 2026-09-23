import React, { useEffect, useState, type ReactNode } from 'react';
import { RefreshCw, User, Clock, MessageSquare, AlertTriangle } from 'lucide-react';
import { adminApi } from '@/api/admin';
import { useAuth } from '@/contexts/AuthContext';
import { useNavigate } from 'react-router-dom';
import { EmptyState } from '@/components/common/EmptyState';
import { ErrorState } from '@/components/common/ErrorState';
import { Spinner } from '@/components/common/Spinner';
import { format } from 'date-fns';
import type { QueryLog } from '@/types/api';

interface StatCard {
  icon: ReactNode;
  label: string;
  value: string | number;
}

export function AdminPage() {
  const { user, isAdmin, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  const [logs, setLogs] = useState<QueryLog[] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  // Redirect non-admins
  useEffect(() => {
    if (!authLoading && !isAdmin) {
      navigate('/chat', { replace: true });
    }
  }, [isAdmin, authLoading, navigate]);

  async function fetchLogs() {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.getQueryLogs();
      setLogs(data);
    } catch (err) {
      setError(err);
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    if (!authLoading && isAdmin) {
      fetchLogs();
    }
  }, [authLoading, isAdmin]);

  if (authLoading) {
    return (
      <div className="empty-state" style={{ paddingTop: 80 }}>
        <Spinner size={28} />
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <EmptyState
        icon={<AlertTriangle size={24} />}
        title="Access Denied"
        description="This page is restricted to administrators."
      />
    );
  }

  const stats: StatCard[] = logs
    ? [
        {
          icon: <MessageSquare size={18} color="var(--color-brand-500)" />,
          label: 'Total Queries',
          value: logs.length,
        },
        {
          icon: <User size={18} color="var(--color-success)" />,
          label: 'Unique Users',
          value: new Set(logs.map(l => l.user_id)).size,
        },
        {
          icon: <Clock size={18} color="var(--color-warning)" />,
          label: 'Latest Query',
          value: logs[0] ? format(new Date(logs[0].timestamp), 'dd MMM, HH:mm') : '—',
        },
      ]
    : [];

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-neutral-50)' }}>
      {/* Header */}
      <div className="page-header">
        <div className="page-header-inner">
          <div>
            <h1 className="page-title">Query Logs</h1>
            <p className="page-subtitle">
              All user queries — visible to admins only
            </p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            {logs !== null && (
              <span className="badge badge-brand">{logs.length} total</span>
            )}
            <button
              className="btn btn-secondary btn-sm"
              onClick={fetchLogs}
              disabled={isLoading}
              id="admin-refresh-btn"
            >
              <RefreshCw size={14} className={isLoading ? 'spinner' : ''} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      <div className="admin-layout">
        {/* Stats summary */}
        {logs !== null && logs.length > 0 ? (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: 14,
              marginBottom: 24,
            }}
          >
            {stats.map(stat => (
              <div key={stat.label} className="card" style={{ padding: '16px 18px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  {stat.icon}
                  <span style={{ fontSize: '0.8rem', color: 'var(--color-text-muted)', fontWeight: 500 }}>
                    {stat.label}
                  </span>
                </div>
                <div style={{ fontSize: '1.375rem', fontWeight: 700 }}>{stat.value}</div>
              </div>
            ))}
          </div>
        ) : null}

        {isLoading ? (
          <div className="empty-state">
            <Spinner size={28} />
            <span style={{ color: 'var(--color-text-muted)' }}>Loading query logs…</span>
          </div>
        ) : error ? (
          <ErrorState error={error} onRetry={fetchLogs} />
        ) : logs !== null && logs.length === 0 ? (
          <EmptyState
            icon={<MessageSquare size={24} />}
            title="No queries yet"
            description="Query logs will appear here once users start using the AI assistant."
          />
        ) : logs && logs.length > 0 ? (
          <div className="card" style={{ overflow: 'hidden' }}>
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" aria-label="Query logs">
                <thead>
                  <tr>
                    <th style={{ width: 60 }}>ID</th>
                    <th style={{ width: 90 }}>User ID</th>
                    <th>Query</th>
                    <th style={{ width: 160 }}>Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(log => (
                    <tr key={log.id}>
                      <td style={{ color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                        {log.id}
                      </td>
                      <td>
                        <span className="badge badge-neutral">
                          <User size={11} />
                          {log.user_id}
                        </span>
                      </td>
                      <td>
                        <div className="query-text-cell" title={log.query}>
                          {log.query}
                        </div>
                      </td>
                      <td style={{ color: 'var(--color-text-muted)', fontSize: '0.8125rem', whiteSpace: 'nowrap' }}>
                        {(() => {
                          try {
                            return format(new Date(log.timestamp), 'dd MMM yyyy, HH:mm');
                          } catch {
                            return log.timestamp;
                          }
                        })()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div
              style={{
                padding: '10px 16px',
                background: 'var(--color-neutral-50)',
                borderTop: '1px solid var(--color-border)',
                fontSize: '0.78rem',
                color: 'var(--color-text-muted)',
              }}
            >
              Showing all {logs.length} records · The backend returns all logs without pagination.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
