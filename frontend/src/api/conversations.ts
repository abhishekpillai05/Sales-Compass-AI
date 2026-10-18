import { apiGet, apiDelete, apiPatch, apiPost } from './client';
import type {
  Conversation,
  ConversationDetail,
  SalesStateResponse,
  RecommendationsPayload,
  CandidateProduct,
} from '@/types/api';

export const conversationsApi = {
  list: () => apiGet<Conversation[]>('/conversations'),

  get: (id: number) => apiGet<ConversationDetail>(`/conversations/${id}`),

  delete: (id: number) => apiDelete<{ message: string }>(`/conversations/${id}`),

  rename: (id: number, title: string) =>
    apiPatch<{ title: string }, Conversation>(`/conversations/${id}`, { title }),

  getDealState: (id: number) => apiGet<SalesStateResponse>(`/conversations/${id}/deal`),

  selectProduct: (
    id: number,
    data: { product: CandidateProduct; quantity: number; price?: string }
  ) => apiPost<typeof data, SalesStateResponse>(`/conversations/${id}/deal/select-product`, data),

  confirmDeal: (
    id: number,
    data?: { confirmation_text?: string; quantity?: number; price?: string }
  ) => apiPost<typeof data, SalesStateResponse>(`/conversations/${id}/deal/confirm`, data || {}),

  getRecommendations: (id: number) =>
    apiPost<Record<string, never>, RecommendationsPayload>(
      `/conversations/${id}/deal/recommendations`,
      {}
    ),

  reopenDeal: (id: number, data?: { reason?: string }) =>
    apiPost<typeof data, SalesStateResponse>(`/conversations/${id}/deal/reopen`, data || {}),
};

