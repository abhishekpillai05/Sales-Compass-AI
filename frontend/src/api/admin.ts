import { apiGet, apiPatch } from './client';
import type {
  QueryLog,
  AdminUserItem,
  AdminUserListResponse,
  UserRole,
  UserStatus,
} from '@/types/api';

export interface GetUsersParams {
  search?: string;
  role?: string;
  status?: string;
  sort_by?: string;
  order?: 'asc' | 'desc';
  limit?: number;
  offset?: number;
}

export const adminApi = {
  getQueryLogs: () =>
    apiGet<QueryLog[]>('/admin/query-logs'),

  getUsers: (params?: GetUsersParams) => {
    const searchParams = new URLSearchParams();
    if (params?.search) searchParams.set('search', params.search);
    if (params?.role) searchParams.set('role', params.role);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.sort_by) searchParams.set('sort_by', params.sort_by);
    if (params?.order) searchParams.set('order', params.order);
    if (params?.limit !== undefined) searchParams.set('limit', String(params.limit));
    if (params?.offset !== undefined) searchParams.set('offset', String(params.offset));

    const qs = searchParams.toString();
    return apiGet<AdminUserListResponse>(`/admin/users${qs ? `?${qs}` : ''}`);
  },

  getUser: (userId: number) =>
    apiGet<AdminUserItem>(`/admin/users/${userId}`),

  updateUserRole: (userId: number, role: UserRole) =>
    apiPatch<{ role: UserRole }, AdminUserItem>(`/admin/users/${userId}/role`, { role }),

  updateUserStatus: (userId: number, status: UserStatus) =>
    apiPatch<{ status: UserStatus }, AdminUserItem>(`/admin/users/${userId}/status`, { status }),
};
