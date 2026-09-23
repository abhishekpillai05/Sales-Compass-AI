import { apiGet, apiDelete, apiPatch } from './client';
import type { Conversation, ConversationDetail } from '@/types/api';

export const conversationsApi = {
  list: () => apiGet<Conversation[]>('/conversations'),

  get: (id: number) => apiGet<ConversationDetail>(`/conversations/${id}`),

  delete: (id: number) => apiDelete<{ message: string }>(`/conversations/${id}`),

  rename: (id: number, title: string) =>
    apiPatch<{ title: string }, Conversation>(`/conversations/${id}`, { title }),
};
