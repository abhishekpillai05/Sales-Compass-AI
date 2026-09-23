import { apiPost } from './client';
import type { SearchRequest, SearchResponse } from '@/types/api';

export const searchApi = {
  search: (data: SearchRequest) =>
    apiPost<SearchRequest, SearchResponse>('/search', data),
};
