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
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
} from 'lucide-react';
import { adminApi } from '@/api/admin';
import { useAuth, getErrorMessage } from '@/contexts/AuthContext';
import { Spinner } from '@/components/common/Spinner';
import { EmptyState } from '@/components/common/EmptyState';
import { ConfirmModal } from '@/components/common/ConfirmModal';
import { format } from 'date-fns';
import type { AdminUserItem, UserRole, UserStatus } from '@/types/api';

export type SortMethod =
  | 'id_asc'
  | 'id_desc'
  | 'username_asc'
  | 'username_desc'
  | 'email_asc'
  | 'email_desc'
  | 'role_admin'
  | 'role_salesman'
  | 'status_active'
  | 'status_revoked'
  | 'created_desc'
  | 'created_asc'
  | 'login_desc'
  | 'login_asc';

export function ManagementPage() {
  const { user: currentUser, isAdmin, isLoading: authLoading } = useAuth();
  const navigate = useNavigate();

  // Data state
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filters & Sorting (ID Ascending is the default)
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('ALL');
  const [statusFilter, setStatusFilter] = useState<string>('ALL');
  const [sortMethod, setSortMethod] = useState<SortMethod>('id_asc');

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

  // Fetch users from API with sorting and filters
  const fetchUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: {
        search?: string;
        role?: string;
        status?: string;
        sort_by?: string;
        order?: 'asc' | 'desc';
      } = {};

      if (searchQuery.trim()) params.search = searchQuery.trim();
      if (roleFilter !== 'ALL') params.role = roleFilter;
      if (statusFilter !== 'ALL') params.status = statusFilter;

      // Map sort method to backend parameters
      if (sortMethod === 'id_asc') { params.sort_by = 'id'; params.order = 'asc'; }
      else if (sortMethod === 'id_desc') { params.sort_by = 'id'; params.order = 'desc'; }
      else if (sortMethod === 'username_asc') { params.sort_by = 'username'; params.order = 'asc'; }
      else if (sortMethod === 'username_desc') { params.sort_by = 'username'; params.order = 'desc'; }
      else if (sortMethod === 'email_asc') { params.sort_by = 'email'; params.order = 'asc'; }
      else if (sortMethod === 'email_desc') { params.sort_by = 'email'; params.order = 'desc'; }
      else if (sortMethod === 'role_admin') { params.sort_by = 'role'; params.order = 'asc'; }
      else if (sortMethod === 'role_salesman') { params.sort_by = 'role'; params.order = 'desc'; }
      else if (sortMethod === 'status_active') { params.sort_by = 'status'; params.order = 'asc'; }
      else if (sortMethod === 'status_revoked') { params.sort_by = 'status'; params.order = 'desc'; }
      else if (sortMethod === 'created_desc') { params.sort_by = 'created_at'; params.order = 'desc'; }
      else if (sortMethod === 'created_asc') { params.sort_by = 'created_at'; params.order = 'asc'; }

      const res = await adminApi.getUsers(params);
      setUsers(res.users);
      setTotalCount(res.total);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, [searchQuery, roleFilter, statusFilter, sortMethod]);

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

  // Client-side instant sorting layer & computed list
  const sortedUsers = useMemo(() => {
    const list = [...users];
    switch (sortMethod) {
      case 'id_asc':
        return list.sort((a, b) => a.id - b.id);
      case 'id_desc':
        return list.sort((a, b) => b.id - a.id);
      case 'username_asc':
        return list.sort((a, b) => (a.username || '').localeCompare(b.username || ''));
      case 'username_desc':
        return list.sort((a, b) => (b.username || '').localeCompare(a.username || ''));
      case 'email_asc':
        return list.sort((a, b) => (a.email || '').localeCompare(b.email || ''));
      case 'email_desc':
        return list.sort((a, b) => (b.email || '').localeCompare(a.email || ''));
      case 'role_admin':
        return list.sort((a, b) => (a.role === 'ADMIN' ? -1 : 1));
      case 'role_salesman':
        return list.sort((a, b) => (a.role === 'SALESMAN' ? -1 : 1));
      case 'status_active':
        return list.sort((a, b) => (a.status === 'ACTIVE' ? -1 : 1));
      case 'status_revoked':
        return list.sort((a, b) => (a.status === 'REVOKED' ? -1 : 1));
      case 'created_desc':
        return list.sort(
          (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
        );
      case 'created_asc':
        return list.sort(
          (a, b) => new Date(a.created_at || 0).getTime() - new Date(b.created_at || 0).getTime()
        );
      case 'login_desc':
        return list.sort((a, b) => {
          if (!a.last_login && !b.last_login) return 0;
          if (!a.last_login) return 1;
          if (!b.last_login) return -1;
          return new Date(b.last_login).getTime() - new Date(a.last_login).getTime();
        });
      case 'login_asc':
        return list.sort((a, b) => {
          if (!a.last_login && !b.last_login) return 0;
          if (!a.last_login) return 1;
          if (!b.last_login) return -1;
          return new Date(a.last_login).getTime() - new Date(b.last_login).getTime();
        });
      default:
        return list.sort((a, b) => a.id - b.id);
    }
  }, [users, sortMethod]);

  const handleHeaderSort = (column: 'id' | 'email' | 'role' | 'status' | 'created' | 'login') => {
    switch (column) {
      case 'id':
        setSortMethod(prev => (prev === 'id_asc' ? 'id_desc' : 'id_asc'));
        break;
      case 'email':
        setSortMethod(prev => (prev === 'email_asc' ? 'email_desc' : 'email_asc'));
        break;
      case 'role':
        setSortMethod(prev => (prev === 'role_admin' ? 'role_salesman' : 'role_admin'));
        break;
      case 'status':
        setSortMethod(prev => (prev === 'status_active' ? 'status_revoked' : 'status_active'));
        break;
      case 'created':
        setSortMethod(prev => (prev === 'created_desc' ? 'created_asc' : 'created_desc'));
        break;
      case 'login':
        setSortMethod(prev => (prev === 'login_desc' ? 'login_asc' : 'login_desc'));
        break;
    }
  };

  const renderSortIcon = (column: 'id' | 'email' | 'role' | 'status' | 'created' | 'login') => {
    let isActive = false;
    let isAsc = true;
    if (column === 'id' && (sortMethod === 'id_asc' || sortMethod === 'id_desc')) {
      isActive = true;
      isAsc = sortMethod === 'id_asc';
    } else if (column === 'email' && (sortMethod === 'email_asc' || sortMethod === 'email_desc')) {
      isActive = true;
      isAsc = sortMethod === 'email_asc';
    } else if (column === 'role' && (sortMethod === 'role_admin' || sortMethod === 'role_salesman')) {
      isActive = true;
      isAsc = sortMethod === 'role_admin';
    } else if (column === 'status' && (sortMethod === 'status_active' || sortMethod === 'status_revoked')) {
      isActive = true;
      isAsc = sortMethod === 'status_active';
    } else if (column === 'created' && (sortMethod === 'created_desc' || sortMethod === 'created_asc')) {
      isActive = true;
      isAsc = sortMethod === 'created_asc';
    } else if (column === 'login' && (sortMethod === 'login_desc' || sortMethod === 'login_asc')) {
      isActive = true;
      isAsc = sortMethod === 'login_asc';
    }

    if (isActive) {
      return isAsc ? (
        <ArrowUp size={13} className="sort-icon-active" />
      ) : (
        <ArrowDown size={13} className="sort-icon-active" />
      );
    }
    return <ArrowUpDown size={13} className="sort-icon-idle" />;
  };

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

          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* Sort Method Selector (ID Ascending is Default) */}
            <div className="management-sort-wrapper">
              <ArrowUpDown size={15} style={{ color: 'var(--color-text-muted)' }} />
              <select
                value={sortMethod}
                onChange={e => setSortMethod(e.target.value as SortMethod)}
                className="form-select"
                id="sort-method-select"
                title="Sort users by"
              >
                <optgroup label="ID Number (Default)">
                  <option value="id_asc">Sort: ID (1 → 9) [Default]</option>
                  <option value="id_desc">Sort: ID (9 → 1)</option>
                </optgroup>
                <optgroup label="Username & Email">
                  <option value="username_asc">Sort: Username (A → Z)</option>
                  <option value="username_desc">Sort: Username (Z → A)</option>
                  <option value="email_asc">Sort: Email (A → Z)</option>
                  <option value="email_desc">Sort: Email (Z → A)</option>
                </optgroup>
                <optgroup label="Date & Activity">
                  <option value="created_desc">Sort: Registered (Newest)</option>
                  <option value="created_asc">Sort: Registered (Oldest)</option>
                  <option value="login_desc">Sort: Last Login (Recent)</option>
                  <option value="login_asc">Sort: Last Login (Oldest)</option>
                </optgroup>
                <optgroup label="Role & Status">
                  <option value="role_admin">Sort: Role (Admin first)</option>
                  <option value="role_salesman">Sort: Role (Salesman first)</option>
                  <option value="status_active">Sort: Status (Active first)</option>
                  <option value="status_revoked">Sort: Status (Revoked first)</option>
                </optgroup>
              </select>
            </div>

            {/* Role Filter */}
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

            {/* Status Filter */}
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
                    <th
                      onClick={() => handleHeaderSort('id')}
                      className="th-sortable"
                      title="Click to sort by ID / User"
                    >
                      <div className="th-sortable-inner">
                        <span>User (ID)</span>
                        {renderSortIcon('id')}
                      </div>
                    </th>
                    <th
                      onClick={() => handleHeaderSort('email')}
                      className="th-sortable"
                      title="Click to sort by Email"
                    >
                      <div className="th-sortable-inner">
                        <span>Email</span>
                        {renderSortIcon('email')}
                      </div>
                    </th>
                    <th
                      onClick={() => handleHeaderSort('role')}
                      className="th-sortable"
                      title="Click to sort by Role"
                    >
                      <div className="th-sortable-inner">
                        <span>Role</span>
                        {renderSortIcon('role')}
                      </div>
                    </th>
                    <th
                      onClick={() => handleHeaderSort('status')}
                      className="th-sortable"
                      title="Click to sort by Status"
                    >
                      <div className="th-sortable-inner">
                        <span>Status</span>
                        {renderSortIcon('status')}
                      </div>
                    </th>
                    <th
                      onClick={() => handleHeaderSort('created')}
                      className="th-sortable"
                      title="Click to sort by Registration Date"
                    >
                      <div className="th-sortable-inner">
                        <span>Registered</span>
                        {renderSortIcon('created')}
                      </div>
                    </th>
                    <th
                      onClick={() => handleHeaderSort('login')}
                      className="th-sortable"
                      title="Click to sort by Last Login"
                    >
                      <div className="th-sortable-inner">
                        <span>Last Login</span>
                        {renderSortIcon('login')}
                      </div>
                    </th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedUsers.map(u => {
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
