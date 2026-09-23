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
