import { apiPost } from './client';
import type { SearchRequest, AskResponse } from '@/types/api';

export const askApi = {
  ask: (data: SearchRequest) =>
    apiPost<SearchRequest, AskResponse>('/ask', data),
};
