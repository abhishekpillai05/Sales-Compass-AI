import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Search,
  Shield,
  ShieldAlert,
  UserCheck,
  UserX,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  Calendar,
  Lock,
} from 'lucide-react';
import { adminApi } from '@/api/admin';
import { useAuth, getErrorMessage } from '@/contexts/AuthContext';
import { Spinner } from '@/components/common/Spinner';
import { EmptyState } from '@/components/common/EmptyState';
import { ConfirmModal } from '@/components/common/ConfirmModal';
import { format } from 'date-fns';
import type { AdminUserItem, UserRole, UserStatus } from '@/types/api';

export function ManagementPage() {
  const { user: currentUser, isAdmin, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  // Data state
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');

  // Modal states
  const [roleModalUser, setRoleModalUser] = useState<AdminUserItem | null>(null);
  const [targetNewRole, setTargetNewRole] = useState<UserRole>('ADMIN');
  const [isUpdatingRole, setIsUpdatingRole] = useState(false);

  const [statusModalUser, setStatusModalUser] = useState<AdminUserItem | null>(null);
  const [targetNewStatus, setTargetNewStatus] = useState<UserStatus>('REVOKED');
  const [isUpdatingStatus, setIsUpdatingStatus] = useState(false);

  // Defense-in-depth: redirect non-admin users
  useEffect(() => {
    if (!authLoading && !isAdmin) {
      navigate('/chat', { replace: true });
    }
  }, [authLoading, isAdmin, navigate]);

  // Fetch users from API
  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: { search?: string; role?: string; status?: string } = {};
      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (roleFilter !== 'ALL') params.role = roleFilter;
      if (statusFilter !== 'ALL') params.status = statusFilter;

      const res = await adminApi.getUsers(params);
      setUsers(res.users);
      setTotalCount(res.total);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, roleFilter, statusFilter]);

  // Load users when filters change
  useEffect(() => {
    if (isAdmin) {
      const timer = setTimeout(() => {
        fetchUsers();
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [fetchUsers, isAdmin]);

  // Auto-dismiss success message
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 4000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // Handlers for initiating actions
  const openRoleModal = (user: AdminUserItem) => {
    const nextRole: UserRole = user.role.toUpperCase() === 'ADMIN' ? 'SALESMAN' : 'ADMIN';
    setTargetNewRole(nextRole);
    setRoleModalUser(user);
  };

  const openStatusModal = (user: AdminUserItem) => {
    const nextStatus: UserStatus =
      user.status.toUpperCase() === 'ACTIVE' ? 'REVOKED' : 'ACTIVE';
    setTargetNewStatus(nextStatus);
    setStatusModalUser(user);
  };

  // Execute Role Update
  const handleConfirmRoleChange = async () => {
    if (!roleModalUser) return;
    setIsUpdatingRole(true);
    setError(null);
    try {
      const updated = await adminApi.updateUserRole(roleModalUser.id, targetNewRole);
      setUsers(prev =>
        prev.map(u => (u.id === updated.id ? { ...u, role: updated.role } : u))
      );
      setSuccessMessage(
        `Successfully changed ${updated.username}'s role to ${updated.role}.`
      );
      setRoleModalUser(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsUpdatingRole(false);
    }
  };

  // Execute Status Update (Revoke / Restore)
  const handleConfirmStatusChange = async () => {
    if (!statusModalUser) return;
    setIsUpdatingStatus(true);
    setError(null);
    try {
      const updated = await adminApi.updateUserStatus(statusModalUser.id, targetNewStatus);
      setUsers(prev =>
        prev.map(u => (u.id === updated.id ? { ...u, status: updated.status } : u))
      );
      setSuccessMessage(
        targetNewStatus === 'REVOKED'
          ? `Access revoked for ${updated.username}. Active sessions terminated.`
          : `Access successfully restored for ${updated.username}.`
      );
      setStatusModalUser(null);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsUpdatingStatus(false);
    }
  };

  if (authLoading) {
    return (
      <div className="empty-state" style={{ paddingTop: 80 }}>
        <Spinner size={32} />
      </div>
    );
  }

  if (!isAdmin) return null;

  return (
    <div className="management-page">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-header-inner">
          <div>
            <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <Users size={24} style={{ color: 'var(--color-primary)' }} />
              User Management
            </h1>
            <p className="page-subtitle">
              Audit registered users, assign roles, and revoke or restore application access.
            </p>
          </div>
          <button
            className="btn btn-secondary"
            onClick={fetchUsers}
            disabled={isLoading}
            id="refresh-users-btn"
          >
            <RefreshCw size={15} className={isLoading ? 'spin' : ''} />
            Refresh
          </button>
        </div>
      </div>

      <div className="page-content" style={{ padding: '24px 32px' }}>
        {/* Success Alert */}
        {successMessage && (
          <div className="alert alert-success animate-fade-in" style={{ marginBottom: 20 }}>
            <CheckCircle2 size={18} style={{ flexShrink: 0 }} />
            <span>{successMessage}</span>
          </div>
        )}

        {/* Error Alert */}
        {error && (
          <div className="alert alert-danger animate-fade-in" style={{ marginBottom: 20 }}>
            <AlertCircle size={18} style={{ flexShrink: 0 }} />
            <span>{error}</span>
          </div>
        )}

        {/* Filter and Search Bar */}
        <div className="management-filters-card">
          <div className="search-input-wrapper" style={{ flex: 1, minWidth: 260 }}>
            <Search size={16} className="search-icon" />
            <input
              type="text"
              placeholder="Search by username or email..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="form-input search-input"
              id="user-search-input"
            />
          </div>

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <select
              value={roleFilter}
              onChange={e => setRoleFilter(e.target.value)}
              className="form-select"
              id="role-filter-select"
            >
              <option value="ALL">All Roles</option>
              <option value="ADMIN">Admin</option>
              <option value="SALESMAN">Salesman</option>
            </select>

            <select
              value={statusFilter}
              onChange={e => setStatusFilter(e.target.value)}
              className="form-select"
              id="status-filter-select"
            >
              <option value="ALL">All Statuses</option>
              <option value="ACTIVE">Active</option>
              <option value="REVOKED">Revoked</option>
            </select>
          </div>
        </div>

        {/* Users Table */}
        <div className="card table-card" style={{ marginTop: 16 }}>
          {isLoading && users.length === 0 ? (
            <div style={{ padding: '60px 0', textAlign: 'center' }}>
              <Spinner size={30} />
              <p style={{ marginTop: 12, color: 'var(--color-text-muted)' }}>
                Loading users...
              </p>
            </div>
          ) : users.length === 0 ? (
            <EmptyState
              icon={<Users size={32} />}
              title="No users found"
              description={
                searchQuery || roleFilter !== 'ALL' || statusFilter !== 'ALL'
                  ? 'No user matches the selected search filters.'
                  : 'No users have registered yet.'
              }
            />
          ) : (
            <div className="table-responsive">
              <table className="data-table" id="admin-users-table">
                <thead>
                  <tr>
                    <th>User</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Registered</th>
                    <th>Last Login</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => {
                    const isSelf = currentUser?.id === u.id;
                    const isUserAdmin = u.role.toUpperCase() === 'ADMIN';
                    const isUserActive = u.status.toUpperCase() === 'ACTIVE';

                    const initials = u.username ? u.username.slice(0, 2).toUpperCase() : '??';

                    return (
                      <tr key={u.id} className={!isUserActive ? 'row-revoked' : ''}>
                        {/* User Identity */}
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <div className="user-avatar-sm">{initials}</div>
                            <div>
                              <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span>{u.username}</span>
                                {isSelf && (
                                  <span className="badge badge-subtle" title="You are logged in as this user">
                                    You
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                                ID: #{u.id}
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Email */}
                        <td>
                          <span style={{ fontSize: '0.875rem' }}>{u.email || '—'}</span>
                        </td>

                        {/* Role */}
                        <td>
                          <span
                            className={`role-badge ${
                              isUserAdmin ? 'role-badge-admin' : 'role-badge-salesman'
                            }`}
                          >
                            {isUserAdmin ? 'ADMIN' : 'SALESMAN'}
                          </span>
                        </td>

                        {/* Status */}
                        <td>
                          <span
                            className={`status-pill ${
                              isUserActive ? 'status-pill-active' : 'status-pill-revoked'
                            }`}
                          >
                            {isUserActive ? (
                              <>
                                <span className="status-dot status-dot-active" />
                                Active
                              </>
                            ) : (
                              <>
                                <span className="status-dot status-dot-revoked" />
                                Revoked
                              </>
                            )}
                          </span>
                        </td>

                        {/* Registered */}
                        <td>
                          <span
                            style={{
                              fontSize: '0.8125rem',
                              color: 'var(--color-text-muted)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 5,
                            }}
                          >
                            <Calendar size={13} />
                            {u.created_at ? format(new Date(u.created_at), 'MMM d, yyyy') : '—'}
                          </span>
                        </td>

                        {/* Last Login */}
                        <td>
                          <span
                            style={{
                              fontSize: '0.8125rem',
                              color: 'var(--color-text-muted)',
                              display: 'flex',
                              alignItems: 'center',
                              gap: 5,
                            }}
                          >
                            <Clock size={13} />
                            {u.last_login ? format(new Date(u.last_login), 'MMM d, h:mm a') : 'Never'}
                          </span>
                        </td>

                        {/* Actions */}
                        <td style={{ textAlign: 'right' }}>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'flex-end',
                              gap: 8,
                            }}
                          >
                            {/* Role Toggle Button */}
                            <button
                              type="button"
                              className="btn btn-xs btn-outline"
                              onClick={() => openRoleModal(u)}
                              disabled={isSelf}
                              title={
                                isSelf
                                  ? 'You cannot change your own admin role'
                                  : isUserAdmin
                                  ? 'Demote to Salesman'
                                  : 'Promote to Admin'
                              }
                            >
                              <Shield size={13} />
                              {isUserAdmin ? 'Make Salesman' : 'Make Admin'}
                            </button>

                            {/* Status Toggle Button */}
                            {isUserActive ? (
                              <button
                                type="button"
                                className="btn btn-xs btn-outline-danger"
                                onClick={() => openStatusModal(u)}
                                disabled={isSelf}
                                title={
                                  isSelf
                                    ? 'You cannot revoke your own account'
                                    : 'Revoke application access'
                                }
                              >
                                <UserX size={13} />
                                Revoke
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-xs btn-outline-success"
                                onClick={() => openStatusModal(u)}
                                disabled={isSelf}
                                title="Restore application access"
                              >
                                <UserCheck size={13} />
                                Restore
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Table Footer */}
          <div
            style={{
              padding: '12px 20px',
              borderTop: '1px solid var(--color-border)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              fontSize: '0.8125rem',
              color: 'var(--color-text-muted)',
            }}
          >
            <span>
              Showing {users.length} of {totalCount} total registered users
            </span>
          </div>
        </div>
      </div>

      {/* Role Change Confirmation Modal */}
      <ConfirmModal
        isOpen={roleModalUser !== null}
        title={targetNewRole === 'ADMIN' ? 'Promote to Admin?' : 'Demote to Salesman?'}
        confirmLabel={targetNewRole === 'ADMIN' ? 'Promote to Admin' : 'Demote to Salesman'}
        isDestructive={targetNewRole === 'SALESMAN'}
        isLoading={isUpdatingRole}
        onConfirm={handleConfirmRoleChange}
        onCancel={() => setRoleModalUser(null)}
        description={
          <div>
            <p style={{ marginBottom: 12 }}>
              Are you sure you want to change the role for{' '}
              <strong>{roleModalUser?.username}</strong> to{' '}
              <span className={`role-badge ${targetNewRole === 'ADMIN' ? 'role-badge-admin' : 'role-badge-salesman'}`}>
                {targetNewRole}
              </span>
              ?
            </p>
            {targetNewRole === 'ADMIN' ? (
              <div className="modal-info-box modal-info-box-primary">
                <Shield size={16} style={{ flexShrink: 0 }} />
                <span>
                  <strong>Admin Privileges:</strong> This user will receive complete access to the
                  application, including User Management, Document Upload, and Query Logs.
                </span>
              </div>
            ) : (
              <div className="modal-info-box modal-info-box-warning">
                <ShieldAlert size={16} style={{ flexShrink: 0 }} />
                <span>
                  <strong>Restricted Access:</strong> This user will no longer be able to access the
                  Management panel, Document Ingestion, or Query Logs.
                </span>
              </div>
            )}
          </div>
        }
      />

      {/* Access Revocation / Restoration Confirmation Modal */}
      <ConfirmModal
        isOpen={statusModalUser !== null}
        title={targetNewStatus === 'REVOKED' ? 'Revoke User Access?' : 'Restore User Access?'}
        confirmLabel={targetNewStatus === 'REVOKED' ? 'Revoke Access' : 'Restore Access'}
        isDestructive={targetNewStatus === 'REVOKED'}
        isLoading={isUpdatingStatus}
        onConfirm={handleConfirmStatusChange}
        onCancel={() => setStatusModalUser(null)}
        description={
          <div>
            <p style={{ marginBottom: 12 }}>
              Are you sure you want to {targetNewStatus === 'REVOKED' ? 'revoke' : 'restore'} application
              access for <strong>{statusModalUser?.username}</strong>?
            </p>
            {targetNewStatus === 'REVOKED' ? (
              <div className="modal-info-box modal-info-box-danger">
                <Lock size={16} style={{ flexShrink: 0 }} />
                <span>
                  <strong>Impact of Revocation:</strong>
                  <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                    <li>The user will be blocked from logging into the platform.</li>
                    <li>All active sessions and tokens will be immediately invalidated.</li>
                    <li>Any ongoing API requests (Chat, Search) will receive HTTP 403 Forbidden.</li>
                  </ul>
                </span>
              </div>
            ) : (
              <div className="modal-info-box modal-info-box-success">
                <UserCheck size={16} style={{ flexShrink: 0 }} />
                <span>
                  <strong>Access Restored:</strong> This user will be permitted to log in again and
                  access all features according to their role ({statusModalUser?.role}).
                </span>
              </div>
            )}
          </div>
        }
      />
    </div>
  );
}
