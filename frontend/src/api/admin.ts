import { apiGet } from './client';
import type { QueryLog } from '@/types/api';

export const adminApi = {
  getQueryLogs: () =>
    apiGet<QueryLog[]>('/admin/query-logs'),
};
