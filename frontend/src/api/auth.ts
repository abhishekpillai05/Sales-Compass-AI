import { apiPost, apiGet } from './client';
import type { UserLogin, UserRegister, UserResponse } from '@/types/api';

export const authApi = {
  login: (data: UserLogin) =>
    apiPost<UserLogin, UserResponse>('/auth/login', data),

  register: (data: UserRegister) =>
    apiPost<UserRegister, UserResponse>('/auth/register', data),

  me: () =>
    apiGet<UserResponse>('/auth/me'),

  logout: () =>
    apiPost<Record<string, never>, { message: string }>('/auth/logout', {}),
};
